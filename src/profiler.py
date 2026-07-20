"""
profiler.py — Profilo intelligence per partecipata pubblica.

Legge la tabella dei fatti unificata (data/fatti_partecipate.parquet)
e produce profilo strutturato su 5 dimensioni + score.

Tipico utilizzo:
    from profiler import profila_cf
    profilo = profila_cf("97103880585")
"""

import duckdb
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FATTI = str(DATA_DIR / "fatti_partecipate.parquet")


def _conn():
    return duckdb.connect()


def _df(con, sql, params=None):
    """Esegue SQL e restituisce lista di dict."""
    if params:
        return con.execute(sql, params).fetchdf().to_dict("records")
    return con.execute(sql).fetchdf().to_dict("records")


# ── Dimensioni ──────────────────────────────────────────────────

def profilo_assetto(cf, con):
    """Assetto: denominazione, settore, metriche strutturali dall'ultimo anno MEF."""
    # Prendi l'ultimo anno disponibile per questo cf
    ultimo = con.execute(f"""
        SELECT MAX(anno) AS anno FROM read_parquet('{FATTI}')
        WHERE cf = ? AND fonte = 'mef'
    """, [cf]).fetchone()[0]
    if not ultimo:
        return {"errore": f"CF {cf} non trovato"}

    rows = _df(con, f"""
        SELECT metrica, importo, denominazione, settore
        FROM read_parquet('{FATTI}')
        WHERE cf = ? AND fonte = 'mef' AND anno = {ultimo}
    """, params=[cf])

    if not rows:
        return {"errore": f"Nessun dato MEF per {cf}"}

    denom = rows[0].get("denominazione", "")
    settore = rows[0].get("settore", "")

    # Mappa metriche → valori
    metriche = {r["metrica"]: r["importo"] for r in rows}

    return {
        "denominazione": denom,
        "settore": settore,
        "addetti": metriche.get("addetti"),
        "valore_produzione": metriche.get("valore_produzione"),
        "risultato_esercizio": metriche.get("risultato_esercizio"),
        "patrimonio_netto": metriche.get("patrimonio_netto"),
        "costo_personale": metriche.get("costo_personale"),
        "ultimo_anno": ultimo,
    }


def profilo_occupazione(cf, con):
    """Serie storica addetti."""
    rows = _df(con, f"""
        SELECT anno, importo AS addetti
        FROM read_parquet('{FATTI}')
        WHERE cf = ? AND fonte = 'mef' AND metrica = 'addetti'
        ORDER BY anno
    """, params=[cf])

    if not rows:
        return {}

    addetti_per_anno = {int(r["anno"]): int(r["addetti"]) for r in rows}
    vals = list(addetti_per_anno.values())
    trend = (vals[-1] - vals[0]) / vals[0] * 100 if len(vals) >= 2 else 0

    return {
        "addetti_per_anno": addetti_per_anno,
        "trend_percentuale": round(trend, 1),
    }


def profilo_governance(cf, con):
    """Compensi dai rappresentanti."""
    rows = _df(con, f"""
        SELECT anno, importo AS compenso
        FROM read_parquet('{FATTI}')
        WHERE cf = ? AND fonte = 'rappresentanti' AND metrica = 'compenso'
        ORDER BY anno
    """, params=[cf])

    if not rows:
        return {}

    compenso_totale = sum(r["compenso"] for r in rows if r["compenso"])
    compenso_medio = compenso_totale / len(rows) if rows else 0
    anni = set(r["anno"] for r in rows)

    return {
        "n_incarichi_remunerati": len(rows),
        "compenso_totale": compenso_totale,
        "compenso_medio": round(compenso_medio, 0),
        "anni_coperti": sorted(anni),
    }


def profilo_appalti(cf, con):
    """Gare bandite (ANAC)."""
    df = con.execute(f"""
        SELECT anno,
               COUNT(*) AS n_gare,
               SUM(importo) AS importo_totale,
               AVG(importo) AS importo_medio
        FROM read_parquet('{FATTI}')
        WHERE cf = ? AND fonte = 'anac'
        GROUP BY anno
        ORDER BY anno
    """, [cf]).fetchdf()

    if df.empty:
        return {}

    return {
        "gare_per_anno": df.to_dict("records"),
        "totale_gare": int(df["n_gare"].sum()),
        "importo_complessivo_totale": float(df["importo_totale"].sum()),
    }


def profilo_appalti_vinti(cf, con):
    """Gare vinte (ANAC Aggiudicatari)."""
    df = con.execute(f"""
        SELECT anno,
               COUNT(DISTINCT id_aggiudicazione) AS n_gare,
               SUM(importo) AS importo_totale,
               AVG(importo) AS importo_medio
        FROM read_parquet('{FATTI}')
        WHERE cf = ? AND fonte = 'aggiudicatario'
        GROUP BY anno
        ORDER BY anno
    """, [cf]).fetchdf()

    if df.empty:
        return {}

    return {
        "gare_per_anno": df.to_dict("records"),
        "totale_gare": int(df["n_gare"].sum()),
        "importo_complessivo_totale": float(df["importo_totale"].sum()),
    }


def profilo_aiuti(cf, con):
    """Aiuti di Stato (RNA)."""
    df = con.execute(f"""
        SELECT anno,
               COUNT(*) AS n_aiuti,
               SUM(importo) AS totale_esl
        FROM read_parquet('{FATTI}')
        WHERE cf = ? AND fonte = 'aiuto_stato'
        GROUP BY anno
        ORDER BY anno
    """, [cf]).fetchdf()

    if df.empty:
        return {}

    return {
        "aiuti_per_anno": df.to_dict("records"),
        "totale_esl": float(df["totale_esl"].sum()),
        "n_aiuti_distinti": int(df["n_aiuti"].sum()),
    }


# ── Score ───────────────────────────────────────────────────────

def _fascia(val, soglie):
    """Restituisce punti per fasce: [(soglia, punti), ...]."""
    for soglia, punti in sorted(soglie, reverse=True):
        if val >= soglia:
            return punti
    return 0


def calcola_score(profilo):
    """Score composito: esposizione (0-100) + performance (0-100) + copertura (0-100)."""
    occ = profilo.get("occupazione", {})
    app = profilo.get("appalti", {})
    app_vinti = profilo.get("appalti_vinti", {})
    aiu = profilo.get("aiuti_stato", {})
    gov = profilo.get("governance", {})
    att = profilo.get("assetto", {})

    addetti = 0
    if occ and "addetti_per_anno" in occ:
        vals = list(occ["addetti_per_anno"].values())
        addetti = max(vals) if vals else 0

    importo_appalti = app.get("importo_complessivo_totale", 0) if app else 0
    importo_appalti_vinti = app_vinti.get("importo_complessivo_totale", 0) if app_vinti else 0
    importo_aiuti = aiu.get("totale_esl", 0) if aiu else 0
    valore_produzione = att.get("valore_produzione", 0) or 0

    # ── Esposizione ──
    esp = 0
    esp += _fascia(addetti, [(100000, 25), (50000, 20), (10000, 12), (1000, 6), (500, 3), (100, 1)])
    esp += _fascia(importo_appalti, [(10e9, 25), (1e9, 18), (100e6, 10), (10e6, 5), (1e6, 2)])
    esp += _fascia(importo_appalti_vinti, [(10e9, 15), (1e9, 10), (100e6, 5), (10e6, 2)])
    esp += _fascia(importo_aiuti, [(500e6, 20), (100e6, 12), (10e6, 6), (1e6, 3)])

    # Bonus: valore produzione (disponibile solo per non-IAS)
    if valore_produzione > 0:
        esp += min(10, _fascia(valore_produzione, [(10e9, 10), (1e9, 7), (100e6, 4), (10e6, 2)]))

    score = {}
    score["esposizione"] = min(esp, 100)

    # ── Performance (trend + robustezza) ──
    perf = 50  # base

    if occ and "trend_percentuale" in occ:
        t = occ["trend_percentuale"]
        perf += _fascia(t, [(20, 30), (10, 20), (5, 10), (2, 5), (0, 0), (-5, -10), (-10, -20)])
    else:
        perf -= 20  # nessun dato occupazionale

    # Bonus per completezza informativa
    if valore_produzione > 0:
        perf += 10  # bilancio CO.E.P. disponibile
    if gov:
        perf += 5   # governance trasparente
    if app and aiu:
        perf += 5   # multi-fonte

    score["performance"] = max(0, min(perf, 100))

    # ── Copertura informativa (quante fonti hanno dati) ──
    copertura = sum([
        bool(occ and occ.get("addetti_per_anno")),
        bool(gov),
        bool(app),
        bool(aiu),
        valore_produzione > 0,
    ])
    score["copertura"] = copertura * 20  # 0-100

    return score


# ── Orchestratore ───────────────────────────────────────────────

def profila_cf(cf, denominazione=None):
    """Profilo intelligence per CF, dalla tabella fatti unificata."""
    if not Path(FATTI).exists():
        return {"errore": f"Tabella fatti non trovata: {FATTI}. Esegui prima build_fatti.py"}

    con = _conn()
    profilo = {
        "cf": cf,
        "denominazione": denominazione or "",
        "assetto": profilo_assetto(cf, con),
        "occupazione": profilo_occupazione(cf, con),
        "governance": profilo_governance(cf, con),
        "appalti": profilo_appalti(cf, con),
        "appalti_vinti": profilo_appalti_vinti(cf, con),
        "aiuti_stato": profilo_aiuti(cf, con),
        "score": {},
    }

    if "errore" in profilo["assetto"]:
        profilo["errore"] = profilo["assetto"]["errore"]
    else:
        profilo["denominazione"] = profilo["assetto"]["denominazione"]

    profilo["score"] = calcola_score(profilo)
    con.close()
    return profilo


def profila_lista(cf_list):
    """Profili per lista di CF."""
    risultati = []
    for item in cf_list:
        cf = item.get("cf_norm") or item.get("cf")
        denom = item.get("denominazione") or item.get("nome", "")
        print(f"[profiler] {cf} — {denom}")
        risultati.append(profila_cf(cf, denom))
    return risultati


def main():
    import sys, json
    cf = sys.argv[1] if len(sys.argv) > 1 else "97103880585"
    profilo = profila_cf(cf)
    print(json.dumps(profilo, indent=2, default=str))


if __name__ == "__main__":
    main()

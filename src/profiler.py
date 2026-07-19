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


def _df(con, sql):
    """Esegue SQL e restituisce lista di dict."""
    return con.execute(sql).fetchdf().to_dict("records")


# ── Dimensioni ──────────────────────────────────────────────────

def profilo_assetto(cf, con):
    """Assetto: denominazione, settore, metriche strutturali dall'ultimo anno MEF."""
    # Prendi l'ultimo anno disponibile per questo cf
    ultimo = con.execute(f"""
        SELECT MAX(anno) AS anno FROM read_parquet('{FATTI}')
        WHERE cf = '{cf}' AND fonte = 'mef'
    """).fetchone()[0]
    if not ultimo:
        return {"errore": f"CF {cf} non trovato"}

    rows = _df(con, f"""
        SELECT metrica, importo, denominazione, settore
        FROM read_parquet('{FATTI}')
        WHERE cf = '{cf}' AND fonte = 'mef' AND anno = {ultimo}
    """)

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
        WHERE cf = '{cf}' AND fonte = 'mef' AND metrica = 'addetti'
        ORDER BY anno
    """)

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
        WHERE cf = '{cf}' AND fonte = 'rappresentanti' AND metrica = 'compenso'
        ORDER BY anno
    """)

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
        WHERE cf = '{cf}' AND fonte = 'anac'
        GROUP BY anno
        ORDER BY anno
    """).fetchdf()

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
        WHERE cf = '{cf}' AND fonte = 'aiuto_stato'
        GROUP BY anno
        ORDER BY anno
    """).fetchdf()

    if df.empty:
        return {}

    return {
        "aiuti_per_anno": df.to_dict("records"),
        "totale_esl": float(df["totale_esl"].sum()),
        "n_aiuti_distinti": int(df["n_aiuti"].sum()),
    }


# ── Score ───────────────────────────────────────────────────────

def calcola_score(profilo):
    score = {"esposizione": 0, "performance": 0}

    addetti = 0
    occ = profilo.get("occupazione", {})
    if occ and "addetti_per_anno" in occ:
        vals = list(occ["addetti_per_anno"].values())
        addetti = max(vals) if vals else 0

    appalti = profilo.get("appalti", {})
    importo_appalti = appalti.get("importo_complessivo_totale", 0) if appalti else 0

    aiuti = profilo.get("aiuti_stato", {})
    importo_aiuti = aiuti.get("totale_esl", 0) if aiuti else 0

    pts = 0
    if addetti > 50000: pts += 40
    elif addetti > 10000: pts += 20
    elif addetti > 1000: pts += 10
    if importo_appalti > 1e9: pts += 40
    elif importo_appalti > 1e8: pts += 20
    elif importo_appalti > 1e7: pts += 10
    if importo_aiuti > 1e8: pts += 20
    elif importo_aiuti > 1e7: pts += 10
    elif importo_aiuti > 1e6: pts += 5
    score["esposizione"] = min(pts, 100)

    if occ and "trend_percentuale" in occ:
        t = occ["trend_percentuale"]
        if t > 5: score["performance"] = 80
        elif t > 0: score["performance"] = 60
        elif t > -10: score["performance"] = 40
        else: score["performance"] = 20

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


if __name__ == "__main__":
    import sys, json
    cf = sys.argv[1] if len(sys.argv) > 1 else "97103880585"
    profilo = profila_cf(cf)
    print(json.dumps(profilo, indent=2, default=str))

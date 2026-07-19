"""
profiler.py — Profilo intelligence per partecipata pubblica.

Incrocisa 5 dataset (MEF, Rappresentanti, ANAC, RNA, IPA) e produce
un dizionario strutturato con metriche su 7 dimensioni:
assetto, governance, occupazione, appalti, aiuti, trasparenza, score.

Tipico utilizzo:
    from profiler import profila_cf
    profilo = profila_cf("97103880585")  # Poste Italiane
"""

import duckdb
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Path cache locali (prodotti da fetch_data.py)
LOCAL_MEF  = DATA_DIR / "mef_partecipazioni.parquet"
LOCAL_IPA  = DATA_DIR / "ipa_enti.parquet"
LOCAL_ANAC = DATA_DIR / "anac_bandi_gara.parquet"
LOCAL_RNA  = DATA_DIR / "rna_aiuti_stato.parquet"
LOCAL_RAPP = DATA_DIR / "mef_rappresentanti_partecipate.parquet"


def _conn():
    return duckdb.connect()


def _cf_mef(cf):
    """Formatta il CF nel formato MEF (con parentesi quadre)."""
    return f"[{cf}]"


# ── Dimensioni ──────────────────────────────────────────────────

def profilo_assetto(cf, con):
    """Assetto proprietario: ente, forma giuridica, settore, quotata."""
    cf_mef = _cf_mef(cf)
    row = con.execute(f"""
        SELECT
            amministrazione_denominazione,
            partecipata_denominazione,
            partecipata_forma_giuridica,
            partecipata_anno_di_costituzione,
            partecipata_stato_giuridico,
            partecipata_settore_attivita,
            partecipata_divisione_ateco,
            emittente_azioni_quotate,
            CASE WHEN emittente_azioni_quotate = 'SI' THEN TRUE ELSE FALSE END AS quotata,
            tipo_controllo,
            quota_partecipazione_diretta,
            servizi_affidati
        FROM read_parquet('{LOCAL_MEF}')
        WHERE partecipata_codice_fiscale = '{cf_mef}' AND anno = 2023
        LIMIT 1
    """).fetchone()

    if not row:
        return {"errore": f"CF {cf} non trovato in MEF partecipazioni 2023"}

    keys = [
        "ente_partecipante", "denominazione", "forma_giuridica",
        "anno_costituzione", "stato", "settore", "divisione_ateco",
        "emittente_azioni_quotate_raw", "quotata", "tipo_controllo",
        "quota_partecipazione_diretta", "servizi_affidati"
    ]
    return dict(zip(keys, row))


def profilo_occupazione(cf, con):
    """Serie storica addetti 2020-2023."""
    cf_mef = _cf_mef(cf)
    rows = con.execute(f"""
        SELECT anno, partecipata_numero_di_addetti AS addetti
        FROM read_parquet('{LOCAL_MEF}')
        WHERE partecipata_codice_fiscale = '{cf_mef}'
          AND partecipata_numero_di_addetti IS NOT NULL
        ORDER BY anno
    """).fetchall()

    if not rows:
        return {}

    addetti_per_anno = {int(r[0]): int(r[1]) for r in rows}
    addetti_list = [v for v in addetti_per_anno.values() if v]
    trend = (addetti_list[-1] - addetti_list[0]) / addetti_list[0] if len(addetti_list) >= 2 else 0

    return {
        "addetti_per_anno": addetti_per_anno,
        "trend_percentuale": round(trend * 100, 1),
        "fonte": "mef_partecipazioni"
    }


def profilo_governance(cf, con):
    """Compensi, incarichi, gender balance dai rappresentanti MEF."""
    rows = con.execute(f"""
        SELECT
            COUNT(*) AS n_incarichi,
            COUNT(DISTINCT rapp_id) AS n_persone,
            SUM(incarico_importo_eur) AS compenso_totale,
            AVG(incarico_importo_eur) AS compenso_medio,
            SUM(CASE WHEN rapp_genere = 'M' THEN 1 ELSE 0 END) AS n_uomini,
            SUM(CASE WHEN rapp_genere = 'F' THEN 1 ELSE 0 END) AS n_donne,
            SUM(CASE WHEN incarico_gratuito = 'INCARICO GRATUITO' THEN 1 ELSE 0 END) AS gratuiti
        FROM read_parquet('{LOCAL_RAPP}')
        WHERE REPLACE(REPLACE(societa_cf, '[', ''), ']', '') = '{cf}'
          AND anno = 2023
    """).fetchone()

    if not rows or rows[0] == 0:
        return {}

    profilo = {
        "n_incarichi": int(rows[0]),
        "n_persone": int(rows[1]),
        "compenso_totale": float(rows[2]) if rows[2] else 0,
        "compenso_medio": float(rows[3]) if rows[3] else 0,
        "n_uomini": int(rows[4]),
        "n_donne": int(rows[5]),
        "incarichi_gratuiti": int(rows[6]),
    }
    tot_persone = profilo["n_uomini"] + profilo["n_donne"]
    profilo["percentuale_donne"] = round(profilo["n_donne"] / tot_persone * 100, 1) if tot_persone else 0

    # Presidente e AD
    for ruolo in ["Presidente", "AD"]:
        like = "%Presidente%" if ruolo == "Presidente" else "%Amministratore Delegato%"
        r = con.execute(f"""
            SELECT TRIM(rapp_cognome || ' ' || rapp_nome), incarico_importo_eur
            FROM read_parquet('{LOCAL_RAPP}')
            WHERE REPLACE(REPLACE(societa_cf, '[', ''), ']', '') = '{cf}'
              AND anno = 2023
              AND incarico_tipo LIKE '{like}'
            ORDER BY incarico_importo_eur DESC
            LIMIT 1
        """).fetchone()
        if r:
            profilo[ruolo.lower()] = {"nome": str(r[0]), "compenso": float(r[1]) if r[1] else 0}

    return profilo


def profilo_appalti(cf, con):
    """Gare bandite dalla partecipata come stazione appaltante (ANAC)."""
    df = con.execute(f"""
        SELECT
            anno_pubblicazione AS anno,
            COUNT(DISTINCT cig) AS n_gare,
            SUM(importo_complessivo_gara) AS importo_complessivo,
            SUM(importo_lotto) AS importo_lotti,
            COUNT(DISTINCT CASE WHEN flag_pnrr THEN cig END) AS gare_pnrr,
            COUNT(DISTINCT CASE WHEN flag_urgenza THEN cig END) AS gare_urgenza
        FROM read_parquet('{LOCAL_ANAC}')
        WHERE (cf_amministrazione_appaltante = '{cf}'
               OR denominazione_amministrazione_appaltante LIKE '%POSTE ITALIANE%')
          AND stato = 'ATTIVO'
        GROUP BY anno_pubblicazione
        ORDER BY anno_pubblicazione
    """).fetchdf()

    if df.empty:
        return {}

    return {
        "gare_per_anno": df.to_dict("records"),
        "totale_gare": int(df["n_gare"].sum()),
        "importo_complessivo_totale": float(df["importo_complessivo"].sum()) if "importo_complessivo" in df else 0,
        "totale_gare_pnrr": int(df["gare_pnrr"].sum()) if "gare_pnrr" in df else 0,
        "totale_gare_urgenza": int(df["gare_urgenza"].sum()) if "gare_urgenza" in df else 0,
    }


def profilo_aiuti(cf, con):
    """Aiuti di Stato ricevuti (RNA)."""
    df = con.execute(f"""
        SELECT
            anno,
            COUNT(DISTINCT cor) AS n_aiuti,
            SUM(elemento_aiuto) AS totale_esl,
            COUNT(DISTINCT soggetto_concedente) AS n_concedenti
        FROM read_parquet('{LOCAL_RNA}')
        WHERE denominazione_beneficiario LIKE '%POSTE ITALIANE%'
           OR codice_fiscale_beneficiario = '{cf}'
        GROUP BY anno
        ORDER BY anno
    """).fetchdf()

    if df.empty:
        return {}

    # Concedente principale (per importo totale)
    concedente = con.execute(f"""
        SELECT soggetto_concedente, SUM(elemento_aiuto) AS tot
        FROM read_parquet('{LOCAL_RNA}')
        WHERE denominazione_beneficiario LIKE '%POSTE ITALIANE%'
           OR codice_fiscale_beneficiario = '{cf}'
        GROUP BY soggetto_concedente
        ORDER BY tot DESC
        LIMIT 1
    """).fetchone()

    return {
        "aiuti_per_anno": df.to_dict("records"),
        "totale_esl": float(df["totale_esl"].sum()),
        "n_aiuti_distinti": int(df["n_aiuti"].sum()),
        "principale_concedente": str(concedente[0]) if concedente else None,
        "importo_principale_concedente": float(concedente[1]) if concedente else 0,
    }


def profilo_trasparenza(cf, con):
    """Sezione trasparenza da scan (se disponibile)."""
    # Per ora stub: restituisce None. Sara' popolato dallo scanner.
    # Il dato viene da scanner_report.csv / scanner_report_centrali.csv
    return {
        "disponibile": False,
        "nota": "Dato popolato dal modulo scanner. Eseguire scan preliminare."
    }


def profilo_borsa(cf, denominazione):
    """Stub per dati Borsa Italiana (fonte esterna)."""
    return {
        "disponibile": False,
        "nota": "Dati finanziari Borsa Italiana non ancora integrati. Fonte: borsaitaliana.it"
    }


# ── Score ───────────────────────────────────────────────────────

def calcola_score(profilo):
    """Score composito: esposizione, trasparenza, performance."""
    score = {"esposizione": 0, "trasparenza": 0, "performance": 0}

    # Esposizione: basa su addetti e importi appalti
    addetti = 0
    occ = profilo.get("occupazione", {})
    if occ and "addetti_per_anno" in occ:
        vals = list(occ["addetti_per_anno"].values())
        addetti = max(vals)

    appalti = profilo.get("appalti", {})
    importo_appalti = appalti.get("importo_complessivo_totale", 0) if appalti else 0

    aiuti = profilo.get("aiuti_stato", {})
    importo_aiuti = aiuti.get("totale_esl", 0) if aiuti else 0

    # Score esposizione 0-100
    # Addetti: >50000 = 40pt, >10000 = 20pt, >1000 = 10pt
    # Appalti: >1Mld = 40pt, >100M = 20pt, >10M = 10pt
    # Aiuti: >100M = 20pt, >10M = 10pt, >1M = 5pt
    pts = 0
    if addetti > 50000:
        pts += 40
    elif addetti > 10000:
        pts += 20
    elif addetti > 1000:
        pts += 10

    if importo_appalti > 1e9:
        pts += 40
    elif importo_appalti > 1e8:
        pts += 20
    elif importo_appalti > 1e7:
        pts += 10

    if importo_aiuti > 1e8:
        pts += 20
    elif importo_aiuti > 1e7:
        pts += 10
    elif importo_aiuti > 1e6:
        pts += 5

    score["esposizione"] = min(pts, 100)

    # Trasparenza (stub)
    score["trasparenza"] = 0

    # Performance: trend occupazione
    occ = profilo.get("occupazione", {})
    if occ and "trend_percentuale" in occ:
        trend = occ["trend_percentuale"]
        # Trend addetti positivo = bene, ma per aziende pubbliche
        # un calo controllato puo' essere efficientamento
        if trend > 5:
            score["performance"] = 80
        elif trend > 0:
            score["performance"] = 60
        elif trend > -10:
            score["performance"] = 40
        else:
            score["performance"] = 20

    return score


# ── Orchestratore ───────────────────────────────────────────────

def profila_cf(cf, denominazione=None):
    """Produce il profilo intelligence completo per un CF.

    Args:
        cf: Codice Fiscale della partecipata (senza parentesi).
        denominazione: Opzionale, per arricchimento.

    Returns:
        dict strutturato con tutte le dimensioni.
    """
    con = _conn()
    profilo = {
        "cf": cf,
        "denominazione": denominazione or "",
        "assetto": profilo_assetto(cf, con),
        "occupazione": profilo_occupazione(cf, con),
        "governance": profilo_governance(cf, con),
        "appalti": profilo_appalti(cf, con),
        "aiuti_stato": profilo_aiuti(cf, con),
        "trasparenza": profilo_trasparenza(cf, con),
        "borsa": profilo_borsa(cf, denominazione),
        "score": {},
        "fonti": ["mef_partecipazioni", "mef_rappresentanti_partecipate",
                   "anac_bandi_gara", "rna_aiuti_stato", "ipa_enti"]
    }

    # Se mancano dati di base, segnala
    if "errore" in profilo["assetto"]:
        profilo["errore"] = profilo["assetto"]["errore"]

    profilo["score"] = calcola_score(profilo)
    con.close()
    return profilo


def profila_lista(cf_list):
    """Produce profili per una lista di CF.

    Args:
        cf_list: lista di dict con chiavi 'cf_norm' e 'denominazione'.

    Returns:
        list di profili.
    """
    risultati = []
    for item in cf_list:
        cf = item.get("cf_norm") or item.get("cf")
        denom = item.get("denominazione") or item.get("nome", "")
        print(f"[profiler] Profilo {cf} — {denom}")
        profilo = profila_cf(cf, denom)
        risultati.append(profilo)
    return risultati


if __name__ == "__main__":
    import sys, json
    cf = sys.argv[1] if len(sys.argv) > 1 else "97103880585"
    profilo = profila_cf(cf)
    print(json.dumps(profilo, indent=2, default=str))

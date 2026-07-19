"""
build_fatti.py — Costruisce la tabella dei fatti unificata per le partecipate.

1. Forza il refresh dei dati dalle 26 partecipate MEF centrali
2. Aggrega i dati MEF per (cf, anno, metrica) — elimina duplicati da multi-dichiarazione
3. Produce data/fatti_partecipate.parquet in formato (fonte, cf, anno, importo, metrica)
"""

import duckdb
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT = DATA_DIR / "fatti_partecipate.parquet"

# Path cache locali (prodotti da fetch_data.py)
LOCAL_MEF  = DATA_DIR / "mef_partecipazioni.parquet"
LOCAL_ANAC = DATA_DIR / "anac_bandi_gara.parquet"
LOCAL_RNA  = DATA_DIR / "rna_aiuti_stato.parquet"
LOCAL_RAPP = DATA_DIR / "mef_rappresentanti_partecipate.parquet"


def _conn():
    return duckdb.connect()


def _fetch_forza_centrali():
    """Forza refresh dei dati per le partecipate MEF centrali."""
    from fetch_data import cf_targets_centrali, fetch_mef, fetch_ipa
    from fetch_data import fetch_anac, fetch_rna, fetch_rappresentanti

    print("[fatti] Forza refresh dati centrali...")
    fetch_mef(force=True)
    fetch_ipa(force=True)

    cfs = cf_targets_centrali()
    print(f"[fatti] Partecipate target: {len(cfs)}")

    fetch_anac(force=True, cfs=cfs)
    fetch_rna(force=True, cfs=cfs)
    fetch_rappresentanti(force=True, cfs=cfs)
    return cfs


def step_mef(con, path):
    """Metriche MEF aggregate per (cf, anno, metrica)."""
    print("[fatti] MEF: metriche aggregate...")
    con.execute("CREATE OR REPLACE TABLE _mef (fonte VARCHAR, cf VARCHAR, anno BIGINT, importo DOUBLE, metrica VARCHAR, denominazione VARCHAR, settore VARCHAR);")

    for col, metrica in [
        ("partecipata_numero_di_addetti", "addetti"),
        ("partecipata_valore_della_produzione_co_e_p", "valore_produzione"),
        ("partecipata_risultato_d_esercizio_co_e_p", "risultato_esercizio"),
        ("partecipata_patrimonio_netto_co_e_p", "patrimonio_netto"),
        ("partecipata_costo_del_personale_co_e_p", "costo_personale"),
    ]:
        con.execute(f"""
            INSERT INTO _mef
            SELECT 'mef',
                   TRIM(REPLACE(REPLACE(partecipata_codice_fiscale, '[', ''), ']', '')) AS cf,
                   anno, MAX({col}) AS importo, '{metrica}',
                   MAX(TRIM(partecipata_denominazione)), MAX(partecipata_settore_attivita)
            FROM read_parquet('{path}')
            WHERE {col} IS NOT NULL AND {col} > 0
            GROUP BY cf, anno
        """)

    n = con.execute("SELECT count(*) FROM _mef").fetchone()[0]
    print(f"  → {n} righe")


def step_rappresentanti(con, path):
    """Compensi dai rappresentanti MEF."""
    print("[fatti] Rappresentanti: compensi...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _rapp AS
        SELECT 'rappresentanti' AS fonte,
               TRIM(REPLACE(REPLACE(societa_cf, '[', ''), ']', '')) AS cf,
               anno, incarico_importo_eur AS importo, 'compenso' AS metrica,
               MAX(societa) AS denominazione, '' AS settore
        FROM read_parquet('{path}')
        WHERE incarico_importo_eur IS NOT NULL AND incarico_importo_eur > 0
        GROUP BY cf, anno, incarico_importo_eur
    """)
    n = con.execute("SELECT count(*) FROM _rapp").fetchone()[0]
    print(f"  → {n} righe")


def step_anac(con, path):
    """Gare bandite (ANAC)."""
    print("[fatti] ANAC: gare bandite...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _anac AS
        SELECT 'anac' AS fonte, cf_amministrazione_appaltante AS cf,
               anno_pubblicazione AS anno, importo_complessivo_gara AS importo,
               'gara' AS metrica,
               MAX(denominazione_amministrazione_appaltante) AS denominazione, '' AS settore
        FROM read_parquet('{path}')
        WHERE stato = 'ATTIVO' AND importo_complessivo_gara > 0
          AND cf_amministrazione_appaltante IS NOT NULL
        GROUP BY cf_amministrazione_appaltante, anno_pubblicazione, importo_complessivo_gara
    """)
    n = con.execute("SELECT count(*) FROM _anac").fetchone()[0]
    n_cf = con.execute("SELECT count(DISTINCT cf) FROM _anac").fetchone()[0]
    print(f"  → {n} righe, {n_cf} enti")


def step_rna(con, path):
    """Aiuti di Stato (RNA)."""
    print("[fatti] RNA: aiuti di Stato...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _rna AS
        SELECT 'aiuto_stato' AS fonte, codice_fiscale_beneficiario AS cf,
               anno, elemento_aiuto AS importo, 'aiuto_esl' AS metrica,
               MAX(denominazione_beneficiario) AS denominazione, '' AS settore
        FROM read_parquet('{path}')
        WHERE elemento_aiuto > 0 AND codice_fiscale_beneficiario IS NOT NULL
        GROUP BY codice_fiscale_beneficiario, anno, elemento_aiuto
    """)
    n = con.execute("SELECT count(*) FROM _rna").fetchone()[0]
    n_cf = con.execute("SELECT count(DISTINCT cf) FROM _rna").fetchone()[0]
    print(f"  → {n} righe, {n_cf} enti")


def unifica(con):
    """Unisce tutte le fonti in un unico parquet."""
    print("[fatti] Unificazione...")
    con.execute("""
        CREATE OR REPLACE TABLE _fatti AS
        SELECT * FROM _mef UNION ALL BY NAME SELECT * FROM _rapp
        UNION ALL BY NAME SELECT * FROM _anac UNION ALL BY NAME SELECT * FROM _rna
    """)
    con.execute(f"COPY _fatti TO '{OUTPUT}' (FORMAT PARQUET)")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{OUTPUT}')").fetchone()[0]
    enti = con.execute(f"SELECT count(DISTINCT cf) FROM read_parquet('{OUTPUT}')").fetchone()[0]
    print(f"[fatti] Salvato: {OUTPUT} ({n:,} righe, {enti:,} enti)")


def main():
    print("[fatti] Costruzione tabella fatti partecipate...")
    _fetch_forza_centrali()

    con = _conn()
    step_mef(con, str(LOCAL_MEF))
    step_rappresentanti(con, str(LOCAL_RAPP))
    step_anac(con, str(LOCAL_ANAC))
    step_rna(con, str(LOCAL_RNA))
    unifica(con)


if __name__ == "__main__":
    main()

"""
build_fatti.py — Costruisce la tabella dei fatti unificata per le partecipate.

1. Forza il refresh dei dati dalle 26 partecipate MEF centrali
2. Aggrega i dati MEF per (cf, anno, metrica) — elimina duplicati da multi-dichiarazione
3. Produce data/fatti_partecipate.parquet in formato (fonte, cf, anno, importo, metrica)
"""

import duckdb, sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT = DATA_DIR / "fatti_partecipate.parquet"


def _conn():
    return duckdb.connect()


def _fetch_forza_centrali():
    """Forza refresh dei dati per le partecipate MEF centrali."""
    from fetch_data import cf_targets_centrali, fetch_all
    print("[fatti] Forza refresh dati centrali...")

    # Prima forza refresh MEF e IPA (serve per estrarre i CF target)
    from fetch_data import fetch_mef, fetch_ipa
    fetch_mef(force=True)
    fetch_ipa(force=True)

    cfs = cf_targets_centrali()
    print(f"[fatti] Partecipate target: {len(cfs)}")

    # Ora forza ANAC, RNA, rappresentanti filtrati per questi CF
    from fetch_data import fetch_anac, fetch_rna, fetch_rappresentanti
    fetch_anac(force=True, cfs=cfs)
    fetch_rna(force=True, cfs=cfs)
    fetch_rappresentanti(force=True, cfs=cfs)

    return cfs


def step_mef_aggregato(con, mef_path):
    """MEF: metriche aggregate per (cf, anno, metrica) — elimina duplicati da multi-dichiarazione."""
    print("[fatti] MEF: metriche aggregate...")

    def _agg(col, metrica):
        con.execute(f"""
            INSERT INTO _mef
            SELECT 'mef' AS fonte,
                   TRIM(REPLACE(REPLACE(partecipata_codice_fiscale, '[', ''), ']', '')) AS cf,
                   anno,
                   MAX({col}) AS importo,
                   '{metrica}' AS metrica,
                   MAX(TRIM(partecipata_denominazione)) AS denominazione,
                   MAX(partecipata_settore_attivita) AS settore
            FROM read_parquet('{mef_path}')
            WHERE {col} IS NOT NULL AND {col} > 0
            GROUP BY cf, anno
        """)

    con.execute("CREATE OR REPLACE TABLE _mef (fonte VARCHAR, cf VARCHAR, anno BIGINT, importo DOUBLE, metrica VARCHAR, denominazione VARCHAR, settore VARCHAR);")
    _agg("partecipata_numero_di_addetti", "addetti")
    _agg("partecipata_valore_della_produzione_co_e_p", "valore_produzione")
    _agg("partecipata_risultato_d_esercizio_co_e_p", "risultato_esercizio")
    _agg("partecipata_patrimonio_netto_co_e_p", "patrimonio_netto")
    _agg("partecipata_costo_del_personale_co_e_p", "costo_personale")

    n = con.execute("SELECT count(*) FROM _mef").fetchone()[0]
    print(f"  → {n} righe (erano 809k prima dell'aggregazione)")


def step_rappresentanti(con, rapp_path):
    """Rappresentanti: compensi (già aggregato per CF)."""
    print("[fatti] Rappresentanti: compensi...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _rapp AS
        SELECT 'rappresentanti' AS fonte,
               TRIM(REPLACE(REPLACE(societa_cf, '[', ''), ']', '')) AS cf,
               anno,
               incarico_importo_eur AS importo,
               'compenso' AS metrica,
               MAX(societa) AS denominazione,
               '' AS settore
        FROM read_parquet('{rapp_path}')
        WHERE incarico_importo_eur IS NOT NULL AND incarico_importo_eur > 0
        GROUP BY cf, anno, incarico_importo_eur
    """)
    n = con.execute("SELECT count(*) FROM _rapp").fetchone()[0]
    n_cf = con.execute("SELECT count(DISTINCT cf) FROM _rapp").fetchone()[0]
    print(f"  → {n} righe, {n_cf} enti")


def step_anac(con, anac_path):
    """ANAC: gare bandite (una riga per gara, non aggregare)."""
    print("[fatti] ANAC: gare bandite...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _anac AS
        SELECT 'anac' AS fonte,
               cf_amministrazione_appaltante AS cf,
               anno_pubblicazione AS anno,
               importo_complessivo_gara AS importo,
               'gara' AS metrica,
               MAX(denominazione_amministrazione_appaltante) AS denominazione,
               '' AS settore
        FROM read_parquet('{anac_path}')
        WHERE stato = 'ATTIVO'
          AND importo_complessivo_gara IS NOT NULL
          AND importo_complessivo_gara > 0
          AND cf_amministrazione_appaltante IS NOT NULL
          AND cf_amministrazione_appaltante != ''
        GROUP BY cf_amministrazione_appaltante, anno_pubblicazione, importo_complessivo_gara
    """)
    n = con.execute("SELECT count(*) FROM _anac").fetchone()[0]
    n_cf = con.execute("SELECT count(DISTINCT cf) FROM _anac").fetchone()[0]
    print(f"  → {n} righe, {n_cf} enti")


def step_rna(con, rna_path):
    """RNA: aiuti di Stato (una riga per aiuto, non aggregare)."""
    print("[fatti] RNA: aiuti di Stato...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _rna AS
        SELECT 'aiuto_stato' AS fonte,
               codice_fiscale_beneficiario AS cf,
               anno,
               elemento_aiuto AS importo,
               'aiuto_esl' AS metrica,
               MAX(denominazione_beneficiario) AS denominazione,
               MAX(soggetto_concedente) AS settore
        FROM read_parquet('{rna_path}')
        WHERE elemento_aiuto IS NOT NULL AND elemento_aiuto > 0
          AND codice_fiscale_beneficiario IS NOT NULL
          AND codice_fiscale_beneficiario != ''
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
        SELECT * FROM _mef
        UNION ALL BY NAME
        SELECT * FROM _rapp
        UNION ALL BY NAME
        SELECT * FROM _anac
        UNION ALL BY NAME
        SELECT * FROM _rna
    """)

    con.execute(f"COPY _fatti TO '{OUTPUT}' (FORMAT PARQUET)")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{OUTPUT}')").fetchone()[0]
    enti = con.execute(f"SELECT count(DISTINCT cf) FROM read_parquet('{OUTPUT}')").fetchone()[0]

    # Verifica duplicati residui
    dups = con.execute(f"""
        SELECT count(*) FROM (
            SELECT cf, anno, metrica, fonte, count(*) AS n
            FROM read_parquet('{OUTPUT}')
            GROUP BY cf, anno, metrica, fonte
            HAVING count(*) > 1
        )
    """).fetchone()[0]

    print(f"[fatti] Salvato: {OUTPUT}")
    print(f"[fatti] Righe: {n:,} — Enti unici: {enti:,} — Duplicati residui: {dups}")


def main():
    print("[fatti] Costruzione tabella fatti partecipate...")

    # 1. Forza refresh dati per le 26 centrali
    _fetch_forza_centrali()

    mef_path = str(DATA_DIR / "mef_partecipazioni.parquet")
    anac_path = str(DATA_DIR / "anac_bandi_gara.parquet")
    rna_path = str(DATA_DIR / "rna_aiuti_stato.parquet")
    rapp_path = str(DATA_DIR / "mef_rappresentanti_partecipate.parquet")

    con = _conn()
    step_mef_aggregato(con, mef_path)
    step_rappresentanti(con, rapp_path)
    step_anac(con, anac_path)
    step_rna(con, rna_path)
    unifica(con)


if __name__ == "__main__":
    main()

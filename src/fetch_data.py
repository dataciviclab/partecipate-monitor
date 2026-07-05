"""
fetch_data.py — Scarica i dataset di base (MEF + IPA) da GCS via DuckDB.
Se GCS non e' raggiungibile (es. in CI senza credenziali), usa cache locale.
"""

import duckdb, json, os, sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GCS_MEF = "gs://dataciviclab-clean/mef_partecipazioni/*/mef_partecipazioni_*_clean.parquet"
GCS_IPA = "gs://dataciviclab-clean/ipa_enti/*/*.parquet"
LOCAL_MEF = DATA_DIR / "mef_partecipazioni.parquet"
LOCAL_IPA = DATA_DIR / "ipa_enti.parquet"


def _conn():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='us-east-1';")
    return con


def fetch_mef(force=False):
    """Scarica mef_partecipazioni da GCS o usa cache."""
    if LOCAL_MEF.exists() and not force:
        print(f"[fetch] Usa cache locale: {LOCAL_MEF}")
        return str(LOCAL_MEF)

    print("[fetch] Scarica mef_partecipazioni da GCS...")
    con = _conn()
    con.execute(f"""
        COPY (SELECT * FROM read_parquet('{GCS_MEF}'))
        TO '{LOCAL_MEF}' (FORMAT PARQUET)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{LOCAL_MEF}')").fetchone()[0]
    print(f"[fetch] Salvato: {LOCAL_MEF} ({n} righe)")
    return str(LOCAL_MEF)


def fetch_ipa(force=False):
    """Scarica ipa_enti da GCS o usa cache."""
    if LOCAL_IPA.exists() and not force:
        print(f"[fetch] Usa cache locale: {LOCAL_IPA}")
        return str(LOCAL_IPA)

    print("[fetch] Scarica ipa_enti da GCS...")
    con = _conn()
    con.execute(f"""
        COPY (SELECT * FROM read_parquet('{GCS_IPA}'))
        TO '{LOCAL_IPA}' (FORMAT PARQUET)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{LOCAL_IPA}')").fetchone()[0]
    print(f"[fetch] Salvato: {LOCAL_IPA} ({n} righe)")
    return str(LOCAL_IPA)


def estrai_partecipate(only_controllo=False, max_siti=None):
    """Estrae l'elenco delle partecipate con sito web (IPA join)."""
    mef_path = fetch_mef()
    ipa_path = fetch_ipa()

    filtro = ""
    if only_controllo:
        filtro = "AND m.tipo_controllo IS NOT NULL AND m.tipo_controllo != '' AND m.tipo_controllo != 'nessuno'"

    con = duckdb.connect()
    q = f"""
    WITH mef AS (
        SELECT DISTINCT
            TRIM(REPLACE(REPLACE(partecipata_codice_fiscale, '[', ''), ']', '')) AS cf_norm,
            TRIM(partecipata_denominazione) AS denominazione,
            CASE WHEN tipo_controllo IS NULL OR tipo_controllo = '' OR tipo_controllo = 'nessuno'
                 THEN 'partecipata' ELSE 'controllo_pubblico' END AS categoria
        FROM read_parquet('{mef_path}')
        WHERE anno = 2023 {filtro}
    )
    SELECT m.cf_norm, m.denominazione, m.categoria,
           i.sito_istituzionale, i.tipologia AS tipologia_ipa
    FROM mef m
    JOIN read_parquet('{ipa_path}') i
         ON m.cf_norm = i.codice_fiscale_ente
    WHERE i.sito_istituzionale IS NOT NULL AND i.sito_istituzionale != ''
    ORDER BY m.denominazione
    """
    df = con.execute(q).fetchdf()
    if max_siti:
        df = df.head(max_siti)
    print(f"[fetch] Partecipate con sito web: {len(df)}")
    return df.to_dict("records")


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    fetch_mef(force)
    fetch_ipa(force)
    print("[fetch] Fatto.")

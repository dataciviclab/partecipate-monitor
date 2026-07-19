"""
fetch_data.py — Scarica dataset multi-fonte (MEF, IPA, ANAC, RNA) da GCS via DuckDB.
Se GCS non e' raggiungibile (es. in CI senza credenziali), usa cache locale.
Supporta fetch filtrato per CF target per ridurre volume dati.
"""

import duckdb, json, os, sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Path GCS dataset clean — TUTTI con underscore (verificati su GCS)
GCS_MEF  = "gs://dataciviclab-clean/mef_partecipazioni/*/*.parquet"
GCS_IPA  = "gs://dataciviclab-clean/ipa_enti/*/*.parquet"
GCS_ANAC = "gs://dataciviclab-clean/anac_bandi_gara/*/*.parquet"
GCS_RNA  = "gs://dataciviclab-clean/rna_aiuti_stato/*/*.parquet"
GCS_RAPP = "gs://dataciviclab-clean/mef_rappresentanti_partecipate/*/*.parquet"

# Cache locali
LOCAL_MEF  = DATA_DIR / "mef_partecipazioni.parquet"
LOCAL_IPA  = DATA_DIR / "ipa_enti.parquet"
LOCAL_ANAC = DATA_DIR / "anac_bandi_gara.parquet"
LOCAL_RNA  = DATA_DIR / "rna_aiuti_stato.parquet"
LOCAL_RAPP = DATA_DIR / "mef_rappresentanti_partecipate.parquet"


def _conn():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='us-east-1';")
    return con


def _fetch_parquet(label, gcs_pattern, local_path, force=False, cfs=None, cf_col=None):
    """Scarica un dataset da GCS (con filtro CF opzionale) o usa cache."""
    if local_path.exists() and not force:
        n = _count_rows(local_path)
        print(f"[fetch] Usa cache locale: {local_path} ({n} righe)")
        return str(local_path)

    print(f"[fetch] Scarica {label} da GCS...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = _conn()

    where = ""
    if cfs and cf_col:
        cf_list = ", ".join(f"'{c}'" for c in cfs)
        where = f"WHERE {cf_col} IN ({cf_list})"

    sql = f"SELECT * FROM read_parquet('{gcs_pattern}', union_by_name=True) {where}"
    con.execute(f"COPY ({sql}) TO '{local_path}' (FORMAT PARQUET)")
    n = _count_rows(local_path)
    print(f"[fetch] Salvato: {local_path} ({n} righe)")
    return str(local_path)


def _count_rows(path):
    con = duckdb.connect()
    try:
        return con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
    except Exception:
        return 0


def fetch_mef(force=False):
    """Scarica mef_partecipazioni da GCS o usa cache."""
    return _fetch_parquet("mef_partecipazioni", GCS_MEF, LOCAL_MEF, force)


def fetch_ipa(force=False):
    """Scarica ipa_enti da GCS o usa cache."""
    return _fetch_parquet("ipa_enti", GCS_IPA, LOCAL_IPA, force)


def fetch_anac(force=False, cfs=None):
    """Scarica anac_bandi_gara da GCS, opzionalmente filtrato per CF stazione appaltante."""
    return _fetch_parquet("anac_bandi_gara", GCS_ANAC, LOCAL_ANAC, force,
                          cfs=cfs, cf_col="cf_amministrazione_appaltante")


def fetch_rna(force=False, cfs=None):
    """Scarica rna_aiuti_stato da GCS, opzionalmente filtrato per CF beneficiario."""
    return _fetch_parquet("rna_aiuti_stato", GCS_RNA, LOCAL_RNA, force,
                          cfs=cfs, cf_col="codice_fiscale_beneficiario")


def fetch_rappresentanti(force=False, cfs=None):
    """Scarica mef_rappresentanti_partecipate da GCS, filtrato per CF societa' (con parentesi)."""
    if LOCAL_RAPP.exists() and not force:
        n = _count_rows(LOCAL_RAPP)
        print(f"[fetch] Usa cache locale: {LOCAL_RAPP} ({n} righe)")
        return str(LOCAL_RAPP)

    print("[fetch] Scarica mef_rappresentanti_partecipate da GCS...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = _conn()

    where = ""
    if cfs:
        # MEF rappresentanti usa formato [CF] con parentesi; normalizziamo
        cf_conditions = " OR ".join(
            f"REPLACE(REPLACE(societa_cf, '[', ''), ']', '') = '{c}'" for c in cfs
        )
        where = f"WHERE {cf_conditions}"

    sql = f"SELECT * FROM read_parquet('{GCS_RAPP}') {where}"
    con.execute(f"COPY ({sql}) TO '{LOCAL_RAPP}' (FORMAT PARQUET)")
    n = _count_rows(LOCAL_RAPP)
    print(f"[fetch] Salvato: {LOCAL_RAPP} ({n} righe)")
    return str(LOCAL_RAPP)


def fetch_all(force=False, cfs=None):
    """Scarica tutti i dataset. Se cfs=None, scarica full."""
    fetch_mef(force)
    fetch_ipa(force)
    fetch_anac(force, cfs)
    fetch_rna(force, cfs)
    fetch_rappresentanti(force, cfs)


def estrai_partecipate(only_controllo=False, max_siti=None, solo_mef_centrali=False):
    """Estrae l'elenco delle partecipate con sito web (IPA join).

    Args:
        only_controllo: solo partecipate con controllo pubblico dichiarato.
        max_siti: limite massimo di risultati.
        solo_mef_centrali: solo partecipate MEF 100% (>100 addetti, controllo pieno).
    """
    mef_path = fetch_mef()
    ipa_path = fetch_ipa()

    filtro_controllo = ""
    if only_controllo:
        filtro_controllo = "AND tipo_controllo IS NOT NULL AND tipo_controllo != '' AND tipo_controllo != 'nessuno'"

    filtro_centrali = ""
    if solo_mef_centrali:
        filtro_centrali = """
            AND amministrazione_denominazione = 'MINISTERO DELL''ECONOMIA E DELLE FINANZE'
            AND partecipata_stato_giuridico = 'Attiva'
            AND partecipata_numero_di_addetti >= 100
        """

    join_type = "LEFT" if solo_mef_centrali else "INNER"
    filter_sito = "" if solo_mef_centrali else "AND i.sito_istituzionale IS NOT NULL"

    con = duckdb.connect()
    q = f"""
    WITH mef AS (
        SELECT DISTINCT
            TRIM(REPLACE(REPLACE(partecipata_codice_fiscale, '[', ''), ']', '')) AS cf_norm,
            TRIM(partecipata_denominazione) AS denominazione,
            MAX(partecipata_numero_di_addetti) AS addetti,
            CASE WHEN tipo_controllo IS NULL OR tipo_controllo = '' OR tipo_controllo = 'nessuno'
                 THEN 'partecipata' ELSE 'controllo_pubblico' END AS categoria,
            CASE WHEN emittente_azioni_quotate = 'SI' THEN TRUE ELSE FALSE END AS quotata
        FROM read_parquet('{mef_path}')
        WHERE anno = 2023 {filtro_controllo} {filtro_centrali}
        GROUP BY cf_norm, denominazione, categoria, quotata
    )
    SELECT m.cf_norm, m.denominazione, m.addetti, m.categoria, m.quotata,
           i.sito_istituzionale, i.tipologia AS tipologia_ipa
    FROM mef m
    {join_type} JOIN read_parquet('{ipa_path}') i
         ON m.cf_norm = i.codice_fiscale_ente
    {filter_sito}
    ORDER BY m.addetti DESC NULLS LAST
    """
    df = con.execute(q).fetchdf()
    if max_siti:
        df = df.head(max_siti)
    print(f"[fetch] Partecipate trovate: {len(df)}")
    return df.to_dict("records")


def cf_targets_centrali():
    """Estrae i CF delle partecipate MEF 100% (>100 addetti)."""
    partecipate = estrai_partecipate(solo_mef_centrali=True)
    return [p["cf_norm"] for p in partecipate if p["cf_norm"]]


def main():
    import sys
    force = "--force" in sys.argv

    if "--centrali" in sys.argv:
        cfs = cf_targets_centrali()
        print(f"[fetch] Target: {len(cfs)} partecipate centrali")
        fetch_all(force, cfs=cfs)
    elif "--all" in sys.argv:
        fetch_all(force)
    else:
        fetch_mef(force)
        fetch_ipa(force)
        print("[fetch] Fatto. Usa --all per tutti i dataset, --centrali per solo MEF 100%")


if __name__ == "__main__":
    main()

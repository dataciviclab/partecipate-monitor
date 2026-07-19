"""
build_fatti.py — Costruisce la tabella dei fatti unificata per le partecipate.

Legge i 5 dataset (MEF, rappresentanti, ANAC, RNA, IPA) e produce
data/fatti_partecipate.parquet in formato (fonte, cf, anno, importo, metadati).
Pronto per essere usato dal profiler senza join distribuiti.
"""

import duckdb
from pathlib import Path
from fetch_data import (
    fetch_mef, fetch_ipa, fetch_anac, fetch_rna, fetch_rappresentanti
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT = DATA_DIR / "fatti_partecipate.parquet"


def _conn():
    return duckdb.connect()


def step_mef(con):
    """Fonte: mef_partecipazioni → addetti, valore produzione, risultato, patrimonio."""
    mef = fetch_mef()
    print("[fatti] MEF: estrazione metriche...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _mef AS
        SELECT 'mef' AS fonte,
               TRIM(REPLACE(REPLACE(partecipata_codice_fiscale, '[', ''), ']', '')) AS cf,
               anno,
               partecipata_numero_di_addetti AS importo,
               'addetti' AS metrica,
               partecipata_denominazione AS denominazione,
               partecipata_settore_attivita AS settore
        FROM read_parquet('{mef}')
        WHERE partecipata_numero_di_addetti IS NOT NULL
          AND partecipata_numero_di_addetti > 0
    """)


def step_mef_finanziario(con):
    """Fonte: mef_partecipazioni → metriche economico-patrimoniali."""
    mef = fetch_mef()
    print("[fatti] MEF: metriche finanziarie...")
    con.execute(f"""
        INSERT INTO _mef
        SELECT 'mef' AS fonte,
               TRIM(REPLACE(REPLACE(partecipata_codice_fiscale, '[', ''), ']', '')) AS cf,
               anno,
               partecipata_valore_della_produzione_co_e_p AS importo,
               'valore_produzione' AS metrica,
               partecipata_denominazione AS denominazione,
               partecipata_settore_attivita AS settore
        FROM read_parquet('{mef}')
        WHERE partecipata_valore_della_produzione_co_e_p IS NOT NULL
          AND partecipata_valore_della_produzione_co_e_p > 0
    """)
    for col, metrica in [
        ("partecipata_risultato_d_esercizio_co_e_p", "risultato_esercizio"),
        ("partecipata_patrimonio_netto_co_e_p", "patrimonio_netto"),
        ("partecipata_costo_del_personale_co_e_p", "costo_personale"),
    ]:
        con.execute(f"""
            INSERT INTO _mef
            SELECT 'mef', 
                   TRIM(REPLACE(REPLACE(partecipata_codice_fiscale, '[', ''), ']', '')),
                   anno, {col}, '{metrica}',
                   partecipata_denominazione, partecipata_settore_attivita
            FROM read_parquet('{mef}')
            WHERE {col} IS NOT NULL AND {col} != 0
        """)


def step_rappresentanti(con):
    """Fonte: mef_rappresentanti_partecipate → compensi."""
    rapp = fetch_rappresentanti()
    print("[fatti] Rappresentanti: compensi...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _rapp AS
        SELECT 'rappresentanti' AS fonte,
               TRIM(REPLACE(REPLACE(societa_cf, '[', ''), ']', '')) AS cf,
               anno,
               incarico_importo_eur AS importo,
               'compenso' AS metrica,
               societa AS denominazione,
               incarico_tipo AS settore
        FROM read_parquet('{rapp}')
        WHERE incarico_importo_eur IS NOT NULL AND incarico_importo_eur > 0
    """)


def step_anac(con):
    """Fonte: anac_bandi_gara → importi gare per SA."""
    anac = fetch_anac()
    print("[fatti] ANAC: gare bandite...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _anac AS
        SELECT 'anac' AS fonte,
               cf_amministrazione_appaltante AS cf,
               anno_pubblicazione AS anno,
               importo_complessivo_gara AS importo,
               'gara' AS metrica,
               denominazione_amministrazione_appaltante AS denominazione,
               oggetto_principale_contratto AS settore
        FROM read_parquet('{anac}')
        WHERE stato = 'ATTIVO'
          AND importo_complessivo_gara IS NOT NULL
          AND importo_complessivo_gara > 0
    """)


def step_rna(con):
    """Fonte: rna_aiuti_stato → aiuti concessi."""
    rna = fetch_rna()
    print("[fatti] RNA: aiuti di Stato...")
    con.execute(f"""
        CREATE OR REPLACE TABLE _rna AS
        SELECT 'aiuto_stato' AS fonte,
               codice_fiscale_beneficiario AS cf,
               anno,
               elemento_aiuto AS importo,
               'aiuto_esl' AS metrica,
               denominazione_beneficiario AS denominazione,
               soggetto_concedente AS settore
        FROM read_parquet('{rna}')
        WHERE elemento_aiuto IS NOT NULL AND elemento_aiuto > 0
    """)


def unifica(con):
    """Unisce tutte le fonti in un unico parquet."""
    print("[fatti] Unificazione...")
    con.execute("DROP TABLE IF EXISTS _mef_fin;")
    
    # Unisci tutte le tabelle
    con.execute("""
        CREATE OR REPLACE TABLE _fatti AS
        SELECT * FROM _mef
        UNION ALL BY NAME
        SELECT fonte, cf, anno, importo, 'compenso' AS metrica, denominazione, '' AS settore FROM _rapp
        UNION ALL BY NAME
        SELECT * FROM _anac
        UNION ALL BY NAME
        SELECT * FROM _rna
    """)
    
    # Salva
    con.execute(f"COPY _fatti TO '{OUTPUT}' (FORMAT PARQUET)")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{OUTPUT}')").fetchone()[0]
    enti = con.execute(f"SELECT count(DISTINCT cf) FROM read_parquet('{OUTPUT}')").fetchone()[0]
    print(f"[fatti] Salvato: {OUTPUT}")
    print(f"[fatti] Righe: {n:,} — Enti unici: {enti:,}")


def main():
    print("[fatti] Costruzione tabella fatti partecipate...")
    con = _conn()
    
    step_mef(con)
    step_mef_finanziario(con)
    step_rappresentanti(con)
    step_anac(con)
    step_rna(con)
    unifica(con)


if __name__ == "__main__":
    main()

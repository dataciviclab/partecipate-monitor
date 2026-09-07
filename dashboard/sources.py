"""Data sources per la dashboard Partecipate Monitor.

Layer sottile che wrappa ``lab_connectors.duckdb.queries`` con
``@st.cache_data`` per Streamlit. Tutta la logica di risoluzione
path e auto-detect locale/GCS sta in lab-connectors.

I cross-dataset marts (by_regione, by_settore, profilo_ente) sono
calcolati al volo con DuckDB leggendo i mart dei singoli dataset.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from lab_connectors.duckdb.queries import (
    load_mart_all_years,
    load_mart_table,
)
from lab_connectors.formatters import fmt_eur as _fmt_eur
from lab_connectors.formatters import fmt_num as _fmt_num
from lab_connectors.formatters import fmt_pct as _fmt_pct
from lab_connectors.registry import load_registry


def _safe(val):
    """Convert pandas NAType to None (lab_connectors formatters don't handle it)."""
    import pandas as pd
    if val is None or (isinstance(val, float) and val != val):
        return None
    if isinstance(val, type(pd.NA)):
        return None
    return val


def fmt_eur(val):  # noqa: F401 — re-exported for pages
    return _fmt_eur(_safe(val))


def fmt_num(val):  # noqa: F401 — re-exported for pages
    return _fmt_num(_safe(val))


def fmt_pct(val, **kw):  # noqa: F401 — re-exported for pages
    return _fmt_pct(_safe(val), **kw)

# ── Costanti dominio ────────────────────────────────────────────────────────

_REPO = Path(__file__).parent.parent

_registry = load_registry(_REPO / "registry" / "registry.json")

def _years_for(slug: str) -> list[int]:
    ds = next((d for d in _registry.datasets if d.slug == slug), None)
    if ds is None or not hasattr(ds, "period") or ds.period is None:
        return []
    p = ds.period
    start = getattr(p, "start", None) or (p.get("start") if isinstance(p, dict) else None)
    end = getattr(p, "end", None) or (p.get("end") if isinstance(p, dict) else None)
    if start and end:
        return list(range(int(start), int(end) + 1))
    return []

SLUG_PARTECIPAZIONI = "mef_partecipazioni"
SLUG_RAPPRESENTANTI = "mef_rappresentanti_partecipate"
SLUG_ADEMPIMENTI = "mef_adempimenti"

YEARS_PARTECIPAZIONI = _years_for(SLUG_PARTECIPAZIONI)
YEARS_RAPPRESENTANTI = _years_for(SLUG_RAPPRESENTANTI)
YEARS_ADEMPIMENTI = _years_for(SLUG_ADEMPIMENTI)

YEARS = sorted(set(YEARS_PARTECIPAZIONI + YEARS_RAPPRESENTANTI + YEARS_ADEMPIMENTI))
YEARS_COMBINED = sorted(set(YEARS_PARTECIPAZIONI) & set(YEARS_RAPPRESENTANTI) & set(YEARS_ADEMPIMENTI))


# ── Mart loaders (toolkit pipeline, auto-detect locale/GCS) ─────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_partecipate(year: int | None = None):
    if year is not None:
        return load_mart_table(SLUG_PARTECIPAZIONI, "mart_partecipate", year)
    return load_mart_all_years(SLUG_PARTECIPAZIONI, "mart_partecipate", YEARS_PARTECIPAZIONI)


@st.cache_data(ttl=3600, show_spinner=False)
def load_rappresentanti(year: int | None = None):
    if year is not None:
        return load_mart_table(SLUG_RAPPRESENTANTI, "mart_rappresentanti", year)
    return load_mart_all_years(SLUG_RAPPRESENTANTI, "mart_rappresentanti", YEARS_RAPPRESENTANTI)


@st.cache_data(ttl=3600, show_spinner=False)
def load_adempimenti(year: int | None = None):
    if year is not None:
        return load_mart_table(SLUG_ADEMPIMENTI, "mart_adempimenti", year)
    return load_mart_all_years(SLUG_ADEMPIMENTI, "mart_adempimenti", YEARS_ADEMPIMENTI)


# ── Cross-dataset: calcolo al volo con DuckDB ───────────────────────────────

def _duckdb_df(sql: str):
    from lab_connectors.duckdb.core import safe_connect
    with safe_connect() as con:
        return con.sql(sql).df()


def _mart_url(slug: str, table: str, year: int) -> str:
    """Risolvi URL parquet: locale se esiste, GCS altrimenti."""
    from lab_connectors.duckdb.queries import _resolve_url
    return _resolve_url("mart", "mart_parquet", slug=slug, year=str(year), table=table)


@st.cache_data(ttl=3600, show_spinner=False)
def load_by_regione(year: int):
    """Aggregati per regione — calcolato al volo."""
    p = _mart_url(SLUG_PARTECIPAZIONI, "mart_partecipate", year)
    a = _mart_url(SLUG_ADEMPIMENTI, "mart_adempimenti", year)
    r = _mart_url(SLUG_RAPPRESENTANTI, "mart_rappresentanti", year)

    sql = f"""
    WITH partecipate AS (
        SELECT anno, regione_sede,
            COUNT(DISTINCT cf) AS n_partecipate,
            SUM(addetti) AS addetti_totali,
            SUM(valore_produzione) AS valore_produzione_totale,
            SUM(risultato_esercizio) AS risultato_esercizio_totale,
            SUM(patrimonio_netto) AS patrimonio_netto_totale
        FROM read_parquet('{p}')
        WHERE regione_sede IS NOT NULL
        GROUP BY anno, regione_sede
    ),
    adempimenti AS (
        SELECT anno, regione_sede,
            COUNT(*) AS n_enti_totali,
            COUNT(*) FILTER (WHERE adempiente) AS n_adempienti,
            COUNT(*) FILTER (WHERE NOT adempiente) AS n_inadempienti,
            ROUND(100.0 * COUNT(*) FILTER (WHERE NOT adempiente) / NULLIF(COUNT(*), 0), 1) AS pct_inadempimento,
            SUM(partecipazioni_dichiarate) AS partecipazioni_dichiarate_totali,
            SUM(incarichi_dichiarati) AS incarichi_dichiarati_totali
        FROM read_parquet('{a}')
        WHERE regione_sede IS NOT NULL
        GROUP BY anno, regione_sede
    ),
    rappresentanti AS (
        SELECT anno, regione_sede,
            SUM(spesa_totale_eur) AS spesa_governance_totale,
            SUM(n_incarichi) AS n_incarichi_totali
        FROM read_parquet('{r}')
        WHERE regione_sede IS NOT NULL AND spesa_totale_eur > 0
        GROUP BY anno, regione_sede
    ),
    all_keys AS (
        SELECT anno, regione_sede FROM partecipate
        UNION SELECT anno, regione_sede FROM adempimenti
        UNION SELECT anno, regione_sede FROM rappresentanti
    )
    SELECT k.anno, k.regione_sede AS regione,
        a.n_enti_totali, a.n_adempienti, a.n_inadempienti, a.pct_inadempimento,
        a.partecipazioni_dichiarate_totali, a.incarichi_dichiarati_totali,
        p.n_partecipate, p.addetti_totali, p.valore_produzione_totale,
        p.risultato_esercizio_totale, p.patrimonio_netto_totale,
        r.spesa_governance_totale, r.n_incarichi_totali AS n_incarichi_governance
    FROM all_keys k
    LEFT JOIN partecipate p ON k.anno = p.anno AND k.regione_sede = p.regione_sede
    LEFT JOIN adempimenti a ON k.anno = a.anno AND k.regione_sede = a.regione_sede
    LEFT JOIN rappresentanti r ON k.anno = r.anno AND k.regione_sede = r.regione_sede
    ORDER BY k.anno, k.regione_sede
    """
    return _duckdb_df(sql)


@st.cache_data(ttl=3600, show_spinner=False)
def load_by_settore(year: int):
    """Aggregati per settore — calcolato al volo."""
    p = _mart_url(SLUG_PARTECIPAZIONI, "mart_partecipate", year)

    sql = f"""
    WITH dedup AS (
        SELECT anno, cf, settore_attivita,
            MAX(addetti) AS addetti, MAX(valore_produzione) AS valore_produzione,
            MAX(risultato_esercizio) AS risultato_esercizio, MAX(patrimonio_netto) AS patrimonio_netto,
            MAX(costo_personale) AS costo_personale
        FROM read_parquet('{p}')
        GROUP BY anno, cf, settore_attivita
    )
    SELECT anno, settore_attivita,
        COUNT(DISTINCT cf) AS n_partecipate,
        SUM(addetti) AS addetti_totali,
        SUM(valore_produzione) AS valore_produzione_totale,
        SUM(risultato_esercizio) AS risultato_esercizio_totale,
        SUM(patrimonio_netto) AS patrimonio_netto_totale,
        SUM(costo_personale) AS costo_personale_totale,
        ROUND(100.0 * SUM(addetti) / NULLIF(SUM(SUM(addetti)) OVER (PARTITION BY anno), 0), 1) AS pct_addetti,
        ROUND(100.0 * SUM(valore_produzione) / NULLIF(SUM(SUM(valore_produzione)) OVER (PARTITION BY anno), 0), 1) AS pct_valore_produzione
    FROM dedup
    WHERE settore_attivita IS NOT NULL
    GROUP BY anno, settore_attivita
    ORDER BY anno, valore_produzione_totale DESC
    """
    return _duckdb_df(sql)


@st.cache_data(ttl=3600, show_spinner=False)
def load_profilo_ente(year: int):
    """Profilo unificato per amministrazione — join di tutti i 3 dataset."""
    p = _mart_url(SLUG_PARTECIPAZIONI, "mart_partecipate", year)
    a = _mart_url(SLUG_ADEMPIMENTI, "mart_adempimenti", year)

    sql = f"""
    WITH partecipate AS (
        SELECT anno, cf AS cf_amm,
            MAX(denominazione) AS denominazione, MAX(settore_attivita) AS settore_attivita,
            MAX(regione_sede) AS regione_sede,
            COUNT(DISTINCT cf) AS n_partecipate,
            SUM(addetti) AS addetti_totali, SUM(valore_produzione) AS valore_produzione_totale,
            SUM(risultato_esercizio) AS risultato_esercizio_totale,
            SUM(patrimonio_netto) AS patrimonio_netto_totale,
            SUM(costo_personale) AS costo_personale_totale
        FROM read_parquet('{p}')
        GROUP BY anno, cf
    )
    SELECT a.cf, a.anno,
        COALESCE(a.denominazione, p.denominazione) AS denominazione,
        COALESCE(a.settore_istituzionale, p.settore_attivita) AS settore_attivita,
        a.regione_sede, a.adempiente, a.compliance_score,
        a.partecipazioni_dichiarate, a.incarichi_dichiarati,
        a.negativa_partecipazioni_societarie, a.negativa_partecipazioni_nonsocietarie,
        a.negativa_incarichi,
        p.n_partecipate, p.addetti_totali, p.valore_produzione_totale,
        p.risultato_esercizio_totale, p.patrimonio_netto_totale, p.costo_personale_totale
    FROM read_parquet('{a}') a
    LEFT JOIN partecipate p ON a.cf = p.cf_amm AND a.anno = p.anno
    ORDER BY a.cf, a.anno
    """
    return _duckdb_df(sql)


# ── GCS live queries (ANAC, RNA, IPA) ───────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def gare_per_cf(cf: str, year: int):
    from lab_connectors.duckdb.core import safe_connect
    from lab_connectors.gcs.paths import https_url

    url = https_url("clean", "clean_parquet", slug="anac_bandi_gara", year=year)
    with safe_connect() as con:
        return con.sql(
            f"SELECT * FROM read_parquet('{url}') "
            f"WHERE cf_amministrazione_appaltante = '{cf}' "
            f"ORDER BY data_pubblicazione DESC"
        ).df()


@st.cache_data(ttl=3600, show_spinner=False)
def aiuti_per_cf(cf: str, year: int):
    from lab_connectors.duckdb.core import safe_connect
    from lab_connectors.gcs.paths import https_url

    url = https_url("clean", "clean_parquet", slug="rna_aiuti_stato", year=year)
    with safe_connect() as con:
        return con.sql(
            f"SELECT * FROM read_parquet('{url}') "
            f"WHERE codice_fiscale_beneficiario = '{cf}' "
            f"ORDER BY elemento_aiuto DESC"
        ).df()


@st.cache_data(ttl=3600, show_spinner=False)
def ipa_per_cf(cf: str):
    from lab_connectors.duckdb.core import safe_connect
    from lab_connectors.gcs.paths import https_url

    url = https_url("clean", "clean_parquet", slug="ipa_enti", year=2026)
    with safe_connect() as con:
        return con.sql(
            f"SELECT * FROM read_parquet('{url}') "
            f"WHERE codice_fiscale_ente = '{cf}' LIMIT 1"
        ).df()


# ── Entity selector ──────────────────────────────────────────────────────────

def entity_selector(key: str = "entity", label: str = "Seleziona partecipata"):
    df = load_partecipate()
    if df is None or df.empty:
        st.warning("Dati non disponibili. Esegui `make run`.")
        st.stop()

    anni = sorted(df["anno"].unique())
    anno = st.sidebar.selectbox("Anno", anni, index=len(anni) - 1, key=f"{key}_anno")

    df_anno = df[df["anno"] == anno].sort_values("denominazione")
    if df_anno.empty:
        st.warning("Nessuna entita' per i filtri selezionati.")
        st.stop()

    options = [f"{r['denominazione'][:80]} — {r['cf']}" for _, r in df_anno.iterrows()]
    cf_map = {opt: r["cf"] for opt, (_, r) in zip(options, df_anno.iterrows())}

    selected = st.selectbox(label, options, key=f"{key}_sel")
    cf = cf_map[selected]
    denom = df_anno[df_anno["cf"] == cf]["denominazione"].iloc[0]
    return cf, denom, anno

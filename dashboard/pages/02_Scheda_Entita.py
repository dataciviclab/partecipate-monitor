import plotly.express as px
import streamlit as st
from sources import (
    YEARS,
    YEARS_COMBINED,
    aiuti_per_cf,
    entity_selector,
    fmt_eur,
    fmt_num,
    gare_per_cf,
    ipa_per_cf,
    load_partecipate,
)

st.title("Scheda Entita")

cf, denom, anno_ref = entity_selector(key="scheda")

df = load_partecipate(anno_ref)
if df is None:
    st.warning("Dati non disponibili.")
    st.stop()

row = df[df["cf"] == cf]
if row.empty:
    st.error("Nessun dato per questo CF.")
    st.stop()

r = row.iloc[0]

# ── Anagrafica ──────────────────────────────────────────────────────────────

st.subheader(r.get("denominazione", denom))

c1, c2, c3, c4 = st.columns(4)
c1.metric("CF", cf)
c2.metric("Regione", r.get("regione_sede", "-"))
c3.metric("Settore", (r.get("settore_attivita") or "-"))
c4.metric("Forma giuridica", r.get("forma_giuridica", "-"))

# ── Metriche strutturali ────────────────────────────────────────────────────

st.subheader("Metriche")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Addetti", fmt_num(r.get("addetti")))
c2.metric("Valore produzione", fmt_eur(r.get("valore_produzione")))
c3.metric("Patrimonio netto", fmt_eur(r.get("patrimonio_netto")))
c4.metric("Costo personale", fmt_eur(r.get("costo_personale")))

c1, c2, c3, c4 = st.columns(4)
roe = r.get("roe")
c1.metric("ROE", f"{roe:.2%}" if roe is not None else "-")
c2.metric("Cost ratio", f"{r.get('cost_ratio', 0):.1%}" if r.get("cost_ratio") is not None else "-")
c3.metric("Taglia", r.get("taglia", "-"))
c4.metric("N. amministrazioni", fmt_num(r.get("n_amministrazioni")))

# ── Trend (multi-anno) ──────────────────────────────────────────────────────

st.subheader("Trend")
frames = []
for y in YEARS_COMBINED:
    d = load_partecipate(y)
    if d is not None:
        row_y = d[d["cf"] == cf]
        if not row_y.empty:
            frames.append(row_y)

if len(frames) > 1:
    import pandas as pd
    trend = pd.concat(frames, ignore_index=True)

    fig = px.line(trend, x="anno", y="addetti", markers=True,
                  labels={"anno": "Anno", "addetti": "Addetti"})
    st.plotly_chart(fig, use_container_width=True)

    fin_cols = {"valore_produzione": "Valore produzione",
                "risultato_esercizio": "Risultato esercizio",
                "patrimonio_netto": "Patrimonio netto"}
    fin_data = trend[["anno"] + list(fin_cols.keys())].melt(id_vars="anno", var_name="metrica", value_name="importo")
    fin_data["metrica"] = fin_data["metrica"].map(fin_cols)
    fig = px.line(fin_data, x="anno", y="importo", color="metrica", markers=True,
                  labels={"anno": "Anno", "importo": "EUR", "metrica": ""})
    st.plotly_chart(fig, use_container_width=True)

# ── ANAC + RNA (anno selezionato) ──────────────────────────────────────────

anno_ext = st.selectbox("Anno fonti esterne", YEARS, index=len(YEARS) - 1, key="scheda_anno_ext")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Appalti ANAC")
    try:
        gare = gare_per_cf(cf, anno_ext)
        if not gare.empty:
            st.metric("Gare bandite", len(gare))
            cols = [c for c in ["cig", "oggetto_gara", "importo_complessivo_gara", "stato"]
                    if c in gare.columns]
            st.dataframe(gare[cols].head(10), use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna gara.")
    except Exception as e:
        st.warning(f"Errore ANAC: {e}")

with c2:
    st.subheader("Aiuti di Stato")
    try:
        aiuti = aiuti_per_cf(cf, anno_ext)
        if not aiuti.empty:
            st.metric("Totale aiuti", fmt_eur(aiuti["elemento_aiuto"].sum()))
            cols = [c for c in ["titolo_misura", "elemento_aiuto", "soggetto_concedente"]
                    if c in aiuti.columns]
            st.dataframe(aiuti[cols].head(10), use_container_width=True, hide_index=True)
        else:
            st.info("Nessun aiuto.")
    except Exception as e:
        st.warning(f"Errore RNA: {e}")

# ── IPA ─────────────────────────────────────────────────────────────────────

try:
    ipa = ipa_per_cf(cf)
    if not ipa.empty:
        r_ipa = ipa.iloc[0]
        st.caption(f"IPA: {r_ipa.get('tipologia', '-')} | {r_ipa.get('sito_istituzionale', '-')} | {r_ipa.get('mail1', '-')}")
except Exception:
    pass

import plotly.express as px
import streamlit as st
from sources import YEARS_COMBINED, fmt_eur, fmt_num, load_partecipate

st.title("Confronto")

df = load_partecipate()
if df is None or df.empty:
    st.warning("Dati non disponibili. Esegui `make run`.")
    st.stop()

anni = sorted(df["anno"].unique())
anno = st.sidebar.selectbox("Anno", anni, index=len(anni) - 1)

df_anno = df[df["anno"] == anno].sort_values("denominazione")

# ── Selezione entita' ──────────────────────────────────────────────────────

n = st.sidebar.slider("Nr. entita' da confrontare", 2, 8, 3)

options = [f"{r['denominazione'][:60]} — {r['cf']}" for _, r in df_anno.iterrows()]
cf_map = {opt: r["cf"] for opt, (_, r) in zip(options, df_anno.iterrows())}

selected = st.sidebar.multiselect("Seleziona entita'", options, default=options[:n], key="confronto_sel")
if not selected:
    st.info("Seleziona almeno un'entita'.")
    st.stop()

cfs = [cf_map[s] for s in selected]
df_conv = df_anno[df_anno["cf"].isin(cfs)]

# ── Tabella comparativa ─────────────────────────────────────────────────────

st.subheader(f"Confronto ({anno})")

cols_show = [
    ("denominazione", "Denominazione"),
    ("settore_attivita", "Settore"),
    ("regione_sede", "Regione"),
    ("addetti", "Addetti"),
    ("valore_produzione", "Valore produzione"),
    ("risultato_esercizio", "Risultato esercizio"),
    ("patrimonio_netto", "Patrimonio netto"),
    ("costo_personale", "Costo personale"),
    ("roe", "ROE"),
    ("cost_ratio", "Cost ratio"),
    ("taglia", "Taglia"),
    ("n_amministrazioni", "N. amministrazioni"),
]

table = df_conv[["cf"] + [c[0] for c in cols_show]].copy()
table.columns = ["CF"] + [c[1] for c in cols_show]

# Formatta
for col in ["Addetti", "N. amministrazioni"]:
    if col in table.columns:
        table[col] = table[col].apply(fmt_num)
for col in ["Valore produzione", "Risultato esercizio", "Patrimonio netto", "Costo personale"]:
    if col in table.columns:
        table[col] = table[col].apply(fmt_eur)
if "ROE" in table.columns:
    table["ROE"] = table["ROE"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "-")
if "Cost ratio" in table.columns:
    table["Cost ratio"] = table["Cost ratio"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "-")

st.dataframe(table.set_index("CF"), use_container_width=True)

# ── Grafici comparativi ────────────────────────────────────────────────────

st.subheader("Grafici")

metriche = [
    ("addetti", "Addetti"),
    ("valore_produzione", "Valore produzione"),
    ("risultato_esercizio", "Risultato esercizio"),
    ("patrimonio_netto", "Patrimonio netto"),
]

for col, label in metriche:
    fig = px.bar(df_conv, x="denominazione", y=col,
                 labels={"denominazione": "", col: label},
                 height=250)
    st.plotly_chart(fig, use_container_width=True)

# ── Trend ──────────────────────────────────────────────────────────────────

st.subheader("Trend addetti")
frames = []
for y in YEARS_COMBINED:
    d = load_partecipate(y)
    if d is not None:
        rows = d[d["cf"].isin(cfs)]
        if not rows.empty:
            frames.append(rows)

if len(frames) > 1:
    import pandas as pd
    trend = pd.concat(frames, ignore_index=True)
    fig = px.line(trend, x="anno", y="addetti", color="denominazione", markers=True,
                  labels={"anno": "Anno", "addetti": "Addetti", "denominazione": ""})
    st.plotly_chart(fig, use_container_width=True)

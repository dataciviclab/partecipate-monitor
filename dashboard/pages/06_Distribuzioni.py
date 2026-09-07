import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sources import YEARS_COMBINED, fmt_num, load_partecipate, load_rappresentanti

st.title("Distribuzioni")

anno = st.sidebar.selectbox("Anno", YEARS_COMBINED, index=len(YEARS_COMBINED) - 1)

df = load_partecipate(anno)
df_rapp = load_rappresentanti(anno)

if df is None or df.empty:
    st.warning("Dati non disponibili. Esegui `make run`.")
    st.stop()

# ── Taglia ──────────────────────────────────────────────────────────────────

st.subheader("Distribuzione per taglia")
taglia_dist = df["taglia"].value_counts()
order = ["piccola", "media", "medio-grande", "grande", "sconosciuta"]
colors = {"piccola": "#6366f1", "media": "#22c55e", "medio-grande": "#f59e0b", "grande": "#ef4444", "sconosciuta": "#94a3b8"}
fig = go.Figure(go.Bar(
    x=[t for t in order if t in taglia_dist.index],
    y=[taglia_dist[t] for t in order if t in taglia_dist.index],
    marker_color=[colors.get(t, "#94a3b8") for t in order if t in taglia_dist.index],
    text=[fmt_num(taglia_dist[t]) for t in order if t in taglia_dist.index],
    textposition="outside",
))
fig.update_layout(height=300, margin=dict(t=20, b=20), xaxis_title="", yaxis_title="N. enti")
st.plotly_chart(fig, use_container_width=True)

# ── Metriche per taglia ─────────────────────────────────────────────────────

st.subheader("Metriche per taglia")
taglia_stats = df.groupby("taglia").agg(
    n=("cf", "count"),
    addetti_medio=("addetti", "median"),
    roe_medio=("roe", "median"),
    cost_ratio_medio=("cost_ratio", "median"),
    valore_produzione=("valore_produzione", "sum"),
).reset_index()
taglia_stats = taglia_stats.set_index("taglia").loc[[t for t in order if t in taglia_stats.index]].reset_index()

c1, c2, c3, c4 = st.columns(4)
for i, row in taglia_stats.iterrows():
    cols = [c1, c2, c3, c4][i % 4]
    with cols:
        st.metric(
            f"{row['taglia']} ({fmt_num(row['n'])})",
            f"ROE {row['roe_medio']:.1%}" if row['roe_medio'] == row['roe_medio'] else "ROE -",
        )

# ── Box plot ROE per taglia ────────────────────────────────────────────────

st.subheader("ROE per taglia")
roe_data = df[(df["roe"].notnull()) & (df["roe"] > -1) & (df["roe"] < 1)].copy()
if not roe_data.empty:
    fig = px.box(roe_data, x="taglia", y="roe", color="taglia",
                 color_discrete_map=colors,
                 labels={"taglia": "Taglia", "roe": "ROE"},
                 height=350)
    fig.add_hline(y=0, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

# ── Cost ratio ──────────────────────────────────────────────────────────────

st.subheader("Distribuzione cost ratio")
cr = df["cost_ratio"].dropna()
cr = cr[(cr >= 0) & (cr <= 2)]
fig = px.histogram(cr, x="cost_ratio", nbins=40, marginal="box",
                   labels={"cost_ratio": "Cost ratio (costo personale / valore produzione)"},
                   height=300, color_discrete_sequence=["#6366f1"])
fig.add_vline(x=cr.median(), line_dash="dash", line_color="red",
              annotation_text=f"Mediana: {cr.median():.1%}")
st.plotly_chart(fig, use_container_width=True)

# ── Scatter ROE vs Addetti (log scale) ─────────────────────────────────────

st.subheader("ROE vs Dimensione")
scatter = df[(df["roe"].notnull()) & (df["roe"] > -1) & (df["roe"] < 1) & (df["addetti"] > 0)].copy()
fig = px.scatter(scatter, x="addetti", y="roe", color="taglia",
                 color_discrete_map=colors,
                 hover_data=["denominazione", "regione_sede", "settore_attivita"],
                 labels={"addetti": "Addetti", "roe": "ROE", "taglia": "Taglia"},
                 height=400, opacity=0.6)
fig.update_xaxes(type="log")
fig.add_hline(y=0, line_dash="dash", line_color="red")
st.plotly_chart(fig, use_container_width=True)

# ── Gender gap (se disponibile) ────────────────────────────────────────────

if df_rapp is not None and not df_rapp.empty:
    st.subheader("Gender gap (spesa F/M)")
    gap = df_rapp[df_rapp["ratio_f_m"].notnull()]["ratio_f_m"]
    gap = gap[(gap > 0) & (gap < 3)]
    fig = px.histogram(gap, x="ratio_f_m", nbins=30, marginal="box",
                       labels={"ratio_f_m": "Rapporto F/M"},
                       height=300, color_discrete_sequence=["#22c55e"])
    fig.add_vline(x=1.0, line_dash="dash", line_color="red",
                  annotation_text="Parita'")
    st.plotly_chart(fig, use_container_width=True)

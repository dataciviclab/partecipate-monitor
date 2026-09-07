import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sources import YEARS_ADEMPIMENTI, fmt_num, load_adempimenti

st.title("Compliance TUSP")

anno = st.sidebar.selectbox("Anno", YEARS_ADEMPIMENTI, index=len(YEARS_ADEMPIMENTI) - 1)

df = load_adempimenti(anno)
if df is None or df.empty:
    st.warning("Dati non disponibili. Esegui `make run`.")
    st.stop()

# ── KPI ─────────────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.metric("Enti totali", fmt_num(len(df)))
c2.metric("Adempienti", fmt_num(df["adempiente"].sum()))
c3.metric("Inadempienti", fmt_num((~df["adempiente"]).sum()))
score_medio = df["compliance_score"].mean()
c4.metric("Score medio", f"{score_medio:.1f}/4")

# ── Distribuzione compliance score ──────────────────────────────────────────

st.subheader("Distribuzione compliance score")
score_dist = df["compliance_score"].value_counts().sort_index()
fig = px.bar(x=score_dist.index, y=score_dist.values,
             labels={"x": "Score", "y": "N. enti"},
             color=score_dist.index,
             color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e", "#16a34a", "#15803d"])
fig.update_layout(height=300, margin=dict(t=20, b=20), showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# ── Categoria compliance ────────────────────────────────────────────────────

st.subheader("Categorie compliance")
cat_dist = df["categoria_compliance"].value_counts()
colors = {"trasparente": "#22c55e", "parziale": "#f59e0b", "minima": "#f97316", "inadempiente": "#ef4444"}
fig = go.Figure(go.Pie(
    labels=cat_dist.index,
    values=cat_dist.values,
    marker_colors=[colors.get(c, "#94a3b8") for c in cat_dist.index],
    textinfo="percent+value",
    hole=0.4,
))
fig.update_layout(height=300, margin=dict(t=20, b=20))
st.plotly_chart(fig, use_container_width=True)

# ── Top inadempienti ────────────────────────────────────────────────────────

st.subheader("Enti inadempienti")
inad = df[~df["adempiente"]].sort_values("partecipazioni_dichiarate", ascending=False)
cols = ["cf", "denominazione", "regione_sede", "categoria",
        "partecipazioni_dichiarate", "incarichi_dichiarati", "compliance_score"]
st.dataframe(inad[cols].head(50), use_container_width=True, hide_index=True)

# ── Dichiarazioni negative ──────────────────────────────────────────────────

st.subheader("Dichiarazioni negative")
neg = df[df["dichiarazione_negativa_totale"]]
st.metric("Dichiarazione negativa totale", fmt_num(len(neg)))
if not neg.empty:
    st.dataframe(neg[["cf", "denominazione", "regione_sede", "categoria"]].head(30),
                 use_container_width=True, hide_index=True)

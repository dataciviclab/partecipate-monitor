import plotly.graph_objects as go
import streamlit as st
from sources import (
    YEARS_COMBINED,
    fmt_num,
    load_by_regione,
    load_by_settore,
)
from sources import (
    load_by_regione as _load_regione,
)

st.title("Panoramica")

anno = st.sidebar.selectbox("Anno", YEARS_COMBINED, index=len(YEARS_COMBINED) - 1)

df = load_by_regione(anno)
df_prev = _load_regione(anno - 1) if anno - 1 in YEARS_COMBINED else None
df_set = load_by_settore(anno)

if df is None:
    st.warning("Dati non disponibili. Esegui `make run`.")
    st.stop()

# ── Helpers ─────────────────────────────────────────────────────────────────

def _delta(curr, prev):
    """Calcola delta assoluto e percentuale."""
    if prev is None or prev == 0 or curr != curr:
        return None, None
    d = curr - prev
    return d, d / abs(prev)


def _fmt_delta(curr, prev, fmt_fn=fmt_num):
    """Formatta delta per st.metric."""
    d, pct = _delta(curr, prev)
    if d is None:
        return None, None
    label = fmt_fn(abs(d))
    if abs(d) == abs(curr):
        return None, None
    return f"{'+' if d >= 0 else '-'}{label}", f"{'+' if pct >= 0 else '-'}{abs(pct):.1%}"


def _sum(df, col):
    return df[col].sum() if df is not None and col in df.columns else None

# ── KPI con delta ───────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)

curr_enti = _sum(df, "n_enti_totali")
curr_inad = _sum(df, "n_inadempienti")
curr_part = _sum(df, "n_partecipate")
curr_add = _sum(df, "addetti_totali")

prev_enti = _sum(df_prev, "n_enti_totali")
prev_inad = _sum(df_prev, "n_inadempienti")
prev_part = _sum(df_prev, "n_partecipate")
prev_add = _sum(df_prev, "addetti_totali")

d_enti, p_enti = _fmt_delta(curr_enti, prev_enti)
d_inad, p_inad = _fmt_delta(curr_inad, prev_inad)
d_part, p_part = _fmt_delta(curr_part, prev_part)
d_add, p_add = _fmt_delta(curr_add, prev_add)

c1.metric("Enti totali", fmt_num(curr_enti), delta=d_enti, delta_color="off")
c2.metric("Inadempienti", fmt_num(curr_inad), delta=d_inad, delta_color="inverse")
c3.metric("Partecipate", fmt_num(curr_part), delta=d_part, delta_color="off")
c4.metric("Addetti", fmt_num(curr_add), delta=d_add, delta_color="off")

# ── Trend 4 anni ────────────────────────────────────────────────────────────

st.subheader("Trend")
trend_data = []
for y in YEARS_COMBINED:
    dy = load_by_regione(y)
    if dy is not None:
        trend_data.append({
            "anno": y,
            "enti_totali": dy["n_enti_totali"].sum(),
            "inadempienti": dy["n_inadempienti"].sum(),
            "partecipate": dy["n_partecipate"].sum(),
            "addetti": dy["addetti_totali"].sum(),
        })

if len(trend_data) > 1:
    import pandas as pd
    trend = pd.DataFrame(trend_data)

    c1, c2 = st.columns(2)

    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend["anno"], y=trend["partecipate"],
            name="Partecipate", mode="lines+markers",
            line=dict(color="#6366f1", width=3),
        ))
        fig.add_trace(go.Scatter(
            x=trend["anno"], y=trend["addetti"] / 1000,
            name="Addetti (k)", mode="lines+markers",
            line=dict(color="#22c55e", width=3), yaxis="y2",
        ))
        fig.update_layout(
            height=300, margin=dict(t=20, b=20),
            yaxis=dict(title="Partecipate"),
            yaxis2=dict(title="Addetti (k)", overlaying="y", side="right"),
            legend=dict(x=0, y=1.15, orientation="h"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend["anno"], y=trend["inadempienti"],
            name="Inadempienti", mode="lines+markers",
            line=dict(color="#ef4444", width=3), fill="tozeroy",
            fillcolor="rgba(239,68,68,0.1)",
        ))
        pct_inad = trend["inadempienti"] / trend["enti_totali"] * 100
        fig.add_trace(go.Scatter(
            x=trend["anno"], y=pct_inad,
            name="% inadempimento", mode="lines+markers",
            line=dict(color="#f59e0b", width=2, dash="dash"), yaxis="y2",
        ))
        fig.update_layout(
            height=300, margin=dict(t=20, b=20),
            yaxis=dict(title="Inadempienti"),
            yaxis2=dict(title="% inadempimento", overlaying="y", side="right"),
            legend=dict(x=0, y=1.15, orientation="h"),
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Regioni ─────────────────────────────────────────────────────────────────

st.subheader("Per regione")
reg = df.sort_values("addetti_totali", ascending=False)

c1, c2 = st.columns(2)

with c1:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=reg["regione"], y=reg["addetti_totali"],
        name="Addetti", marker_color="#6366f1",
    ))
    fig.update_layout(
        height=350, margin=dict(t=20, b=20),
        xaxis=dict(title=""), yaxis=dict(title="Addetti"),
    )
    st.plotly_chart(fig, use_container_width=True)

with c2:
    reg_filtro = reg[reg["pct_inadempimento"].notnull()].sort_values("pct_inadempimento", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=reg_filtro["regione"], y=reg_filtro["pct_inadempimento"],
        name="% inadempimento", marker_color="#ef4444",
    ))
    fig.update_layout(
        height=350, margin=dict(t=20, b=20),
        xaxis=dict(title=""), yaxis=dict(title="% inadempimento"),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Settori ─────────────────────────────────────────────────────────────────

if df_set is not None and not df_set.empty:
    st.subheader("Per settore attivita")
    import plotly.express as px
    fig = px.treemap(df_set, path=["settore_attivita"], values="addetti_totali",
                     hover_data=["n_partecipate", "valore_produzione_totale"],
                     height=350)
    st.plotly_chart(fig, use_container_width=True)

import plotly.express as px
import streamlit as st
from sources import fmt_eur, fmt_pct, load_partecipate, load_rappresentanti

st.title("Governance — Rappresentanti")

df = load_rappresentanti()
if df is None or df.empty:
    st.warning("Dati non disponibili. Esegui `make run`.")
    st.stop()

anni = sorted(df["anno"].unique())
df_ult = df[df["anno"] == anni[-1]]

# Denominazioni per join
df_part = load_partecipate(anni[-1])
if df_part is not None:
    denom_map = df_part.set_index("cf")["denominazione"].to_dict()
else:
    denom_map = {}

df_ult["denominazione"] = df_ult["cf"].map(denom_map).fillna("-")

# ── KPI globali ─────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.metric("Spesa totale", fmt_eur(df_ult["spesa_totale_eur"].sum()))
c2.metric("CF coinvolti", f"{df_ult['cf'].nunique()}")
c3.metric("Incarichi totali", f"{df_ult['n_incarichi'].sum()}")
tot_incarichi = df_ult["n_incarichi"].sum()
tot_gratuiti = df_ult["n_gratuiti"].sum()
c4.metric("Gratuiti", f"{tot_gratuiti} / {tot_incarichi} ({tot_gratuiti/tot_incarichi:.0%})")

# ── Trend spesa ─────────────────────────────────────────────────────────────

st.subheader("Trend spesa totale")
trend = df.groupby("anno").agg(
    spesa=("spesa_totale_eur", "sum"),
    n_cf=("cf", "nunique"),
    n_incarichi=("n_incarichi", "sum"),
).reset_index()

fig = px.bar(trend, x="anno", y="spesa", hover_data=["n_cf", "n_incarichi"],
             labels={"anno": "Anno", "spesa": "Spesa totale EUR"})
st.plotly_chart(fig, use_container_width=True)

# ── Gender gap ──────────────────────────────────────────────────────────────

st.subheader("Gender gap")
gap = df.groupby("anno").agg(
    spesa_uomini=("spesa_uomini", "sum"),
    spesa_donne=("spesa_donne", "sum"),
).reset_index()
gap["ratio_f_m"] = gap["spesa_donne"] / gap["spesa_uomini"]

fig = px.line(gap, x="anno", y="ratio_f_m", markers=True,
             labels={"anno": "Anno", "ratio_f_m": "Rapporto F/M (spesa)"})
fig.add_hline(y=1.0, line_dash="dash", line_color="gray")
st.plotly_chart(fig, use_container_width=True)

# ── Top entita per spesa ────────────────────────────────────────────────────

st.subheader(f"Top entita per spesa ({anni[-1]})")
top = df_ult.nlargest(20, "spesa_totale_eur")[
    ["denominazione", "cf", "n_incarichi", "spesa_totale_eur", "spesa_media_eur",
     "n_gratuiti", "pct_gratuiti", "ratio_f_m"]
].copy()
top["spesa_totale_eur"] = top["spesa_totale_eur"].apply(fmt_eur)
top["spesa_media_eur"] = top["spesa_media_eur"].apply(fmt_eur)
top["pct_gratuiti"] = top["pct_gratuiti"].apply(fmt_pct)
top["ratio_f_m"] = top["ratio_f_m"].apply(lambda x: f"{x:.2f}" if x == x else "-")
st.dataframe(top, use_container_width=True, hide_index=True)

# ── Enti con spesa più concentrata ──────────────────────────────────────────

st.subheader(f"Spesa concentrata su poche persone ({anni[-1]})")
conc = df_ult[df_ult["concentrazione_spesa"].notnull()].nlargest(15, "concentrazione_spesa").copy()
conc["denominazione"] = conc["cf"].map(denom_map).fillna("-")
conc = conc[["denominazione", "cf", "n_incarichi", "spesa_totale_eur", "spesa_max_eur", "concentrazione_spesa"]]
conc["spesa_totale_eur"] = conc["spesa_totale_eur"].apply(fmt_eur)
conc["spesa_max_eur"] = conc["spesa_max_eur"].apply(fmt_eur)
conc["concentrazione_spesa"] = conc["concentrazione_spesa"].apply(lambda x: f"{x:.0%}")
st.dataframe(conc, use_container_width=True, hide_index=True)
st.caption("Concentrazione = incarico piu' costoso / spesa totale. 100% = tutta la spesa e' su una persona.")

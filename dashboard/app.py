import streamlit as st
from lab_connectors.branding import apply_branding

st.set_page_config(
    page_title="Partecipate Monitor",
    page_icon="🏛️",
    layout="wide",
)

apply_branding(
    repo_name="partecipate-monitor", repo_url="https://github.com/dataciviclab/partecipate-monitor"
)

pages = {
    "": [
        st.Page("pages/01_Panoramica.py", title="Panoramica", icon="📊", default=True),
    ],
    "Analisi": [
        st.Page("pages/02_Scheda_Entita.py", title="Scheda Entita", icon="🏢"),
        st.Page("pages/03_Governance.py", title="Governance", icon="👥"),
        st.Page("pages/04_Compliance.py", title="Compliance TUSP", icon="✅"),
    ],
    "Esplora": [
        st.Page("pages/05_Confronto.py", title="Confronto", icon="⚖️"),
        st.Page("pages/06_Distribuzioni.py", title="Distribuzioni", icon="📈"),
        st.Page("pages/06_SQL.py", title="Query SQL", icon="🧪"),
    ],
}

nav = st.navigation(pages, position="sidebar")
nav.run()

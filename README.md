# partecipate-monitor — Le societa' partecipate pubbliche italiane

**Pipeline dati + dashboard Streamlit per monitorare le societa' partecipate pubbliche.**

## Fonti dati

| Fonte | Proprieta' | Anni | Uso |
|---|---|---|---|
| MEF Partecipazioni | pipeline toolkit | 2020–2023 | anagrafica + metriche |
| MEF Rappresentanti | pipeline toolkit | 2018–2023 | compensi governance |
| MEF Adempimenti | pipeline toolkit | 2020–2023 | compliance TUSP |
| ANAC Bandi Gara | GCS live | 2016–2025 | appalti banditi |
| RNA Aiuti Stato | GCS live | 2017–2026 | aiuti ricevuti |
| IPA Enti | GCS live | 2026 | anagrafica PA |

## Quickstart

```bash
# Pipeline dati (richiede [pipeline] extras)
pip install -e ".[pipeline]"
make run

# Dashboard (richiede [dashboard] extras)
pip install -e ".[dashboard]"
make dashboard
```

## Struttura

```
partecipate-monitor/
├── datasets/
│   ├── mef-partecipazioni/       ← MEF partecipazioni (anagrafica + metriche)
│   ├── mef-rappresentanti/       ← MEF rappresentanti (compensi governance)
│   └── mef-adempimenti/          ← MEF adempimenti TUSP (compliance)
├── dashboard/                    ← Streamlit (7 pagine)
│   ├── 01_Panoramica.py          ← KPI, trend, regioni, settori
│   ├── 02_Scheda_Entita.py       ← profilo unificato + ANAC/RNA live
│   ├── 03_Governance.py          ← gender gap, concentrazione spesa
│   ├── 04_Compliance.py          ← score, inadempienti, distribuzione
│   ├── 05_Confronto.py           ← side-by-side 2+ entita
│   ├── 06_Distribuzioni.py       ← histogram, scatter, box plot
│   └── 06_SQL.py                 ← query SQL diretta (lab-connectors)
├── registry/                     ← registry.json (toolkit)
├── Makefile
└── pyproject.toml
```

## Dashboard

| Pagina | Fonte | Cosa mostra |
|---|---|---|
| Panoramica | by_regione, by_settore | KPI con delta, trend 4 anni, regioni, settori |
| Scheda Entita | partecipate + GCS live | profilo unificato, trend, ANAC/RNA |
| Governance | rappresentanti | gender gap, concentrazione spesa, top entita |
| Compliance TUSP | adempimenti | score, categorie, lista inadempienti |
| Confronto | partecipate | tabella + chart confronto 2-8 entita |
| Distribuzioni | partecipate + rappresentanti | histogram, scatter, box plot |
| Query SQL | lab-connectors | SQL diretto sui clean layer |

## Licenza

MIT

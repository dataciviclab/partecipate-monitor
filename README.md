# partecipate-monitor

[![Report intelligence](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml)
[![Test rapido](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml)

Intelligence sulle **società partecipate pubbliche italiane**.

Incrocia 6 dataset (MEF Partecipazioni, MEF Rappresentanti, ANAC Bandi Gara, ANAC Aggiudicatari, RNA Aiuti di Stato, IndicePA) e produce profili strutturati per **121 partecipate a controllo pubblico** con oltre 500 addetti.

## Dashboard

→ **[https://dataciviclab.github.io/partecipate-monitor](https://dataciviclab.github.io/partecipate-monitor)**

Dashboard interattiva con grafico, filtri e ordinamento:
- **Grafico** distribuzione score esposizione (Chart.js)
- **Filtri**: ricerca testo, settore, anno
- **Ordinamento** colonne cliccando sulle intestazioni
- **Dettaglio** su click riga: occupazione, banditi/vinti, aiuti

## Dati correnti

| Indicatore | Valore |
|---|---|
| Partecipate monitorate | **121** (controllo pubblico, >500 addetti) |
| Con appalti banditi | 117 |
| Con appalti vinti | 117 |
| Con aiuti di Stato | 120 |
| Con dati governance | 99 |
| Periodo addetti | 2020–2023 |
| Periodo appalti | 2016–2025 |
| Periodo aiuti | 2018–2026 |

## Profilo (6 dimensioni)

| Dimensione | Fonte | Cosa contiene |
|---|---|---|
| **Assetto** | MEF Partecipazioni | denominazione, settore, addetti, valore produzione, risultato, patrimonio (108/121) |
| **Occupazione** | MEF Partecipazioni | 4 anni di addetti, trend percentuale |
| **Governance** | MEF Rappresentanti | compensi CdA, numero incarichi (99/121) |
| **Appalti banditi** | ANAC Bandi Gara | gare bandite per anno, importi, PNRR, urgenza |
| **Appalti vinti** | ANAC Aggiudicatari | gare vinte per anno, importi |
| **Aiuti di Stato** | RNA Aiuti | aiuti ricevuti per anno, ESL, concedente |

## Score

Il profiler calcola tre score (0-100):

| Score | Componenti |
|---|---|
| **Esposizione** | Addetti (25) + Banditi (25) + Vinti (15) + Aiuti (20) + Valore produzione (10) |
| **Performance** | Trend occupazionale + Completezza informativa + Multi-fonte |
| **Copertura** | Quante fonti su 5 hanno dati per il CF |

## Architettura

```
partecipate-monitor/
├── src/
│   ├── fetch_data.py       # Download 6 dataset da GCS
│   ├── build_fatti.py      # Tabella fatti unificata (322k righe, 8k enti)
│   ├── profiler.py         # Profilo intelligence per CF (6 dimensioni + score)
│   └── report.py           # Report JSON (121 profili)
├── reports/
│   ├── index.html          # Dashboard interattiva (Chart.js, filtri)
│   └── data.json           # Profili machine-readable
├── data/                   # Cache parquet (generati dalla CI)
├── tests/
│   └── test_profili.py     # Gold set test (7 CF, 10 verifiche)
├── Makefile                # Comandi principali
└── .github/workflows/
    ├── scan-weekly.yml     # CI settimanale: fetch → build → report → gold set
    └── test.yml            # CI su PR: smoke test profiler
```

## Utilizzo

```bash
git clone https://github.com/dataciviclab/partecipate-monitor.git
cd partecipate-monitor
pip install -e .

# Pipeline completa
make all        # fetch + build + report

# Singoli step
make fetch      # Scarica dati per 121 partecipate
make build      # Costruisce tabella fatti
make report     # Genera data.json con profili
make profile    # Profilo Poste Italiane
make clean      # Rimuove cache

# Test
pytest tests/ -v
```

## Test

```bash
pytest tests/ -v
```

Gold set test (`tests/test_profili.py`) verifica per 7 partecipate centrali:
- denominazione, addetti in range, score esposizione minimo
- presenza/assenza di appalti banditi, vinti, aiuti, governance
- dati CO.E.P. (per società non IAS)

Il test richiede la tabella fatti. Eseguire `make build` prima.

## Fonti

- **MEF Partecipazioni** — Censimento annuale partecipate pubbliche (2020–2023)
- **MEF Rappresentanti** — Compensi rappresentanti PA nei CdA (2018–2023)
- **ANAC Bandi Gara** — Gare pubbliche bandite (CIG, 2016–2025)
- **ANAC Aggiudicatari** — Gare pubbliche vinte (2016–2025)
- **RNA Aiuti di Stato** — Registro Nazionale Aiuti (MIMIT, 2018–2026)
- **IndicePA** — Anagrafe enti e siti web (AgID)

## Licenza

MIT

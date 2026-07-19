# partecipate-monitor

[![Scan settimanale](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml)
[![Test rapido](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml)

Intelligence sulle **società partecipate pubbliche italiane**.

Incrocisa 5 dataset (MEF Partecipazioni, MEF Rappresentanti, ANAC Bandi Gara, RNA Aiuti di Stato, IndicePA) e produce profili strutturati per le 26 partecipate a controllo MEF diretto.

## Dashboard

→ **[https://dataciviclab.github.io/partecipate-monitor](https://dataciviclab.github.io/partecipate-monitor)**

Classifica per score di esposizione e performance, schede dettaglio per ogni partecipata con:
- Assetto proprietario, addetti e trend occupazionale
- Compensi e incarichi dei vertici
- Appalti banditi (importi, PNRR, urgenza)
- Aiuti di Stato ricevuti

## Dati correnti

| Indicatore | Valore |
|---|---|
| Partecipate monitorate | **26** (controllo MEF diretto) |
| Con appalti ANAC | 23 |
| Con aiuti di Stato | 25 |
| Con dati governance | 26 |
| Periodo addetti | 2020–2023 |
| Periodo appalti | 2016–2025 |
| Periodo aiuti | 2018–2026 |

## Architettura

```
partecipate-monitor/
├── src/
│   ├── fetch_data.py          # Download 5 dataset da GCS (MEF, IPA, ANAC, RNA, Rappr.)
│   ├── build_fatti.py         # Tabella fatti unificata (154k righe, 8.060 enti)
│   ├── profiler.py            # Profilo intelligence per CF (5 dimensioni + score)
│   └── report.py              # Report JSON
├── reports/
│   ├── index.html             # Dashboard statica (JS puro)
│   └── data.json              # Profili machine-readable
├── data/                      # Cache parquet (generati dalla CI)
└── .github/workflows/
    ├── scan-weekly.yml         # CI settimanale
    └── test.yml               # Test su PR
```

## Utilizzo

```bash
git clone https://github.com/dataciviclab/partecipate-monitor.git
cd partecipate-monitor
pip install -e .

# Pipeline completa
python src/fetch_data.py --centrali   # Scarica dati per le 26 partecipate
python src/build_fatti.py             # Costruisce tabella fatti
python src/report.py --profili        # Genera data.json con profili

# Profilo singola partecipata
python src/profiler.py 97103880585    # Poste Italiane
```

## Fonti

- **MEF Partecipazioni** — Censimento annuale partecipate pubbliche (2020–2023)
- **MEF Rappresentanti** — Compensi rappresentanti PA nei CdA (2018–2023)
- **ANAC Bandi Gara** — Gare pubbliche bandite (CIG, 2016–2025)
- **RNA Aiuti di Stato** — Registro Nazionale Aiuti (MIMIT, 2018–2026)
- **IndicePA** — Anagrafe enti e siti web (AgID)

## Licenza

MIT

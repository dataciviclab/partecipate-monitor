# partecipate-monitor

[![Scan settimanale](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml)
[![Test rapido](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml)

Intelligence sulle **società partecipate pubbliche italiane**.

Incrocia 5 dataset (MEF Partecipazioni, MEF Rappresentanti, ANAC Bandi Gara, RNA Aiuti di Stato, IndicePA) e produce profili strutturati per le 26 partecipate a controllo MEF diretto.

> **Nota**: il monitoraggio della trasparenza dei siti web (ex scanner) è stato dismesso.
> I dati storici (89% siti con sezione AT, 84,9% file in PDF, 7,5% formato aperto)
> sono ancora disponibili nei commit precedenti del repository.

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

### Makefile
```bash
make fetch      # Scarica dati per le 26 partecipate
make build      # Costruisce tabella fatti unificata
make report     # Genera data.json con profili
make profile    # Profilo Poste Italiane
make all        # fetch + build + report
make clean      # Rimuove cache e output
```

### Manuale
```bash
pip install -e .
python src/fetch_data.py --centrali
python src/build_fatti.py
python src/report.py --profili
python src/profiler.py 97103880585    # Poste Italiane
```

## Test

```bash
pytest tests/ -v
```

Gold set test (`tests/test_profili.py`) verifica per 6 partecipate centrali:
- denominazione, addetti in range, score esposizione minimo
- presenza/assenza di appalti, aiuti, governance
- dati CO.E.P. (per società non IAS)

## Score intelligence

Il profiler calcola tre score (0-100):

| Score | Componenti | Peso |
|---|---|---|
| **Esposizione** | Addetti + Appalti banditi + Aiuti ricevuti + Valore produzione | 100 |
| **Performance** | Trend occupazionale + Completezza informativa + Multi-fonte | 100 |
| **Copertura** | Quante fonti su 5 hanno dati per il CF | 100 |

## Fonti

- **MEF Partecipazioni** — Censimento annuale partecipate pubbliche (2020–2023)
- **MEF Rappresentanti** — Compensi rappresentanti PA nei CdA (2018–2023)
- **ANAC Bandi Gara** — Gare pubbliche bandite (CIG, 2016–2025)
- **RNA Aiuti di Stato** — Registro Nazionale Aiuti (MIMIT, 2018–2026)
- **IndicePA** — Anagrafe enti e siti web (AgID)

## Licenza

MIT

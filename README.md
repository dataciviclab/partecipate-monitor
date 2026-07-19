# partecipate-monitor

[![Scan settimanale](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml)
[![Test rapido](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml)

Intelligence sulle **società partecipate pubbliche italiane** — dalla trasparenza dei siti web ai profili multi-fonte (MEF, ANAC, RNA).

## Cosa fa

Il monitoraggio unisce **due piani**:

**1. Scanner trasparenza** — ogni settimana scansiona ~975 siti di partecipate in controllo pubblico per verificare:
- Hanno la sezione "Amministrazione Trasparente" / "Società Trasparente"?
- Quali categorie pubblicano (bilanci, personale, bandi, ecc.)?
- In quali formati (PDF, CSV, XML...)?

**2. Intelligence partecipate centrali** — per le 26 partecipate MEF (controllo pubblico diretto), incrocia 5 dataset:
- **MEF Partecipazioni** — addetti, settore, forma giuridica, assetto proprietario
- **MEF Rappresentanti** — compensi, incarichi dei vertici
- **ANAC Bandi Gara** — appalti banditi (importi, PNRR, urgenza)
- **RNA Aiuti di Stato** — contributi pubblici ricevuti
- **IndicePA** — sito web e contatti

## Dashboard

→ **[https://dataciviclab.github.io/partecipate-monitor](https://dataciviclab.github.io/partecipate-monitor)**

Classifica per score di esposizione, schede dettaglio per ogni partecipata, trend occupazionali, appalti e aiuti di Stato.

## Dati correnti

| Indicatore | Valore |
|---|---|
| Partecipate centrali monitorate | **26** |
| Di cui con appalti ANAC | 23 |
| Di cui con aiuti di Stato | 25 |
| Di cui con dati governance | 26 |
| Siti trasparenza scansionati | ~975 |
| Con sezione trasparenza | ~89% |

## Architettura

```
partecipate-monitor/
├── src/
│   ├── fetch_data.py          # Download 5 dataset da GCS (MEF, IPA, ANAC, RNA, Rappr.)
│   ├── build_fatti.py         # Tabella fatti unificata (154k righe, 8.060 enti)
│   ├── profiler.py            # Profilo intelligence per CF (5 dimensioni + score)
│   ├── scanner.py             # Scanner sezione trasparenza (5 stadi)
│   ├── catalogo.py            # 13 categorie ANAC
│   ├── formati.py             # Deep scan formati
│   └── report.py              # Report JSON (usa data.json + profili)
├── reports/
│   ├── index.html             # Dashboard statica (JS puro, zero dipendenze)
│   └── data.json              # Tutti i profili machine-readable
├── data/                      # Cache e output (generati dalla CI)
├── scripts/                   # Automazione
└── .github/workflows/         # CI settimanale
```

## Utilizzo

```bash
git clone https://github.com/dataciviclab/partecipate-monitor.git
cd partecipate-monitor
pip install -e .

# Pipeline completa (scanner + intelligence)
python src/fetch_data.py                # MEF + IPA (per scanner)
python src/scanner.py --solo-controllo
python src/catalogo.py
python src/formati.py
python src/fetch_data.py --centrali     # ANAC + RNA + Rappr. (per intelligence)
python src/build_fatti.py               # Tabella fatti
python src/report.py --profili          # JSON con profili
```

Singoli moduli:

```bash
# Profilo di una partecipata per CF
python -m src.profiler 97103880585       # Poste Italiane

# Solo scanner trasparenza
python src/fetch_data.py
python src/scanner.py --solo-controllo
python src/report.py
```

## Licenza

MIT

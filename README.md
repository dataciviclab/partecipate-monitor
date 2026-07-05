# partecipate-monitor

Monitoraggio automatico della trasparenza delle **società partecipate pubbliche italiane**.

Ogni settimana verifica:
1. **Quante** hanno la sezione "Società Trasparente" / "Amministrazione Trasparente"
2. **Quali categorie** pubblicano (bilanci, personale, bandi, ecc.)
3. **In quali formati** pubblicano i dati (PDF, XLSX, CSV, XML...)

## Dati

- **Fonte partecipate**: MEF — Censimento annuale delle partecipazioni pubbliche (`mef_partecipazioni`)
- **Fonte siti web**: IndicePA — AgID (`ipa_enti`)
- **Universo**: ~2.500 società partecipate con sito web in IPA
- **Focus**: ~975 società in **controllo pubblico** (obblighi pieni D.Lgs 33/2013)

## Report

Il report aggiornato è pubblicato su **GitHub Pages**:
→ [https://dataciviclab.github.io/partecipate-monitor](https://dataciviclab.github.io/partecipate-monitor)

## Utilizzo

```bash
# Clona
git clone https://github.com/dataciviclab/partecipate-monitor.git
cd partecipate-monitor

# Installa dipendenze
pip install httpx duckdb pandas

# Esegui l'intera pipeline
bash scripts/run_all.sh
```

Singoli step:
```bash
python src/fetch_data.py              # Scarica MEF + IPA da GCS
python src/scanner.py --solo-controllo # Scan sezione trasparenza
python src/catalogo.py                 # Estrai categorie pubblicate
python src/formati.py                  # Analisi formati file
python src/report.py                   # Genera report markdown + JSON
```

## Struttura

```
partecipate-monitor/
├── src/              # Moduli Python
│   ├── fetch_data.py # Caricamento dati (MEF + IPA)
│   ├── scanner.py    # Verifica sezione trasparenza
│   ├── catalogo.py   # Estrazione categorie ANAC
│   ├── formati.py    # Analisi formati file
│   └── report.py     # Generazione report
├── data/             # Snapshot dei risultati
│   ├── scanner_report.json
│   ├── catalogo.csv
│   ├── formati_report.json
│   └── history/      # Serie storica
├── reports/          # Report per GitHub Pages
├── scripts/          # Script di automazione
└── .github/workflows/ # CI: scan settimanale + deploy pages
```

## Licenza

MIT

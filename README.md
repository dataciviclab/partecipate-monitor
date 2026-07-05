# partecipate-monitor

[![Scan settimanale](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/scan-weekly.yml)
[![Test rapido](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml/badge.svg)](https://github.com/dataciviclab/partecipate-monitor/actions/workflows/test.yml)

Monitoraggio automatico della trasparenza delle **società partecipate pubbliche italiane**.

Ogni settimana verifica:
1. **Quante** hanno la sezione "Società Trasparente" / "Amministrazione Trasparente"
2. **Quali categorie** pubblicano (bilanci, personale, bandi, ecc.)
3. **In quali formati** pubblicano i dati (PDF, XLSX, CSV, XML...)

## Risultati correnti

| Indicatore | Valore |
|---|---|
| Siti scansionati | 975 |
| Con sezione trasparenza | **875 (89,7%)** |
| File trovati | **44.575** (deep scan) |
| Siti con formato aperto | **50** |
| PDF | 84,9% |
| XML | 0,7% |

## Dati

- **Fonte partecipate**: MEF — Censimento annuale (`mef_partecipazioni`)
- **Fonte siti web**: IndicePA — AgID (`ipa_enti`)
- **Universo**: ~2.500 società partecipate con sito web in IPA
- **Focus**: ~975 società in **controllo pubblico** (obblighi D.Lgs 33/2013)

## Report

Il report aggiornato è pubblicato su **GitHub Pages**:
→ [https://dataciviclab.github.io/partecipate-monitor](https://dataciviclab.github.io/partecipate-monitor)

## Utilizzo

```bash
git clone https://github.com/dataciviclab/partecipate-monitor.git
cd partecipate-monitor
pip install httpx duckdb pandas

# Esegui l'intera pipeline
bash scripts/run_all.sh
```

Singoli step:
```bash
python src/fetch_data.py              # Scarica MEF + IPA da GCS
python src/scanner.py --solo-controllo # Scan sezione trasparenza
python src/catalogo.py                 # Estrai categorie pubblicate
python src/formati.py                  # Deep scan formati (sotto-pagine)
python src/report.py                   # Genera report HTML + JSON
```

## Struttura

```
partecipate-monitor/
├── src/              # Moduli Python
│   ├── fetch_data.py # Caricamento dati (MEF + IPA)
│   ├── scanner.py    # Scanner v2 (combinatorio + SaaS + timeout adattivo)
│   ├── catalogo.py   # Estrazione 13 categorie ANAC
│   ├── formati.py    # Deep scan formati (pagina + sotto-sezioni)
│   └── report.py     # Report HTML + trend storico
├── data/             # Snapshot e storico
│   └── history/      # Serie storica scan precedenti
├── reports/          # GitHub Pages
├── scripts/          # Automazione
└── .github/workflows/ # CI
```

## Architettura scanner

```
1. Homepage → cerca link "trasparen" (href + testo)
2. Sitemap.xml → cerca URL "trasparen"
3. Path combinatori → 18 pattern in parallelo
4. Known patterns → pattern da check manuali
5. SaaS probe → 4 piattaforme (portaletrasparenza.net, ecc.)
   Timeout adattivo: 3s primo giro, 8s sui timeout
```

## Licenza

MIT

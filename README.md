# partecipate-monitor — Le società partecipate pubbliche italiane

**Chi possiede cosa? 121 grandi partecipate pubbliche monitorate, 6 fonti incrociate, 3 dimensioni di analisi.**

Le società partecipate pubbliche italiane muovono miliardi di euro. Questo progetto
le monitora incrociando 6 dataset pubblici: MEF Partecipazioni, MEF Rappresentanti,
ANAC Bandi Gara, ANAC Aggiudicatari, RNA Aiuti di Stato e IndicePA.

## Cosa contiene

| Indicatore | Valore |
|---|---|
| Partecipate monitorate | **121** (controllo pubblico, >500 addetti) |
| Con appalti banditi | 117 |
| Con appalti vinti | 117 |
| Con aiuti di Stato | 120 |
| Periodo addetti | 2020–2023 |
| Periodo appalti | 2016–2025 |

### Dashboard interattiva

→ **[https://dataciviclab.github.io/partecipate-monitor](https://dataciviclab.github.io/partecipate-monitor)**

## Esempi di domande

- **Quali partecipate ricevono più aiuti di Stato?** E quali bandiscono più appalti?
- **Come cambiano i compensi dei CdA tra società?**
- **Quali settori hanno la maggiore esposizione economica?**
- **C'è relazione tra appalti vinti e aiuti ricevuti?**
- **Quali partecipate hanno la governance più trasparente?**

## Tre modi per accedere ai dati

### 1. Via dashboard live

La [dashboard interattiva](https://dataciviclab.github.io/partecipate-monitor) permette
di esplorare i profili con filtri, grafici e ordinamenti.

### 2. Via DuckDB diretto

```python
import duckdb
duckdb.sql("""
    SELECT denominazione, settore, addetti, score_esposizione
    FROM read_parquet('data/fatti.parquet')
    ORDER BY score_esposizione DESC
    LIMIT 20
""").show()
```

### 3. Via report JSON

I profili machine-readable sono in `reports/data.json`.

## Profilo (6 dimensioni)

| Dimensione | Fonte | Cosa contiene |
|---|---|---|
| **Assetto** | MEF Partecipazioni | denominazione, settore, addetti, valore produzione |
| **Occupazione** | MEF Partecipazioni | 4 anni di trend addetti |
| **Governance** | MEF Rappresentanti | compensi CdA, numero incarichi |
| **Appalti banditi** | ANAC Bandi Gara | gare per anno, importi, PNRR |
| **Appalti vinti** | ANAC Aggiudicatari | gare vinte per anno, importi |
| **Aiuti di Stato** | RNA Aiuti | aiuti ricevuti, ESL, concedente |

Il profiler calcola tre score (0-100): **Esposizione**, **Performance**, **Copertura**.

## Partecipa

- **Hai una domanda su questi dati?** Apri una [Discussion](https://github.com/orgs/dataciviclab/discussions/new?category=Domanda)
- **Vuoi contribuire?** Vedi [come contribuire al Lab](https://github.com/dataciviclab/dataciviclab/blob/main/docs/come-contribuire.md)

## Architettura

```
partecipate-monitor/
├── src/           ← fetch, build, profiler, report
├── reports/       ← dashboard HTML + JSON profili
├── tests/         ← gold set (7 CF, 10 verifiche)
├── Makefile
└── .github/workflows/  ← CI settimanale
```

**CI settimanale**: fetch dati → build fatti → report → gold set test → deploy dashboard.

## Licenza

MIT

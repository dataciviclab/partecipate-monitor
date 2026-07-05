"""
report.py — Genera report markdown + JSON per GitHub Pages.
Legge gli output di scanner + catalogo + formati e produce report/index.md.
"""

import json, csv, sys
from datetime import datetime
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

FILES = {
    "scanner": DATA_DIR / "scanner_report.json",
    "catalogo": DATA_DIR / "catalogo.csv",
    "formati": DATA_DIR / "formati_report.json",
}


def carica_dati():
    dati = {}
    if FILES["scanner"].exists():
        with open(FILES["scanner"]) as f:
            dati["scanner"] = json.load(f)
    if FILES["formati"].exists():
        with open(FILES["formati"]) as f:
            dati["formati"] = json.load(f)

    if FILES["catalogo"].exists():
        csv.field_size_limit(10 * 1024 * 1024)
        with open(FILES["catalogo"]) as f:
            rows = list(csv.DictReader(f))
        dati["catalogo_count"] = len(rows)
        raggiungibili = [r for r in rows if r.get("raggiungibile", "").upper() == "TRUE"]
        if raggiungibili:
            score = [float(r.get("score", 0) or 0) for r in raggiungibili]
            dati["score_medio"] = round(sum(score) / len(score), 1)
            dati["score_max"] = max(score)
            dati["score_min"] = min(score)
            # Distribuzione
            bins = {f"{i*10}-{(i+1)*10-1 if i<9 else 100}": 0 for i in range(10)}
            for s in score:
                idx = min(int(s // 10), 9)
                key = f"{idx*10}-{min((idx+1)*10-1, 100)}"
                bins[key] = bins.get(key, 0) + 1
            dati["distribuzione"] = bins
            # Per categoria
            cat_list = ["disposizioni_generali", "organizzazione", "consulenti",
                         "personale", "bandi_contratti", "sovvenzioni", "bilanci",
                         "beni_immobili", "controlli", "pagamenti", "accesso_civico"]
            cat_stat = {}
            for c in cat_list:
                n = sum(1 for r in raggiungibili if r.get(c, "") == "SI")
                cat_stat[c] = round(100 * n / len(raggiungibili), 1)
            dati["categorie"] = cat_stat

    return dati


def genera_markdown(dati):
    s = dati.get("scanner", {})
    f = dati.get("formati", {})

    md = []
    md.append("# Osservatorio Partecipate Pubbliche\n")
    md.append(f"_Report generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}_\n")

    # Scanner
    if s:
        tot = s.get("totale_siti", 0)
        trovati = s.get("sezione_trovata", 0)
        perc = s.get("percentuale", 0)
        md.append("## Sezione Trasparenza\n")
        md.append(f"| Indicatore | Valore |")
        md.append(f"|------------|-------:|")
        md.append(f"| Siti scansionati | {tot} |")
        md.append(f"| Con sezione trasparenza | **{trovati}** ({perc}%) |")
        md.append(f"| Senza sezione | {tot - trovati} |")

        cp = s.get("controllo_pubblico", {})
        sp = s.get("solo_partecipata", {})
        if cp:
            md.append(f"| Controllo pubblico: trovata | {cp.get('trovata',0)}/{cp.get('totale',0)} |")
        if sp:
            md.append(f"| Solo partecipate: trovata | {sp.get('trovata',0)}/{sp.get('totale',0)} |")
        md.append("")

    # Formati
    if f:
        md.append("## Formati di Pubblicazione\n")
        md.append(f"| Formato | File | % |")
        md.append(f"|---------|----:|---:|")
        for fmt, count in f.get("formati", {}).items():
            perc = round(100 * count / f["totale_file_trovati"], 1) if f["totale_file_trovati"] else 0
            md.append(f"| `.{fmt}` | {count} | {perc}% |")
        md.append("")
        md.append(f"- Siti con formato aperto (CSV/XML/JSON): **{f.get('siti_con_formato_aperto', 0)}**")
        md.append(f"- Siti con solo PDF: **{f.get('siti_solo_pdf', 0)}**")
        md.append("")

    # Catalogo
    if "categorie" in dati:
        md.append("## Categorie Pubblicate\n")
        md.append(f"_Score medio: **{dati.get('score_medio', 0)}%**_\n")
        md.append("| Categoria | % presenza |")
        md.append("|-----------|----------:|")
        for cat, pct in sorted(dati["categorie"].items(), key=lambda x: -x[1]):
            md.append(f"| {cat.replace('_', ' ')} | {pct}% |")
        md.append("")

    # Conclusione
    md.append("---")
    md.append("_Dati aggiornati settimanalmente. Codice: [github.com/dataciviclab/partecipate-monitor](https://github.com/dataciviclab/partecipate-monitor)_\n")

    return "\n".join(md)


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    dati = carica_dati()
    markdown = genera_markdown(dati)

    with open(REPORTS_DIR / "index.md", "w") as f:
        f.write(markdown)

    # JSON machine-readable
    with open(REPORTS_DIR / "data.json", "w") as f:
        json.dump(dati, f, indent=2, ensure_ascii=False)

    print(f"[report] Generato: reports/index.md")
    print(f"[report] Generato: reports/data.json")


if __name__ == "__main__":
    main()

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


def genera_html(dati):
    s = dati.get("scanner", {})
    f = dati.get("formati", {})

    h = []
    h.append("""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Osservatorio Partecipate Pubbliche</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }
  h1 { color: #2c3e50; border-bottom: 2px solid #27ae60; padding-bottom: 8px; }
  h2 { color: #2c3e50; margin-top: 30px; }
  table { border-collapse: collapse; width: 100%; margin: 15px 0; }
  th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
  th { background: #f5f5f5; font-weight: 600; }
  td:last-child { text-align: right; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 0.9em; }
  .badge-green { background: #27ae60; color: white; }
  .badge-red { background: #e74c3c; color: white; }
  .badge-gray { background: #95a5a6; color: white; }
  .summary { display: flex; gap: 15px; flex-wrap: wrap; margin: 20px 0; }
  .card { flex: 1; min-width: 150px; padding: 15px; border-radius: 8px; text-align: center; }
  .card h3 { margin: 0 0 5px 0; font-size: 0.9em; }
  .card .num { font-size: 1.8em; font-weight: bold; }
  .card-green { background: #e8f8f0; border: 1px solid #27ae60; }
  .card-red { background: #fdecea; border: 1px solid #e74c3c; }
  .card-gray { background: #f5f5f5; border: 1px solid #95a5a6; }
  .footer { margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd; font-size: 0.85em; color: #666; }
</style>
</head>
<body>
""")

    h.append(f"<h1>Osservatorio Partecipate Pubbliche</h1>")
    h.append(f"<p><em>Report generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}</em></p>")

    # Scanner
    if s:
        tot = s.get("totale_siti", 0)
        trovati = s.get("sezione_trovata", 0)
        perc_trovati = s.get("percentuale", 0)
        non_trovati = tot - trovati

        h.append(f"""
<div class="summary">
  <div class="card card-green">
    <h3>Con sezione trasparenza</h3>
    <div class="num">{trovati}</div>
    <div>{perc_trovati}% del totale</div>
  </div>
  <div class="card card-red">
    <h3>Senza sezione</h3>
    <div class="num">{non_trovati}</div>
    <div>{100-perc_trovati:.1f}% del totale</div>
  </div>
  <div class="card card-gray">
    <h3>Siti scansionati</h3>
    <div class="num">{tot}</div>
    <div>controllo pubblico</div>
  </div>
</div>
""")

        h.append("<h2>Sezione Trasparenza</h2>")
        h.append("<table><tr><th>Indicatore</th><th>Valore</th></tr>")
        h.append(f"<tr><td>Siti scansionati</td><td>{tot}</td></tr>")
        h.append(f"<tr><td>Con sezione trasparenza</td><td><span class='badge badge-green'>{trovati}</span> ({perc_trovati}%)</td></tr>")
        h.append(f"<tr><td>Senza sezione</td><td><span class='badge badge-red'>{non_trovati}</span> ({100-perc_trovati:.1f}%)</td></tr>")

        cp = s.get("controllo_pubblico", {})
        if cp:
            h.append(f"<tr><td>Controllo pubblico: trovata</td><td>{cp.get('trovata',0)}/{cp.get('totale',0)}</td></tr>")
        h.append("</table>")

    # Formati
    if f:
        h.append("<h2>Formati di Pubblicazione</h2>")
        h.append(f"<p>Siti con formato aperto (CSV/XML/JSON/ODS): <strong>{f.get('siti_con_formato_aperto', 0)}</strong> su {f.get('totale_siti_analizzati', 0)}</p>")
        h.append("<table><tr><th>Formato</th><th>File</th><th>%</th></tr>")
        for fmt, count in f.get("formati", {}).items():
            pct = round(100 * count / f["totale_file_trovati"], 1) if f["totale_file_trovati"] else 0
            h.append(f"<tr><td><code>.{fmt}</code></td><td>{count}</td><td>{pct}%</td></tr>")
        h.append("</table>")
        h.append(f"<p>Siti solo PDF: <strong>{f.get('siti_solo_pdf', 0)}</strong></p>")

    # Catalogo
    if "categorie" in dati:
        h.append(f"<h2>Categorie Pubblicate</h2>")
        h.append(f"<p>Score medio: <strong>{dati.get('score_medio', 0)}%</strong></p>")
        h.append("<table><tr><th>Categoria</th><th>% presenza</th></tr>")
        for cat, pct in sorted(dati["categorie"].items(), key=lambda x: -x[1]):
            label = cat.replace('_', ' ').title()
            bar = '█' * int(pct / 5)
            h.append(f"<tr><td>{label}</td><td>{bar} {pct}%</td></tr>")
        h.append("</table>")

    h.append("""
<div class="footer">
<p>Dati aggiornati settimanalmente.</p>
<p><a href="https://github.com/dataciviclab/partecipate-monitor">github.com/dataciviclab/partecipate-monitor</a></p>
</div>
</body>
</html>
""")

    return "\n".join(h)


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    dati = carica_dati()
    html = genera_html(dati)

    with open(REPORTS_DIR / "index.html", "w") as f:
        f.write(html)

    # JSON machine-readable
    with open(REPORTS_DIR / "data.json", "w") as f:
        json.dump(dati, f, indent=2, ensure_ascii=False)

    print(f"[report] Generato: reports/index.html")
    print(f"[report] Generato: reports/data.json")


if __name__ == "__main__":
    main()

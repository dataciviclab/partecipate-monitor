"""
report.py — Genera dashboard aggregata + schede intelligence individuali.

Supporta due modalità:
  report.py              → solo dashboard classica (scanner + catalogo + formati)
  report.py --profili    → dashboard + profili intelligence per partecipate centrali
"""

import json, csv, sys, os
from datetime import datetime
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
SCHEDE_DIR = REPORTS_DIR / "schede"

FILES = {
    "scanner": DATA_DIR / "scanner_report.json",
    "catalogo": DATA_DIR / "catalogo.csv",
    "formati": DATA_DIR / "formati_report.json",
}


# ── Dashboard classica (immutata) ──────────────────────────────

def carica_trend():
    trend = []
    HISTORY_DIR = DATA_DIR / "history"
    if not HISTORY_DIR.exists():
        return trend
    dates = sorted([d for d in HISTORY_DIR.iterdir() if d.is_dir() and d.name[:4].isdigit()])
    for d in dates:
        snap_file = d / "scanner_report.json"
        if snap_file.exists():
            with open(snap_file) as f:
                snap = json.load(f)
            trend.append({
                "data": d.name,
                "totale_siti": snap.get("totale_siti", 0),
                "sezione_trovata": snap.get("sezione_trovata", 0),
                "percentuale": snap.get("percentuale", 0),
            })
    return trend


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
            bins = {f"{i*10}-{(i+1)*10-1 if i<9 else 100}": 0 for i in range(10)}
            for s in score:
                idx = min(int(s // 10), 9)
                key = f"{idx*10}-{min((idx+1)*10-1, 100)}"
                bins[key] = bins.get(key, 0) + 1
            dati["distribuzione"] = bins
            cat_list = ["disposizioni_generali", "organizzazione", "consulenti",
                         "personale", "bandi_contratti", "sovvenzioni", "bilanci",
                         "beni_immobili", "controlli", "pagamenti", "accesso_civico"]
            cat_stat = {}
            for c in cat_list:
                n = sum(1 for r in raggiungibili if r.get(c, "") == "SI")
                cat_stat[c] = round(100 * n / len(raggiungibili), 1)
            dati["categorie"] = cat_stat

    dati["trend"] = carica_trend()
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
  .score { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
  .score-alto { background: #27ae60; color: white; }
  .score-medio { background: #f39c12; color: white; }
  .score-basso { background: #e74c3c; color: white; }
</style>
</head>
<body>
""")

    h.append(f"<h1>Osservatorio Partecipate Pubbliche</h1>")
    h.append(f"<p><em>Report generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}</em></p>")

    if s:
        tot = s.get("totale_siti", 0)
        trovati = s.get("sezione_trovata", 0)
        perc_trovati = s.get("percentuale", 0)
        non_trovati = tot - trovati
        h.append(f"""
<div class="summary">
  <div class="card card-green"><h3>Con sezione trasparenza</h3><div class="num">{trovati}</div><div>{perc_trovati}% del totale</div></div>
  <div class="card card-red"><h3>Senza sezione</h3><div class="num">{non_trovati}</div><div>{100-perc_trovati:.1f}% del totale</div></div>
  <div class="card card-gray"><h3>Siti scansionati</h3><div class="num">{tot}</div><div>controllo pubblico</div></div>
</div>""")

    # Se ci sono profili, mostra la classifica
    if "profili" in dati and dati["profili"]:
        h.append("<h2>Partecipate Centrali — Score Intelligence</h2>")
        h.append("<table><tr><th>Società</th><th>Esposizione</th><th>Performance</th><th>Scheda</th></tr>")
        for p in sorted(dati["profili"], key=lambda x: x.get("score", {}).get("esposizione", 0), reverse=True):
            nome = p.get("denominazione", "?")
            slug = nome.lower().replace(" ", "-").replace("'", "")[:30]
            sc = p.get("score", {})
            esp = sc.get("esposizione", 0)
            perf = sc.get("performance", 0)
            badge_esp = "score-alto" if esp >= 70 else ("score-medio" if esp >= 40 else "score-basso")
            badge_perf = "score-alto" if perf >= 70 else ("score-medio" if perf >= 40 else "score-basso")
            link = f"<a href='schede/{slug}.html'>scheda</a>"
            h.append(f"<tr><td>{nome}</td><td><span class='score {badge_esp}'>{esp}</span></td><td><span class='score {badge_perf}'>{perf}</span></td><td>{link}</td></tr>")
        h.append("</table>")

    # Scanner dettaglio
    if s:
        h.append("<h2>Sezione Trasparenza</h2>")
        h.append("<table><tr><th>Indicatore</th><th>Valore</th></tr>")
        h.append(f"<tr><td>Siti scansionati</td><td>{tot}</td></tr>")
        h.append(f"<tr><td>Con sezione trasparenza</td><td><span class='badge badge-green'>{trovati}</span> ({perc_trovati}%)</td></tr>")
        h.append(f"<tr><td>Senza sezione</td><td><span class='badge badge-red'>{non_trovati}</span> ({100-perc_trovati:.1f}%)</td></tr>")
        cp = s.get("controllo_pubblico", {})
        if cp:
            h.append(f"<tr><td>Controllo pubblico: trovata</td><td>{cp.get('trovata',0)}/{cp.get('totale',0)}</td></tr>")
        h.append("</table>")

    # Formati (invariato)
    if f:
        h.append("<h2>Formati di Pubblicazione</h2>")
        h.append(f"<p>Siti con formato aperto (CSV/XML/JSON/ODS): <strong>{f.get('siti_con_formato_aperto', 0)}</strong> su {f.get('totale_siti_analizzati', 0)}</p>")
        h.append("<table><tr><th>Formato</th><th>File</th><th>%</th></tr>")
        for fmt, count in f.get("formati", {}).items():
            pct = round(100 * count / f["totale_file_trovati"], 1) if f["totale_file_trovati"] else 0
            h.append(f"<tr><td><code>.{fmt}</code></td><td>{count}</td><td>{pct}%</td></tr>")
        h.append("</table>")
        h.append(f"<p>Siti solo PDF: <strong>{f.get('siti_solo_pdf', 0)}</strong></p>")

    if "categorie" in dati:
        h.append("<h2>Categorie Pubblicate</h2>")
        h.append(f"<p>Score medio: <strong>{dati.get('score_medio', 0)}%</strong></p>")
        h.append("<table><tr><th>Categoria</th><th>% presenza</th></tr>")
        for cat, pct in sorted(dati["categorie"].items(), key=lambda x: -x[1]):
            label = cat.replace('_', ' ').title()
            bar = '█' * int(pct / 5)
            h.append(f"<tr><td>{label}</td><td>{bar} {pct}%</td></tr>")
        h.append("</table>")

    trend = dati.get("trend", [])
    if len(trend) >= 2:
        h.append("<h2>Trend Storico</h2>")
        h.append("<table><tr><th>Data</th><th>Trovati</th><th>%</th></tr>")
        for t in trend:
            h.append(f"<tr><td>{t['data']}</td><td>{t['sezione_trovata']}/{t['totale_siti']}</td><td>{t['percentuale']}%</td></tr>")
        h.append("</table>")
        first, last = trend[0], trend[-1]
        delta = round(last['percentuale'] - first['percentuale'], 1)
        icon = "📈" if delta > 0 else "📉"
        h.append(f"<p>{icon} Dall'inizio: <strong>{delta:+.1f}%</strong></p>")

    h.append("""
<div class="footer">
<p>Dati aggiornati settimanalmente.</p>
<p><a href="https://github.com/dataciviclab/partecipate-monitor">github.com/dataciviclab/partecipate-monitor</a></p>
</div>
</body>
</html>""")

    return "\n".join(h)


# ── Schede intelligence individuali ────────────────────────────

def _fmt_euro(val):
    """Formatta un importo in euro leggibile."""
    if val is None or val == 0:
        return "—"
    if abs(val) >= 1e9:
        return f"€{val/1e9:.1f} Mld"
    if abs(val) >= 1e6:
        return f"€{val/1e6:.1f} M"
    return f"€{val:,.0f}"


def genera_scheda_html(profilo):
    """HTML per la scheda intelligence di una partecipata."""
    a = profilo.get("assetto", {})
    o = profilo.get("occupazione", {})
    g = profilo.get("governance", {})
    ap = profilo.get("appalti", {})
    ai = profilo.get("aiuti_stato", {})
    sc = profilo.get("score", {})
    nome = profilo.get("denominazione", "?")

    h = []
    h.append(f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{nome} — Scheda Intelligence</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #333; }}
  h1 {{ color: #2c3e50; border-bottom: 2px solid #2980b9; padding-bottom: 8px; }}
  h2 {{ color: #2c3e50; margin-top: 25px; font-size: 1.2em; border-left: 3px solid #2980b9; padding-left: 10px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 0.9em; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  td:last-child {{ text-align: right; }}
  .card {{ display: inline-block; padding: 10px 15px; border-radius: 6px; margin: 5px; text-align: center; min-width: 120px; }}
  .card .num {{ font-size: 1.4em; font-weight: bold; }}
  .card .label {{ font-size: 0.75em; color: #666; }}
  .score-alto {{ background: #27ae60; color: white; }}
  .score-medio {{ background: #f39c12; color: white; }}
  .score-basso {{ background: #e74c3c; color: white; }}
  .score-nero {{ background: #34495e; color: white; }}
  .footer {{ margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd; font-size: 0.85em; color: #666; }}
  .highlight {{ background: #fff3cd; }}
  .grid {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 15px 0; }}
</style>
</head>
<body>
""")

    h.append(f"<h1>{nome}</h1>")
    h.append(f"<p><strong>CF:</strong> {profilo.get('cf', '')}")

    # Badge score
    for key, label in [("esposizione", "Esposizione"), ("performance", "Performance")]:
        val = sc.get(key, 0)
        css = "score-alto" if val >= 70 else ("score-medio" if val >= 40 else "score-basso")
        h.append(f" <span class='card {css}'><span class='num'>{val}</span><br><span class='label'>{label}</span></span>")

    h.append("</p>")

    # Assetto
    if a and "errore" not in a:
        h.append("<h2>Assetto Proprietario</h2>")
        h.append("<table>")
        for k, v in [("Ente partecipante", a.get("ente_partecipante")),
                      ("Forma giuridica", a.get("forma_giuridica")),
                      ("Settore", a.get("settore")),
                      ("Divisione ATECO", a.get("divisione_ateco")),
                      ("Anno costituzione", a.get("anno_costituzione")),
                      ("Stato", a.get("stato")),
                      ("Controllo", a.get("tipo_controllo")),
                      ("Quotata", "✅ SI" if a.get("quotata") else "❌ NO"),
                      ("Servizi affidati da PA", a.get("servizi_affidati", "—"))]:
            h.append(f"<tr><td>{k}</td><td>{v or '—'}</td></tr>")
        h.append("</table>")

    # Occupazione
    if o and "addetti_per_anno" in o:
        h.append("<h2>Occupazione</h2>")
        h.append("<table><tr><th>Anno</th><th>Addetti</th></tr>")
        for anno, add in sorted(o["addetti_per_anno"].items()):
            h.append(f"<tr><td>{anno}</td><td>{add:,}</td></tr>")
        h.append(f"<tr class='highlight'><td><strong>Trend</strong></td><td><strong>{o.get('trend_percentuale', 0):+.1f}%</strong></td></tr>")
        h.append("</table>")

    # Governance
    if g:
        h.append("<h2>Governance e Compensi (2023)</h2>")
        h.append("<table>")
        h.append(f"<tr><td>Persone in CdA</td><td>{g.get('n_persone', 0)}</td></tr>")
        h.append(f"<tr><td>Compenso totale</td><td>{_fmt_euro(g.get('compenso_totale'))}</td></tr>")
        h.append(f"<tr><td>Compenso medio</td><td>{_fmt_euro(g.get('compenso_medio'))}</td></tr>")
        h.append(f"<tr><td>Donne</td><td>{g.get('n_donne', 0)} ({g.get('percentuale_donne', 0)}%)</td></tr>")
        h.append(f"<tr><td>Uomini</td><td>{g.get('n_uomini', 0)}</td></tr>")
        h.append(f"<tr><td>Incarichi gratuiti</td><td>{g.get('incarichi_gratuiti', 0)}</td></tr>")
        if "presidente" in g:
            h.append(f"<tr><td>Presidente</td><td>{g['presidente']['nome']} ({_fmt_euro(g['presidente']['compenso'])})</td></tr>")
        if "ad" in g:
            h.append(f"<tr><td>AD</td><td>{g['ad']['nome']} ({_fmt_euro(g['ad']['compenso'])})</td></tr>")
        h.append("</table>")

    # Appalti
    if ap and "gare_per_anno" in ap:
        h.append("<h2>Appalti Banditi (ANAC)</h2>")
        h.append(f"<p>Totale gare: <strong>{ap.get('totale_gare', 0):,}</strong> — Importo complessivo: <strong>{_fmt_euro(ap.get('importo_complessivo_totale', 0))}</strong></p>")
        h.append(f"<p>Gare PNRR: {ap.get('totale_gare_pnrr', 0)} — Gare urgenza: {ap.get('totale_gare_urgenza', 0)}</p>")
        h.append("<table><tr><th>Anno</th><th>Gare</th><th>Importo compl.</th><th>PNRR</th><th>Urgenza</th></tr>")
        for g in ap["gare_per_anno"]:
            h.append(f"<tr><td>{g['anno']}</td><td>{g['n_gare']:,}</td><td>{_fmt_euro(g.get('importo_complessivo', 0))}</td><td>{g.get('gare_pnrr', 0)}</td><td>{g.get('gare_urgenza', 0)}</td></tr>")
        h.append("</table>")

    # Aiuti di Stato
    if ai and "aiuti_per_anno" in ai:
        h.append("<h2>Aiuti di Stato Ricevuti (RNA)</h2>")
        h.append(f"<p>Totale ESL: <strong>{_fmt_euro(ai.get('totale_esl', 0))}</strong> — Aiuti distinti: <strong>{ai.get('n_aiuti_distinti', 0)}</strong></p>")
        h.append(f"<p>Principale concedente: <strong>{ai.get('principale_concedente', '?')}</strong> ({_fmt_euro(ai.get('importo_principale_concedente', 0))})</p>")
        h.append("<table><tr><th>Anno</th><th>Aiuti</th><th>ESL</th><th>Concedenti</th></tr>")
        for a in ai["aiuti_per_anno"]:
            h.append(f"<tr><td>{a['anno']}</td><td>{a['n_aiuti']}</td><td>{_fmt_euro(a.get('totale_esl', 0))}</td><td>{a.get('n_concedenti', 0)}</td></tr>")
        h.append("</table>")

    h.append(f"""
<div class="footer">
<p>Generato da <a href="https://github.com/dataciviclab/partecipate-monitor">partecipate-monitor</a> — dati aggiornati settimanalmente.</p>
<p>Fonti: MEF Partecipazioni, MEF Rappresentanti, ANAC Bandi Gara, RNA Aiuti di Stato, IndicePA.</p>
</div>
</body>
</html>""")

    return "\n".join(h)


# ── Main ────────────────────────────────────────────────────────

def genera_profili():
    """Carica i profili intelligence per le partecipate centrali."""
    from profiler import profila_lista
    from fetch_data import estrai_partecipate, cf_targets_centrali

    print("[report] Caricamento profili intelligence...")
    cfs = cf_targets_centrali()
    partecipate = estrai_partecipate(solo_mef_centrali=True)
    print(f"[report] Partecipate centrali trovate: {len(cfs)}")

    profili = profila_lista(partecipate)
    print(f"[report] Profili generati: {len(profili)}")
    return profili


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDE_DIR.mkdir(parents=True, exist_ok=True)

    genera_profili_flag = "--profili" in sys.argv

    # Dashboard classica
    dati = carica_dati()
    html = genera_html(dati)

    # Se richiesto, aggiungi profili intelligence
    if genera_profili_flag:
        try:
            profili = genera_profili()
            dati["profili"] = profili

            # Rigenera HTML dashboard con classifica profili
            html = genera_html(dati)

            # Salva singole schede
            for p in profili:
                nome = p.get("denominazione", "sconosciuto")
                slug = nome.lower().replace(" ", "-").replace("'", "").replace(",", "").replace(".", "")[:40]
                scheda_html = genera_scheda_html(p)
                scheda_path = SCHEDE_DIR / f"{slug}.html"
                with open(scheda_path, "w") as f:
                    f.write(scheda_html)
                print(f"[report] Scheda: schede/{slug}.html")
        except Exception as e:
            print(f"[report] ERRORE generazione profili: {e}")
            import traceback
            traceback.print_exc()

    with open(REPORTS_DIR / "index.html", "w") as f:
        f.write(html)

    with open(REPORTS_DIR / "data.json", "w") as f:
        json.dump(dati, f, indent=2, ensure_ascii=False)

    print(f"[report] Generato: reports/index.html")
    print(f"[report] Generato: reports/data.json")


if __name__ == "__main__":
    main()

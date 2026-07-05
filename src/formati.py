"""
formati.py — Analisi dei formati dei file pubblicati nelle pagine trasparenza.
Strategia: pagina principale + sotto-sezioni (deep scan).
"""

import asyncio, csv, json, sys, os, re, time
from datetime import datetime
from pathlib import Path
from collections import Counter
from urllib.parse import urljoin, urlparse

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOGO_IN = DATA_DIR / "catalogo.csv"
OUTPUT = DATA_DIR / "formati_report.json"

CONCURRENCY = 10
TIMEOUT = 10
MAX_SUB_PAGES = 8  # quante sotto-sezioni seguire per sito

FILE_EXT = re.compile(r"\.(pdf|xls|xlsx|csv|xml|doc|docx|ods|zip|json|rdf|odt)$", re.I)

# Keyword per identificare sotto-sezioni nella pagina trasparenza
KEYWORDS_SEZIONI = [
    'disposizioni', 'generali', 'organizzazione', 'consulenti', 'collaboratori',
    'personale', 'selezione', 'concorsi', 'bandi', 'contratti',
    'sovvenzioni', 'contributi', 'sussidi', 'bilanci', 'beni', 'immobili',
    'patrimonio', 'controlli', 'pagamenti', 'accesso', 'civico',
    'incarichi', 'titolari', 'procedimenti', 'provvedimenti', 'privacy',
    'dati personali', 'performance', 'piano', 'prevenzione', 'corruzione',
    'attività', 'legale', 'trasparenza',
]

def estrai_link_sezioni(html, base_url):
    """Trova link a sotto-sezioni nella pagina trasparenza."""
    if not html:
        return []
    html_lower = html.lower()
    sezioni = []
    for m in re.finditer(
        r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>\s*([^<]{4,80}?)\s*</a>',
        html, re.IGNORECASE
    ):
        href = m.group(1).strip()
        testo = m.group(2).strip().lower()
        # Salta link tecnici
        if any(s in testo for s in ['css', 'javascript', 'mailto:', 'tel:', 'home', 'contatti']):
            continue
        if any(k in testo for k in KEYWORDS_SEZIONI):
            url = urljoin(base_url, href) if not href.startswith('http') else href
            sezioni.append(url)
    # Dedup
    return list(dict.fromkeys(sezioni))


async def analizza(entries, progress_cb=None):
    sem = asyncio.Semaphore(CONCURRENCY)
    results = []
    headers = {"User-Agent": "partecipate-monitor/1.0"}

    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers,
                                  follow_redirects=True, verify=False) as client:

        async def lavora(entry):
            async with sem:
                url = entry.get("url_trasparenza", "")
                if not url:
                    return None
                formati_shallow = Counter()
                formati_deep = Counter()
                n_sub_pages = 0
                
                try:
                    # PASSO 1: pagina principale
                    resp = await client.get(url)
                    html_orig = resp.text if resp.status_code in (200, 202) else ""
                    html = html_orig.lower() if html_orig else ""
                    
                    if html and len(html) > 500:
                        for m in re.finditer(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>', html):
                            ext = FILE_EXT.search(m.group(1).lower())
                            if ext:
                                formati_shallow[ext.group(1)] += 1
                        
                        # PASSO 2: sotto-sezioni (usa HTML ORIGINALE per preservare case URL)
                        sezioni = estrai_link_sezioni(html_orig, url)
                        for sub_url in sezioni[:MAX_SUB_PAGES]:
                            try:
                                resp_sub = await client.get(sub_url)
                                html_sub = resp_sub.text.lower() if resp_sub.status_code in (200, 202) else ""
                                if html_sub and len(html_sub) > 500:
                                    for m in re.finditer(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>', html_sub):
                                        ext = FILE_EXT.search(m.group(1).lower())
                                        if ext:
                                            formati_deep[ext.group(1)] += 1
                                    n_sub_pages += 1
                            except:
                                continue
                
                except:
                    pass
                
                # Combina: deep prevale (file in sotto-sezioni + pagina principale)
                formati_totali = formati_shallow + formati_deep
                
                return {
                    "cf": entry.get("cf", ""),
                    "denominazione": entry.get("denominazione", ""),
                    "url": url,
                    "formati_shallow": dict(formati_shallow),
                    "formati_deep": dict(formati_deep),
                    "formati": dict(formati_totali),
                    "totale_file": sum(formati_totali.values()),
                    "n_sub_pages": n_sub_pages,
                }

        tasks = [asyncio.create_task(lavora(e)) for e in entries]
        n = len(entries)
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            r = await coro
            if r:
                results.append(r)
            if progress_cb and (i + 1) % 50 == 0:
                ok = sum(1 for x in results if x and x["totale_file"] > 0)
                progress_cb(i + 1, n, ok)

    return [r for r in results if r]


def report(results):
    totale_file = sum(r["totale_file"] for r in results)
    formati_totali = Counter()
    formati_shallow_tot = Counter()
    formati_deep_tot = Counter()
    
    for r in results:
        for f, c in r["formati"].items():
            formati_totali[f] += c
        for f, c in r.get("formati_shallow", {}).items():
            formati_shallow_tot[f] += c
        for f, c in r.get("formati_deep", {}).items():
            formati_deep_tot[f] += c

    siti_con_file = sum(1 for r in results if r["totale_file"] > 0)
    siti_solo_pdf = sum(1 for r in results
                        if r["totale_file"] > 0
                        and list(r["formati"].keys()) == ["pdf"])
    siti_aperti = sum(1 for r in results
                      if any(f in ("csv", "xml", "json", "ods") for f in r["formati"]))
    
    # Per-site set tracking per metriche accurate
    cf_aperti_shallow = {r["cf"] for r in results
                         if any(f in ("csv", "xml", "json", "ods") for f in r.get("formati_shallow", {}))}
    cf_aperti_deep_only = {r["cf"] for r in results
                           if (any(f in ("csv", "xml", "json", "ods") for f in r.get("formati_deep", {}))
                               and r["cf"] not in cf_aperti_shallow)}
    siti_aperti_grazie_deep = len(cf_aperti_deep_only)
    
    sub_tot = sum(r["n_sub_pages"] for r in results)
    sub_med = round(sub_tot / len(results), 1) if results else 0

    sintesi = {
        "data_scan": datetime.now().isoformat(),
        "totale_siti_analizzati": len(results),
        "totale_file_trovati": totale_file,
        "siti_con_file": siti_con_file,
        "siti_solo_pdf": siti_solo_pdf,
        "siti_con_formato_aperto": siti_aperti,
        "siti_aperti_solo_shallow": len(cf_aperti_shallow),
        "siti_aperti_grazie_deep": siti_aperti_grazie_deep,
        "sotto_pagine_analizzate": sub_tot,
        "media_sotto_pagine_per_sito": sub_med,
        "file_shallow": dict(formati_shallow_tot.most_common()),
        "file_deep": dict(formati_deep_tot.most_common()),
        "formati": dict(formati_totali.most_common()),
    }

    with open(OUTPUT, "w") as f:
        json.dump(sintesi, f, indent=2, ensure_ascii=False)

    print(f"\n[formati] Report: {OUTPUT}")
    print(f"[formati] Totale file: {totale_file} ({sum(formati_shallow_tot.values())} shallow + {sum(formati_deep_tot.values())} deep)")
    print(f"[formati] Sotto-pagine analizzate: {sub_tot} (media {sub_med}/sito)")
    print(f"[formati] Formati aperti (XML/CSV/JSON/ODS): {siti_aperti}/{len(results)} siti")
    pct_pdf = round(100 * formati_totali.get("pdf", 0) / totale_file, 1) if totale_file else 0
    pct_xml = round(100 * formati_totali.get("xml", 0) / totale_file, 1) if totale_file else 0
    print(f"[formati] PDF: {formati_totali.get('pdf',0)} ({pct_pdf}%), XML: {formati_totali.get('xml',0)} ({pct_xml}%)")
    return sintesi


def main():
    csv.field_size_limit(10 * 1024 * 1024)

    if not CATALOGO_IN.exists():
        print("[formati] ERRORE: esegui prima catalogo.py")
        sys.exit(1)

    with open(CATALOGO_IN) as f:
        entries = list(csv.DictReader(f))

    raggiungibili = [e for e in entries if e.get("raggiungibile", "").upper() == "TRUE"]
    print(f"[formati] Deep scan su {len(raggiungibili)} pagine (max {MAX_SUB_PAGES} sotto-pagine ciascuna)")

    def progress(done, total, con_file):
        print(f"  [{done}/{total}] con file: {con_file}", flush=True)

    results = asyncio.run(analizza(raggiungibili, progress))
    report(results)


if __name__ == "__main__":
    main()

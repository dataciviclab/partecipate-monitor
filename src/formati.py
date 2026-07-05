"""
formati.py — Analisi dei formati dei file pubblicati nelle pagine trasparenza.
Scarica la pagina principale e classifica tutti i link a documenti per formato.
"""

import asyncio, csv, json, sys, os, re, time
from datetime import datetime
from pathlib import Path
from collections import Counter

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOGO_IN = DATA_DIR / "catalogo.csv"
OUTPUT = DATA_DIR / "formati_report.json"

CONCURRENCY = 12
TIMEOUT = 10

FILE_EXT = re.compile(r"\.(pdf|xls|xlsx|csv|xml|doc|docx|ods|zip|json|rdf|odt)$", re.I)


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
                formati = Counter()
                try:
                    resp = await client.get(url)
                    html = resp.text.lower() if resp.status_code == 200 else ""
                    if html and len(html) > 500:
                        for m in re.finditer(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>', html):
                            ext = FILE_EXT.search(m.group(1).lower())
                            if ext:
                                formati[ext.group(1)] += 1
                except:
                    pass
                return {
                    "cf": entry.get("cf", ""),
                    "denominazione": entry.get("denominazione", ""),
                    "url": url,
                    "formati": dict(formati),
                    "totale_file": sum(formati.values()),
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
    for r in results:
        for f, c in r["formati"].items():
            formati_totali[f] += c

    siti_con_file = sum(1 for r in results if r["totale_file"] > 0)
    siti_solo_pdf = sum(1 for r in results
                         if r["totale_file"] > 0
                         and list(r["formati"].keys()) == ["pdf"])
    siti_aperti = sum(1 for r in results
                       if any(f in ("csv", "xml", "json", "ods") for f in r["formati"]))

    sintesi = {
        "data_scan": datetime.now().isoformat(),
        "totale_siti_analizzati": len(results),
        "totale_file_trovati": totale_file,
        "siti_con_file": siti_con_file,
        "siti_solo_pdf": siti_solo_pdf,
        "siti_con_formato_aperto": siti_aperti,
        "formati": dict(formati_totali.most_common()),
    }

    with open(OUTPUT, "w") as f:
        json.dump(sintesi, f, indent=2, ensure_ascii=False)

    print(f"\n[formati] Report: {OUTPUT}")
    print(f"[formati] Totale file: {totale_file}")
    print(f"[formati] Formati aperti (XML/CSV/JSON/ODS): {siti_aperti}/{len(results)} siti")
    for f, c in formati_totali.most_common():
        print(f"  .{f:5s}: {c} ({round(100*c/totale_file,1)}%)")
    return sintesi


def main():
    csv.field_size_limit(10 * 1024 * 1024)

    if not CATALOGO_IN.exists():
        print("[formati] ERRORE: esegui prima catalogo.py")
        sys.exit(1)

    with open(CATALOGO_IN) as f:
        entries = list(csv.DictReader(f))

    raggiungibili = [e for e in entries if e.get("raggiungibile", "").upper() == "TRUE"]
    print(f"[formati] Analisi formati su {len(raggiungibili)} pagine")

    def progress(done, total, con_file):
        print(f"  [{done}/{total}] con file: {con_file}", flush=True)

    results = asyncio.run(analizza(raggiungibili, progress))
    report(results)


if __name__ == "__main__":
    main()

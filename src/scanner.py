"""
scanner.py — Verifica la presenza della sezione "Società Trasparente"
sui siti web delle partecipate pubbliche.

Strategia: homepage → cerca link "trasparen" → fallback su path diretti.
"""

import asyncio, csv, json, sys, os, time, re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.fetch_data import estrai_partecipate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORT_FILE = DATA_DIR / "scanner_report.csv"
SINTESI_FILE = DATA_DIR / "scanner_report.json"

CONCURRENCY = 15
TIMEOUT = 8

FALLBACK_PATHS = [
    "/amministrazione-trasparente",
    "/amministrazione-trasparente/",
    "/amministrazione-trasparente.html",
    "/amministrazionetrasparente",
    "/societa-trasparente",
    "/societa-trasparente/",
    "/societa-trasparente-2",
    "/societa-trasparente-2/",
    "/societa-trasparente-3",
    "/societa-trasparente-3/",
    "/societa_trasparente.php",
    "/societa-trasparente.php",
    "/amministrazione-trasparente.php",
    "/trasparenza",
    "/trasparenza/",
    "/societa-trasparenza",
    "/societa-trasparenza/",
    "/it/amministrazione-trasparente",
    "/it/amministrazione-trasparente/",
    "/it/societa-trasparente",
    "/it/societa-trasparente/",
    "/it/page/amministrazione-trasparente.html",
    "/it/trasparenza",
    "/it/trasparenza/",
    "/it/content/trasparenza",
    "/it/ilgruppo/comelavoriamo/pagine/amministrazionetrasparente",
    "/newsite/trasparenza",
    "/newsite/trasparenza/",
]


def normalizza_url(sito):
    sito = sito.strip().strip("'\"")
    if not sito.startswith("http"):
        sito = "https://" + sito
    return sito.rstrip("/")


def cerca_trasparenza_in_html(html, base_url):
    """Cerca link a sezioni trasparenza nell'HTML.
    Cerca tag <a> completi: se l'href o il testo contengono 'trasparen',
    restituisce l'href assoluto.
    Esclude link a risorse non-HTML (CSS, JS, immagini, etc.)."""
    if not html:
        return []
    
    SKIP_EXT = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
                ".ico", ".woff", ".woff2", ".ttf", ".eot", ".webp", ".mp4",
                ".pdf", ".xls", ".xlsx", ".csv", ".xml", ".doc", ".docx",
                ".zip", ".json", ".ods", ".odt")
    
    risultati = []
    # Cerca tag <a> completi: href="..." e testo
    for m in re.finditer(
        r'<a[^>]*href=["\']([^"\']+?)["\'][^>]*>([^<]*?)</a>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href = m.group(1).strip()
        testo = m.group(2).strip()
        combined = href.lower() + testo.lower()
        
        # Deve contenere "trasparen" da qualche parte
        if "trasparen" not in combined:
            continue
        
        # Salta asset non-HTML
        href_path = urlparse(href).path.lower()
        if any(href_path.endswith(ext) for ext in SKIP_EXT):
            continue
        
        # Ricostruisci URL assoluto
        if href.startswith("http"):
            url = href
        elif href.startswith("/"):
            url = base_url + href
        elif href.startswith("#"):
            url = base_url + href
        else:
            url = base_url + "/" + href
        
        risultati.append({"tipo": "href", "valore": url, "testo": testo[:80]})
    
    # Fallback: cerca solo testo (per link non in <a> o malformati)
    if not risultati:
        for m in re.finditer(r">([^<]*trasparen[tz][^<]*)<", html.lower()):
            risultati.append({"tipo": "testo", "valore": m.group(1).strip()})
    
    # Dedup
    visti = set()
    unici = []
    for r in risultati:
        key = r.get("valore", r.get("tipo", "")) + r.get("tipo", "")
        if key not in visti:
            visti.add(key)
            unici.append(r)
    return unici


async def scanner(entries, progress_cb=None):
    sem = asyncio.Semaphore(CONCURRENCY)
    results = []
    start_global = time.time()
    errori_rete = 0

    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=5)
    headers = {
        "User-Agent": "partecipate-monitor/1.0 (https://github.com/dataciviclab/partecipate-monitor)",
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(
        limits=limits, timeout=TIMEOUT, headers=headers,
        follow_redirects=True, verify=False
    ) as client:

        async def scansiona(entry):
            async with sem:
                base = normalizza_url(entry["sito_istituzionale"])
                out = {
                    "cf": entry["cf_norm"],
                    "denominazione": entry["denominazione"],
                    "sito": base,
                    "categoria": entry["categoria"],
                    "trovata": False,
                    "metodo": "",
                    "url": "",
                    "errore": "",
                }
                try:
                    resp = await client.get(base)
                    if resp.status_code in (200, 202) and resp.text:
                        frammenti = cerca_trasparenza_in_html(resp.text, base)
                        if frammenti:
                            out["trovata"] = True
                            out["metodo"] = "link_in_homepage"
                            hrefs = [f for f in frammenti if f["tipo"] == "href"]
                            if hrefs:
                                out["url"] = hrefs[0]["valore"]
                            else:
                                out["url"] = frammenti[0]["valore"]
                            return out

                    # PASSO 2: sitemap.xml — cerca URL con "trasparen"
                    for sm_path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
                        try:
                            sm_resp = await client.get(base + sm_path)
                            if sm_resp.status_code in (200, 202) and len(sm_resp.text) > 100:
                                sm_text = sm_resp.text.lower()
                                if "trasparen" in sm_text:
                                    urls = re.findall(
                                        r'<loc>([^<]*trasparen[^<]*)</loc>',
                                        sm_resp.text, re.IGNORECASE
                                    )
                                    if urls:
                                        out["trovata"] = True
                                        out["metodo"] = "sitemap"
                                        out["url"] = urls[0]
                                        return out
                                break  # sitemap trovata ma senza trasparenza
                        except:
                            continue

                    # PASSO 3: fallback esteso
                    for path in FALLBACK_PATHS:
                        try:
                            r2 = await client.get(base + path)
                            if r2.status_code in (200, 202):
                                out["trovata"] = True
                                out["metodo"] = "path_diretto"
                                out["url"] = base + path
                                return out
                            elif r2.status_code in (301, 302, 303, 307, 308):
                                loc = r2.headers.get("location", "").lower()
                                if "trasparen" in loc:
                                    out["trovata"] = True
                                    out["metodo"] = "redirect"
                                    out["url"] = base + path
                                    return out
                        except:
                            continue
                except httpx.ConnectError:
                    out["errore"] = "connessione_rifiutata"
                except httpx.TimeoutException:
                    out["errore"] = "timeout"
                except Exception as e:
                    out["errore"] = str(e)[:80]
                return out

        tasks = [asyncio.create_task(scansiona(e)) for e in entries]
        n = len(entries)
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            r = await coro
            results.append(r)
            if r["errore"]:
                errori_rete += 1
            if progress_cb and (i + 1) % 50 == 0:
                trovati = sum(1 for x in results if x["trovata"])
                elapsed = time.time() - start_global
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                progress_cb(i + 1, n, trovati, errori_rete, rate)

    return results


def salva_report(results):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(REPORT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cf", "denominazione", "sito", "categoria",
                      "trovata", "metodo", "url", "errore"])
        for r in results:
            w.writerow([
                r["cf"], r["denominazione"], r["sito"], r["categoria"],
                "SI" if r["trovata"] else "NO",
                r.get("metodo", ""), r.get("url", ""), r.get("errore", ""),
            ])

    totale = len(results)
    trovati = sum(1 for r in results if r["trovata"])
    sintesi = {
        "data_scan": datetime.now().isoformat(),
        "totale_siti": totale,
        "sezione_trovata": trovati,
        "sezione_non_trovata": totale - trovati,
        "percentuale": round(100 * trovati / totale, 1),
        "controllo_pubblico": {
            "totale": sum(1 for r in results if r["categoria"] == "controllo_pubblico"),
            "trovata": sum(1 for r in results if r["trovata"] and r["categoria"] == "controllo_pubblico"),
        },
        "solo_partecipata": {
            "totale": sum(1 for r in results if r["categoria"] == "partecipata"),
            "trovata": sum(1 for r in results if r["trovata"] and r["categoria"] == "partecipata"),
        },
        "errori": dict(
            __import__("collections").Counter(r["errore"] for r in results if r["errore"]).most_common()
        ),
    }

    with open(SINTESI_FILE, "w") as f:
        json.dump(sintesi, f, indent=2, ensure_ascii=False)

    print(f"\n[scanner] Report: {REPORT_FILE}")
    print(f"[scanner] Sintesi: {SINTESI_FILE}")
    print(f"[scanner] Trovati: {trovati}/{totale} ({sintesi['percentuale']}%)")
    return sintesi


def main():
    import time

    only_controllo = "--solo-controllo" in sys.argv
    max_siti = None
    for a in sys.argv:
        if a.startswith("--max="):
            max_siti = int(a.split("=")[1])

    print(f"[scanner] Avvio scan {'solo controllo' if only_controllo else 'tutti'} "
          f"{f'(max {max_siti})' if max_siti else ''}")

    def progress(done, total, trovati, errori, rate):
        rimanenti = total - done
        stima = rimanenti / rate if rate > 0 else 0
        print(f"  [{done}/{total}] trovati {trovati} | errori {errori} | "
              f"{rate:.1f}/s | stima ~{stima/60:.0f}min", flush=True)

    entries = estrai_partecipate(only_controllo=only_controllo, max_siti=max_siti)
    start = time.time()
    results = asyncio.run(scanner(entries, progress))
    print(f"[scanner] Tempo: {time.time()-start:.1f}s")
    salva_report(results)


if __name__ == "__main__":
    main()

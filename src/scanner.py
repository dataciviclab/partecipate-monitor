"""
scanner.py — Verifica la presenza della sezione "Società Trasparente"
sui siti web delle partecipate pubbliche.

Strategia a stadi con diagnostica:
  1. Homepage → link "trasparen" (href + testo)
  2. Sitemap → URL "trasparen"
  3. Path combinatori (non fissi)
  4. SaaS probe (piattaforme note)
  Diagnostica: per ogni fallimento registra il motivo
"""

import asyncio, csv, json, sys, os, time, re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from itertools import product

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.fetch_data import estrai_partecipate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORT_FILE = DATA_DIR / "scanner_report.csv"
SINTESI_FILE = DATA_DIR / "scanner_report.json"
PATTERNS_FILE = Path(__file__).resolve().parent.parent / "data" / "known_patterns.json"

CONCURRENCY = 15
TIMEOUT = 8
TIMEOUT_FAST = 3  # primo tentativo: se non risponde in 3s, riprova dopo

# ── Pattern base per generazione combinatoria ──────────────────────────

BASEWORDS = [
    "amministrazione-trasparente",
    "societa-trasparente",
    "trasparenza",
]

PREFIXES = [
    "", "/it", "/la-societa", "/newsite",
    "/it/page", "/it/content",
]

SUFFIXES = [
    "", "/", ".html", ".php",
    "-2", "-2/", "-3", "-3/",
]

# Piattaforme SaaS note
SAAS_PLATFORMS = [
    "portaletrasparenza.net",
    "portaleamministrazionetrasparente.it",
    "trasparenza-valutazione-merito.it",
    "contrasparenza.it",
]

SKIP_EXT = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
            ".ico", ".woff", ".woff2", ".ttf", ".eot", ".webp", ".mp4",
            ".pdf", ".xls", ".xlsx", ".csv", ".xml", ".doc", ".docx",
            ".zip", ".json", ".ods", ".odt")


# ── Helpers ─────────────────────────────────────────────────────────────

def normalizza_url(sito):
    sito = sito.strip().strip("'\"")
    if not sito.startswith("http"):
        sito = "https://" + sito
    return sito.rstrip("/")


def genera_path():
    """Path ordinati per probabilità. Solo i primi 15 più frequenti."""
    return [
        "/amministrazione-trasparente", "/amministrazione-trasparente/",
        "/societa-trasparente", "/societa-trasparente/",
        "/trasparenza", "/trasparenza/",
        "/it/amministrazione-trasparente", "/it/amministrazione-trasparente/",
        "/it/societa-trasparente", "/it/societa-trasparente/",
        "/societa-trasparente-2", "/societa-trasparente-2/",
        "/amministrazione-trasparente.html",
        "/societa_trasparente.php",
        "/it/page/amministrazione-trasparente.html",
        "/it/content/trasparenza",
        "/newsite/trasparenza", "/newsite/trasparenza/",
    ]


def carica_pattern():
    """Carica pattern conosciuti da check manuali precedenti."""
    if PATTERNS_FILE.exists():
        with open(PATTERNS_FILE) as f:
            return json.load(f)
    return {"url_patterns": [], "saas_subdominio": []}


def salva_pattern(pattern):
    PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PATTERNS_FILE, "w") as f:
        json.dump(pattern, f, indent=2, ensure_ascii=False)


def cerca_trasparenza_in_html(html, base_url):
    """Cerca tag <a> completi con 'trasparen' in href o testo."""
    if not html:
        return []
    risultati = []
    for m in re.finditer(
        r'<a[^>]*href=["\']([^"\']+?)["\'][^>]*>([^<]*?)</a>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href = m.group(1).strip()
        testo = m.group(2).strip()
        if "trasparen" not in (href.lower() + testo.lower()):
            continue
        href_path = urlparse(href).path.lower()
        if any(href_path.endswith(ext) for ext in SKIP_EXT):
            continue
        if href.startswith("http"):
            url = href
        elif href.startswith("/"):
            url = base_url + href
        elif href.startswith("#"):
            url = base_url + href
        else:
            url = base_url + "/" + href
        risultati.append({"tipo": "href", "valore": url, "testo": testo[:80]})
    if not risultati:
        for m in re.finditer(r">([^<]*trasparen[tz][^<]*)<", html.lower()):
            risultati.append({"tipo": "testo", "valore": m.group(1).strip()})
    visti = set()
    unici = []
    for r in risultati:
        key = str(r.get("valore", "")) + str(r.get("tipo", ""))
        if key not in visti:
            visti.add(key)
            unici.append(r)
    return unici


def slug_da_nome(nome):
    """Genera slug dal nome della partecipata per probe SaaS."""
    s = nome.lower().strip().replace("'", "").replace('"', "")
    s = re.sub(r'[^a-z0-9]+', '', s)
    return s[:30]


def estratti_da_saas(slug, dominio):
    """Genera URL SaaS da provare."""
    urls = []
    for platform in SAAS_PLATFORMS:
        urls.append(f"https://{slug}.{platform}")
        urls.append(f"https://{slug}.{platform}/")
    # Subdomain trasparenza.sito.it
    parsed = urlparse(dominio)
    hostname = parsed.hostname or dominio.replace("https://", "").replace("http://", "").split("/")[0]
    urls.append(f"https://trasparenza.{hostname}")
    urls.append(f"https://amministrazionetrasparente.{hostname}")
    return urls


# ── Scanner ─────────────────────────────────────────────────────────────

async def scanner(entries, progress_cb=None):
    combinatori = genera_path()
    known = carica_pattern()
    extra_patterns = known.get("url_patterns", [])
    headers = {
        "User-Agent": "partecipate-monitor/1.0 (https://github.com/dataciviclab/partecipate-monitor)",
        "Accept": "text/html,application/xhtml+xml",
    }
    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=5)

    async def scansiona(entry, client, timeout_label=""):
        base = normalizza_url(entry["sito_istituzionale"])
        out = {
            "cf": entry["cf_norm"],
            "denominazione": entry["denominazione"],
            "sito": base,
            "categoria": entry["categoria"],
            "trovata": False, "metodo": "", "url": "", "errore": "",
            "nota": timeout_label,
        }
        t0 = time.time()
        try:
            resp = await client.get(base)
            out["nota"] = f"homepage: {resp.status_code}"
            if resp.status_code in (200, 202) and resp.text:
                frammenti = cerca_trasparenza_in_html(resp.text, base)
                if frammenti:
                    out["trovata"] = True
                    out["metodo"] = "link_in_homepage"
                    hrefs = [f for f in frammenti if f["tipo"] == "href"]
                    out["url"] = hrefs[0]["valore"] if hrefs else frammenti[0]["valore"]
                    return out
                out["nota"] += f", {len(resp.text)}b, no link trasparen"

            for sm_path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
                try:
                    sm = await client.get(base + sm_path)
                    if sm.status_code in (200, 202) and "trasparen" in (sm.text or "").lower():
                        urls = re.findall(r'<loc>([^<]*trasparen[^<]*)</loc>', sm.text or "", re.IGNORECASE)
                        if urls:
                            out["trovata"] = True
                            out["metodo"] = "sitemap"
                            out["url"] = urls[0]
                            return out
                except:
                    continue

            # Path combinatori
            async def check_path(path):
                try:
                    r = await client.get(base + path)
                    ok = r.status_code in (200, 202) and r.text and "trasparen" in r.text.lower()[:5000]
                    return (r.status_code, base + path, ok)
                except:
                    return (None, path, False)

            fallback_403 = 0
            for i in range(0, len(combinatori), 5):
                batch = combinatori[i:i+5]
                rb = await asyncio.gather(*[check_path(p) for p in batch])
                for status, url, content_ok in rb:
                    if status == 403: fallback_403 += 1
                    if status in (200, 202) and content_ok:
                        out["trovata"] = True
                        out["metodo"] = "path_combinatorio"
                        out["url"] = url
                        return out
            out["nota"] += f", {len(combinatori)} paths ({fallback_403} forbidden)"

            # Known patterns
            for pattern in extra_patterns:
                try:
                    r3 = await client.get(base + pattern)
                    if r3.status_code in (200, 202) and r3.text and "trasparen" in r3.text.lower()[:5000]:
                        out["trovata"] = True
                        out["metodo"] = "known_pattern"
                        out["url"] = base + pattern
                        return out
                except:
                    continue

            # SaaS probe
            slug = slug_da_nome(entry["denominazione"])
            for saas_url in estratti_da_saas(slug, base):
                try:
                    r4 = await client.get(saas_url)
                    if r4.status_code in (200, 202) and r4.text and "trasparen" in r4.text.lower()[:5000]:
                        out["trovata"] = True
                        out["metodo"] = "saas"
                        out["url"] = saas_url
                        return out
                except:
                    continue

            elapsed = int((time.time() - t0) * 1000)
            out["nota"] += f", {elapsed}ms"

        except httpx.TimeoutException:
            out["errore"] = "timeout"
        except httpx.ConnectError:
            out["errore"] = "connessione_rifiutata"
        except Exception as e:
            out["errore"] = str(e)[:80]
        return out

    # ── Passaggio 1: veloce (3s timeout) ──
    print(f"[scanner] Passaggio 1: veloce ({TIMEOUT_FAST}s timeout)...")
    results = []
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(limits=limits, timeout=TIMEOUT_FAST,
                                  headers=headers, follow_redirects=True, verify=False) as client:
        async def run_fast(e):
            async with sem:
                return await scansiona(e, client, "fast")
        tasks = [asyncio.create_task(run_fast(e)) for e in entries]
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            r = await coro
            results.append(r)
            if progress_cb and (i + 1) % 100 == 0:
                trovati = sum(1 for x in results if x["trovata"])
                print(f"  [passaggio 1: {i+1}/{len(entries)}] trovati {trovati}", flush=True)

    # ── Passaggio 2: lento (8s) solo timeout ──
    timeout_sites = [e for e, r in zip(entries, results) if r["errore"] == "timeout"]
    if timeout_sites:
        print(f"[scanner] Passaggio 2: lento ({TIMEOUT}s) su {len(timeout_sites)} siti in timeout...")
        sem2 = asyncio.Semaphore(CONCURRENCY)
        async with httpx.AsyncClient(limits=limits, timeout=TIMEOUT,
                                      headers=headers, follow_redirects=True, verify=False) as client:
            async def run_slow(e):
                async with sem2:
                    return await scansiona(e, client, "slow")
            tasks2 = [asyncio.create_task(run_slow(e)) for e in timeout_sites]
            # Sostituisci i risultati dei timeout con quelli nuovi
            timeout_idx = {e.get("cf_norm", i): i for i, e in enumerate(entries)}
            for coro in asyncio.as_completed(tasks2):
                r = await coro
                # Trova l'indice originale
                for idx, entry in enumerate(entries):
                    if entry["cf_norm"] == r["cf"]:
                        results[idx] = r
                        break

    trovati = sum(1 for r in results if r["trovata"])
    errori = sum(1 for r in results if r["errore"])
    print(f"[scanner] Trovati: {trovati}/{len(entries)} ({round(100*trovati/len(entries),1)}%)")
    return results


def salva_report(results):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(REPORT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cf", "denominazione", "sito", "categoria",
                      "trovata", "metodo", "url", "errore", "nota"])
        for r in results:
            w.writerow([
                r["cf"], r["denominazione"], r["sito"], r["categoria"],
                "SI" if r["trovata"] else "NO",
                r.get("metodo", ""), r.get("url", ""), r.get("errore", ""),
                r.get("nota", ""),
            ])

    from collections import Counter
    totale = len(results)
    trovati = sum(1 for r in results if r["trovata"])
    per_metodo = Counter(r.get("metodo", "?") for r in results)
    per_nota = Counter(r.get("nota", "") for r in results if not r["trovata"])

    sintesi = {
        "data_scan": datetime.now().isoformat(),
        "totale_siti": totale,
        "sezione_trovata": trovati,
        "sezione_non_trovata": totale - trovati,
        "percentuale": round(100 * trovati / totale, 1),
        "metodi": dict(per_metodo.most_common()),
        "diagnostica_non_trovati": dict(per_nota.most_common(10)),
        "errori": dict(Counter(r["errore"] for r in results if r["errore"]).most_common()),
    }

    with open(SINTESI_FILE, "w") as f:
        json.dump(sintesi, f, indent=2, ensure_ascii=False)

    print(f"\n[scanner] Report: {REPORT_FILE}")
    print(f"[scanner] Sintesi: {SINTESI_FILE}")
    print(f"[scanner] Trovati: {trovati}/{totale} ({sintesi['percentuale']}%)")
    print(f"[scanner] Metodi: {dict(per_metodo.most_common(5))}")
    if per_nota:
        print(f"[scanner] Diagnostica: {dict(per_nota.most_common(3))}")
    return sintesi


def main():
    only_controllo = "--solo-controllo" in sys.argv
    max_siti = None
    for a in sys.argv:
        if a.startswith("--max="):
            max_siti = int(a.split("=")[1])

    print(f"[scanner] Avvio scan v2 (combinatorio + SaaS + diagnostica)")
    print(f"[scanner] Path combinatori: {len(genera_path())}")
    print(f"[scanner] Saas probe: {len(SAAS_PLATFORMS)} piattaforme")
    print(f"[scanner] Timeout: {TIMEOUT_FAST}s primo passaggio, {TIMEOUT}s secondo")

    entries = estrai_partecipate(only_controllo=only_controllo, max_siti=max_siti)
    start = time.time()
    results = asyncio.run(scanner(entries))
    salva_report(results)


if __name__ == "__main__":
    main()

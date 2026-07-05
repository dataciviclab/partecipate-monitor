"""
catalogo.py — Per ogni partecipata con sezione trovata, analizza
la pagina trasparenza ed estrae quali categorie ANAC sono pubblicate.
"""

import asyncio, csv, json, sys, os, re, time
from datetime import datetime
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORT_SCANNER = DATA_DIR / "scanner_report.csv"
OUTPUT = DATA_DIR / "catalogo.csv"

CONCURRENCY = 10
TIMEOUT = 10

CATEGORIE = [
    ("disposizioni_generali", ["disposizioni generali", "atti generali", "riferimenti normativi",
                                "piano triennale", "prevenzione corruzione", "codice disciplinare"]),
    ("organizzazione", ["organizzazione", "organi", "titolari incarichi", "organo amministrativo",
                         "organo controllo", "assemblea"]),
    ("consulenti", ["consulenti", "collaboratori", "incarichi consulenza", "curricula"]),
    ("personale", ["personale", "dirigenti", "dotazione organica", "tassi assenza",
                    "contrattazione", "contratto collettivo"]),
    ("selezione_personale", ["selezione personale", "concorsi", "reclutamento", "assunzioni"]),
    ("bandi_contratti", ["bandi", "contratti", "gara", "affidamento", "appalto", "cig"]),
    ("sovvenzioni", ["sovvenzioni", "contributi", "sussidi", "vantaggi economici",
                      "erogazioni", "agevolazioni"]),
    ("bilanci", ["bilanci", "bilancio", "rendiconto", "economico", "patrimoniale", "esercizio"]),
    ("beni_immobili", ["beni immobili", "patrimonio", "canoni", "locazioni", "fitti"]),
    ("controlli", ["controlli", "rilievi", "organismo vigilanza", "oiv", "corte conti", "revisione"]),
    ("pagamenti", ["pagamenti", "fatture", "tempi pagamento", "indicatore tempestività", "iban"]),
    ("accesso_civico", ["accesso civico", "accesso generalizzato", "diritto accesso"]),
    ("privacy", ["privacy", "dati personali", "informativa"]),
]


def cerca_categorie(html):
    if not html:
        return {}
    html_lower = html.lower()
    risultato = {}
    for chiave, keyword_list in CATEGORIE:
        trovato = False
        for kw in keyword_list:
            if kw in html_lower:
                trovato = True
                break
        risultato[chiave] = trovato
    return risultato


async def estrai(entries, progress_cb=None):
    sem = asyncio.Semaphore(CONCURRENCY)
    results = []
    headers = {"User-Agent": "partecipate-monitor/1.0"}

    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers,
                                  follow_redirects=True, verify=False) as client:
        async def lavora(entry):
            async with sem:
                url = entry.get("url", "")
                if not url:
                    base = entry.get("sito", "").rstrip("/")
                    url = base + "/amministrazione-trasparente"
                out = {
                    "cf": entry["cf"],
                    "denominazione": entry["denominazione"],
                    "url_trasparenza": url,
                    "categoria": entry["categoria"],
                    "raggiungibile": False,
                    "errore": "",
                }
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.text) > 200:
                        out["raggiungibile"] = True
                        out["categorie"] = cerca_categorie(resp.text)
                except Exception as e:
                    out["errore"] = str(e)[:80]
                return out

        tasks = [asyncio.create_task(lavora(e)) for e in entries]
        n = len(entries)
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            r = await coro
            results.append(r)
            if progress_cb and (i + 1) % 50 == 0:
                ok = sum(1 for x in results if x.get("raggiungibile"))
                progress_cb(i + 1, n, ok)

    return results


def salva(results):
    campi_cat = [k for k, _ in CATEGORIE]
    campi_base = ["cf", "denominazione", "url_trasparenza", "categoria",
                   "raggiungibile", "errore"]

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(campi_base + campi_cat + ["categorie_trovate", "score"])
        for r in results:
            riga = [r.get(c, "") for c in campi_base]
            if r.get("categorie"):
                cat = r["categorie"]
                n_trovate = sum(1 for c in campi_cat if cat.get(c, False))
                for c in campi_cat:
                    riga.append("SI" if cat.get(c, False) else "NO")
                riga.append(n_trovate)
                riga.append(round(100 * n_trovate / len(campi_cat), 1))
            else:
                riga.extend([""] * len(campi_cat))
                riga.append(0)
                riga.append(0)
            w.writerow(riga)

    return campi_cat


def report(results, campi_cat):
    ok = [r for r in results if r.get("raggiungibile")]
    print(f"\n[catalogo] Pagine raggiungibili: {len(ok)}/{len(results)}")
    print("[catalogo] Categorie pubblicate (%):")
    for c in campi_cat:
        n = sum(1 for r in ok if r.get("categorie", {}).get(c, False))
        print(f"  {c:25s}: {n}/{len(ok)} ({round(100*n/len(ok),1)}%)")


def main():
    csv.field_size_limit(10 * 1024 * 1024)

    if not REPORT_SCANNER.exists():
        print("[catalogo] ERRORE: esegui prima lo scanner (scanner_report.csv mancante)")
        sys.exit(1)

    with open(REPORT_SCANNER) as f:
        entries = list(csv.DictReader(f))

    # Solo trovati
    trovati = [e for e in entries if e.get("trovata", "") == "SI"]
    print(f"[catalogo] Analisi {len(trovati)} siti con sezione trovata")

    def progress(done, total, ok):
        print(f"  [{done}/{total}] pagine caricate: {ok}", flush=True)

    results = asyncio.run(estrai(trovati, progress))
    campi_cat = salva(results)
    report(results, campi_cat)
    print(f"[catalogo] Salvato: {OUTPUT}")


if __name__ == "__main__":
    main()

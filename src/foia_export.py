"""
foia_export.py — Genera foia_targets.json nello schema condiviso
(data-advocacy/schemas/foia_target_schema.json).

Output: reports/foia_targets.json
"""

import csv, json, sys, re, urllib.request
from datetime import date
from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
SCHEMA_LOCAL = Path(__file__).resolve().parent.parent.parent / "data-advocacy" / "schemas" / "foia_target_schema.json"
SCHEMA_URL = "https://raw.githubusercontent.com/dataciviclab/data-advocacy/main/schemas/foia_target_schema.json"
GCS_IPA = "gs://dataciviclab-clean/ipa_enti/*/*.parquet"
LOCAL_IPA = DATA_DIR / "ipa_enti.parquet"


def _slug(nome):
    s = nome.lower().strip().replace("'", "").replace('"', "")
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def carica_pec():
    ipa_path = str(LOCAL_IPA) if LOCAL_IPA.exists() else GCS_IPA
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='us-east-1';")
    rows = con.execute(f"""
        SELECT codice_fiscale_ente, mail1, tipo_mail1, mail2, tipo_mail2
        FROM read_parquet('{ipa_path}')
    """).fetchdf()
    pec_map = {}
    for _, r in rows.iterrows():
        cf = r['codice_fiscale_ente']
        if not cf:
            continue
        pec = ''
        for m, t in [('mail1', 'tipo_mail1'), ('mail2', 'tipo_mail2')]:
            if r.get(t) and isinstance(r[t], str) and r[t].lower() == 'pec' and r.get(m) and isinstance(r[m], str):
                pec = r[m].strip()
                break
        pec_map[cf] = pec
    return pec_map


def genera():
    csv.field_size_limit(10 * 1024 * 1024)

    # Leggi scanner report
    with open(DATA_DIR / "scanner_report.csv") as f:
        scan = list(csv.DictReader(f))

    # Leggi PEC
    pec_map = carica_pec()
    print(f"[foia] PEC caricate: {len(pec_map)}")

    targets = []
    for row in scan:
        if row['categoria'] != 'controllo_pubblico':
            continue

        cf = row['cf']
        trovata = row['trovata'] == 'SI'
        errore = row['errore']
        pec = pec_map.get(cf, '')
        denominazione = row['denominazione'].strip("'\" ")

        if trovata:
            continue  # ha la sezione, non serve FOIA

        if errore:
            violazione = "non_verificabile"
            norma = "Art. 2-bis D.Lgs 33/2013"
            priorita = 3
            dettaglio = f"Non verificabile: {errore}"
        else:
            violazione = "nessuna_sezione"
            norma = "Art. 2-bis D.Lgs 33/2013"
            priorita = 1
            dettaglio = "Sito raggiungibile ma nessuna sezione trasparenza trovata"

        targets.append({
            "id": _slug(denominazione),
            "denominazione": denominazione,
            "pec": pec or "",
            "codice_fiscale": cf,
            "sito_web": row['sito'],
            "categoria": "controllo_pubblico",
            "violazione": violazione,
            "norma_violata": norma,
            "priorita": priorita,
            "dettaglio": dettaglio,
            "fonte_dato": f"scan {date.today().isoformat()}",
            "metadata": {"tipo_controllo": "controllo_pubblico"},
        })

    targets.sort(key=lambda t: (t['priorita'], t['denominazione']))

    output = {
        "fonte": "partecipate-monitor",
        "data_generazione": date.today().isoformat(),
        "targets": targets,
    }

    # Valida contro schema (locale o GitHub)
    import jsonschema
    schema = None
    if SCHEMA_LOCAL.exists():
        with open(SCHEMA_LOCAL) as f:
            schema = json.load(f)
    else:
        try:
            resp = urllib.request.urlopen(SCHEMA_URL, timeout=5)
            schema = json.loads(resp.read())
        except Exception as e:
            print(f"[foia] ERRORE: impossibile caricare schema ({e})", file=sys.stderr)
            sys.exit(1)
    try:
        jsonschema.validate(instance=output, schema=schema)
    except jsonschema.ValidationError as e:
        print(f"[foia] ERRORE validazione schema: {e}", file=sys.stderr)
        sys.exit(1)
    print("[foia] Validazione schema: OK")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "foia_targets.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    p1 = sum(1 for t in targets if t['priorita'] == 1)
    p3 = sum(1 for t in targets if t['priorita'] == 3)
    con_pec = sum(1 for t in targets if t['pec'])
    print(f"\n[foia] Report: {out_path}")
    print(f"[foia] Target totali: {len(targets)}")
    print(f"[foia]   P1 (urgente):       {p1}")
    print(f"[foia]   P3 (non verificab.): {p3}")
    print(f"[foia]   Con PEC:            {con_pec}")
    print(f"[foia]   Senza PEC:          {len(targets) - con_pec}")


if __name__ == "__main__":
    genera()

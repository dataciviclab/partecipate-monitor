"""
foia_export.py — Genera foia_targets.json nello schema condiviso
(data-advocacy/schemas/foia_target_schema.json).

Produce priorità:
  P1: partecipate in controllo pubblico senza sezione trasparenza
  P2: partecipate in controllo pubblico con sezione ma solo PDF
  P3: partecipate non controllo senza sezione

Output: reports/foia_targets.json
"""

import csv, json, sys, os
from datetime import date
from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "data-advocacy" / "schemas" / "foia_target_schema.json"

GCS_IPA = "gs://dataciviclab-clean/ipa_enti/*/*.parquet"
LOCAL_IPA = DATA_DIR / "ipa_enti.parquet"


def _slug(nome):
    """Genera slug da denominazione."""
    import re
    s = nome.lower().strip()
    s = s.replace("'", "").replace('"', "")
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def carica_ipa_con_pec():
    """Carica IPA con PEC da cache locale o GCS."""
    ipa_path = str(LOCAL_IPA) if LOCAL_IPA.exists() else GCS_IPA
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='us-east-1';")
    
    q = f"""
    SELECT codice_fiscale_ente, denominazione_ente, sito_istituzionale,
           mail1, tipo_mail1, mail2, tipo_mail2, mail3, tipo_mail3,
           tipologia
    FROM read_parquet('{ipa_path}')
    """
    df = con.execute(q).fetchdf()
    
    # Estrai PEC: prima mail con tipo_mail = 'Pec'
    pec_map = {}
    for _, r in df.iterrows():
        cf = r['codice_fiscale_ente']
        if not cf:
            continue
        pec = ''
        for m, t in [('mail1', 'tipo_mail1'), ('mail2', 'tipo_mail2'), ('mail3', 'tipo_mail3')]:
            tipo = r.get(t)
            val = r.get(m)
            if tipo and isinstance(tipo, str) and tipo.lower() == 'pec' and val and isinstance(val, str):
                pec = val.strip()
                break
        pec_map[cf] = {
            'pec': pec,
            'denominazione_ipa': r['denominazione_ente'],
            'sito': r['sito_istituzionale'],
            'tipologia_ipa': r['tipologia'],
        }
    return pec_map


def genera_targets():
    print("[foia] Carica dati scan...")
    
    with open(DATA_DIR / "scanner_report.csv") as f:
        scanner = list(csv.DictReader(f))
    
    # Carica catalogo se esiste
    catalogo = {}
    catalogo_path = DATA_DIR / "catalogo.csv"
    if catalogo_path.exists():
        with open(catalogo_path) as f:
            for r in csv.DictReader(f):
                catalogo[r['cf']] = r
    
    # Carica formati se esiste
    formati_path = DATA_DIR / "formati_report.json"
    formati_aperti = set()
    # Nota: formati.py non salva dettaglio per CF. Per ora usiamo catalogo.
    
    print("[foia] Carica PEC da IPA...")
    pec_map = carica_ipa_con_pec()
    print(f"[foia]   {len(pec_map)} enti con PEC")
    
    targets = []
    
    for row in scanner:
        cf = row['cf']
        trovata = row['trovata'] == 'SI'
        denominazione = row['denominazione']
        sito = row['sito']
        categoria = row['categoria']
        errore = row['errore']
        
        # Dati IPA
        info_ipa = pec_map.get(cf, {})
        pec = info_ipa.get('pec', '')
        
        # Dati catalogo
        info_cat = catalogo.get(cf, {})
        score = float(info_cat.get('score', 0)) if info_cat else 0
        ragg = info_cat.get('raggiungibile', '') == 'TRUE'
        
        # Determina violazione e priorità
        if categoria == 'controllo_pubblico':
            if not trovata and not errore:
                violazione = "nessuna_sezione"
                norma = "Art. 2-bis D.Lgs 33/2013"
                priorita = 1
                dettaglio = "Sito raggiungibile ma nessuna sezione trasparenza trovata"
            elif not trovata and errore:
                violazione = "non_verificabile"
                norma = "Art. 2-bis D.Lgs 33/2013"
                priorita = 3
                dettaglio = f"Non verificabile: {errore}"
            elif trovata and ragg and score < 30:
                violazione = "sezione_incompleta"
                norma = "Art. 7 D.Lgs 33/2013"
                priorita = 2
                dettaglio = f"Sezione trasparenza presente ma incompleta (score {score}%)"
            elif trovata and ragg and score >= 30:
                # Ha sezione, ora vediamo formati
                # Per ora: se score alto ma nessun dato su formati aperti, segnala
                violazione = "formato_chiuso"
                norma = "Art. 7 D.Lgs 33/2013"
                priorita = 2
                dettaglio = f"Sezione presente (score {score}%) ma formato non verificato"
            else:
                continue
        else:
            # Partecipata non controllo: priorità più bassa
            if not trovata and not errore:
                violazione = "nessuna_sezione"
                norma = "Art. 2-bis c.3 D.Lgs 33/2013"
                priorita = 3
                dettaglio = "Partecipata non controllo senza sezione (obblighi limitati)"
            else:
                continue
        
        target = {
            "id": _slug(denominazione),
            "denominazione": denominazione.strip("'\" "),
            "pec": pec or "",
            "codice_fiscale": cf,
            "sito_web": sito,
            "categoria": categoria,
            "violazione": violazione,
            "norma_violata": norma,
            "priorita": priorita,
            "dettaglio": dettaglio,
            "fonte_dato": f"scan {date.today().isoformat()}",
            "metadata": {
                "score_catalogo": score,
                "regione": "",
                "tipo_controllo": categoria,
            }
        }
        targets.append(target)
    
    # Ordina: priorità poi denominazione
    targets.sort(key=lambda t: (t['priorita'], t['denominazione']))
    
    output = {
        "fonte": "partecipate-monitor",
        "data_generazione": date.today().isoformat(),
        "targets": targets,
    }
    
    # Valida contro schema se presente
    if SCHEMA_PATH.exists():
        try:
            import jsonschema
            with open(SCHEMA_PATH) as f:
                schema = json.load(f)
            jsonschema.validate(instance=output, schema=schema)
            print(f"[foia] Validazione schema: OK")
        except ImportError:
            print("[foia] jsonschema non installato, skip validazione")
        except Exception as e:
            print(f"[foia] ERRORE validazione schema: {e}")
    
    # Salva
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "foia_targets.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Statistiche
    p1 = sum(1 for t in targets if t['priorita'] == 1)
    p2 = sum(1 for t in targets if t['priorita'] == 2)
    p3 = sum(1 for t in targets if t['priorita'] == 3)
    con_pec = sum(1 for t in targets if t['pec'])
    
    print(f"\n[foia] Report: {out_path}")
    print(f"[foia] Target totali: {len(targets)}")
    print(f"[foia]   P1 (urgente - senza sezione):      {p1}")
    print(f"[foia]   P2 (media - formato/incompleto):   {p2}")
    print(f"[foia]   P3 (bassa - non controllo):        {p3}")
    print(f"[foia]   Con PEC:                           {con_pec}")
    print(f"[foia]   Senza PEC:                         {len(targets) - con_pec}")
    
    return output


if __name__ == "__main__":
    genera_targets()

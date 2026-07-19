"""
report.py — Genera report JSON con profili intelligence.

Modalità:
  report.py              → dashboard classica (scanner + catalogo + formati)
  report.py --profili    → aggiunge profili intelligence a data.json
"""

import json, csv, sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

FILES = {
    "scanner": DATA_DIR / "scanner_report.json",
    "catalogo": DATA_DIR / "catalogo.csv",
    "formati": DATA_DIR / "formati_report.json",
}


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
    dati["trend"] = carica_trend()
    dati["generato_il"] = datetime.now().isoformat()
    return dati


def genera_profili():
    """Profili intelligence per le partecipate MEF centrali."""
    from profiler import profila_lista
    from fetch_data import estrai_partecipate

    print("[report] Caricamento profili intelligence...")
    partecipate = estrai_partecipate(solo_mef_centrali=True)
    print(f"[report] Partecipate centrali: {len(partecipate)}")
    profili = profila_lista(partecipate)
    return profili


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    dati = carica_dati()

    if "--profili" in sys.argv:
        profili = genera_profili()
        dati["profili"] = profili

    with open(REPORTS_DIR / "data.json", "w") as f:
        json.dump(dati, f, indent=2, ensure_ascii=False)
    print(f"[report] Aggiornato: reports/data.json")


if __name__ == "__main__":
    main()

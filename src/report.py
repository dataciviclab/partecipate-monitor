"""
report.py — Genera reports/data.json con i profili intelligence.
"""

import json, sys
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def main():
    from profiler import profila_lista
    from fetch_data import estrai_partecipate

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("[report] Profili intelligence...")
    partecipate = estrai_partecipate(solo_mef_centrali=True)
    profili = profila_lista(partecipate)

    dati = {
        "generato_il": datetime.now().isoformat(),
        "profili": profili,
    }

    with open(REPORTS_DIR / "data.json", "w") as f:
        json.dump(dati, f, indent=2, ensure_ascii=False)
    print(f"[report] Fatto: reports/data.json ({len(profili)} profili)")


if __name__ == "__main__":
    main()

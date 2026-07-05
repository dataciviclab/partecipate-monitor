#!/usr/bin/env bash
# run_all.sh — Esegue l'intera pipeline del monitor
set -euo pipefail

echo "=== partecipate-monitor: RUN ALL ==="
echo ""

echo "1. Fetch data (MEF + IPA)"
python src/fetch_data.py
echo ""

echo "2. Scanner trasparenza"
python src/scanner.py --solo-controllo
echo ""

echo "3. Catalogo categorie"
python src/catalogo.py
echo ""

echo "4. Analisi formati"
python src/formati.py
echo ""

echo "5. Genera report"
python src/report.py
echo ""

echo "=== DONE ==="

#!/usr/bin/env bash
# update_history.sh — Salva snapshot giornaliero dei risultati
set -euo pipefail

DATE=$(date +%Y-%m-%d)
HIST_DIR="data/history/$DATE"

mkdir -p "$HIST_DIR"

# Copia gli ultimi report
for f in data/scanner_report.json data/catalogo.csv data/formati_report.json reports/index.md reports/data.json; do
    if [ -f "$f" ]; then
        cp "$f" "$HIST_DIR/"
    fi
done

echo "[history] Snapshot salvato in $HIST_DIR"

"""
Test: foia_export.py produce output valido secondo lo schema condiviso.
Esegue l'export su dati reali (max 10 siti) e valida l'output.
"""

import json, sys, subprocess, tempfile
from pathlib import Path

# Usa lo schema dal path locale o da GitHub
SCHEMA_LOCAL = Path(__file__).resolve().parent.parent.parent / "data-advocacy" / "schemas" / "foia_target_schema.json"
SCHEMA_URL = "https://raw.githubusercontent.com/dataciviclab/data-advocacy/main/schemas/foia_target_schema.json"


def _carica_schema():
    if SCHEMA_LOCAL.exists():
        with open(SCHEMA_LOCAL) as f:
            return json.load(f)
    import urllib.request
    resp = urllib.request.urlopen(SCHEMA_URL, timeout=5)
    return json.loads(resp.read())


def test_foia_export_output_valido():
    """Esegue foia_export.py e verifica che l'output rispetti lo schema."""
    repo_root = Path(__file__).resolve().parent.parent

    # Esegue foia_export.py
    result = subprocess.run(
        [sys.executable, str(repo_root / "src" / "foia_export.py")],
        cwd=repo_root, capture_output=True, text=True, timeout=60,
    )
    # Deve terminare con successo
    assert result.returncode == 0, f"foia_export.py fallito:\n{result.stderr}"

    # Legge l'output
    out_path = repo_root / "reports" / "foia_targets.json"
    assert out_path.exists(), "foia_targets.json non generato"
    with open(out_path) as f:
        output = json.load(f)

    # Valida contro schema
    import jsonschema
    schema = _carica_schema()
    jsonschema.validate(instance=output, schema=schema)

    # Verifica struttura minima
    assert "fonte" in output, "manca 'fonte'"
    assert "data_generazione" in output, "manca 'data_generazione'"
    assert "targets" in output, "manca 'targets'"
    assert isinstance(output["targets"], list), "'targets' non è una lista"
    if output["targets"]:
        t = output["targets"][0]
        for campo in ("id", "denominazione", "violazione", "priorita"):
            assert campo in t, f"manca '{campo}' nel target"

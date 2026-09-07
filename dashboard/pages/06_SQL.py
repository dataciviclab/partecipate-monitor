"""Query SQL — Interroga direttamente i dati delle partecipate pubbliche."""

from pathlib import Path

from lab_connectors.duckdb.sql_page import render_sql_query
from lab_connectors.registry import load_registry

registry = load_registry(Path(__file__).parent.parent.parent / "registry" / "registry.json")

render_sql_query(
    registry=registry,
    prefix="partecipate-pubbliche",
    default_slug="mef_partecipazioni",
    title="Query SQL",
    description=(
        "Interroga direttamente i dati MEF delle partecipate pubbliche. "
        "Usa ``clean_input`` come nome della tabella virtuale."
    ),
)

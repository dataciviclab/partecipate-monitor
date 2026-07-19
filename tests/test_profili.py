"""
Gold set test per profiler intelligence.

Verifica che i profili delle partecipate centrali abbiano metriche
coerenti con i valori attesi. Previene regressioni silenziose.
"""

import json, sys, pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from profiler import profila_cf, FATTI

if not Path(FATTI).exists():
    pytest.skip(
        f"Tabella fatti non trovata: {FATTI}\n"
        "Esegui 'make build' o 'python src/build_fatti.py' prima di lanciare i test.",
        allow_module_level=True,
    )

# Gold set: CF → metriche minime attese
# (basate su dati MEF 2023)
GOLD = {
    "97103880585": {  # Poste Italiane
        "denominazione": "POSTE ITALIANE",
        "addetti_min": 100000,
        "addetti_max": 120000,
        "score_esposizione_min": 60,
        "ha_appalti": True,
        "ha_aiuti": True,
        "ha_governance": True,
    },
    "00401990585": {  # Leonardo
        "denominazione": "LEONARDO",
        "addetti_min": 25000,
        "addetti_max": 35000,
        "score_esposizione_min": 15,
        "ha_appalti": False,
        "ha_aiuti": True,
        "ha_governance": True,
    },
    "06382641006": {  # RAI
        "denominazione": "RAI",
        "addetti_min": 10000,
        "addetti_max": 15000,
        "score_esposizione_min": 30,
        "ha_appalti": True,
        "ha_aiuti": True,
        "ha_governance": True,
    },
    "00484960588": {  # ENI
        "denominazione": "ENI",
        "addetti_min": 8000,
        "addetti_max": 15000,
        "score_esposizione_min": 40,
        "ha_appalti": True,
        "ha_aiuti": True,
        "ha_governance": True,
    },
    "00811720580": {  # ENEL
        "denominazione": "ENEL",
        "addetti_min": 500,
        "addetti_max": 2000,
        "score_esposizione_min": 15,
        "ha_appalti": True,
        "ha_aiuti": True,
        "ha_governance": True,
    },
    "11957540153": {  # A2A
        "denominazione": "A2A",
        "addetti_min": 10000,
        "addetti_max": 15000,
        "score_esposizione_min": 40,
        "ha_appalti": True,
        "ha_aiuti": True,
        "ha_governance": True,
    },
    "05754381001": {  # GSE
        "denominazione": "GSE",
        "addetti_min": 500,
        "addetti_max": 1000,
        "score_esposizione_min": 15,
        "ha_appalti": True,
        "ha_aiuti": False,
        "ha_governance": True,
        "ha_valore_produzione": True,  # CO.ED.P. popolato (non IAS)
    },
}


def test_gold_profili():
    """Testa ogni CF del gold set contro metriche attese."""
    errati = []
    for cf, attesi in GOLD.items():
        profilo = profila_cf(cf)

        if "errore" in profilo:
            errati.append(f"{cf}: errore profilo — {profilo['errore']}")
            continue

        # Denominazione
        if attesi["denominazione"].lower() not in profilo.get("denominazione", "").lower():
            errati.append(f"{cf}: denominazione non contiene '{attesi['denominazione']}'")

        # Addetti
        addetti = profilo.get("assetto", {}).get("addetti", 0) or 0
        if addetti < attesi["addetti_min"] or addetti > attesi["addetti_max"]:
            errati.append(f"{cf}: addetti {addetti} fuori range [{attesi['addetti_min']}, {attesi['addetti_max']}]")

        # Score esposizione
        score_esp = profilo.get("score", {}).get("esposizione", 0)
        if score_esp < attesi["score_esposizione_min"]:
            errati.append(f"{cf}: score esposizione {score_esp} < minimo {attesi['score_esposizione_min']}")

        # Appalti
        ha_appalti = bool(profilo.get("appalti"))
        if ha_appalti != attesi["ha_appalti"]:
            errati.append(f"{cf}: ha_appalti={ha_appalti} atteso={attesi['ha_appalti']}")

        # Aiuti
        ha_aiuti = bool(profilo.get("aiuti_stato"))
        if ha_aiuti != attesi["ha_aiuti"]:
            errati.append(f"{cf}: ha_aiuti={ha_aiuti} atteso={attesi['ha_aiuti']}")

        # Governance
        ha_governance = bool(profilo.get("governance"))
        if ha_governance != attesi["ha_governance"]:
            errati.append(f"{cf}: ha_governance={ha_governance} atteso={attesi['ha_governance']}")

        # Valore produzione (CO.E.P.)
        if attesi.get("ha_valore_produzione"):
            vp = profilo.get("assetto", {}).get("valore_produzione")
            if not vp:
                errati.append(f"{cf}: valore_produzione assente ma atteso")

    assert not errati, "\n".join(errati)

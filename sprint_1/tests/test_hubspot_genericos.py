"""Tests pytest para R-DVV-12 — detección de firmas HubSpot genéricas repetidas.

Espejo de TEST O de `test_fase2.py`. Cuando ≥3 clientes en una corrida tienen
la misma triple `(consultor, actividad, ingresos)` desde HubSpot, esa firma se
marca como genérica y para esos clientes el pipeline cae a REGISTROS para los
campos cliente (manteniendo cc/email/phone/contact_id de HubSpot).
"""
from __future__ import annotations

import pytest

from pipeline_davivienda import detectar_hubspot_genericos


class _MockHubSpot:
    """Mock minimal de HubSpotClient para tests."""

    def __init__(self, mapping: dict):
        self.mapping = mapping  # nombre -> dict(actividad, ingresos)

    def match_contact_cascade(self, cedula, email, nombre, properties):
        d = self.mapping.get(nombre, {})
        if not d:
            return {}
        return {
            "matched_by": "nombre",
            "contact": {
                "id": "x",
                "properties": {
                    "hubspot_owner_id": "",
                    "actividad_economica": d.get("actividad", ""),
                    "ingresos_demostrables": d.get("ingresos", ""),
                },
            },
        }

    def get_owner(self, owner_id):
        return {"firstName": "", "lastName": ""}


def _pendientes(*nombres) -> list[dict]:
    return [
        {"row_idx": i + 1, "nombre": n, "cc": str(i + 1), "email": f"x{i}@x"}
        for i, n in enumerate(nombres)
    ]


# ---- Caso canónico: 3 clientes misma firma → marcada genérica ---------
def test_detecta_firma_repetida_3_clientes():
    mapping = {
        "CLIENTE A": {"actividad": "Vis Davivienda", "ingresos": "$3,186,000"},
        "CLIENTE B": {"actividad": "Vis Davivienda", "ingresos": "$3,186,000"},
        "CLIENTE C": {"actividad": "Vis Davivienda", "ingresos": "$3,186,000"},
        "CLIENTE D": {"actividad": "Empleado", "ingresos": "$5,000,000"},
    }
    hs = _MockHubSpot(mapping)
    pendientes = _pendientes("CLIENTE A", "CLIENTE B", "CLIENTE C", "CLIENTE D")
    firmas = detectar_hubspot_genericos(hs, pendientes, umbral=3)
    assert len(firmas) == 1
    firma_esperada = ("", "Vis Davivienda", "$3,186,000")
    assert firma_esperada in firmas
    # Cliente D firma única — NO genérica
    firma_d = ("", "Empleado", "$5,000,000")
    assert firma_d not in firmas


# ---- Umbral: solo 2 clientes con misma firma → NO marcada -------------
def test_no_marca_si_menos_que_umbral():
    mapping = {
        "A": {"actividad": "Vis", "ingresos": "$1,000,000"},
        "B": {"actividad": "Vis", "ingresos": "$1,000,000"},
        "C": {"actividad": "Empleado", "ingresos": "$2,000,000"},
    }
    hs = _MockHubSpot(mapping)
    firmas = detectar_hubspot_genericos(hs, _pendientes("A", "B", "C"), umbral=3)
    assert len(firmas) == 0, f"con umbral=3 y solo 2 repetidos NO marca, got {firmas}"


# ---- Umbral configurable: con umbral=2, sí marca ----------------------
def test_umbral_configurable():
    mapping = {
        "A": {"actividad": "X", "ingresos": "$1k"},
        "B": {"actividad": "X", "ingresos": "$1k"},
    }
    hs = _MockHubSpot(mapping)
    firmas = detectar_hubspot_genericos(hs, _pendientes("A", "B"), umbral=2)
    assert len(firmas) == 1


# ---- Múltiples firmas genéricas simultáneas ---------------------------
def test_multiples_firmas_genericas():
    mapping = {
        "A1": {"actividad": "Vis", "ingresos": "$3M"},
        "A2": {"actividad": "Vis", "ingresos": "$3M"},
        "A3": {"actividad": "Vis", "ingresos": "$3M"},
        "B1": {"actividad": "Empleado", "ingresos": "$5M"},
        "B2": {"actividad": "Empleado", "ingresos": "$5M"},
        "B3": {"actividad": "Empleado", "ingresos": "$5M"},
    }
    hs = _MockHubSpot(mapping)
    firmas = detectar_hubspot_genericos(
        hs, _pendientes(*mapping.keys()), umbral=3
    )
    assert len(firmas) == 2


# ---- Sin matches en HubSpot: 0 firmas genéricas -----------------------
def test_sin_matches_no_marca():
    """Si HubSpot no responde a ningún cliente, no hay firmas que marcar."""
    hs = _MockHubSpot({})  # mapping vacío → todos los matches retornan {}
    firmas = detectar_hubspot_genericos(hs, _pendientes("A", "B", "C"), umbral=3)
    assert len(firmas) == 0

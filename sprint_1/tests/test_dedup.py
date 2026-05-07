"""Tests pytest para `dedup_por_credito` (B9 idempotencia STAGING).

Espejo de TEST P en `test_fase2.py` (script lineal golden), expresado como
funciones pytest individuales para facilitar futura migracion a CI.
"""
from __future__ import annotations

import pytest

from listar_pendientes_hoy import dedup_por_credito


def test_primera_corrida_staging_vacia():
    pendientes = [{"credito": "A1"}, {"credito": "A2"}, {"credito": "A3"}]
    nuevos = dedup_por_credito(pendientes, set())
    assert len(nuevos) == 3
    assert [p["credito"] for p in nuevos] == ["A1", "A2", "A3"]


def test_segunda_corrida_idempotente():
    """Re-ejecutar listar_pendientes con los mismos creditos no duplica."""
    pendientes = [{"credito": "A1"}, {"credito": "A2"}]
    creditos_en_staging = {"A1", "A2"}
    nuevos = dedup_por_credito(pendientes, creditos_en_staging)
    assert nuevos == [], f"idempotencia rota: dio {nuevos}"


def test_corrida_con_uno_nuevo_y_dos_existentes():
    pendientes = [
        {"credito": "A1"},
        {"credito": "A2"},
        {"credito": "A4"},  # nuevo
    ]
    nuevos = dedup_por_credito(pendientes, {"A1", "A2"})
    assert len(nuevos) == 1
    assert nuevos[0]["credito"] == "A4"


def test_whitespace_en_credito():
    """Espacios en bordes no deben generar falsos negativos en dedup."""
    pendientes = [
        {"credito": "  A1  "},  # ya esta (con espacios)
        {"credito": "A99"},     # nuevo
    ]
    nuevos = dedup_por_credito(pendientes, {"A1"})
    assert len(nuevos) == 1
    assert nuevos[0]["credito"] == "A99"


def test_pendiente_sin_clave_credito_no_crash():
    """Defensivo: missing key no debe romper la funcion."""
    pendientes = [{"nombre": "X sin credito"}, {"credito": "A1"}]
    nuevos = dedup_por_credito(pendientes, {"OTRO_ID"})
    # Pendiente sin credito pasa (string vacio not in set), el otro tambien
    assert len(nuevos) == 2


@pytest.mark.parametrize("staging,esperados", [
    (set(), 3),
    ({"A1"}, 2),
    ({"A1", "A2"}, 1),
    ({"A1", "A2", "A3"}, 0),
])
def test_progresion_acumulada(staging: set, esperados: int):
    """A medida que STAGING acumula, dedup remueve mas."""
    pendientes = [{"credito": "A1"}, {"credito": "A2"}, {"credito": "A3"}]
    nuevos = dedup_por_credito(pendientes, staging)
    assert len(nuevos) == esperados

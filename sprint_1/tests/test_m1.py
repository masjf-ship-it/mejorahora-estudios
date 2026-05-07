"""Tests pytest para validador M1 (`validar_extraccion_davivienda::validar_datos_cliente`).

Espejo de TESTS I, J, K, L, M de `test_fase2.py` (script lineal golden),
expresados como funciones pytest individuales.

M1 vive en `validar_extraccion_davivienda.py`, stdlib only. La fixture
construye instancias de `DatosClienteExcel` (de `excel_populator.py`,
que requiere openpyxl — incluido en `requirements.txt`).
"""
from __future__ import annotations

import pytest

from excel_populator import DatosClienteExcel
from validar_extraccion_davivienda import validar_datos_cliente


def _datos_fernando_canonicos(**overrides) -> DatosClienteExcel:
    """Helper: caso base que SIEMPRE pasa M1 (Fernando canónico).

    Cada test override solo lo que quiera fallar.
    """
    base = dict(
        credito_id="570238110001018-4",
        nombre="FERNANDO RODRIGO GALLO MARTINEZ",
        banco="DAVIVIENDA",
        cuota_mensual=229000.0,
        plazo_inicial=240,
        plazo_pendiente=137,
        tasa_ea=0.12,
        frech_subsidio=0.0,
        seguro_vida=29383.0,
        seguro_incendio=52976.0,
        seguro_terremoto=12758.0,
        capital_mensual=35608.0,
        interes_mensual=99275.0,
        saldo_capital=12_985_250.0,
        consultor="YERINSON JESUS SALINAS PERDOMO",
        actividad_economica="Vis Davivienda",
        abono_efectivo=200_000.0,
        ingresos=4_800_000.0,
    )
    base.update(overrides)
    return DatosClienteExcel(**base)


# ---- TEST I — saldo bajo ----------------------------------------------
def test_m1_falla_saldo_capital_bajo():
    datos = _datos_fernando_canonicos(saldo_capital=500_000.0)
    ok, errores, _ = validar_datos_cliente(datos)
    assert ok is False
    assert any("saldo_capital sospechosamente bajo" in e for e in errores), \
        f"err esperado 'saldo bajo', got {errores}"


# ---- TEST J — caso happy path -----------------------------------------
def test_m1_pasa_caso_canonico_fernando():
    datos = _datos_fernando_canonicos()
    ok, errores, _ = validar_datos_cliente(datos)
    assert ok is True, f"err inesperados: {errores}"
    assert errores == []


# ---- TEST K — plazo_pendiente > plazo_inicial -------------------------
def test_m1_falla_plazo_pendiente_mayor_inicial():
    datos = _datos_fernando_canonicos(plazo_inicial=100, plazo_pendiente=200)
    ok, errores, _ = validar_datos_cliente(datos)
    assert ok is False
    assert any("plazo_pendiente" in e and "imposible" in e for e in errores), \
        f"err esperado 'plazo imposible', got {errores}"


# ---- TEST L — tasa_ea sin normalizar -----------------------------------
def test_m1_falla_tasa_no_normalizada():
    datos = _datos_fernando_canonicos(tasa_ea=14.31)
    ok, errores, _ = validar_datos_cliente(datos)
    assert ok is False
    assert any("tasa_ea parece porcentaje" in e for e in errores), \
        f"err esperado 'tasa sin normalizar', got {errores}"


# ---- TEST M — seguro_vida=0 con incendio>0 (R-DVV-10) -----------------
def test_m1_falla_seguro_vida_cero_con_incendio_positivo():
    datos = _datos_fernando_canonicos(
        seguro_vida=0.0, seguro_incendio=23_730.0,
        # ajustar capital/intereses para que la suma siga siendo razonable
        cuota_mensual=1_092_000.0, capital_mensual=113_807.0,
        interes_mensual=930_193.0, plazo_pendiente=218,
        saldo_capital=91_419_952.0, tasa_ea=0.129,
    )
    ok, errores, _ = validar_datos_cliente(datos)
    assert ok is False
    assert any("seguro_vida=0" in e and "incendio" in e for e in errores), \
        f"err esperado 'seguro_vida=0 con incendio', got {errores}"


@pytest.mark.parametrize("tasa,esperado_ok", [
    (0.0001, True),    # tasa muy pequeña pero positiva
    (0.50, True),      # decimal alto pero válido
    (0.0, False),      # tasa 0
    (1.5, False),      # > 1 sin normalizar
])
def test_m1_rango_tasa_ea(tasa: float, esperado_ok: bool):
    datos = _datos_fernando_canonicos(tasa_ea=tasa)
    ok, _, _ = validar_datos_cliente(datos)
    assert ok is esperado_ok, f"tasa={tasa} esperaba ok={esperado_ok}"

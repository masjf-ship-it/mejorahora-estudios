"""Tests pytest para R-DVV-07 — proyección a 6ta cuota Davivienda/DaviBank.

Espejo de TESTS A, B, C de `test_fase2.py` (golden lineal). Validan que
`proyectar_sexta_cuota()` aplica solo cuando:
  - banco ∈ {DAVIVIENDA, DAVIBANK}
  - cuotas_pagadas < 6

y proyecta `saldo_capital` + reduce `plazo_pendiente` los meses faltantes.
"""
from __future__ import annotations

import pytest

from excel_populator import DatosClienteExcel
from pipeline_davivienda import proyectar_sexta_cuota


def _datos_julieth_canonica(**overrides) -> DatosClienteExcel:
    """Caso canónico Julieth: Davivienda, cuotas_pagadas=2 (plazo_pend=238).

    R-DVV-07 DEBE aplicar y proyectar a cuotas_pagadas=6.
    """
    base = dict(
        credito_id="570000601203902-9",
        nombre="JULIETH VALENCIA RAMIREZ",
        banco="DAVIVIENDA",
        cuota_mensual=1_633_000.0,
        plazo_inicial=240,
        plazo_pendiente=238,
        tasa_ea=0.131,
        frech_subsidio=0.0,
        seguro_vida=32_685.0,
        seguro_incendio=43_666.0,
        seguro_terremoto=0.0,
        capital_mensual=133_042.0,
        interes_mensual=1_422_958.0,
        saldo_capital=137_943_278.0,
        consultor="BRILLID SALINAS",
        actividad_economica="Vis",
        abono_efectivo=500_000.0,
        ingresos=4_000_000.0,
    )
    base.update(overrides)
    return DatosClienteExcel(**base)


# ---- TEST A — R-DVV-07 aplica (caso canónico Julieth) -----------------
def test_rdvv07_aplica_julieth():
    datos = _datos_julieth_canonica()
    datos, info = proyectar_sexta_cuota(datos)
    assert info["aplicada"] is True
    assert info["meses"] == 4, f"meses faltantes esperado 4, got {info['meses']}"
    assert info["cuotas_pagadas_antes"] == 2
    assert datos.plazo_pendiente == 234, f"esperado 234, got {datos.plazo_pendiente}"
    # Tolerancia ±$5k en saldo proyectado (aritmética PMT con redondeo tasa_mv)
    esperado = 137_087_668.0
    diff = abs(datos.saldo_capital - esperado)
    assert diff <= 5_000.0, (
        f"saldo_capital {datos.saldo_capital:,.0f} vs esperado {esperado:,.0f} "
        f"(diff {diff:,.0f} > tol 5000)"
    )


# ---- TEST B — R-DVV-07 NO aplica si cuotas_pagadas >= 6 ----------------
def test_rdvv07_no_aplica_cuotas_ge_6():
    datos = _datos_julieth_canonica(plazo_pendiente=230)  # cuotas_pagadas = 10
    saldo_antes = datos.saldo_capital
    plazo_antes = datos.plazo_pendiente
    datos, info = proyectar_sexta_cuota(datos)
    assert info["aplicada"] is False
    assert datos.saldo_capital == saldo_antes, "saldo intacto cuando R-DVV-07 no aplica"
    assert datos.plazo_pendiente == plazo_antes, "plazo intacto"


# ---- TEST C — R-DVV-07 NO aplica a bancos != Davivienda/DaviBank ------
@pytest.mark.parametrize("banco", ["BANCOLOMBIA", "BANCO DE BOGOTA", "CAJA SOCIAL", "AV VILLAS"])
def test_rdvv07_no_aplica_otros_bancos(banco: str):
    datos = _datos_julieth_canonica(banco=banco)  # cuotas_pagadas=2 pero banco distinto
    saldo_antes = datos.saldo_capital
    datos, info = proyectar_sexta_cuota(datos)
    assert info["aplicada"] is False, f"R-DVV-07 NO debe aplicar a {banco}"
    assert datos.saldo_capital == saldo_antes


# ---- DaviBank (mismo grupo Davivienda, MOM §1.1) ----------------------
def test_rdvv07_aplica_davibank():
    """R-DVV-07 también aplica a DaviBank (MOM §1.1)."""
    datos = _datos_julieth_canonica(banco="DAVIBANK")
    datos, info = proyectar_sexta_cuota(datos)
    assert info["aplicada"] is True, "DaviBank usa misma política que Davivienda"


# ---- Edge: cuotas_pagadas=5 (justo en el borde) ------------------------
def test_rdvv07_borde_cuotas_pagadas_5():
    """Cuotas pagadas = 5 (plazo_pend = plazo_inicial - 5). Aplica con meses=1."""
    datos = _datos_julieth_canonica(plazo_pendiente=235)
    datos, info = proyectar_sexta_cuota(datos)
    assert info["aplicada"] is True
    assert info["meses"] == 1
    assert info["cuotas_pagadas_antes"] == 5


# ---- Edge: cuotas_pagadas=6 (umbral exacto) ----------------------------
def test_rdvv07_no_aplica_borde_cuotas_pagadas_6():
    """Cuotas pagadas = 6 exacto: NO aplica (política banco ya cumplida)."""
    datos = _datos_julieth_canonica(plazo_pendiente=234)
    datos, info = proyectar_sexta_cuota(datos)
    assert info["aplicada"] is False

"""Tests pytest para R-DVV-18 — guardia plazo pendiente + pre-check Ley 546.

Caso real (2026-05-05, Alexandra Bernal Vargas): el proponedor generaba
opciones de 150+ cuotas para un cliente con 29 cuotas pendientes, doble
violación: (1) extender plazo (anti-§20.12); (2) Ley 546 (crédito total
< 5 años, no es viable).

Fix:
  A. Wrapper `proponer_plazos()` filtra cualquier opción >= plazo_pend_anos.
  B. `_proponer_mixto_viable` y `_proponer_por_saltos_100k` techos
     `max(anio_max, ceil(anio_min_legal))` solo si `anio_min_legal < plazo_pend_anos`.

Estos tests blindan el wrapper para cualquier método (Mode A, B, E, manual,
escalonado) usando inputs que históricamente disparaban opciones extensoras.
"""
from __future__ import annotations

import pytest

from proponedor_plazos import proponer_plazos


# ---- CASO ALEXANDRA — pre-check Ley 546 + guardia ---------------------
def test_rdvv18_alexandra_bernal_no_extiende():
    """29 cuotas pendientes (2.42 años), plazo_pagado=0. Ley 546 exige
    crédito_total >= 5 años. Antes generaba opciones >= 30 cuotas.

    El wrapper debe filtrar cualquier opción >= 2.42 años (29/12).
    El pipeline pre-check separately abortaria con NO_VIABLE_LEY_546,
    pero aquí validamos directamente el wrapper del proponedor.
    """
    propuesta = proponer_plazos(
        plazo_pendiente_meses=29,
        tasa_ea=0.107,
        saldo=10_000_000,
        seguros_totales=50_000,
        ingresos_cliente=2_000_000,
        plazo_pagado_meses=0,
    )
    plazo_pend_anos = 29 / 12.0
    for p in propuesta.plazos_anos:
        assert p < plazo_pend_anos, (
            f"R-DVV-18 violado: opción {p:.2f} años >= plazo_pendiente "
            f"{plazo_pend_anos:.2f} años (extension del crédito)."
        )


# ---- Caso normal: cliente con 200 cuotas pendientes -------------------
def test_rdvv18_caso_normal_no_filtra_demas():
    """Plazo pendiente largo (200m = 16.67 años): el wrapper no debe
    filtrar opciones razonables (5-15 años).
    """
    propuesta = proponer_plazos(
        plazo_pendiente_meses=200,
        tasa_ea=0.12,
        saldo=100_000_000,
        seguros_totales=80_000,
        ingresos_cliente=5_000_000,
        plazo_pagado_meses=40,
    )
    assert len(propuesta.plazos_anos) >= 1, "debe retornar al menos 1 opción"
    plazo_pend_anos = 200 / 12.0
    for p in propuesta.plazos_anos:
        assert p < plazo_pend_anos, f"opción {p} >= plazo_pendiente {plazo_pend_anos}"
    # Y debe retornar opciones razonables (no todas <1 año)
    assert max(propuesta.plazos_anos) > 1.0, (
        f"todas las opciones <1 año es sospechoso: {propuesta.plazos_anos}"
    )


# ---- Edge: plazo_pendiente justo en el umbral 5 años ------------------
def test_rdvv18_plazo_60m_borde_ley546():
    """60m = 5 años exactos. Si plazo_pagado=0, anio_min_legal=5.
    El cliente está justo en el umbral. Debe haber pocas opciones viables
    (todas < 5 años) o ninguna si el techo está en 5 estricto.
    """
    propuesta = proponer_plazos(
        plazo_pendiente_meses=60,
        tasa_ea=0.10,
        saldo=20_000_000,
        seguros_totales=60_000,
        ingresos_cliente=3_000_000,
        plazo_pagado_meses=0,
    )
    plazo_pend_anos = 5.0
    for p in propuesta.plazos_anos:
        assert p < plazo_pend_anos, (
            f"opción {p} >= 5 años violaría R-DVV-18 con plazo_pend=60m"
        )


# ---- Manual override también pasa por el wrapper ---------------------
def test_rdvv18_manual_override_filtra_extensores():
    """Si el usuario pasa plazos manuales que incluyen una extensión
    (>= plazo_pendiente), el wrapper debe filtrarlos también.
    """
    propuesta = proponer_plazos(
        plazo_pendiente_meses=120,  # 10 años
        tasa_ea=0.11,
        saldo=50_000_000,
        seguros_totales=50_000,
        plazos_manuales=[8, 9, 10, 12, 15],  # 12 y 15 son extensores (>=10)
    )
    plazo_pend_anos = 10.0
    for p in propuesta.plazos_anos:
        assert p < plazo_pend_anos, (
            f"manual override no debe pasar opción {p} >= {plazo_pend_anos}"
        )
    # Las opciones válidas (8, 9) sí deben estar
    assert any(abs(p - 8.0) < 0.01 for p in propuesta.plazos_anos), (
        f"opción 8 años (válida) debió pasar. got: {propuesta.plazos_anos}"
    )


# ---- Plazo pagado >=5 años: anio_min_legal=0.5 ------------------------
def test_rdvv18_plazo_pagado_largo_no_restringe():
    """Cliente con 100m pagados (8.3 años) + 40m pendientes. Ya cumplió
    los 5 años Ley 546, así que `anio_min_legal=0.5`. Wrapper sigue
    filtrando >= plazo_pendiente (40/12 ≈ 3.33 años).
    """
    propuesta = proponer_plazos(
        plazo_pendiente_meses=40,
        tasa_ea=0.10,
        saldo=10_000_000,
        seguros_totales=40_000,
        ingresos_cliente=4_000_000,
        plazo_pagado_meses=100,
    )
    plazo_pend_anos = 40 / 12.0
    for p in propuesta.plazos_anos:
        assert p < plazo_pend_anos, f"opción {p} viola R-DVV-18"

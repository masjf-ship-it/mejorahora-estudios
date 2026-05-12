"""Tests pytest para `_staging_update` en pipeline_davivienda.

Espejo de TEST H de test_fase2.py. Valida:
  - Nota CRM se escribe en columna L (col 12, 1-based)
  - Nota previa se preserva concatenada con ' | '
  - Nota vacia NO sobreescribe nota existente
  - Si idx no tiene 'nota_crm' (STAGING sin columna), no falla

Fase 3 Mejora #1 — MASTER_RULES §3.8.
"""
from __future__ import annotations

import pytest

from pipeline_davivienda import _staging_update


class _MockWS:
    """Mock minimal de gspread worksheet."""

    def __init__(self, initial_cells: dict | None = None):
        self.cells = dict(initial_cells or {})  # {(row, col): value}

    def update_cell(self, row, col, value):
        self.cells[(row, col)] = value

    def cell(self, row, col):
        class _C:
            def __init__(self, value):
                self.value = value

        return _C(self.cells.get((row, col), ""))


# Columna L = 11 (0-based) → 12 (1-based en gspread)
_IDX_COMPLETO = {"estado": 0, "link_estudio": 1, "nota_crm": 11}


def test_staging_update_escribe_nota_en_columna_L():
    """H.1: nota CRM nueva en row sin nota previa → escrita en col 12."""
    ws = _MockWS()
    _staging_update(
        ws, row_idx=5, idx=_IDX_COMPLETO,
        estado="Excel generado", link="https://drive/x", nota_crm="Nota test",
    )
    assert ws.cells.get((5, 1)) == "Excel generado", "estado en col 1"
    assert ws.cells.get((5, 2)) == "https://drive/x", "link en col 2"
    assert ws.cells.get((5, 12)) == "Nota test", "nota_crm en col 12 (L)"


def test_staging_update_concat_con_nota_previa():
    """H.2: si hay nota previa, concatena con ' | '."""
    ws = _MockWS(initial_cells={(5, 12): "Nota previa del analista"})
    _staging_update(
        ws, row_idx=5, idx=_IDX_COMPLETO,
        estado="Excel generado", link="", nota_crm="R-DVV-07 aplicada",
    )
    esperado = "Nota previa del analista | R-DVV-07 aplicada"
    assert ws.cells.get((5, 12)) == esperado, (
        f"nota previa preservada + concat. got: {ws.cells.get((5, 12))!r}"
    )


def test_staging_update_nota_vacia_no_sobreescribe():
    """H.3: si nota_crm es '', NO toca columna L existente."""
    ws = _MockWS(initial_cells={(5, 12): "Nota existente"})
    _staging_update(
        ws, row_idx=5, idx=_IDX_COMPLETO,
        estado="Excel generado", link="", nota_crm="",
    )
    assert ws.cells.get((5, 12)) == "Nota existente", "nota vacia respeta existente"


def test_staging_update_sin_columna_nota_no_falla():
    """H.4: si idx['nota_crm'] = None, no escribe nada y no rompe."""
    idx_sin_col = {"estado": 0, "link_estudio": 1, "nota_crm": None}
    ws = _MockWS()
    _staging_update(
        ws, row_idx=5, idx=idx_sin_col,
        estado="Excel generado", nota_crm="Intento nota",
    )
    assert (5, 12) not in ws.cells, "sin columna nota_crm, no escribe en col 12"


@pytest.mark.parametrize("nota_previa,nota_nueva,esperado", [
    ("Previa", "Nueva", "Previa | Nueva"),
    ("", "Solo nueva", "Solo nueva"),
    ("Solo previa", "", "Solo previa"),
    ("A", "B | C | D", "A | B | C | D"),
])
def test_staging_update_concat_paramcombinations(nota_previa, nota_nueva, esperado):
    """Cuatro variantes de combinación previa/nueva."""
    ws = _MockWS(initial_cells={(5, 12): nota_previa} if nota_previa else None)
    _staging_update(
        ws, row_idx=5, idx=_IDX_COMPLETO,
        estado="Excel generado", link="", nota_crm=nota_nueva,
    )
    actual = ws.cells.get((5, 12), "")
    assert actual == esperado, f"esperado {esperado!r}, got {actual!r}"

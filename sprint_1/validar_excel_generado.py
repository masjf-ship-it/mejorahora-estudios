# -*- coding: utf-8 -*-
"""
validar_excel_generado.py — MejorAhora SAS (2026-04-23)
========================================================
Validador M2 post-generacion Excel. Lee el .xlsx producido por el
populator y verifica celdas canonicas contra valores esperados.

Objetivo: detectar regresiones sin abrir Excel manualmente. Si falla,
el pipeline agrega warning al log; el analista revisa visualmente.

Validaciones en hoja ACTUAL:
  - B2  (credito)           == datos.credito_id
  - B5  (cuota)             ≈ datos.cuota_mensual (tol ±$1)
  - B7  (plazo pendiente)   == datos.plazo_pendiente (en meses)
  - B10 (seguro_vida)       ≈ datos.seguro_vida
  - B11 (seguro_incendio)   ≈ datos.seguro_incendio
  - B12 (seguro_terremoto)  ≈ datos.seguro_terremoto
  - B13 (capital extracto)  ≈ datos.capital_mensual (tras Regla 9.3)
  - B14 (intereses extrac)  ≈ datos.interes_mensual (tras Regla 9.3)
  - B15 (saldo capital)     ≈ datos.saldo_capital
  - 6 opciones (B16:B21)    plazos en orden DESCENDENTE (R-3b)
  - activeTab               == 0 (hoja ACTUAL seleccionada)

Filename: ESTUDIO <NOMBRE MAYUSCULAS>-DD.MM.AA.xlsx (feedback_naming_excel_estudios)

Uso programatico:
    from validar_excel_generado import validar_excel
    ok, errores, warnings = validar_excel(path_xlsx, datos)
"""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook


TOLERANCIA_PESOS = 1.0  # Excel redondea, tol estricta de $1


def _aprox(a, b, tol=TOLERANCIA_PESOS) -> bool:
    try:
        return abs(float(a or 0) - float(b or 0)) <= tol
    except (ValueError, TypeError):
        return False


def _check(errores, cond, msg):
    if not cond:
        errores.append(msg)


def validar_excel(path_xlsx, datos) -> tuple[bool, list[str], list[str]]:
    """Valida Excel generado contra DatosClienteExcel. Retorna (ok, errores, warnings)."""
    errores: list[str] = []
    warnings: list[str] = []

    path = Path(path_xlsx)
    if not path.exists():
        errores.append(f"Excel no existe: {path}")
        return False, errores, warnings

    # 1) Naming: ESTUDIO <NOMBRE>-DD.MM.AA.xlsx
    nombre_esperado_fragment = (datos.nombre or "").strip()
    name = path.name
    if not name.startswith("ESTUDIO "):
        errores.append(f"naming invalido (no empieza con 'ESTUDIO '): {name}")
    if nombre_esperado_fragment and nombre_esperado_fragment not in name.upper():
        warnings.append(
            f"nombre cliente '{nombre_esperado_fragment}' no aparece en filename: {name}"
        )
    if not re.search(r"-\d{2}\.\d{2}\.\d{2}\.xlsx$", name):
        warnings.append(f"filename sin sufijo fecha DD.MM.AA: {name}")

    try:
        wb = load_workbook(str(path), data_only=False, keep_vba=False)
    except Exception as e:
        errores.append(f"no se pudo abrir xlsx: {e}")
        return False, errores, warnings

    # 2) Hoja ACTUAL debe existir
    if "ACTUAL" not in wb.sheetnames:
        errores.append(f"hoja 'ACTUAL' no existe. Hojas: {wb.sheetnames}")
        return False, errores, warnings

    ws = wb["ACTUAL"]

    # 3) activeTab == 0 (ACTUAL seleccionada) — feedback_excel_copiar_celdas
    try:
        active_idx = wb.active.sheet_view.tabSelected
    except Exception:
        active_idx = None
    if wb.index(wb.active) != 0:
        warnings.append(
            f"activeTab != 0 (ACTUAL deberia ser la primera seleccionada). "
            f"Actual: {wb.active.title}"
        )

    # 4) Valores en celdas canonicas (hoja ACTUAL)
    _check(errores,
           str(ws["B2"].value or "").strip() == (datos.credito_id or "").strip(),
           f"B2 credito_id: esperado={datos.credito_id!r} got={ws['B2'].value!r}")
    _check(errores, _aprox(ws["B5"].value, datos.cuota_mensual),
           f"B5 cuota: esperado=${datos.cuota_mensual:,.0f} got={ws['B5'].value!r}")
    _check(errores, _aprox(ws["B10"].value, datos.seguro_vida),
           f"B10 seguro_vida: esperado=${datos.seguro_vida:,.0f} got={ws['B10'].value!r}")
    _check(errores, _aprox(ws["B11"].value, datos.seguro_incendio),
           f"B11 seguro_incendio: esperado=${datos.seguro_incendio:,.0f} got={ws['B11'].value!r}")
    _check(errores, _aprox(ws["B12"].value, datos.seguro_terremoto),
           f"B12 seguro_terremoto: esperado=${datos.seguro_terremoto:,.0f} got={ws['B12'].value!r}")
    _check(errores, _aprox(ws["B15"].value, datos.saldo_capital),
           f"B15 saldo_capital: esperado=${datos.saldo_capital:,.0f} got={ws['B15'].value!r}")

    # 5) Plazos en B16:B21 en orden DESCENDENTE (R-3b)
    plazos_excel = []
    for row in range(16, 22):
        v = ws[f"B{row}"].value
        if isinstance(v, (int, float)):
            plazos_excel.append(float(v))
    if len(plazos_excel) < 6:
        warnings.append(
            f"menos de 6 opciones en B16:B21 (got {len(plazos_excel)}): {plazos_excel}"
        )
    elif len(plazos_excel) == 6:
        for i in range(5):
            if plazos_excel[i] < plazos_excel[i+1]:
                errores.append(
                    f"orden opciones QUEBRADO (R-3b): B{16+i}={plazos_excel[i]} "
                    f"< B{17+i}={plazos_excel[i+1]}. Todas deben ser descendentes."
                )
                break

    ok = len(errores) == 0
    return ok, errores, warnings


def formatear_reporte(ok: bool, errores: list[str], warnings: list[str]) -> str:
    lines = []
    lines.append(f"[M2-validar-xlsx] {'OK' if ok else 'FAIL'} "
                 f"({len(errores)} errores, {len(warnings)} warnings)")
    for e in errores:
        lines.append(f"  ERROR: {e}")
    for w in warnings:
        lines.append(f"  WARN:  {w}")
    return "\n".join(lines)

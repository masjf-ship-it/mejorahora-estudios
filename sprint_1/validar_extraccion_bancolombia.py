# -*- coding: utf-8 -*-
"""
validar_extraccion_bancolombia.py — MejorAhora SAS (2026-05-15)
================================================================
Validador M1 post-extraccion Bancolombia: asserts antes de generar Excel.

Verifica coherencia de los datos extraidos del PDF (pdfplumber o Gemini Vision)
ya consolidados en DatosClienteExcel.

Si falla alguna validacion dura -> retorna lista de errores. El pipeline
decide bloquear con ILEGIBLE / REVISION_MANUAL.

Validaciones (R-BCO-XX + coherencia general):
  - saldo_capital > $1,000,000 (nunca menor para hipotecario activo)
  - cuota_mensual > 0 y razonable (< $10,000,000)
  - tasa_ea entre 0 y 1 (decimal)
  - tasa_ea > 13% -> probable Mora confundida (R-BCO-20, equivalente R-DVV-20)
  - plazo_inicial > 0
  - plazo_pendiente > 0 y <= plazo_inicial
  - credito_id no vacio
  - nombre no vacio

Warnings (no bloquean):
  - ingresos == 0 (esperado en Bancolombia — NO REQUIERE ingresos certificados)
  - consultor vacio (opcional)
"""
from __future__ import annotations

try:
    from config_reglas import (
        SALDO_MIN_HIPOTECARIO_ACTIVO,
        TOLERANCIA_M1_WARN,
        TOLERANCIA_M1_ERROR,
        TOLERANCIA_G3_SUMA_DUPLICADA,
        M1_CUOTA_MAX_SANITY,
        M1_TASA_EA_WARN_MAX,
        M1_TASA_EA_MAX_PROBABLE_MORA,
    )
except ImportError:
    SALDO_MIN_HIPOTECARIO_ACTIVO = 1_000_000.0
    TOLERANCIA_M1_WARN = 70_000.0
    TOLERANCIA_M1_ERROR = 500_000.0
    TOLERANCIA_G3_SUMA_DUPLICADA = 0.10
    M1_CUOTA_MAX_SANITY = 10_000_000.0
    M1_TASA_EA_WARN_MAX = 0.35
    M1_TASA_EA_MAX_PROBABLE_MORA = 0.13


def validar_datos_cliente(datos) -> tuple[bool, list[str], list[str]]:
    """Retorna (ok, errores, warnings).

    ok = True si no hay errores duros. Las warnings NO afectan ok.
    """
    errores: list[str] = []
    warnings: list[str] = []

    # -------- Campos identidad (duros) --------
    if not (datos.credito_id or "").strip():
        errores.append("credito_id vacio")
    if not (datos.nombre or "").strip():
        errores.append("nombre vacio")

    # -------- Saldo capital --------
    if datos.saldo_capital <= 0:
        errores.append(f"saldo_capital invalido: ${datos.saldo_capital:,.0f}")
    elif datos.saldo_capital < SALDO_MIN_HIPOTECARIO_ACTIVO:
        errores.append(
            f"saldo_capital sospechosamente bajo: ${datos.saldo_capital:,.0f} "
            f"(minimo esperado ${SALDO_MIN_HIPOTECARIO_ACTIVO:,.0f} para hipotecario activo)"
        )

    # -------- Cuota mensual --------
    if datos.cuota_mensual <= 0:
        errores.append(f"cuota_mensual invalida: ${datos.cuota_mensual:,.0f}")
    elif datos.cuota_mensual > M1_CUOTA_MAX_SANITY:
        warnings.append(
            f"cuota_mensual muy alta ${datos.cuota_mensual:,.0f} — verificar manualmente"
        )

    # -------- Tasa EA --------
    if datos.tasa_ea <= 0:
        errores.append(f"tasa_ea invalida: {datos.tasa_ea}")
    elif datos.tasa_ea >= 1.0:
        errores.append(
            f"tasa_ea parece porcentaje sin normalizar: {datos.tasa_ea} "
            f"(esperado decimal 0.xxxx, ej 0.1300 para 13.00%)"
        )
    elif datos.tasa_ea > M1_TASA_EA_MAX_PROBABLE_MORA:
        # R-BCO-20: tasa Bancolombia Cte. Cobrada tipica 8%-13%. Mora ~15-20%.
        # Si > 13% probable confusion con Tasa Mora cobrada.
        errores.append(
            f"tasa_ea {datos.tasa_ea:.4f} ({datos.tasa_ea*100:.2f}%) "
            f"> {M1_TASA_EA_MAX_PROBABLE_MORA*100:.0f}%. Probable confusion "
            f"con Tasa Mora ({datos.tasa_ea*100:.2f}% atipico para Cte. Cobrada "
            f"Bancolombia; R-BCO-20)."
        )

    # -------- Plazos --------
    if datos.plazo_inicial <= 0:
        errores.append(f"plazo_inicial invalido: {datos.plazo_inicial}")
    if datos.plazo_pendiente <= 0:
        errores.append(f"plazo_pendiente invalido: {datos.plazo_pendiente}")
    if (datos.plazo_inicial > 0 and datos.plazo_pendiente > 0
            and datos.plazo_pendiente > datos.plazo_inicial):
        errores.append(
            f"plazo_pendiente {datos.plazo_pendiente} > plazo_inicial "
            f"{datos.plazo_inicial} (imposible)"
        )

    # -------- Coherencia cuota vs cap+int+seg --------
    # Bancolombia: cuota_mensual = valor_cuota_sin_seguros + seguros (sin mora).
    # Capital/intereses de la tabla "Movimientos" pueden NO sumar exactamente
    # a la cuota corriente porque incluyen abonos extras, beneficios, mora.
    # Aqui solo validamos rango razonable (no exactitud).
    seguros = datos.seguro_vida + datos.seguro_incendio + datos.seguro_terremoto
    cap = datos.capital_mensual
    inte = datos.interes_mensual
    if datos.cuota_mensual > 0 and (cap > 0 or inte > 0):
        suma = seguros + cap + inte
        dif = abs(suma - datos.cuota_mensual)
        if dif > TOLERANCIA_M1_ERROR:
            warnings.append(
                f"suma (seg+cap+int)=${suma:,.0f} vs cuota=${datos.cuota_mensual:,.0f} "
                f"diff=${dif:,.0f} (>${TOLERANCIA_M1_ERROR:,.0f}). En Bancolombia es "
                f"comun por abonos extras en la tabla Movimientos. R-BCO no bloquea."
            )

    # -------- Warnings soft --------
    # Bancolombia NO requiere ingresos certificados (R-BCO-05). ingresos=0 es esperado.
    if datos.ingresos > 0:
        warnings.append(
            f"ingresos=${datos.ingresos:,.0f} > 0. Bancolombia NO requiere "
            f"ingresos certificados; el pipeline_bancolombia los setea a 0."
        )
    if datos.abono_efectivo == 0:
        warnings.append("abono_efectivo=$0 — sin target comercial, serie base $100k-$600k")
    if not (datos.consultor or "").strip():
        warnings.append("consultor vacio (OPCIONAL, no bloquea)")

    ok = len(errores) == 0
    return ok, errores, warnings


def formatear_reporte(ok: bool, errores: list[str], warnings: list[str]) -> str:
    """Formatea reporte humano-legible para el log."""
    lines = []
    lines.append(f"[M1-validar-BCO] {'OK' if ok else 'FAIL'} "
                 f"({len(errores)} errores, {len(warnings)} warnings)")
    for e in errores:
        lines.append(f"  ERROR: {e}")
    for w in warnings:
        lines.append(f"  WARN:  {w}")
    return "\n".join(lines)

# -*- coding: utf-8 -*-
"""
validar_extraccion_davivienda.py — MejorAhora SAS (2026-04-23)
==============================================================
Validador M1 post-extraccion: asserts R-DVV-04 antes de generar Excel.

Verifica coherencia de los datos extraidos del PDF (pdfplumber o Vision)
ya consolidados en DatosClienteExcel (post R-DVV-06 override si aplico).

Si falla alguna validacion dura -> retorna lista de errores. El pipeline
decide bloquear con ILEGIBLE / REVISION_MANUAL.

Validaciones (R-DVV-04 + coherencia general):
  - saldo_capital > $1,000,000 (nunca menor para hipotecario activo)
  - cuota_mensual > 0 y razonable (< $10,000,000)
  - tasa_ea entre 0 y 1 (decimal)
  - plazo_inicial > 0
  - plazo_pendiente > 0 y <= plazo_inicial
  - credito_id no vacio
  - nombre no vacio
  - suma seguros + capital_extracto + intereses_extracto ≈ cuota_mensual
    (tolerancia ±$70,000 - Regla 9.3 ya lo permite)

Warnings (no bloquean pero avisan):
  - abono_efectivo == 0 (cliente sin abono declarado)
  - ingresos == 0 (puede activar 0/6 factibles pero es OK)
  - consultor vacio (ok, es opcional)
"""
from __future__ import annotations


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

    # -------- Saldo capital (R-DVV-04: >$1M) --------
    if datos.saldo_capital <= 0:
        errores.append(f"saldo_capital invalido: ${datos.saldo_capital:,.0f}")
    elif datos.saldo_capital < 1_000_000:
        errores.append(
            f"saldo_capital sospechosamente bajo: ${datos.saldo_capital:,.0f} "
            f"(minimo esperado $1,000,000 para hipotecario activo — "
            f"probable confusion con saldo parcial, ver R-DVV-03)"
        )

    # -------- Cuota mensual --------
    if datos.cuota_mensual <= 0:
        errores.append(f"cuota_mensual invalida: ${datos.cuota_mensual:,.0f}")
    elif datos.cuota_mensual > 10_000_000:
        warnings.append(
            f"cuota_mensual muy alta ${datos.cuota_mensual:,.0f} — verificar manualmente"
        )

    # -------- Tasa EA --------
    if datos.tasa_ea <= 0:
        errores.append(f"tasa_ea invalida: {datos.tasa_ea}")
    elif datos.tasa_ea >= 1.0:
        errores.append(
            f"tasa_ea parece porcentaje sin normalizar: {datos.tasa_ea} "
            f"(esperado decimal 0.xxxx, ej 0.1431 para 14.31%)"
        )
    elif datos.tasa_ea > 0.35:
        warnings.append(f"tasa_ea inusualmente alta: {datos.tasa_ea:.4f} ({datos.tasa_ea*100:.2f}%)")

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

    # -------- Anomalia Vision: seguro_vida=0 con seguro_incendio>0 --------
    # Retro 2026-04-24 (Yolly, Maria F, Karen L): Vision a veces extrae mal
    # seguro_vida (queda en 0) cuando el extracto SI tiene valor. Si vida=0
    # pero incendio>0, casi seguro Vision falló -> bloquear y revisar manual.
    if datos.seguro_vida == 0 and datos.seguro_incendio > 0:
        errores.append(
            f"seguro_vida=0 con seguro_incendio=${datos.seguro_incendio:,.0f} > 0. "
            f"Vision probablemente no extrajo seguro_vida del extracto. "
            f"Revisar PDF manualmente y re-procesar tras ajuste."
        )

    # -------- Coherencia cuota vs capital+intereses+seguros (tolerancia Regla 9.3) --------
    seguros = datos.seguro_vida + datos.seguro_incendio + datos.seguro_terremoto
    cap = datos.capital_mensual
    inte = datos.interes_mensual
    if datos.cuota_mensual > 0 and (cap > 0 or inte > 0):
        suma = seguros + cap + inte
        dif = abs(suma - datos.cuota_mensual)
        # Caso especial duplicacion (R-DVV-06 G3): suma ~= 2*cuota. La Regla 9.3
        # corregira capital/intereses despues. M1 NO debe bloquear, solo avisar.
        # 2026-04-24 (caso Yeimy: cap+int+seg duplicados pero R-DVV-06 ya hizo
        # override de seguros; falta 9.3 para cap/int).
        es_duplicacion = (
            datos.cuota_mensual > 0
            and abs(suma - 2.0 * datos.cuota_mensual) / datos.cuota_mensual < 0.10
        )
        if es_duplicacion:
            warnings.append(
                f"suma (seg+cap+int)=${suma:,.0f} ~= 2x cuota=${datos.cuota_mensual:,.0f} "
                f"-> duplicacion R-DVV-06 detectada. Regla 9.3 corregira cap/int."
            )
        elif dif > 500_000:
            errores.append(
                f"suma (seg+cap+int)=${suma:,.0f} vs cuota=${datos.cuota_mensual:,.0f} "
                f"diff=${dif:,.0f} (>$500k indica error de extraccion o duplicacion "
                f"sin override R-DVV-06)"
            )
        elif dif > 70_000:
            warnings.append(
                f"suma (seg+cap+int)=${suma:,.0f} vs cuota=${datos.cuota_mensual:,.0f} "
                f"diff=${dif:,.0f} (>$70k, Regla 9.3 lo ajustara)"
            )

    # -------- Warnings soft (cliente opcional) --------
    if datos.ingresos == 0:
        warnings.append("ingresos=$0 — Mode B no activara, caera a Mode A (agresivas).")
    if datos.abono_efectivo == 0:
        warnings.append("abono_efectivo=$0 — sin target comercial, serie base $100k-$600k")
    if not (datos.consultor or "").strip():
        warnings.append("consultor vacio (OPCIONAL, no bloquea)")

    ok = len(errores) == 0
    return ok, errores, warnings


def formatear_reporte(ok: bool, errores: list[str], warnings: list[str]) -> str:
    """Formatea reporte humano-legible para el log."""
    lines = []
    lines.append(f"[M1-validar] {'OK' if ok else 'FAIL'} "
                 f"({len(errores)} errores, {len(warnings)} warnings)")
    for e in errores:
        lines.append(f"  ERROR: {e}")
    for w in warnings:
        lines.append(f"  WARN:  {w}")
    return "\n".join(lines)

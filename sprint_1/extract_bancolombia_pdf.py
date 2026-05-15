"""
extract_bancolombia_pdf.py - MejorAhora SAS (2026-05-15)
==========================================================
Parser de extractos Bancolombia (Estado de Crédito Hipotecario en PESOS).

Estructura distinta a Davivienda (ver MOM_BANCOLOMBIA.md):
  - Encabezado: "Estado de Crédito Hipotecario en PESOS"
  - Crédito: "Número de crédito 9NNNNNNNNNN" (sin guion verificador)
  - Cuota: "Valor de la cuota sin seguros y sin comisiones $ X" + seguros separados
  - Saldo: "Saldo a la fecha en que se generó el extracto $ X"
  - FRECH: "Valor subsidio Gobierno $ X"
  - Mora: detectada por "Nro. cuotas vencidas > 0" y "Valor cuotas vencidas > 0"

IMPORTANTE — PDFs de Bancolombia están **PROTEGIDOS por contraseña**.
El password es la **cédula del cliente** (parámetro `cedula_fallback`).
Si el cedula_fallback no se conoce/no abre, pdfplumber lanza excepción.

Uso desde código:
    from extract_bancolombia_pdf import parse_bancolombia_pdf
    datos = parse_bancolombia_pdf("ruta/al/pdf.pdf", cedula_fallback="91443052")

Encoding: el PDF tiene mojibake (é→`�`, ó→`�`, ñ→`�`). Los regex usan clases
tolerantes `[eé]`, `[oó]`, `[ñn]`, `[.�]?` para capturar todas las variantes.

Reusa de `extract_davivienda_pdf`: `_limpiar_num`, `_buscar`, `_peso_col`.
"""

import re
import sys
from pathlib import Path

# Reutilizar utilidades de Davivienda (genericas, parser numeros colombianos).
from extract_davivienda_pdf import _limpiar_num, _buscar


def _peso_col(raw: str) -> float:
    """Convierte numero en formato colombiano de miles a float.
    '22.021' -> 22021.0  |  '1,767,048.00' -> 1767048.00
    Reutilizado del extractor Davivienda (logica identica).
    """
    s = (raw or "").strip().replace("$", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        # Estilo ingles (Bancolombia usa este): "1,767,048.00"
        if s.rfind(",") < s.rfind("."):
            return float(s.replace(",", ""))
        else:
            return float(s.replace(".", "").replace(",", "."))
    if "." in s:
        partes = s.split(".")
        if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
            return float(s.replace(".", ""))
        return float(s)
    if "," in s:
        return float(s.replace(",", "."))
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_bancolombia_pdf(pdf_path: str, cedula_fallback: str = "") -> dict:
    """Parsea un extracto Bancolombia y retorna dict con los campos clave.

    cedula_fallback: CC del cliente. Bancolombia protege los PDFs con la CC
    como password de apertura. Sin esto pdfplumber no puede leer.
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "pdfplumber no instalado. Ejecutar: pip install pdfplumber"
        )

    texto_paginas = []
    # Bancolombia PDFs protegidos con cedula como password.
    try:
        with pdfplumber.open(pdf_path, password=cedula_fallback) as pdf:
            for pg in pdf.pages:
                texto_paginas.append(pg.extract_text() or "")
    except Exception as exc:
        raise ValueError(
            f"No se pudo abrir PDF Bancolombia {pdf_path} con password "
            f"'{cedula_fallback[:4]}***'. Detalle: {exc}"
        )

    texto = "\n".join(texto_paginas)

    # =========================================================
    # Validar que es Bancolombia
    # =========================================================
    es_bancolombia = (
        "BANCOLOMBIA" in texto.upper()
        or "Estado de Cr" in texto and "Hipotecario" in texto
        or "bancolombia.com" in texto.lower()
        or "DCF:defensor@bancolombia" in texto
    )
    if not es_bancolombia:
        # Si los identificadores fallan PERO el PDF es escaneado (texto vacio),
        # NO es Bancolombia identificable por texto -> Vision fallback decidira.
        if texto.strip():
            raise ValueError(f"El PDF {pdf_path} no parece ser Bancolombia")

    # =========================================================
    # Tipo de extracto
    # =========================================================
    # Bancolombia: "Plan: CUOTA CONSTANTE EN PESOS-VIVDA VIS" o "...VIVDA NOVIS"
    if "Hipotecario" in texto:
        tipo_extracto = "Hipotecario"
    elif "Leasing" in texto:
        tipo_extracto = "Leasing H."
    else:
        tipo_extracto = "Desconocido"

    # VIS detection (Bancolombia: plan VIVDA VIS vs VIVDA NOVIS)
    es_vis_marker = bool(re.search(r"VIVDA\s+VIS\b", texto, re.IGNORECASE))

    # =========================================================
    # CAMPOS BASICOS
    # =========================================================
    datos = {}

    # Numero de credito (formato Bancolombia: 9NNNNNNNNNN, sin guion verificador)
    datos["credito"] = _buscar(
        r"N[uú\w]mero\s+de\s+cr[eé\w]dito\s+(\d{8,15})",
        texto,
    ) or ""

    # Nombre cliente (despues de "SE�OR(A):" o "SEÑOR(A):")
    nombre = _buscar(
        r"SE[\wÑ]OR\(A\):\s*\n?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+?)\s*\n",
        texto, flags=re.M
    )
    datos["nombre"] = nombre.strip() if nombre else ""

    # Email (Bancolombia no siempre lo incluye)
    datos["email"] = _buscar(
        r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        texto
    ) or ""
    # Skip emails del banco mismo
    if datos["email"] and "bancolombia.com" in datos["email"].lower():
        datos["email"] = ""

    # =========================================================
    # CUOTA (Valor a Pagar incluye seguros y mora si hay)
    # =========================================================
    # "Valor a Pagar $ 1,767,048.00"
    valor_a_pagar = _peso_col(_buscar(
        r"Valor\s+a\s+Pagar\s+\$?\s*([\d,\.]+)", texto, default="0"
    ))

    # "Valor de la cuota sin seguros y sin comisiones $ 1,703,850.00"
    valor_cuota_sin_seg = _peso_col(_buscar(
        r"Valor\s+de\s+la\s+cuota\s+sin\s+seguros[^\$]*?\$?\s*([\d,\.]+)",
        texto, default="0"
    ))

    # Cuota mensual canonica = cuota sin seguros + seguros (sin mora)
    # Razon: "Valor a Pagar" incluye mora si la hay; cuota canonica del estudio
    # es la cuota CORRIENTE del periodo, no la mora vencida.
    # Si no hay mora, valor_cuota_sin_seg + seguros == valor_a_pagar.

    # =========================================================
    # SEGUROS APLICADOS (puede tener asterisco prefijo)
    # =========================================================
    datos["seguro_vida"] = _peso_col(_buscar(
        r"\*?Valor\s+seguro\s+vida\s+\$?\s*([\d,\.]+)", texto, default="0"
    ))
    datos["seguro_incendio"] = _peso_col(_buscar(
        r"\*?Valor\s+seguro\s+incendio\s+\$?\s*([\d,\.]+)", texto, default="0"
    ))
    datos["seguro_terremoto"] = _peso_col(_buscar(
        r"\*?Valor\s+seguro\s+terremoto\s+\$?\s*([\d,\.]+)", texto, default="0"
    ))

    # Cuota mensual final (canonica del estudio)
    seg_total = datos["seguro_vida"] + datos["seguro_incendio"] + datos["seguro_terremoto"]
    if valor_cuota_sin_seg > 0:
        datos["cuota_mensual"] = valor_cuota_sin_seg + seg_total
    else:
        # Fallback: si el campo "sin seguros" no se encontro, usar Valor a Pagar
        # (puede incluir mora — se detecta en validacion posterior)
        datos["cuota_mensual"] = valor_a_pagar

    # Mantener referencia al "Valor a Pagar" total (incluye mora si hay)
    datos["valor_a_pagar"] = valor_a_pagar
    datos["valor_cuota_sin_seguros"] = valor_cuota_sin_seg

    # =========================================================
    # MORA (Bancolombia: cuotas_vencidas + valor_cuotas_vencidas)
    # =========================================================
    datos["cuotas_vencidas"] = int(_limpiar_num(_buscar(
        r"Nro\.\s+cuotas\s+vencidas\s+(\d+)", texto, default="0"
    )))
    datos["valor_cuotas_vencidas"] = _peso_col(_buscar(
        r"Valor\s+cuotas\s+vencidas\s+\$?\s*([\d,\.]+)", texto, default="0"
    ))
    datos["interes_mora"] = _peso_col(_buscar(
        r"Inter[eé\w]s\s+de\s+mora\s+\$?\s*([\d,\.]+)", texto, default="0"
    ))
    # `dias_mora` no aparece explicito en Bancolombia. Lo inferimos:
    # si hay cuotas_vencidas > 0, asumimos mora activa. R-DVV-10c equivalente.
    datos["dias_mora"] = 30 if datos["cuotas_vencidas"] > 0 else 0

    # =========================================================
    # CUOTAS Y PLAZO
    # =========================================================
    datos["plazo_inicial"] = int(_limpiar_num(_buscar(
        r"Plazo\s+total\s+en\s+meses\s+(\d+)", texto, default="0"
    )))
    # "Nro. cuotas pendientes para pago total 236"
    datos["cuotas_pendientes"] = int(_limpiar_num(_buscar(
        r"Nro\.\s+cuotas\s+pendientes\s+para\s+pago\s+total\s+(\d+)",
        texto, default="0"
    )))
    # "Nro. cuota a cancelar 005" -> cuotas pagadas = a_cancelar - 1
    cuota_actual = int(_limpiar_num(_buscar(
        r"Nro\.\s+cuota\s+a\s+cancelar\s+(\d+)", texto, default="0"
    )))
    datos["cuotas_pagadas"] = max(0, cuota_actual - 1)

    # Dias liquidados (Bancolombia no siempre lo explicita; default 30)
    datos["dias_liquidados"] = 30

    # =========================================================
    # SISTEMA AMORTIZACION
    # =========================================================
    # "Plan: CUOTA CONSTANTE EN PESOS-VIVDA VIS"
    if "PESOS" in texto.upper():
        datos["amortizacion"] = "Pesos"
    elif "UVR" in texto.upper():
        datos["amortizacion"] = "Uvr"
    else:
        datos["amortizacion"] = ""

    # =========================================================
    # TASAS
    # =========================================================
    datos["tasa_pactada"] = _peso_col(_buscar(
        r"Tasa\s+inter[eé\w]s\s+pactada\s+([\d,\.]+)\s*%",
        texto, default="0"
    ))
    # Tasa CANONICA del estudio (R-BCO-04): Tasa interes cobrada
    datos["tasa_cobrada"] = _peso_col(_buscar(
        r"Tasa\s+inter[eé\w]s\s+cobrada\s+([\d,\.]+)\s*%",
        texto, default="0"
    ))
    datos["tasa_subsidiada"] = _peso_col(_buscar(
        r"Tasa\s+inter[eé\w]s\s+subsidiada\s+([\d,\.]+)\s*%",
        texto, default="0"
    ))
    datos["tasa_mora_cobrada"] = _peso_col(_buscar(
        r"Tasa\s+inter[eé\w]s\s+mora\s+cobrada\s+([\d,\.]+)\s*%",
        texto, default="0"
    ))

    # =========================================================
    # FRECH (Bancolombia: "Valor subsidio Gobierno")
    # =========================================================
    valor_subsidio_gobierno = _peso_col(_buscar(
        r"Valor\s+subsidio\s+Gobierno\s+\$?\s*([\d,\.]+)",
        texto, default="0"
    ))
    valor_cuota_sin_subsidio = _peso_col(_buscar(
        r"Valor\s+cuota\s+sin\s+subsidio\s+Gobierno\s+\$?\s*([\d,\.]+)",
        texto, default="0"
    ))
    valor_cuota_con_subsidio = _peso_col(_buscar(
        r"Valor\s+cuota\s+con\s+subsidio\s+\$?\s*([\d,\.]+)",
        texto, default="0"
    ))

    datos["tiene_frech"] = (
        valor_subsidio_gobierno > 0
        or datos["tasa_subsidiada"] > 0
        or valor_cuota_con_subsidio > 0
    )
    datos["frech_cobertura_pag1"] = valor_subsidio_gobierno
    datos["pago_minimo_cliente"] = valor_cuota_con_subsidio if datos["tiene_frech"] else 0.0

    # =========================================================
    # SALDO CAPITAL (R-BCO-02)
    # =========================================================
    # Estructura en la pagina 1 (tabla header):
    #   Linea N:   "Fecha de Pago | ... | Valor a Pagar | Saldo a la fecha en que se generó el extracto"
    #   Linea N+1: "2026/05/15 | 2026/04/30 | $ 1,767,048.00 | $ 152,172,660.26"
    # El regex anterior matcheaba el label tambien en "Observaciones" mas abajo
    # y capturaba un numero erroneo. Solucion: localizar la linea de header
    # de la tabla y capturar el ULTIMO monto ($) de la linea de valores siguiente.
    datos["saldo_capital"] = 0.0
    m_header = re.search(
        r"Fecha\s+de\s+Pago[^\n]+Saldo[^\n]+\n([^\n]+)",
        texto
    )
    if m_header:
        linea_valores = m_header.group(1)
        montos = re.findall(r"\$\s*([\d,\.]+)", linea_valores)
        if len(montos) >= 2:
            # Saldo es el ULTIMO monto en esa linea (despues de Valor a Pagar)
            datos["saldo_capital"] = _peso_col(montos[-1])
    # Fallback defensivo si el regex de tabla no matchea
    if datos["saldo_capital"] <= 0:
        # Buscar primer monto > $1M cerca del label "Saldo a la fecha"
        # (limitado a primeras ~500 chars del texto para evitar Observaciones)
        head = texto[:1500]
        montos_grandes = [
            _peso_col(m) for m in re.findall(r"\$\s*([\d,]{4,}(?:\.\d+)?)", head)
            if _peso_col(m) > 1_000_000
        ]
        if montos_grandes:
            # El saldo capital es uno de los montos grandes; tomar el ultimo (despues
            # de Valor a Pagar que tambien puede ser grande)
            datos["saldo_capital"] = max(montos_grandes)

    # =========================================================
    # CAPITAL E INTERESES (extraidos de la tabla Movimientos)
    # =========================================================
    # Bancolombia "Movimientos Último Periodo" tiene tabla con columnas:
    # Fecha | Descripcion | Capital | Int.Corriente | Int.Mora | Vida | Incendio | Terremoto | Otros | Total
    # Estrategia: sumar las columnas Capital e Int.Corriente de todas las filas
    # de movimientos del periodo. Las descripciones son: "Pago Cuota", "Pago Cuota Anticipado",
    # "Abono Extra", "Pago Interés Mora", "Beneficio por Cuota Anticipada".
    capital_aplicado = 0.0
    int_corriente_aplicado = 0.0
    # Buscar lineas que empiecen con fecha YYYY/MM/DD seguida de texto y numeros
    # Patron simplificado: cualquier linea con fecha + numeros = movimiento
    for m in re.finditer(
        r"(\d{4}/\d{2}/\d{2})\s+[A-Za-z\w\s]+?\s+"
        r"([-\d,\.]+)\s+([-\d,\.]+)\s+([-\d,\.]+)\s+"  # cap, int corr, int mora
        r"([-\d,\.]+)\s+([-\d,\.]+)\s+([-\d,\.]+)\s+"  # vida, incendio, terremoto
        r"([-\d,\.]+)\s+([-\d,\.]+)",                   # otros, total
        texto
    ):
        try:
            cap = _peso_col(m.group(2))
            int_corr = _peso_col(m.group(3))
            capital_aplicado += cap
            int_corriente_aplicado += int_corr
        except (ValueError, IndexError):
            continue

    datos["abonos_capital"] = round(capital_aplicado, 2)
    datos["intereses_corrientes"] = round(int_corriente_aplicado, 2)
    datos["intereses_mora"] = datos["interes_mora"]
    datos["total_aplicado"] = round(
        capital_aplicado + int_corriente_aplicado + seg_total + datos["interes_mora"], 2
    )

    # Valores asegurados
    datos["valor_asegurado_vida"] = _peso_col(_buscar(
        r"Valor\s+asegurado\s+Incendio\s+y\s+Terremoto\s+\$?\s*([\d,\.]+)",
        texto, default="0"
    ))  # Bancolombia no detalla valor asegurado vida en pag.1, usamos inmueble
    datos["valor_asegurado_inmueble"] = datos["valor_asegurado_vida"]

    # Tasas de seguros (Bancolombia las tabula por edad pag.2, no aplica directa)
    datos["tasa_seguro_vida"] = 0.0
    datos["tasa_seguro_incendio"] = 0.0

    # Saldo anterior (Bancolombia no lo expone explicitamente; estimable como
    # saldo_capital + abonos_capital del periodo)
    datos["saldo_anterior"] = round(datos["saldo_capital"] + capital_aplicado, 2)

    # Cedula
    datos["cedula"] = cedula_fallback or ""

    # =========================================================
    # VALIDACIONES CRUZADAS
    # =========================================================
    datos["tipo"] = tipo_extracto
    datos["_validacion"] = {}
    _TOL_VALIDACION_EXTRACCION = 100.0  # ±$100 COP ruido redondeo

    # Suma seguros aplicados + capital + intereses + mora ≈ Valor a Pagar
    suma = (datos["abonos_capital"] + datos["intereses_corrientes"]
            + seg_total + datos["interes_mora"])
    diff = abs(valor_a_pagar - suma) if valor_a_pagar > 0 else 0
    datos["_validacion"]["valor_a_pagar_diff"] = round(diff, 2)
    datos["_validacion"]["valor_a_pagar_ok"] = diff < _TOL_VALIDACION_EXTRACCION

    # Tasa para estudio (R-BCO-04): SIEMPRE Tasa interes cobrada
    datos["tasa_estudio"] = datos["tasa_cobrada"]

    # Plazo pagado (derivado)
    datos["plazo_pagado"] = datos["cuotas_pagadas"]

    # Marker VIS (para proponedor_plazos)
    datos["es_vis"] = es_vis_marker

    return datos


def main():
    if len(sys.argv) < 3:
        print("Uso: py extract_bancolombia_pdf.py <ruta_pdf> <cedula>")
        sys.exit(2)
    pdf_path = sys.argv[1]
    cedula = sys.argv[2]
    result = parse_bancolombia_pdf(pdf_path, cedula_fallback=cedula)
    # Print resumen para debug humano
    print(f"Cliente: {result.get('nombre')}")
    print(f"Credito: {result.get('credito')}")
    print(f"Tipo: {result.get('tipo')} (VIS={result.get('es_vis')})")
    print(f"Saldo capital: ${result.get('saldo_capital'):,.2f}")
    print(f"Cuota mensual: ${result.get('cuota_mensual'):,.2f}")
    print(f"  Sin seguros: ${result.get('valor_cuota_sin_seguros'):,.2f}")
    print(f"  Seguros: vida=${result.get('seguro_vida'):,.0f} "
          f"incendio=${result.get('seguro_incendio'):,.0f} "
          f"terremoto=${result.get('seguro_terremoto'):,.0f}")
    print(f"Tasa cobrada (estudio): {result.get('tasa_cobrada'):.2f}% EA")
    print(f"Tasa mora cobrada: {result.get('tasa_mora_cobrada'):.2f}% EA")
    print(f"Plazo inicial: {result.get('plazo_inicial')}m")
    print(f"Cuotas pendientes: {result.get('cuotas_pendientes')}")
    print(f"Cuotas vencidas (mora): {result.get('cuotas_vencidas')}")
    print(f"FRECH: {result.get('tiene_frech')} (cobertura=${result.get('frech_cobertura_pag1'):,.0f})")
    print(f"Validacion suma vs valor_a_pagar: "
          f"diff=${result['_validacion']['valor_a_pagar_diff']:,.2f} "
          f"ok={result['_validacion']['valor_a_pagar_ok']}")


if __name__ == "__main__":
    main()

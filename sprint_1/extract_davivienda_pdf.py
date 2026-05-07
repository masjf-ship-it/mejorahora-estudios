"""
extract_davivienda_pdf.py - MejorAhora SAS
==========================================
Parser robusto de extractos Davivienda (pesos) basado en bank_rules/DAVIVIENDA.md.

Entrada: ruta a PDF extracto Davivienda.
Salida: dict con los 20 campos validados (o CSV row list).

Uso directo:
    py extract_davivienda_pdf.py ruta/al/extracto.pdf

Uso desde codigo:
    from extract_davivienda_pdf import parse_davivienda_pdf
    datos = parse_davivienda_pdf("ruta/al/pdf.pdf", cedula_fallback="79757470")
    # datos es dict con: credito, cuota, tasa_cobrada, saldo, seguros, ...

Requiere: pdfplumber (pip install pdfplumber)
"""

import re
import sys
from pathlib import Path


def _limpiar_num(s: str) -> float:
    """Convierte '$78,705,097.89' o '78.705.097,89' o '-$128,062.62' a float."""
    if s is None:
        return 0.0
    s = str(s).strip()
    if not s or s.upper() in ("N/A", "NAN", "NULL", ""):
        return 0.0
    neg = s.startswith("-")
    s = s.lstrip("-+$ ").rstrip(" ")
    # Quitar separadores de miles (coma o punto anterior al decimal)
    # Heuristica: si tiene tanto coma como punto, el ultimo separador es decimal
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Estilo europeo: 78.705.097,89
            s = s.replace(".", "").replace(",", ".")
        else:
            # Estilo ingles: 78,705,097.89
            s = s.replace(",", "")
    elif "," in s:
        # Solo coma: puede ser decimal (EU) o miles (sin decimales al final)
        # Si tiene 3 digitos despues de la ultima coma -> miles estilo ingles
        partes = s.split(",")
        if len(partes[-1]) == 3 and all(p.isdigit() for p in partes):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    else:
        # Solo punto: puede ser decimal o miles EU (ej. 78.705.097)
        puntos = s.count(".")
        if puntos > 1:
            s = s.replace(".", "")
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return 0.0


def _buscar(pattern: str, texto: str, flags=re.I, grupo=1, default=None):
    m = re.search(pattern, texto, flags)
    if not m:
        return default
    try:
        return m.group(grupo).strip()
    except IndexError:
        return default


def parse_davivienda_pdf(pdf_path: str, cedula_fallback: str = "") -> dict:
    """Parsea un extracto Davivienda y retorna dict con los 20 campos clave.

    cedula_fallback: CC del cliente (del CRM). Davivienda enmascara la cedula
    en el extracto como '0000000000', por eso se pasa aparte.
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "pdfplumber no instalado. Ejecutar: pip install pdfplumber"
        )

    texto_paginas = []
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            texto_paginas.append(pg.extract_text() or "")

    texto = "\n".join(texto_paginas)

    # =========================================================
    # Validar que es Davivienda
    # =========================================================
    es_davivienda = (
        "DAVIVIENDA" in texto.upper()
        or "860.034.313" in texto
        or "Banco Davivienda" in texto
    )
    if not es_davivienda:
        raise ValueError(f"El PDF {pdf_path} no parece ser Davivienda")

    # =========================================================
    # Tipo de extracto (Hipotecario / Leasing / Consumo 590)
    # =========================================================
    if re.search(r"Extracto\s+Leasing\s+Habitacional", texto, re.I):
        tipo_extracto = "Leasing H."
    elif re.search(r"Extracto\s+Cr[eé]dito\s+Hipotecario", texto, re.I):
        tipo_extracto = "Hipotecario"
    elif re.search(r"Extracto\s+Cr[eé]dito(?!\s+Hipotecario)", texto, re.I):
        tipo_extracto = "Consumo 590"  # No aplica - excluir
    else:
        tipo_extracto = "Desconocido"

    # =========================================================
    # CAMPOS PAGINA 1
    # =========================================================
    datos = {}

    # Numero de credito (ej: 570046660023750-2)
    datos["credito"] = _buscar(
        r"Extracto\s+Cr[eé]dito\s+Hipotecario\s+(\d{12,15}-?\d?)",
        texto,
    ) or _buscar(
        r"No\s*del\s*cr[eé]dito:\s*(\d{12,15}-?\d?)", texto
    ) or _buscar(
        r"Extracto\s+Leasing\s+Habitacional\s+(\d{12,15}-?\d?)", texto
    )

    # Nombre cliente (despues de "Apreciado Cliente")
    nombre = _buscar(
        r"Apreciado\s+Cliente[^\n]*\n?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+?)\s+\+",
        texto, flags=re.M
    ) or _buscar(r"Cliente:\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+?)\s", texto)
    datos["nombre"] = nombre.strip() if nombre else ""

    # Email (heuristica: primer email que aparezca)
    datos["email"] = _buscar(
        r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        texto
    ) or ""

    # Cuota (Valor Cuota Mes)
    datos["cuota_mensual"] = _limpiar_num(_buscar(
        r"\+\s*Valor\s+Cuota\s+Mes\s*\$?\s*([\d.,]+)", texto, default="0"
    ))

    # Valor prorrogado y mora
    datos["valor_prorrogado"] = _limpiar_num(_buscar(
        r"\+\s*Valor\s+Prorrogado\s*\$?\s*([\d.,]+)", texto, default="0"
    ))
    datos["valor_mora"] = _limpiar_num(_buscar(
        r"\+\s*Valor\s+en\s+Mora\s*\$?\s*([\d.,]+)", texto, default="0"
    ))

    # Plazo original y cuotas
    datos["plazo_inicial"] = int(_limpiar_num(_buscar(
        r"Plazo\s+(\d{2,3})", texto, default="0"
    )))
    datos["cuotas_pendientes"] = int(_limpiar_num(_buscar(
        r"No\.\s+Cuotas\s+Pdtes\.\s+Pago\s+Total\s+(\d+)", texto, default="0"
    )))
    datos["cuotas_pagadas"] = int(_limpiar_num(_buscar(
        r"No\.\s+Cuotas\s+que\s+se\s+cancela\s+(\d+)", texto, default="0"
    )))

    # Dias
    datos["dias_liquidados"] = int(_limpiar_num(_buscar(
        r"No\.\s+D[ií]as\s+Liquidados\s+(\d+)", texto, default="0"
    )))
    datos["dias_mora"] = int(_limpiar_num(_buscar(
        r"No\.\s+D[ií]as\s+en\s+Mora\s+(\d+)", texto, default="0"
    )))

    # Sistema amortizacion
    sistema = _buscar(r"Sistema\s+de\s+Amortizaci[oó]n\s+([A-ZÁÉÍÓÚÑ\s\$]+?)(?:\s+Tasa|$)",
                       texto, default="")
    if "CUOTA FIJA" in (sistema or "").upper() or "CUOTA FIJA $" in texto.upper():
        datos["amortizacion"] = "Pesos"
    elif "UVR" in (sistema or "").upper():
        datos["amortizacion"] = "Uvr"
    else:
        datos["amortizacion"] = ""

    # Tasas (EA)
    datos["tasa_pactada"] = _limpiar_num(_buscar(
        r"Tasa\s+Inter[eé]s\s+Cte\.?Pactada\s+([\d.,]+)", texto, default="0"
    ))
    datos["tasa_cobrada"] = _limpiar_num(_buscar(
        r"Tasa\s+Inter[eé]s\s+Cte\.?Cobrada\s+([\d.,]+)", texto, default="0"
    ))

    # Tasas seguros (por millon)
    datos["tasa_seguro_vida"] = _limpiar_num(_buscar(
        r"Tasa\s+Seguro\s+de\s+Vida\s+([\d.,]+)", texto, default="0"
    ))
    datos["tasa_seguro_incendio"] = _limpiar_num(_buscar(
        r"Tasa\s+Seguro\s+de\s+Incendio\s+y[\s\S]*?([\d.,]+)\s+por\s+mill[oó]n",
        texto, default="0"
    ))

    # FRECH - deteccion
    datos["tiene_frech"] = bool(re.search(
        r"-\s*Cobertura\s+de\s+Tasa", texto, re.I
    ))
    if datos["tiene_frech"]:
        datos["frech_cobertura_pag1"] = _limpiar_num(_buscar(
            r"-\s*Cobertura\s+de\s+Tasa\s*\$?\s*([\d.,]+)", texto, default="0"
        ))
        datos["pago_minimo_cliente"] = _limpiar_num(_buscar(
            r"Pago\s+M[ií]nimo\s+Cliente\s*\$?\s*([\d.,]+)", texto, default="0"
        ))
    else:
        datos["frech_cobertura_pag1"] = 0.0
        datos["pago_minimo_cliente"] = 0.0

    # =========================================================
    # CAMPOS PAGINA 2
    # =========================================================

    # Seguros aplicados
    # R-DVV-15 (2026-04-27): El extracto Davivienda muestra en la misma linea:
    #   "Seguro de Vida   0,02294   22.021"
    # donde el PRIMER numero es la tasa (formato colombiano con coma: "0,02294")
    # y el SEGUNDO es el monto en pesos (formato colombiano miles con punto: "22.021").
    # _limpiar_num("22.021") devuelve 22.021 (float), no 22021, porque no puede
    # distinguir si el punto es decimal o separador de miles con un solo grupo.
    # Solucion: detectar "monto colombiano" por su patron (digitos.3digitos) y
    # convertir eliminando puntos, en lugar de pasar por _limpiar_num.
    def _peso_col(raw: str) -> float:
        """Convierte numero en formato colombiano de miles a float.
        '22.021' -> 22021.0  |  '1.234.567' -> 1234567.0
        Si tiene coma, la trata como decimal: '22,50' -> 22.5
        """
        s = (raw or "").strip().replace("$", "").replace(" ", "")
        if not s:
            return 0.0
        # Si tiene coma Y punto: colombiano => punto=miles, coma=decimal
        if "," in s and "." in s:
            if s.index(".") < s.index(","):
                return float(s.replace(".", "").replace(",", "."))
            else:
                return float(s.replace(",", ""))
        # Solo punto(s): si el ultimo grupo tiene 3 digitos => miles
        if "." in s:
            partes = s.split(".")
            if all(len(p) == 3 for p in partes[1:]):
                return float(s.replace(".", ""))
            return float(s)
        # Solo coma: decimal
        if "," in s:
            return float(s.replace(",", "."))
        return float(s)

    def _es_tasa(raw: str) -> bool:
        """True si el string parece una tasa/porcentaje (< 1 con coma decimal)."""
        v = _peso_col(raw)
        # Tasas mensuales de seguros tipicamente entre 0.001 y 0.9
        return v < 1.0

    def _extraer_seguro_vida(texto_: str) -> float:
        # R-DVV-15: "Tasa Seguro de Vida 0,02294" aparece ANTES de
        # "Seguro de Vida 22.021" en el extracto Davivienda.
        # re.search encuentra la primera ocurrencia (la tasa), que es < 100,
        # y para ahi sin intentar la siguiente (el monto).
        # Solucion: re.finditer sobre TODAS las ocurrencias; retornar la primera
        # cuyo valor (via _peso_col) sea >= 100 pesos.
        # Patron A: uno o dos numeros tras "Seguro de Vida" (misma linea)
        for m in re.finditer(
            r"Seguro\s+de\s+Vida\s+\$?\s*([\d.,]+)(?:\s+\$?\s*([\d.,]+))?",
            texto_, re.IGNORECASE
        ):
            raw1 = m.group(1)
            raw2 = m.group(2)
            v1 = _peso_col(raw1)
            if v1 >= 100:
                return v1
            if raw2:
                v2 = _peso_col(raw2)
                if v2 >= 100:
                    return v2
        # Patron B: valor en linea siguiente (label sola, monto abajo)
        m3 = re.search(
            r"Seguro\s+de\s+Vida\s*(?::|\n)\s*\$?\s*([\d.,]+)",
            texto_, re.IGNORECASE | re.MULTILINE
        )
        if m3:
            v = _peso_col(m3.group(1))
            if v >= 100:
                return v
        # Patron C: "Seguro Vida" abreviado — misma logica con finditer
        for m in re.finditer(r"Seguro\s+Vida\s+([\d.,]+)", texto_, re.IGNORECASE):
            v = _peso_col(m.group(1))
            if v >= 100:
                return v
        return 0.0
    datos["seguro_vida"] = _extraer_seguro_vida(texto)
    datos["seguro_incendio"] = _limpiar_num(_buscar(
        r"Seguro\s+de\s+Incendio\s+y\s+Anexos\s*\$?\s*([\d.,]+)",
        texto, default="0"
    ))
    # En Davivienda incendio+terremoto suelen estar combinados (= 0 separado)
    datos["seguro_terremoto"] = _limpiar_num(_buscar(
        r"Seguro\s+de\s+Terremoto\s*\$?\s*([\d.,]+)", texto, default="0"
    ))

    datos["intereses_corrientes"] = _limpiar_num(_buscar(
        r"Intereses\s+Corrientes\s*\$?\s*([\d.,]+)", texto, default="0"
    ))
    datos["intereses_mora"] = _limpiar_num(_buscar(
        r"Intereses\s+de\s+Mora\s*\$?\s*([\d.,]+)", texto, default="0"
    ))
    datos["abonos_capital"] = _limpiar_num(_buscar(
        r"Abonos\s+a\s+Capital\s*\$?\s*([\d.,]+)", texto, default="0"
    ))
    datos["total_aplicado"] = _limpiar_num(_buscar(
        r"Total\s+Aplicado\s*\$?\s*([\d.,]+)", texto, default="0"
    ))

    # Valores asegurados
    datos["valor_asegurado_vida"] = _limpiar_num(_buscar(
        r"Valor\s+Asegurado\s+Vida:?\s*\$?\s*([\d.,]+)", texto, default="0"
    ))
    datos["valor_asegurado_inmueble"] = _limpiar_num(_buscar(
        r"Valor\s+Asegurado\s+del\s+Inmueble:?\s*\$?\s*([\d.,]+)",
        texto, default="0"
    ))

    # Saldos (Saldo Anterior / Saldo a [fecha corte])
    datos["saldo_anterior"] = _limpiar_num(_buscar(
        r"Saldo\s+Anterior:?\s*[A-Za-z]{3}\.?\s*\d+/\d+\s*\$?\s*([\d.,]+)",
        texto, default="0"
    ))
    datos["saldo_capital"] = _limpiar_num(_buscar(
        r"Saldo\s+a:\s*[A-Za-z]{3}\.?\s*\d+/\d+\s*\$?\s*([\d.,]+)",
        texto, default="0"
    ))
    # Fallback: ultimo monto despues de "Saldo a:"
    if datos["saldo_capital"] == 0:
        datos["saldo_capital"] = _limpiar_num(_buscar(
            r"Saldo\s+a:?\s*[^\$]*\$?\s*([\d.,]+)", texto, default="0"
        ))

    # Cedula
    datos["cedula"] = cedula_fallback or ""

    # =========================================================
    # VALIDACIONES CRUZADAS
    # =========================================================
    datos["tipo"] = tipo_extracto
    datos["_validacion"] = {}

    # Sin FRECH: Total Aplicado = Capital + Int Corr + Seg Vida + Seg Inc
    if not datos["tiene_frech"]:
        esperado = (datos["abonos_capital"] + datos["intereses_corrientes"]
                    + datos["seguro_vida"] + datos["seguro_incendio"]
                    + datos["seguro_terremoto"])
        diff = abs(datos["total_aplicado"] - esperado)
        datos["_validacion"]["sin_frech_diff"] = round(diff, 2)
        datos["_validacion"]["sin_frech_ok"] = diff < 100.0
    else:
        # Con FRECH: Pago Minimo = Total - Cobertura
        esperado = datos["total_aplicado"] - datos["frech_cobertura_pag1"]
        diff = abs(datos["pago_minimo_cliente"] - esperado)
        datos["_validacion"]["con_frech_diff"] = round(diff, 2)
        datos["_validacion"]["con_frech_ok"] = diff < 100.0

    # Tasa para estudio (regla 4.1 DAVIVIENDA.md)
    datos["tasa_estudio"] = datos["tasa_cobrada"]

    # Plazo pagado (derivado)
    datos["plazo_pagado"] = max(
        0, datos["plazo_inicial"] - datos["cuotas_pendientes"]
    )

    return datos


def datos_a_csv_row(datos: dict, defaults_hubspot: dict = None) -> str:
    """Convierte el dict parseado en una fila CSV compatible con sheets_loader.py
    (42 columnas). Los campos de HubSpot (ingresos, abono, actividad, etc.)
    van vacios o con defaults.
    """
    d = defaults_hubspot or {}
    # Formato: 42 columnas separadas por coma
    # Cuidado: los campos con coma internos van con comillas dobles
    tasa_str = f"{datos['tasa_cobrada']}".replace(".", ",") if datos.get("tasa_cobrada") else "0"
    campos = [
        datos.get("nombre", ""),  # 1 NOMBRE CLIENTE
        "",  # 2 Segundo Titular
        d.get("acceso_hubspot", ""),  # 3 Acceso
        "NORMAL",  # 4 Prioridad
        datos.get("credito", ""),  # 5 Numero de Credito
        d.get("fecha_solicitud", ""),  # 6
        "Pendiente",  # 7 ESTADO
        d.get("fecha_completo_info", ""),  # 8
        "DAVIVIENDA",  # 9 BANCO
        d.get("nota_consultor", ""),  # 10
        d.get("referenciador", ""),  # 11
        d.get("nota_crm", ""),  # 12
        "",  # 13 NOTAS
        "",  # 14
        d.get("equipo", ""),  # 15
        d.get("consultor", ""),  # 16
        "",  # 17
        "",  # 18
        "",  # 19 Estudio
        "",  # 20 Extracto
        datos.get("cedula", ""),  # 21 CC
        datos.get("amortizacion", "Pesos"),  # 22
        datos.get("tipo", "Hipotecario"),  # 23
        f"{int(datos.get('cuota_mensual', 0))}",  # 24 Cuota Mensual
        f"{datos.get('plazo_inicial', 0)}",  # 25 P. Inicial
        f"{datos.get('cuotas_pendientes', 0)}",  # 26 P. Pendiente
        f'"{tasa_str}"',  # 27 Tasa
        "0",  # 28 Frech (campo BD siempre 0; FRECH se refleja en tasa)
        f"{int(datos.get('seguro_vida', 0))}",  # 29
        f"{int(datos.get('seguro_incendio', 0))}",  # 30
        f"{int(datos.get('seguro_terremoto', 0))}",  # 31
        f"{int(datos.get('abonos_capital', 0))}",  # 32 Capital Mensual
        f"{int(datos.get('intereses_corrientes', 0))}",  # 33 Interes Mensual
        f"{int(datos.get('saldo_capital', 0))}",  # 34 Capital Adeudado
        d.get("abono_efectivo", "0"),  # 35
        d.get("ingresos", "0"),  # 36
        d.get("actividad_economica", ""),  # 37
        datos.get("email", ""),  # 38
        d.get("telefono", ""),  # 39
        d.get("ciudad", ""),  # 40
        "",  # 41 REASIGNADOS
        "",  # 42 Mensaje
    ]
    return ",".join(campos)



def main():
    if len(sys.argv) < 2:
        print("Uso: py extract_davivienda_pdf.py <ruta_pdf> [cedula]")
        sys.exit(2)
    pdf_path = sys.argv[1]
    cedula = sys.argv[2] if len(sys.argv) > 2 else ""
    result = parse_davivienda_pdf(pdf_path, cedula_fallback=cedula)
    print(format_as_csv_row(result))


if __name__ == "__main__":
    main()

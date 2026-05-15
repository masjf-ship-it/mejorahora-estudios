# -*- coding: utf-8 -*-
"""
vision_extractor.py - MejorAhora SAS
=====================================
Fallback de extraccion de extractos Davivienda usando Gemini Vision.

Backend: **Vertex AI** (google-genai SDK con `vertexai=True`).
Auth: Service Account `claude-bd-sync@mejorahora-automations.iam.gserviceaccount.com`
      via credentials/sheets_sa.json. Requiere rol "Vertex AI User".
Facturacion: consume el billing del proyecto GCP `mejorahora-automations`,
             donde aplican los creditos de Free Trial (COP 1.1M / 88 dias).

Migracion 2026-04-22 (task #63):
  Antes: google-generativeai + API key (AI Studio) -> pool prepago separado,
         bloqueaba el consumo del Free Trial de GCP.
  Ahora: google-genai (Vertex AI) + service account -> facturacion GCP directa.

Flujo:
  1. Convertir PDF a imagenes PNG (primera y segunda pagina).
  2. Enviar a Gemini con prompt JSON-only.
  3. Parsear respuesta y normalizar tipos.

Dependencias:
  - google-genai >= 0.3             (pip install google-genai)
  - pypdfium2                       (recomendado, sin poppler)
    Alternativa: pdf2image + poppler

Config (sprint_1/config.ini):
  [VERTEX]
  project = mejorahora-automations
  location = us-central1
  credentials_file = ../credentials/sheets_sa.json
"""
from __future__ import annotations

import configparser
import io
import json
import os
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


# ============================================================
# CONFIG
# ============================================================

# Vision config — fuente unica: config_reglas (MASTER_RULES §17.10).
# 2026-05-12: deduplicado de literals locales que duplicaban config_reglas.
# Jose 2026-04-21: priorizar calidad sobre costo (gemini-2.5-pro) para evitar
# errores de lectura que generan conflictos con bancos (caso Carlos Mario Fonseca).
# Alternativas en Vertex: "gemini-2.5-flash" (equilibrio), "gemini-2.0-flash-001".
from config_reglas import (  # noqa: E402
    DEFAULT_GEMINI_MODEL as DEFAULT_MODEL,
    GCP_PROJECT as DEFAULT_PROJECT,
    GCP_LOCATION as DEFAULT_LOCATION,
    MAX_OUTPUT_TOKENS_VISION,
    VISION_MAX_PAGES,
)


def _get_vertex_config() -> dict:
    """Carga project/location/credentials desde env vars o config.ini.

    Precedencia: env var > config.ini [VERTEX] > defaults hardcoded.
    """
    cfg = configparser.ConfigParser()
    cfg.read(SCRIPT_DIR / "config.ini", encoding="utf-8")

    project = (
        os.environ.get("GCP_PROJECT", "").strip()
        or (cfg.get("VERTEX", "project", fallback="").strip() if "VERTEX" in cfg else "")
        or DEFAULT_PROJECT
    )
    location = (
        os.environ.get("GCP_LOCATION", "").strip()
        or (cfg.get("VERTEX", "location", fallback="").strip() if "VERTEX" in cfg else "")
        or DEFAULT_LOCATION
    )

    creds_path = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        or (cfg.get("VERTEX", "credentials_file", fallback="").strip() if "VERTEX" in cfg else "")
    )
    # Fallback al path conocido del proyecto
    if not creds_path:
        candidate = SCRIPT_DIR.parent / "credentials" / "sheets_sa.json"
        if candidate.exists():
            creds_path = str(candidate)
    else:
        # Permitir rutas relativas en config.ini (resueltas contra SCRIPT_DIR)
        cp = Path(creds_path)
        if not cp.is_absolute():
            cp = (SCRIPT_DIR / cp).resolve()
            creds_path = str(cp)

    return {"project": project, "location": location, "credentials_file": creds_path}


def _vertex_client():
    """Retorna un google.genai.Client configurado para Vertex AI."""
    try:
        from google import genai
    except ImportError:
        raise RuntimeError(
            "google-genai SDK no instalado. Ejecutar: pip install google-genai"
        )

    cfg = _get_vertex_config()
    kwargs = {
        "vertexai": True,
        "project": cfg["project"],
        "location": cfg["location"],
    }

    if cfg["credentials_file"]:
        try:
            from google.oauth2 import service_account
        except ImportError:
            raise RuntimeError(
                "google-auth no instalado (viene con google-genai). "
                "Ejecutar: pip install google-auth"
            )
        creds = service_account.Credentials.from_service_account_file(
            cfg["credentials_file"],
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        kwargs["credentials"] = creds

    return genai.Client(**kwargs)


# ============================================================
# PDF -> IMAGENES
# ============================================================

def _pdf_to_png_bytes(pdf_path: Path, max_pages: int = VISION_MAX_PAGES,
                       password: str = "") -> list:
    """Convierte primeras `max_pages` paginas del PDF a PNG bytes.
    Usa pypdfium2 si esta disponible (sin poppler), sino pdf2image.

    2026-05-15: `password` para PDFs protegidos (Bancolombia usa la cedula).
    """
    pdf_path = Path(pdf_path)
    # Intento 1: pypdfium2 (pure-python backend, sin poppler)
    try:
        import pypdfium2 as pdfium
        if password:
            pdf = pdfium.PdfDocument(str(pdf_path), password=password)
        else:
            pdf = pdfium.PdfDocument(str(pdf_path))
        try:
            out = []
            n = min(len(pdf), max_pages)
            for i in range(n):
                page = pdf[i]
                pil_image = page.render(scale=2.0).to_pil()
                buf = io.BytesIO()
                pil_image.save(buf, format="PNG")
                out.append(buf.getvalue())
                page.close()
            return out
        finally:
            # Cierre explicito evita WinError 32 al limpiar tempfile en Windows
            pdf.close()
    except ImportError:
        pass

    # Intento 2: pdf2image + poppler (password no soportado por pdf2image directo;
    # si el PDF requiere password y no hay pypdfium2 disponible, lanza error claro)
    if password:
        raise RuntimeError(
            "PDF requiere password pero pypdfium2 no esta disponible. "
            "pdf2image no soporta password directo. Instalar: pip install pypdfium2"
        )
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError(
            "Se requiere pypdfium2 (recomendado) o pdf2image+poppler. "
            "Instalar: pip install pypdfium2"
        )
    images = convert_from_path(str(pdf_path), dpi=200, first_page=1, last_page=max_pages)
    out = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        out.append(buf.getvalue())
    return out


# ============================================================
# PROMPT Y LLAMADA
# ============================================================

EXTRACTION_PROMPT_DAVIVIENDA = """Eres un parser de extractos bancarios Davivienda (Colombia).

Extrae de la imagen los siguientes campos y responde SOLO con un objeto JSON
valido (sin comentarios, sin texto fuera del JSON, sin bloques markdown).

Campos requeridos (usar null si no aparece):

{
  "credito": string,           // ej "570046660023750-2" o "600xxxxxxxx-x"
  "nombre": string,            // titular, MAYUSCULAS
  "email": string,
  "cuota_mensual": number,     // "Valor Cuota Mes"
  "valor_prorrogado": number,
  "valor_mora": number,
  "plazo_inicial": number,     // meses
  "cuotas_pendientes": number,
  "cuotas_pagadas": number,
  "dias_liquidados": number,
  "dias_mora": number,
  "amortizacion": string,      // "Pesos" si es Cuota Fija $; "Uvr" si UVR
  "tasa_pactada": number,      // EA en decimal 0.xxxx  (ej 0.1431)
  "tasa_cobrada": number,      // EA en decimal 0.xxxx
  "tasa_seguro_vida": number,
  "tasa_seguro_incendio": number,
  "tiene_frech": boolean,
  "frech_cobertura_pag1": number,
  "pago_minimo_cliente": number,
  "seguro_vida": number,
  "seguro_incendio": number,
  "seguro_terremoto": number,
  "intereses_corrientes": number,
  "intereses_mora": number,
  "abonos_capital": number,
  "total_aplicado": number,
  "valor_asegurado_vida": number,
  "valor_asegurado_inmueble": number,
  "saldo_anterior": number,
  "saldo_capital": number,     // "Saldo a: <fecha corte>"
  "seguros_inferior_total": number, // R-DVV-06: valor "+ Seguros" del cuadro inferior 2a hoja (ver mas abajo)
  "tipo": string               // "Hipotecario" | "Leasing H." | "Consumo 590"
}

DICCIONARIO DAVIVIENDA (etiqueta del extracto -> campo JSON):
- "Seguro de Vida"              -> seguro_vida  ⚠️ CRÍTICO ver abajo
- "Seguro de Incendio y Anexos" -> seguro_incendio
- "Seguro de Terremoto"         -> seguro_terremoto (base)
- "Seguro Proteccion de Pagos"  -> SUMAR al seguro_terremoto (convencion MejorAhora:
                                   el slot terremoto agrupa TODO seguro no-vida no-incendio.
                                   Si el PDF muestra solo "Proteccion de Pagos" sin "Terremoto",
                                   seguro_terremoto = valor de "Proteccion de Pagos").
- "Bonos a Capital"             -> abonos_capital (es el CAPITAL MENSUAL del extracto;
                                   NO confundir con "Total Aplicado").
- "Intereses Corrientes"        -> intereses_corrientes
- "Intereses de Mora"           -> intereses_mora
- "Total Aplicado"              -> total_aplicado (pago TOTAL del mes = capital+intereses+seguros.
                                   NUNCA mapear este valor como capital ni como saldo).
- "Valor Cuota Mes"             -> cuota_mensual

SEGURO_VIDA (campo CRITICO reforzado retro 2026-04-24, casos Yolly/Maria F/Karen L):
- En extractos Davivienda hipotecarios CASI SIEMPRE existe seguro de vida (es obligatorio).
- Etiquetas variantes: "Seguro de Vida", "Seg. Vida", "Vida", "Seguro Vida Deudor".
- Si vez una columna o tabla "Valores en Pesos" con varios renglones, el primero o segundo
  típicamente es seguro de vida (entre $5,000 y $200,000 COP).
- Si vez "Seguro de Incendio y Anexos" CON valor > 0, debe haber tambien "Seguro de Vida"
  con valor > 0 — busca harder en el extracto.
- Solo devolver seguro_vida=0 si REALMENTE no aparece en NINGUNA seccion del extracto.
- Falsa interpretacion comun: confundir "Seguro de Vida" con "Valor Asegurado Vida"
  (este ultimo es el monto cubierto, NO la prima mensual).

SEGUROS_INFERIOR_TOTAL (R-DVV-06 — duplicacion cuota por pago irregular):
- Es el valor "+ Seguros" que aparece en el cuadro INFERIOR de la 2a hoja del extracto
  Davivienda, en la seccion de "Valores Aplicados al Periodo" o similar.
- Etiquetas variantes que pueden encontrarse: "+ Seguros", "Seguros", "Total Seguros",
  "Sub-total Seguros".
- Representa la SUMA REAL DE SEGUROS del mes, sin duplicacion. No cambia aunque el cliente
  haya pagado 2 cuotas en el mismo mes (mala pagaduria).
- Buscar SIEMPRE en la 2a hoja del extracto (a veces despues de "Valores aplicados",
  "Detalle de pagos", o secciones equivalentes).
- Si NO aparece ese cuadro (extracto de 1 sola hoja o sin resumen inferior), devolver null.
- Valor tipico: entre $30,000 y $200,000 COP para hipotecarios.
- Ejemplo Leidy Yesenia (leasing Davivienda): seguros_inferior_total = 111315.
- Ejemplo Karen Tatiana Capera: seguros_inferior_total = 46392 (cliente sin duplicacion,
  pero el valor existia porque siempre se reporta).

SALDO_CAPITAL (campo critico — errores aqui generan conflictos bancarios):
- Es el SALDO TOTAL DE LA DEUDA al corte, NO un saldo parcial ni mensual.
- Buscar en el cuadro resumen "Valor en Pesos" del lado derecho del extracto.
- Tomar el valor mas alto de la columna que represente saldo del credito al cierre.
- Typicamente saldo_capital esta en el rango millones (ej 12.985.249,96 para Fernando).
- NO tomar valores pequenos ($2M o menos) que suelen ser saldos parciales o intereses acumulados.
- Si hay dos columnas "Valor en Pesos" (una arriba con detalle mensual, otra abajo con resumen),
  el saldo_capital correcto esta en la de ABAJO (resumen total del credito).

Reglas:
- Montos en pesos colombianos, sin simbolo ni separadores: usar numero (float).
- Porcentajes como decimal: 14,31% -> 0.1431.
- Si una pagina no contiene un campo, no lo inventes: usar null.
- Si ves "Seguro Proteccion de Pagos" pero NO "Seguro de Terremoto": seguro_terremoto = valor de Proteccion de Pagos.
- Si ves ambos: seguro_terremoto = suma de los dos.
- No incluir explicaciones.

EJEMPLO DE REFERENCIA (Fernando Gallo, credito 570238110001018-4):
  seguro_vida=29383, seguro_incendio=52976, seguro_terremoto=12758 (viene de "Proteccion de Pagos"),
  abonos_capital=35607.70, intereses_corrientes=99275.30, saldo_capital=12985249.96,
  cuota_mensual=229000. Si tu extraccion se aleja de este patron en un caso similar, revisa
  que no estes tomando valores del cuadro de amortizacion mensual en lugar del resumen total."""


# ============================================================
# PROMPT BANCOLOMBIA (2026-05-15 — caso Jose, formato distinto)
# ============================================================
EXTRACTION_PROMPT_BANCOLOMBIA = """Eres un parser de extractos bancarios Bancolombia (Colombia).

Extrae de la imagen los siguientes campos y responde SOLO con un objeto JSON
valido (sin comentarios, sin texto fuera del JSON, sin bloques markdown).

ENCABEZADO DEL EXTRACTO:
- Titulo: "Estado de Credito Hipotecario en PESOS"
- Salutacion: "SEÑOR(A): <NOMBRE COMPLETO>"
- Linea con: Fecha de Pago | Fecha en que se genero el extracto | Valor a Pagar | Saldo a la fecha...

Campos requeridos (usar null si no aparece):

{
  "credito": string,           // "Numero de credito 9NNNNNNNNNN" (formato Bancolombia sin guion verificador, ej "90000386475")
  "nombre": string,            // titular completo, MAYUSCULAS, despues de "SEÑOR(A):"
  "email": string,             // si aparece (NO usar emails de @bancolombia.com — esos son del banco)
  "cuota_mensual": number,     // "Valor de la cuota sin seguros y sin comisiones" + seguros (SIN mora). Si solo encuentras "Valor a Pagar", usalo (puede incluir mora — registrar valor_cuotas_vencidas para descontar).
  "valor_a_pagar": number,     // "Valor a Pagar" (header tabla pag.1, incluye mora si la hay)
  "valor_cuota_sin_seguros": number, // "Valor de la cuota sin seguros y sin comisiones"
  "valor_prorrogado": number,  // null si Bancolombia no lo expone
  "valor_mora": number,        // "Valor cuotas vencidas" (si > 0 cliente esta en mora)
  "plazo_inicial": number,     // "Plazo total en meses" (ej 240)
  "cuotas_pendientes": number, // "Nro. cuotas pendientes para pago total"
  "cuotas_pagadas": number,    // ("Nro. cuota a cancelar" - 1)
  "dias_liquidados": number,   // Bancolombia no lo expone explicitamente; usar 30 por defecto
  "dias_mora": number,         // si "Nro. cuotas vencidas" > 0, retornar 30. Sino 0.
  "cuotas_vencidas": number,   // "Nro. cuotas vencidas" (entero)
  "amortizacion": string,      // "Pesos" si Plan menciona "PESOS"; "Uvr" si UVR
  "tasa_pactada": number,      // "Tasa interes pactada X% EA" — decimal (13.00% -> 0.1300)
  "tasa_cobrada": number,      // "Tasa interes cobrada X% EA" — CANONICA para estudio (R-BCO-04)
  "tasa_subsidiada": number,   // "Tasa interes subsidiada X% EA" (decimal)
  "tasa_mora_cobrada": number, // "Tasa interes mora cobrada X% EA" (decimal, suele 14-20%)
  "tasa_seguro_vida": number,  // Bancolombia tabula por edad en pag.2; usar 0 si no aplica
  "tasa_seguro_incendio": number,
  "tiene_frech": boolean,      // true si "Valor subsidio Gobierno" > 0 OR "tasa_subsidiada" > 0
  "frech_cobertura_pag1": number, // "Valor subsidio Gobierno"
  "pago_minimo_cliente": number,  // "Valor cuota con subsidio" si tiene_frech
  "seguro_vida": number,       // "Valor seguro vida" (con o sin asterisco prefijo)
  "seguro_incendio": number,   // "Valor seguro incendio"
  "seguro_terremoto": number,  // "Valor seguro terremoto"
  "intereses_corrientes": number, // suma columna "Intereses Corriente" de la tabla "Movimientos Ultimo Periodo"
  "intereses_mora": number,    // "Interes de mora" (campo unico, NO de la tabla)
  "abonos_capital": number,    // suma columna "Capital" de la tabla "Movimientos Ultimo Periodo"
  "total_aplicado": number,    // suma de Capital + Intereses + Seguros aplicados en el periodo
  "valor_asegurado_vida": number,    // Bancolombia muestra solo "Valor asegurado Incendio y Terremoto"
  "valor_asegurado_inmueble": number, // "Valor asegurado Incendio y Terremoto $ X"
  "saldo_anterior": number,    // saldo capital + abonos del periodo (estimar)
  "saldo_capital": number,     // "Saldo a la fecha en que se genero el extracto $ X" — VALOR EN HEADER TABLA
  "seguros_inferior_total": number, // Bancolombia no expone este campo separado; usar null
  "tipo": string,              // "Hipotecario" si "Estado de Credito Hipotecario"; "Leasing H." si menciona Leasing
  "es_vis": boolean            // true si "Plan: ... VIVDA VIS"; false si "VIVDA NOVIS"
}

DICCIONARIO BANCOLOMBIA (etiqueta del extracto -> campo JSON):
- "Numero de credito 9NNNNNNN" (sin guion) -> credito
- "SEÑOR(A): NOMBRE"               -> nombre
- "Saldo a la fecha en que se genero el extracto" -> saldo_capital
- "Valor a Pagar"                  -> valor_a_pagar
- "Valor de la cuota sin seguros y sin comisiones" -> valor_cuota_sin_seguros
- "Tasa interes cobrada X% EA"     -> tasa_cobrada  ⚠️ CANONICA (R-BCO-04)
- "Tasa interes pactada X% EA"     -> tasa_pactada
- "Tasa interes mora cobrada X%"   -> tasa_mora_cobrada (NUNCA usar como tasa_cobrada)
- "Tasa interes subsidiada X%"     -> tasa_subsidiada
- "Plazo total en meses"           -> plazo_inicial
- "Nro. cuota a cancelar"          -> cuotas_pagadas + 1
- "Nro. cuotas pendientes para pago total" -> cuotas_pendientes
- "Nro. cuotas vencidas"           -> cuotas_vencidas (si > 0, cliente en mora)
- "Valor cuotas vencidas"          -> valor_mora
- "Interes de mora"                -> intereses_mora
- "Valor seguro vida"              -> seguro_vida (puede tener * prefijo)
- "Valor seguro incendio"          -> seguro_incendio
- "Valor seguro terremoto"         -> seguro_terremoto
- "Valor subsidio Gobierno"        -> frech_cobertura_pag1 (FRECH)
- "Valor cuota con subsidio"       -> pago_minimo_cliente (cuando hay FRECH)
- "Valor asegurado Incendio y Terremoto" -> valor_asegurado_inmueble
- "Plan: CUOTA CONSTANTE EN PESOS-VIVDA VIS"   -> es_vis=true, amortizacion="Pesos"
- "Plan: CUOTA CONSTANTE EN PESOS-VIVDA NOVIS" -> es_vis=false, amortizacion="Pesos"

TABLA "Movimientos Ultimo Periodo" (pag.1 final):
Columnas: Fecha | Descripcion | Capital | Intereses Corriente | Intereses Mora | Vida | Incendio | Terremoto | Otros | Total
Sumar columnas:
- abonos_capital = suma de columna "Capital" (puede incluir abonos extras, beneficios)
- intereses_corrientes = suma de columna "Intereses Corriente"
- total_aplicado = suma de columna "Total" (toda la tabla)

CLIENTES EN MORA (Bancolombia):
- Si "Nro. cuotas vencidas" > 0: cliente en mora.
- "Valor a Pagar" incluye TANTO la cuota corriente COMO las vencidas + interes de mora.
- Para `cuota_mensual` del estudio: usar SIEMPRE "Valor de la cuota sin seguros y sin comisiones" + seguros aplicados (NO usar valor_a_pagar porque incluye mora).
- Esto evita inflar la cuota canonica con la deuda atrasada.

CLIENTES CON FRECH (subsidio Gobierno activo):
- "Valor subsidio Gobierno" > 0 indica FRECH activo.
- "Tasa interes subsidiada" > 0 tambien lo confirma.
- La cuota efectiva del cliente es "Valor cuota con subsidio" (no la cuota total).
- Para el estudio, usar `tasa_cobrada` (NO la subsidiada) — el subsidio del Gobierno
  termina en algun momento y queremos estudiar el escenario sin subsidio.

INGRESOS REQUERIDOS:
- Bancolombia NO requiere ingresos certificados para reduccion de plazo (R-BCO-05).
- Si el extracto NO menciona ingresos, dejar el campo `ingresos` fuera del JSON
  (el pipeline lo setea a 0 automaticamente).

ENCODING DEL PDF BANCOLOMBIA:
- Los PDFs originales tienen caracteres mojibake (é → `�`, ó → `�`, ñ → `�`).
- Cuando veas el caracter `�`, asume que probablemente es: e, o, n con tilde.
- Ejemplo: "SE�OR(A):" = "SEÑOR(A):"; "N�mero" = "Numero".

Reglas finales:
- Montos en pesos colombianos: numero float, sin simbolo ni separadores.
- Porcentajes EA como decimal: "13.00% EA" -> 0.1300.
- Si una pagina no contiene un campo, NO LO INVENTES: usar null.
- No incluir explicaciones ni markdown.

EJEMPLO DE REFERENCIA (MARISOL SANCHEZ SALGUERO, credito 90000386475 VIS sin FRECH):
  saldo_capital=152172660.26, cuota_mensual=1767048.00, valor_cuota_sin_seguros=1703850.00,
  seguro_vida=35149, seguro_incendio=16830, seguro_terremoto=11219,
  tasa_cobrada=0.1300, plazo_inicial=240, cuotas_pendientes=236, cuotas_vencidas=0,
  tiene_frech=false, es_vis=true, tipo="Hipotecario".

EJEMPLO DE REFERENCIA EN MORA (YANINE NAVARRO, credito 90000102858 NOVIS):
  saldo_capital=42641427.90, cuota_mensual=494031.05 (sin mora), valor_a_pagar=989714.67 (con mora),
  cuotas_vencidas=1, valor_mora=495683.62, intereses_mora=240.57,
  tasa_cobrada=0.1045, tasa_mora_cobrada=0.1568,
  seguro_vida=17586, seguro_incendio=15106, seguro_terremoto=10070,
  plazo_inicial=240, cuotas_pendientes=177, tiene_frech=false, es_vis=false."""


# ============================================================
# DISPATCHER MULTI-BANCO (2026-05-15)
# ============================================================

PROMPTS_POR_BANCO = {
    "DAVIVIENDA": EXTRACTION_PROMPT_DAVIVIENDA,
    "BANCOLOMBIA": EXTRACTION_PROMPT_BANCOLOMBIA,
}

# Retrocompat: codigo viejo que lee EXTRACTION_PROMPT (default Davivienda).
EXTRACTION_PROMPT = EXTRACTION_PROMPT_DAVIVIENDA


def _get_prompt(banco: str = "DAVIVIENDA") -> str:
    """Retorna el prompt Gemini correcto segun el banco. Default: Davivienda."""
    return PROMPTS_POR_BANCO.get(banco.upper(), EXTRACTION_PROMPT_DAVIVIENDA)


def _call_gemini_vision(image_bytes_list: list, model: str = DEFAULT_MODEL,
                        banco: str = "DAVIVIENDA") -> dict:
    """Llama Gemini via Vertex AI y parsea JSON estricto.

    2026-05-15: parametro `banco` selecciona el prompt apropiado del dict
    PROMPTS_POR_BANCO. Default Davivienda por retrocompat.
    """
    from google.genai import types

    client = _vertex_client()

    parts = [
        types.Part.from_bytes(data=img, mime_type="image/png")
        for img in image_bytes_list
    ]
    parts.append(_get_prompt(banco))

    resp = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            # 2026-04-22: subido de 2048 a 8192 tras caso Fernando donde JSON
            # se truncaba en "cuota. gemini-2.5-pro consume tokens en thinking
            # budget interno antes de emitir salida; 2048 quedaba corto.
            # 2026-05-12: dedup — fuente unica config_reglas.MAX_OUTPUT_TOKENS_VISION.
            max_output_tokens=MAX_OUTPUT_TOKENS_VISION,
            temperature=0.0,
        ),
    )

    full_text = (resp.text or "").strip()
    if not full_text:
        fr = "n/a"
        try:
            fr = str(resp.candidates[0].finish_reason)
        except Exception:
            pass
        raise ValueError(f"Respuesta vacia de Gemini. finish_reason={fr}")

    # Defensa: si por alguna razon viene envuelto en markdown o texto extra
    m = re.search(r"\{[\s\S]*\}", full_text)
    if not m:
        raise ValueError(f"No se encontro JSON en la respuesta de Gemini:\n{full_text[:500]}")
    raw_json = m.group(0)
    return json.loads(raw_json)


# ============================================================
# NORMALIZACION A SCHEMA DEL PARSER CLASSICO
# ============================================================

def _norm_num(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return 0.0


def _merge_with_base(base: dict, vision: dict) -> dict:
    """Prioriza base (pdfplumber) y rellena vacios desde vision."""
    out = dict(base) if base else {}
    for k, v in (vision or {}).items():
        if v is None:
            continue
        current = out.get(k)
        if current in (None, "", 0, 0.0) or (isinstance(current, dict) and not current):
            out[k] = v
    # Normalizar numericos conocidos
    num_fields = [
        "cuota_mensual", "valor_prorrogado", "valor_mora", "plazo_inicial",
        "cuotas_pendientes", "cuotas_pagadas", "dias_liquidados", "dias_mora",
        "tasa_pactada", "tasa_cobrada", "tasa_seguro_vida", "tasa_seguro_incendio",
        "frech_cobertura_pag1", "pago_minimo_cliente", "seguro_vida",
        "seguro_incendio", "seguro_terremoto", "intereses_corrientes",
        "intereses_mora", "abonos_capital", "total_aplicado",
        "valor_asegurado_vida", "valor_asegurado_inmueble", "saldo_anterior",
        "saldo_capital", "seguros_inferior_total",
    ]
    for k in num_fields:
        if k in out:
            out[k] = _norm_num(out[k])
    return out


# ============================================================
# API PUBLICA
# ============================================================

CAMPOS_CRITICOS = [
    "credito", "cuota_mensual", "plazo_inicial", "cuotas_pendientes",
    "tasa_cobrada", "saldo_capital",
]


def necesita_fallback(datos_base: dict) -> bool:
    """True si faltan campos criticos -> disparar Vision."""
    if not datos_base:
        return True
    for k in CAMPOS_CRITICOS:
        v = datos_base.get(k)
        if v in (None, "", 0, 0.0):
            return True
    return False


def extraer_con_vision(pdf_path: Path, base: dict = None,
                       model: str = DEFAULT_MODEL,
                       banco: str = "DAVIVIENDA",
                       password: str = "") -> dict:
    """Llama Gemini Vision sobre el PDF y retorna datos mergeados con `base`.

    Si `base` es None, retorna solo los datos de Vision normalizados.

    2026-05-15: nuevos parametros
      - `banco`: selecciona el prompt apropiado (DAVIVIENDA / BANCOLOMBIA).
      - `password`: password de apertura del PDF (Bancolombia usa la cedula).
    """
    imgs = _pdf_to_png_bytes(pdf_path, max_pages=VISION_MAX_PAGES, password=password)
    vision = _call_gemini_vision(imgs, model=model, banco=banco)
    if base is None:
        return _merge_with_base({}, vision)
    return _merge_with_base(base, vision)


# ============================================================
# SMOKE TEST
# ============================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python vision_extractor.py <ruta_pdf>")
        sys.exit(2)
    pdf = Path(sys.argv[1])
    out = extraer_con_vision(pdf)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))

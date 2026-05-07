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

# gemini-2.5-pro: maxima precision para extractos bancarios.
# Jose 2026-04-21: priorizar calidad sobre costo para evitar errores de lectura
# que generan conflictos con bancos/clientes (ver caso Carlos Mario Fonseca).
# Alternativas en Vertex: "gemini-2.5-flash" (equilibrio), "gemini-2.0-flash-001" (barato).
DEFAULT_MODEL = "gemini-2.5-pro"
DEFAULT_PROJECT = "mejorahora-automations"
DEFAULT_LOCATION = "us-central1"


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

def _pdf_to_png_bytes(pdf_path: Path, max_pages: int = 2) -> list:
    """Convierte primeras `max_pages` paginas del PDF a PNG bytes.
    Usa pypdfium2 si esta disponible (sin poppler), sino pdf2image.
    """
    pdf_path = Path(pdf_path)
    # Intento 1: pypdfium2 (pure-python backend, sin poppler)
    try:
        import pypdfium2 as pdfium
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

    # Intento 2: pdf2image + poppler
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

EXTRACTION_PROMPT = """Eres un parser de extractos bancarios Davivienda (Colombia).

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


def _call_gemini_vision(image_bytes_list: list, model: str = DEFAULT_MODEL) -> dict:
    """Llama Gemini via Vertex AI y parsea JSON estricto."""
    from google.genai import types

    client = _vertex_client()

    parts = [
        types.Part.from_bytes(data=img, mime_type="image/png")
        for img in image_bytes_list
    ]
    parts.append(EXTRACTION_PROMPT)

    resp = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            # 2026-04-22: subido de 2048 a 8192 tras caso Fernando donde JSON
            # se truncaba en "cuota. gemini-2.5-pro consume tokens en thinking
            # budget interno antes de emitir salida; 2048 quedaba corto.
            max_output_tokens=8192,
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
                       model: str = DEFAULT_MODEL) -> dict:
    """Llama Gemini Vision sobre el PDF y retorna datos mergeados con `base`.

    Si `base` es None, retorna solo los datos de Vision normalizados.
    """
    imgs = _pdf_to_png_bytes(pdf_path, max_pages=2)
    vision = _call_gemini_vision(imgs, model=model)
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

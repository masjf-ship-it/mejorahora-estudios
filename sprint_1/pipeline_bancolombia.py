#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_davivienda.py — MejorAhora SAS
========================================
Orquestador E2E autonomo para estudios Davivienda.

Flujo por cliente (fila STAGING):
  1. Buscar carpeta cliente en Drive §4.1 por nombre -> PDF id
  2. Descargar PDF a tmp local
  3. HubSpot cascade (CC -> email -> nombre). Consultor OPCIONAL.
  4. Si PDF protegido: intentar desencriptar con CC (STAGING + HubSpot).
  5. Parsear con pdfplumber; si faltan criticos -> Claude Vision fallback
  6. Clasificar extracto: ok / INCOMPLETO / ILEGIBLE
  7. Construir DatosClienteExcel
  8. Aplicar Regla 9.3 (abono extraordinario) y Regla 9.4 (proponer plazos)
  9. ExcelPopulator.crear_estudio() -> output/ESTUDIO <NOMBRE>-DD.MM.AA.xlsx
 10. Upload a Drive §4.2 (folder analistas)
 11. Actualizar STAGING: estado="Excel generado" + link drive

Hard blockers (solo 4 detienen el estudio):
  PDF_PROTEGIDO           - Encriptado y ninguna CC candidata abre
  EXTRACTO_ILEGIBLE       - pdfplumber + Vision no extrajeron nada util
  EXTRACTO_INCOMPLETO: X  - Faltan algunos campos criticos (X = lista)
  BANCO_NO_TRABAJADO      - Filtrado upstream en listar_pendientes_hoy

Soft (nunca bloquean):
  consultor vacio, ingresos vacio, abono vacio -> Excel se genera igual.

Fase A (hoy):
  - Procesa Hipotecario (570/571) y Leasing Habitacional (600) IGUAL.
  - Jose 2026-04-24: leasing = hipotecario sin ajustes especiales (R-DVV-09).
    FRECH se lee correctamente del extracto y la plantilla maestra calcula bien.

Uso:
    py pipeline_davivienda.py                         # todos los pendientes
    py pipeline_davivienda.py --nombre "FERNANDO..."  # un solo cliente
    py pipeline_davivienda.py --dry-run               # sin generar Excel ni update STAGING
    py pipeline_davivienda.py --max 3                 # limitar cantidad

Scheduled task: MejorAhora\\Pipeline Davivienda AM (DAILY 08:30)
"""
from __future__ import annotations

import argparse
import configparser
import datetime as dt
import json
import re
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

# --- Modulos del proyecto ---
from excel_populator import ExcelPopulator, DatosClienteExcel
from proponedor_plazos import proponer_plazos
from extract_bancolombia_pdf import parse_bancolombia_pdf as parse_pdf_banco
# 2026-05-15: alias parse_pdf_banco (apuntando a Bancolombia) para minimizar diff
# vs pipeline_davivienda original. parse_davivienda_pdf alias retrocompat opcional.
from generar_desde_sheets import (
    aplicar_regla_93_abono_extraordinario,
    ocultar_hoja_bd,
    cargar_config,
    _capital_intereses_simulador,  # retro 2026-04-24: validar DIF.SIMULA post-9.3
)
import drive_client
import vision_extractor
import validar_extraccion_bancolombia as _m1  # 2026-05-15: M1 Bancolombia
import validar_excel_generado as _m2
from hubspot_client import HubSpotClient
try:
    from oauth_drive import get_oauth_drive, upload_to_folder_oauth
    _HAS_OAUTH = True
except Exception:
    _HAS_OAUTH = False


# ============================================================
# CONSTANTES
# ============================================================

BANCO = "BANCOLOMBIA"  # 2026-05-15: pipeline Bancolombia (paralelo a Davivienda)
# Prefijos validos por tipo. Fuente unica: config_reglas.py (R-DVV-08).
# 2026-04-23 (Jose): agregado 571 como hipotecario tras caso Karen Tatiana Capera
# (credito 571616690012705-4 verificado como hipotecario normal Davivienda).
# 2026-05-07: deduplicado — antes estos literals vivian aqui Y en config_reglas.
# 2026-05-12: agregadas tolerancias R-DVV-06 G1/G2/G3 (antes hardcoded en funcion).
from config_reglas import (
    PREFIJOS_HIPOTECARIO,  # noqa: F401  # R-DVV-08 no aplica BCO (ver clasificar_credito)
    PREFIJOS_LEASING,  # noqa: F401
    TOLERANCIA_G1_CUOTA_DUPLICADA,
    UMBRAL_G2_DISCREPANCIA_SEGUROS,
    TOLERANCIA_G3_SUMA_DUPLICADA,
    TOLERANCIA_DIF_SIMULA,
    verify_pesos_template,
)

LOG_DIR = PROJECT_ROOT / "_logs"
LOG_DIR.mkdir(exist_ok=True)


# ============================================================
# STAGING I/O
# ============================================================

def _norm(s: str) -> str:
    import unicodedata
    if not s:
        return ""
    s = str(s).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    for ch in [".", ",", ";", ":", "-", "_", "/", "\\", "|", "(", ")", "*"]:
        s = s.replace(ch, " ")
    return " ".join(s.split())


def _abrir_staging(gc):
    # 2026-05-14: pestana renombrada STAGING -> GENERADOS (config_reglas).
    # La funcion conserva el nombre _abrir_staging por compatibilidad interna.
    from config_reglas import SHEET_PESTANA_DESTINO
    sh = gc.open_by_key(drive_client.SHEET_ID_BD)
    ws = sh.worksheet(SHEET_PESTANA_DESTINO)
    rows = ws.get_all_values()
    if not rows:
        raise RuntimeError(f"{SHEET_PESTANA_DESTINO} vacia (ni header).")
    header = rows[0]
    body = rows[1:]
    idx = {}
    def find(*cands):
        for c in cands:
            k = _norm(c)
            for i, h in enumerate(header):
                if _norm(h) == k:
                    return i
        for c in cands:
            k = _norm(c)
            for i, h in enumerate(header):
                if k in _norm(h):
                    return i
        return None
    idx["nombre"]    = find("NOMBRE CLIENTE", "NOMBRE")
    idx["credito"]   = find("Numero de Credito", "NUMERO DE CREDITO", "CREDITO")
    idx["estado"]    = find("ESTADO")
    idx["banco"]     = find("BANCO")
    idx["cc"]        = find("CC", "Cedula")
    idx["acceso"]    = find("Acceso")  # En STAGING, "Acceso" suele contener la CC
    idx["email"]     = find("E-mail", "EMAIL", "Correo")
    idx["consultor"] = find("Consultor")
    idx["ingresos"]  = find("Ingresos demostrables", "Ingresos", "INGRESOS")
    idx["abono"]     = find("Abono Efectivo", "Abono", "ABONO")
    idx["actividad"] = find("Actividad Econ", "ACTIVIDAD")
    idx["referenciador"] = find("Referenciador")
    idx["telefono"]  = find("Tel", "TELEFONO", "Telefono")
    idx["ciudad"]    = find("Ciudad", "CIUDAD")
    idx["link_estudio"] = find("Estudio", "Link Estudio")
    idx["nota_crm"]  = find("Nota PARA CRM", "NOTA PARA CRM", "Nota CRM", "NOTA CRM")
    if idx["nombre"] is None or idx["banco"] is None:
        raise RuntimeError(f"STAGING sin columnas minimas. Header: {header}")
    return ws, header, body, idx


def _filtrar_pendientes_davivienda(body: list, idx: dict, nombre_filter: str = "",
                                    credito_filter: str = "", force: bool = False) -> list:
    out = []
    for row_i, row in enumerate(body, start=2):  # 1-based + header
        def g(key):
            j = idx.get(key)
            if j is None or j >= len(row):
                return ""
            return (row[j] or "").strip()
        banco = _norm(g("banco"))
        if BANCO.lower() not in banco:
            continue
        estado = _norm(g("estado"))
        if not force:
            if estado in ("excel generado", "procesado", "completado", "realizado"):
                continue
            # 2026-04-24 (R-DVV-09): PENDIENTE_FRECH ya NO bloquea — leasing 600
            # se procesa igual que hipotecario. Los marcados anteriormente con
            # ese estado deben re-procesarse normalmente.
        nombre = g("nombre")
        if not nombre:
            continue
        credito = g("credito")
        if nombre_filter and _norm(nombre_filter) not in _norm(nombre):
            continue
        if credito_filter and credito_filter.strip() not in credito:
            continue
        # CC real puede estar en "CC" o en "Acceso" (inconsistencia STAGING)
        cc_val = g("cc") or g("acceso")
        # Si "acceso" viene como URL (caso REGISTROS importado), descartar
        if cc_val and cc_val.lower().startswith("http"):
            cc_val = g("cc")
        # R-DVV-14: "N/A" no es un CC válido — evita match cruzado en REGISTROS
        if cc_val and cc_val.upper().strip() in ("N/A", "NA", "N.A."):
            cc_val = g("cc")  # solo columna CC pura (no Acceso)
            if cc_val and cc_val.upper().strip() in ("N/A", "NA", "N.A."):
                cc_val = ""  # definitivamente vacío
        out.append({
            "row_idx": row_i,
            "nombre": nombre,
            "credito": credito,
            "cc": cc_val,
            "email": g("email"),
            "consultor": g("consultor"),
            "ingresos": g("ingresos"),
            "abono": g("abono"),
            "actividad_economica": g("actividad"),
            "referenciador": g("referenciador"),
            "telefono": g("telefono"),
            "ciudad": g("ciudad"),
            "estado": g("estado"),
        })
    return out


def _staging_update(ws, row_idx: int, idx: dict, estado: str, link: str = "",
                     nota_crm: str = ""):
    """Actualiza estado, link y (opcional) Nota PARA CRM en fila STAGING.

    2026-04-23 (Fase 3): la nota se escribe en columna L "Nota PARA CRM".
    Regla universal `feedback_nota_crm_columna_l.md` — aplica a bancos con
    ingresos certificados. Si ya hay contenido previo, se PRESERVA y se
    agrega la nueva al final separada por " | ".
    """
    # gspread usa 1-based indexing
    if idx.get("estado") is not None:
        ws.update_cell(row_idx, idx["estado"] + 1, estado)
    if link and idx.get("link_estudio") is not None:
        ws.update_cell(row_idx, idx["link_estudio"] + 1, link)
    if nota_crm and idx.get("nota_crm") is not None:
        col = idx["nota_crm"] + 1
        # Preservar nota previa si existe (concat con separador)
        try:
            prev = (ws.cell(row_idx, col).value or "").strip()
        except Exception:
            prev = ""
        final = nota_crm if not prev else f"{prev} | {nota_crm}"
        ws.update_cell(row_idx, col, final)


# ============================================================
# CLASIFICACION CREDITO — Bancolombia (R-DVV-08 NO aplica)
# ============================================================

def clasificar_credito(credito: str) -> str:
    """Bancolombia: TODO extracto es 'Estado de Credito Hipotecario en PESOS'.

    2026-05-15 (bug clone): la version original heredada de
    pipeline_davivienda.py validaba prefijos 570/571 (hipotecario) y 600
    (leasing) de R-DVV-08. Bancolombia usa formato 9NNNNNNNNNN (sin guion
    verificador, ver MOM_BANCOLOMBIA §3 mapeo y §5 "R-DVV-08 NO aplica").
    Los creditos BCO (ej. 90000404120) no matcheaban ningun prefijo
    Davivienda -> clasificar_credito devolvia "otro" -> el pipeline los
    saltaba con "Credito no reconocido" ANTES de abrir el PDF. Detectado
    en run cloud 2026-05-15 19:43 (4/4 BCO saltados).

    Bancolombia NO tiene taxonomia hipotecario-vs-leasing por prefijo:
    el extracto SIEMPRE es hipotecario (MOM_BANCOLOMBIA §1). Solo se
    retorna "otro" si el credito esta vacio o no es numerico (basura
    real que indicaria fila STAGING corrupta).
    """
    if not credito:
        return "otro"
    num = re.sub(r"[^\d]", "", credito)
    if not num or len(num) < 5:
        # Sin digitos o demasiado corto -> no es un numero de credito valido.
        return "otro"
    # Bancolombia: cualquier credito numerico valido es hipotecario.
    return "hipotecario"


# ============================================================
# EXTRACCION HIBRIDA (pdfplumber + Vision fallback)
# ============================================================

def _seguros_todos_cero(datos: dict) -> bool:
    """R-DVV-10b (2026-05-14): True si los 3 seguros del extracto leidos por
    pdfplumber estan en $0. Davivienda hipotecario tiene seguro de vida
    obligatorio por ley deudores -> probabilidad ~0 de que sea real. Si es 0
    todo, es bug de pdfplumber (caso SARA: cliente en mora, "Valores Aplicados"
    todos en 0 porque la cuota no se pago, pero el seguro AGREGADO esta en otra
    seccion del PDF que pdfplumber no captura).
    """
    if not isinstance(datos, dict):
        return False
    v = float(datos.get("seguro_vida", 0) or 0)
    i = float(datos.get("seguro_incendio", 0) or 0)
    t = float(datos.get("seguro_terremoto", 0) or 0)
    return v == 0 and i == 0 and t == 0


def _esta_en_mora(datos: dict) -> bool:
    """R-DVV-10c (2026-05-14): True si el extracto indica dias en mora > 0.
    Extractos en mora tienen estructura distinta (cuota mes vs cuota total, valores
    aplicados en 0 si la cuota no se pago) -> pdfplumber se confunde. Forzar Gemini.
    """
    if not isinstance(datos, dict):
        return False
    return float(datos.get("dias_mora", 0) or 0) > 0


def _tasa_atipica(datos: dict) -> bool:
    """R-DVV-10d (2026-05-15): True si tasa_cobrada > 13% (probable confusion con
    Tasa Mora). Davivienda Cte. Cobrada típica 6%-13%. Tasa Mora 14-20%. Si
    pdfplumber regex matchea mal (caso historico antes de fix \\s* post-Cte.\\.)
    y captura "14.25" en lugar de "9.50", forzamos retry con Gemini.

    `tasa_cobrada` en datos del PDF viene en formato porcentaje (9.50, no 0.0950).
    """
    if not isinstance(datos, dict):
        return False
    try:
        t = float(datos.get("tasa_cobrada", 0) or 0)
    except (TypeError, ValueError):
        return False
    return t > 13.0


def extraer_pdf_hibrido(pdf_path: Path, cedula_fallback: str = "") -> dict:
    """Intenta pdfplumber, si faltan campos criticos cae a Vision.

    2026-05-14: ampliada con R-DVV-10b (seguros=0 todos) y R-DVV-10c (dias_mora>0)
    para forzar Gemini cuando hay señales de extracción pobre, antes de procesar.

    Trackea cual extractor produjo los datos finales en `datos["_extractor_uso"]`:
      - "pdfplumber" : pdfplumber solo, sin Vision
      - "gemini"     : Vision intervino (fallback total, campos vacios, seguros=0, o mora)
    """
    extractor_uso = "pdfplumber"
    try:
        datos = parse_pdf_banco(str(pdf_path), cedula_fallback=cedula_fallback)
    except Exception as e:
        datos = {}
        print(f"  [extract] pdfplumber fallo: {e}. Usando Vision directo.")
        extractor_uso = "gemini"  # fallback total

    # Razones para forzar Gemini (cada una documentada como regla MOM_DAVIVIENDA):
    razones_gemini = []
    if vision_extractor.necesita_fallback(datos):
        razones_gemini.append("campos criticos vacios")
    if _seguros_todos_cero(datos):
        razones_gemini.append("R-DVV-10b: seguros=0 todos (improbable en hipotecario)")
    if _esta_en_mora(datos):
        razones_gemini.append(
            f"R-DVV-10c: dias_mora={datos.get('dias_mora', 0)} > 0 "
            f"(estructura PDF distinta en extractos con mora)"
        )
    if _tasa_atipica(datos):
        razones_gemini.append(
            f"R-DVV-10d: tasa_cobrada={datos.get('tasa_cobrada')} > 13% "
            f"(probable Mora confundida con Cte. Cobrada)"
        )

    if razones_gemini and extractor_uso != "gemini":
        print(f"  [extract] Disparando Vision por: {' + '.join(razones_gemini)}")
        try:
            # 2026-05-15: pasar banco + password (Bancolombia PDFs protegidos con cedula)
            datos = vision_extractor.extraer_con_vision(
                pdf_path, base=datos,
                banco="BANCOLOMBIA", password=cedula_fallback,
            )
            extractor_uso = "gemini"
        except Exception as e:
            print(f"  [extract] Vision fallback fallo: {e}")
            traceback.print_exc()
    if isinstance(datos, dict):
        datos["_extractor_uso"] = extractor_uso
    return datos


# ============================================================
# ENRIQUECIMIENTO HUBSPOT
# ============================================================

HUBSPOT_PROPS = [
    "firstname", "lastname", "email", "phone", "hubspot_owner_id",
    "identificacion", "cedula", "numero_de_cedula",
    "banco", "banco_donde_tienes_la_hipoteca_o_leasing_habitacional",
    # Ingresos: propiedad real del portal es "valor_de_ingresos"
    "valor_de_ingresos", "ingresos_demostrables", "ingresos_mensuales",
    "abono_efectivo", "abono_extraordinario",
    "actividad_economica", "ocupacion",
]

# Valores de cedula que NO son CC reales — igual que R-DVV-14 en REGISTROS
_CC_INVALIDOS_HS = {"n/a", "na", "n.a.", "n\\a", "n-a", ""}


def enriquecer_con_hubspot(hs: HubSpotClient, cc: str, email: str, nombre: str) -> dict:
    """Cascada CC -> email -> nombre. Retorna {} si no encuentra nada.

    R-DVV-17 (2026-04-29): guard N/A aplicado a HubSpot igual que R-DVV-14 en
    REGISTROS. Si cc es 'N/A' o variantes, se omite la busqueda por cedula y
    se va directo a nombre. Evita match cruzado con los 36+ contactos HubSpot
    que tienen cedula='N/A' y datos de otros clientes.
    """
    # R-DVV-17: ignorar CC invalidos — no buscar por cedula si es N/A o vacio
    cc_clean = (cc or "").strip()
    if cc_clean.lower() in _CC_INVALIDOS_HS:
        cc_clean = ""  # forzar salto directo a busqueda por nombre

    try:
        m = hs.match_contact_cascade(cedula=cc_clean, email=email, nombre=nombre,
                                      properties=HUBSPOT_PROPS)
    except Exception as e:
        print(f"  [hubspot] error: {e}")
        return {}
    contact = m.get("contact") or {}
    if not contact:
        return {}
    props = contact.get("properties") or {}
    owner_id = props.get("hubspot_owner_id", "")
    consultor = ""
    if owner_id:
        try:
            owner = hs.get_owner(owner_id)
            consultor = " ".join(filter(None, [owner.get("firstName", ""), owner.get("lastName", "")])).strip()
        except Exception:
            pass
    cc_hs = (
        props.get("identificacion", "")
        or props.get("cedula", "")
        or props.get("numero_de_cedula", "")
    )
    # R-DVV-17: ingresos — propiedad real del portal es "valor_de_ingresos"
    ingresos_hs = (props.get("valor_de_ingresos")
                   or props.get("ingresos_demostrables")
                   or props.get("ingresos_mensuales") or "")
    # Abono
    abono_hs = (props.get("abono_efectivo") or props.get("abono_extraordinario") or "")
    # Actividad
    actividad_hs = (props.get("actividad_economica") or props.get("ocupacion") or "")
    return {
        "matched_by": m.get("matched_by"),
        "contact_id": contact.get("id"),
        "consultor": consultor,
        "owner_id": owner_id,
        "firstname": props.get("firstname", ""),
        "lastname": props.get("lastname", ""),
        "email": props.get("email", email),
        "phone": props.get("phone", ""),
        "cc": str(cc_hs).strip() if cc_hs else "",
        "ingresos": str(ingresos_hs).strip() if ingresos_hs else "",
        "abono": str(abono_hs).strip() if abono_hs else "",
        "actividad_economica": str(actividad_hs).strip() if actividad_hs else "",
    }


# ============================================================
# DETECCION HUBSPOT GENERICO REPETIDO (P6 retro 2026-04-24)
# ============================================================

def detectar_hubspot_genericos(hs, pendientes: list, umbral: int = 3) -> set:
    """Pre-detecta firmas HubSpot (consultor+actividad+ingresos) que se
    repiten >= umbral veces en la lista de pendientes.

    Las firmas repetidas indican datos genericos por defecto en HubSpot
    que NO son confiables. Caso real 2026-04-24: HubSpot retornaba
    'Brillid Salinas + Docente + $3,186,000' para 5+ clientes Davivienda
    VIS, lo cual era mismo template, no datos reales por cliente.

    Para los clientes con firma genérica, el caller debe ignorar HubSpot
    y caer a REGISTROS (donde están los datos reales por cliente).

    Retorna set de tuplas (consultor, actividad_economica, ingresos).
    """
    firmas_count = {}
    for p in pendientes:
        try:
            hs_data = enriquecer_con_hubspot(
                hs, p.get("cc", ""), p.get("email", ""), p.get("nombre", ""))
            firma = (
                (hs_data.get("consultor") or "").strip(),
                (hs_data.get("actividad_economica") or "").strip(),
                (hs_data.get("ingresos") or "").strip(),
            )
            if any(firma):  # solo cuenta firmas con al menos un campo
                firmas_count[firma] = firmas_count.get(firma, 0) + 1
        except Exception:
            continue
    return {f for f, c in firmas_count.items() if c >= umbral}


# ============================================================
# ENRIQUECIMIENTO REGISTROS (fallback para campos cliente)
# ============================================================

_REGISTROS_CACHE = {"loaded": False, "rows": []}


def _cargar_registros_cache(gc) -> list:
    """Carga REGISTROS una vez por ejecucion y lo cachea."""
    if _REGISTROS_CACHE["loaded"]:
        return _REGISTROS_CACHE["rows"]
    try:
        sh = gc.open_by_key(drive_client.SHEET_ID_BD)
        ws = sh.worksheet("REGISTROS")
        all_vals = ws.get_all_values()
    except Exception as e:
        print(f"  [registros] no se pudo leer: {e}")
        _REGISTROS_CACHE["loaded"] = True
        return []
    if not all_vals:
        _REGISTROS_CACHE["loaded"] = True
        return []
    header = all_vals[0]
    rows = []
    for r in all_vals[1:]:
        d = dict(zip(header, r + [""] * (len(header) - len(r))))
        rows.append(d)
    _REGISTROS_CACHE["rows"] = rows
    _REGISTROS_CACHE["loaded"] = True
    return rows


def enriquecer_con_registros(gc, nombre: str, cc: str = "") -> dict:
    """Busca el cliente en REGISTROS por CC (preferente) o nombre. Fallback."""
    rows = _cargar_registros_cache(gc)
    if not rows:
        return {}
    cc_norm = (cc or "").strip()
    # R-DVV-14: "N/A" no es un CC válido — evita match cruzado en REGISTROS
    if cc_norm.upper() in ("N/A", "NA", "N.A."):
        cc_norm = ""
    nombre_norm = _norm(nombre)
    hit = None
    # Preferir match por CC
    if cc_norm:
        for d in rows:
            if str(d.get("CC", "")).strip() == cc_norm:
                hit = d
                break
    if not hit and nombre_norm:
        tokens = nombre_norm.split()
        for d in rows:
            n = _norm(d.get("NOMBRE CLIENTE", "") or d.get("NOMBRE", ""))
            if all(t in n for t in tokens):
                hit = d
                break
    if not hit:
        return {}
    return {
        "consultor": (hit.get("Consultor") or "").strip(),
        "ingresos": (hit.get("Ingresos demostrables") or "").strip(),
        "abono": (hit.get("Abono Efectivo") or "").strip(),
        "actividad_economica": (hit.get("Actividad Econ\u00f3mica")
                                or hit.get("Actividad Economica") or "").strip(),
        "email": (hit.get("E-mail") or "").strip(),
        "telefono": (hit.get("Tel\u00e9fono") or hit.get("Telefono") or "").strip(),
        "ciudad": (hit.get("Ciudad") or "").strip(),
        "referenciador": (hit.get("Referenciador") or "").strip(),
    }


# ============================================================
# CONSTRUCCION DatosClienteExcel
# ============================================================

def _f(v, default=0.0) -> float:
    """Convierte a float con soporte formato colombiano y rangos.

    2026-04-23 fix (bug Fernando): la version anterior fallaba con:
      - formato colombiano miles con punto: "$4.800.000" -> float("4.800.000") -> ValueError
      - formato con comas de miles: "$4,800,000" -> ValueError
      - rangos tipo "$100.000 a $300.000" -> ValueError

    Nueva logica:
      - Detecta rango "X a Y" con regex -> devuelve promedio (low + high) / 2
      - Formato colombiano (miles con punto, decimal con coma): "1.234.567,89"
      - Formato EN (miles con coma, decimal con punto): "1,234,567.89"
      - Solo punto o solo coma: heuristica por posicion
    """
    if v in (None, ""):
        return float(default)
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return float(default)

    # Deteccion de rango "X a Y" -> promedio
    m = re.match(r'^\s*\$?\s*([\d.,]+)\s+a\s+\$?\s*([\d.,]+)\s*$', s, re.IGNORECASE)
    if m:
        low = _f(m.group(1))
        high = _f(m.group(2))
        if low > 0 and high > 0:
            return (low + high) / 2.0

    # Limpiar simbolos
    s = s.replace("$", "").replace(" ", "").strip()
    if not s:
        return float(default)

    # Heuristica de formato numerico
    has_dot = "." in s
    has_comma = "," in s
    if has_dot and has_comma:
        # Ambos: el que este mas a la derecha es el decimal
        if s.rfind(",") > s.rfind("."):
            # formato colombiano: "1.234.567,89" -> quitar puntos, coma=decimal
            s = s.replace(".", "").replace(",", ".")
        else:
            # formato EN: "1,234,567.89" -> quitar comas
            s = s.replace(",", "")
    elif has_dot and s.count(".") > 1:
        # Multiples puntos: miles colombiano sin decimal: "4.800.000"
        s = s.replace(".", "")
    elif has_comma and s.count(",") > 1:
        # Multiples comas: miles EN sin decimal: "4,800,000"
        s = s.replace(",", "")
    elif has_comma and not has_dot:
        # Solo una coma: heuristica por digitos post-coma
        # 3 digitos exactos -> miles EN/colombiano "200,000" -> 200000
        # 1-2 digitos -> decimal colombiano "1234,56" -> 1234.56
        # 2026-04-27 fix: "$200,000" retornaba 200.0 en lugar de 200000.0
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            s = s.replace(",", "")  # miles
        else:
            s = s.replace(",", ".")  # decimal colombiano
    elif has_dot and not has_comma:
        # Un solo punto sin coma: distinguir miles colombiano vs decimal.
        # 2026-04-23 fix bis (caso Fernando abono "$100.000 a $300.000"):
        # "100.000" -> 100000 (miles col), "100.50" -> 100.5 (decimal).
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            # 3 digitos despues del punto = miles colombiano
            s = s.replace(".", "")
        # else: decimal (1-2 digitos despues del punto) -> dejar igual
    # else: ningun separador -> dejar igual

    try:
        return float(s)
    except Exception:
        return float(default)


def _i(v, default=0) -> int:
    try:
        return int(_f(v, default))
    except Exception:
        return int(default)


def construir_datos(pdf: dict, hs: dict, staging_row: dict, reg: dict = None) -> tuple:
    """Construye DatosClienteExcel + lista de notas CRM generadas.

    Retorna (DatosClienteExcel, notas_crm: list[str]). Las notas deben
    propagarse a STAGING columna L por el caller (R-universal nota CRM).
    """
    reg = reg or {}
    notas_crm: list = []
    nombre = (staging_row.get("nombre") or pdf.get("nombre") or "").upper().strip()
    credito = pdf.get("credito") or staging_row.get("credito") or ""

    cuota = _f(pdf.get("cuota_mensual"))
    plazo_ini = _i(pdf.get("plazo_inicial"))
    plazo_pend = _i(pdf.get("cuotas_pendientes"))
    tasa_ea = _f(pdf.get("tasa_cobrada") or pdf.get("tasa_pactada"))
    # tasa suele venir como 14.31 o 0.1431; normalizar a decimal
    if tasa_ea > 1.0:
        tasa_ea = tasa_ea / 100.0

    seg_vida = _f(pdf.get("seguro_vida"))
    seg_inc = _f(pdf.get("seguro_incendio"))
    seg_ter = _f(pdf.get("seguro_terremoto"))
    cap_mes = _f(pdf.get("abonos_capital"))
    int_mes = _f(pdf.get("intereses_corrientes"))
    saldo = _f(pdf.get("saldo_capital"))

    # R-DVV-06: deteccion de duplicacion de cuota por pago irregular.
    # Aplica SOLO Davivienda. Tres gatillos (OR):
    #   G1: cuota aplicada (total_aplicado) ~= 2 * Valor Cuota Mes (tol 5%)
    #   G2: |seguros_aplicados - seguros_inferior_total| > $10k
    #   G3 (Jose 2026-04-24, caso Yeimy): suma (cap+int+seg) ~= 2*cuota (tol 10%)
    #       Util cuando Vision no extrajo total_aplicado ni seguros_inferior_total.
    # Override seguros: si seguros_inferior_total > 0 lo usa (preciso).
    #                   si no (G3 puro), divide los aplicados entre 2 (estimacion).
    # Capital/intereses los maneja Regla 9.3 (ya automatica, copia del simulador).
    total_aplicado = _f(pdf.get("total_aplicado"))
    seguros_inferior = _f(pdf.get("seguros_inferior_total"))
    seguros_aplicados = seg_vida + seg_inc + seg_ter
    suma_aplicada = seguros_aplicados + cap_mes + int_mes
    g1 = (cuota > 0 and total_aplicado > 0
          and abs(total_aplicado - 2.0 * cuota) / cuota < TOLERANCIA_G1_CUOTA_DUPLICADA)
    # G2 refinado (Jose retro 2026-04-24, caso Karen Tatiana false positive):
    # solo dispara si seg_vida APLICADO > 0. Si vida=0 con incendio>0, casi
    # seguro Vision no extrajo vida -> NO override (M1 nuevo lo bloqueara).
    # Esto evita amontonar valores legitimos en seguro_vida cuando la
    # discrepancia viene de extraccion incompleta, no de duplicacion real.
    g2 = (seguros_inferior > 0 and seguros_aplicados > 0
          and seg_vida > 0
          and abs(seguros_aplicados - seguros_inferior) > UMBRAL_G2_DISCREPANCIA_SEGUROS)
    g3 = (cuota > 0 and suma_aplicada > 0
          and abs(suma_aplicada - 2.0 * cuota) / cuota < TOLERANCIA_G3_SUMA_DUPLICADA)
    if g1 or g2 or g3:
        if seguros_inferior > 0:
            seg_final = seguros_inferior
            fuente_seg = "'+ Seguros' inferior"
        elif seguros_aplicados > 0:
            seg_final = round(seguros_aplicados / 2.0, 2)
            fuente_seg = "aplicados/2 (estimacion G3 sin '+ Seguros')"
        else:
            seg_final = 0.0
            fuente_seg = "sin override (sin datos)"
        print(f"  [R-DVV-06] duplicacion detectada (G1={g1} G2={g2} G3={g3})"
              f" | seguros override: ${seguros_aplicados:,.0f} -> ${seg_final:,.0f}"
              f" en seguro_vida ({fuente_seg})")
        seg_vida = seg_final
        seg_inc = 0.0
        seg_ter = 0.0
        notas_crm.append(
            f"Duplicacion de cuota por mala pagaduria detectada (G1={g1} G2={g2} G3={g3}). "
            f"Seguros: ${seg_final:,.0f} via {fuente_seg}. "
            f"Capital e intereses ajustados por Regla 9.3 automatica."
        )

    # Cascada cliente: HubSpot -> REGISTROS (STAGING excluido de datos financieros)
    # R-DVV-16: STAGING es cola operativa, NO fuente de datos financieros.
    # Si se usa STAGING como fallback para ingresos/abono, datos erroneos del
    # bug N/A (R-DVV-14) o entradas manuales incorrectas polutan el Excel.
    # Solo HubSpot y REGISTROS aportan ingresos, abono y actividad.
    # consultor puede venir de STAGING (es dato operativo, no financiero).
    def _pick(*vals):
        for v in vals:
            if v not in (None, "", 0, "0"):
                return v
        return ""

    consultor = _pick(hs.get("consultor"), reg.get("consultor"), staging_row.get("consultor"))
    actividad = _pick(hs.get("actividad_economica"), reg.get("actividad_economica"))
    ingresos = _f(_pick(hs.get("ingresos"), reg.get("ingresos")))
    abono = _f(_pick(hs.get("abono"), reg.get("abono")))

    datos = DatosClienteExcel(
        credito_id=credito,
        nombre=nombre,
        banco=BANCO,
        cuota_mensual=cuota,
        plazo_inicial=plazo_ini,
        plazo_pendiente=plazo_pend,
        tasa_ea=tasa_ea,
        frech_subsidio=_f(pdf.get("frech_cobertura_pag1")),
        seguro_vida=seg_vida,
        seguro_incendio=seg_inc,
        seguro_terremoto=seg_ter,
        capital_mensual=cap_mes,
        interes_mensual=int_mes,
        saldo_capital=saldo,
        consultor=consultor,
        actividad_economica=actividad,
        abono_efectivo=abono,
        ingresos=ingresos,
    )
    return datos, notas_crm


# ============================================================
# R-DVV-07 — Proyeccion a la sexta cuota paga (2026-04-23)
# ============================================================
# Politica Davivienda/DaviBank: no inician proceso si cliente tiene <6 cuotas
# pagadas. Proyectamos el estudio como si ya estuviera en la 6a cuota.
#
# Ver `bank_rules_davivienda.md` §R-DVV-07 y CHANGELOG 2026-04-23 ~17:30.

BANCOS_SEXTA_CUOTA = ("DAVIVIENDA", "DAVIBANK")


def proyectar_sexta_cuota(datos: DatosClienteExcel) -> tuple[DatosClienteExcel, dict]:
    """Proyeccion a 6a cuota (R-DVV-07). Retorna (datos_modificado, info).

    Si aplica, modifica in-place datos.saldo_capital y datos.plazo_pendiente
    avanzando la amortizacion hasta el mes 6. NO toca capital_mensual,
    interes_mensual (P16 B), seguros ni cuota.

    Algoritmo: amortizacion francesa con cuota_total del extracto (P15 —
    simplicidad comercial, no restar seguros).

    Retorna dict info con {"aplicada": bool, "meses": int, "saldo_antes": x,
    "saldo_despues": y, "cuotas_pagadas_antes": n}.
    """
    info = {"aplicada": False}
    if (datos.banco or "").upper() not in BANCOS_SEXTA_CUOTA:
        return datos, info

    cuotas_pagadas = max(0, datos.plazo_inicial - datos.plazo_pendiente)
    if cuotas_pagadas >= 6:
        return datos, info

    meses_faltantes = 6 - cuotas_pagadas
    if datos.tasa_ea <= 0 or datos.cuota_mensual <= 0 or datos.saldo_capital <= 0:
        return datos, info

    tasa_mv = (1.0 + datos.tasa_ea) ** (1.0 / 12.0) - 1.0
    cuota = float(datos.cuota_mensual)  # P15: cuota total, incluye seguros
    saldo = float(datos.saldo_capital)

    saldo_antes = saldo
    for _ in range(meses_faltantes):
        interes = saldo * tasa_mv
        capital = cuota - interes
        saldo -= capital

    datos.saldo_capital = round(saldo, 2)
    datos.plazo_pendiente = datos.plazo_pendiente - meses_faltantes

    info.update({
        "aplicada": True,
        "meses": meses_faltantes,
        "saldo_antes": saldo_antes,
        "saldo_despues": datos.saldo_capital,
        "cuotas_pagadas_antes": cuotas_pagadas,
    })
    return datos, info


# ============================================================
# HARD BLOCKERS — PDF PASSWORD Y EXTRACTO LEGIBILIDAD
# ============================================================

CAMPOS_CRITICOS_EXTRACTO = [
    "credito", "saldo_capital", "cuota_mensual", "tasa_cobrada",
]


def _desencriptar_pdf_si_protegido(src_path: Path, ccs_candidatas: list,
                                     dst_path: Path) -> Optional[Path]:
    """Detecta y desencripta PDFs protegidos.

    Retorna:
      - src_path si el PDF NO esta encriptado (passthrough).
      - dst_path si estaba encriptado y se logro desencriptar con alguna CC.
      - None si esta encriptado pero ninguna CC abrio.
    """
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        # Sin pypdf no podemos desencriptar. Si el PDF esta protegido,
        # pdfplumber lanzara y marcaremos PDF_PROTEGIDO.
        print("  [pdf] pypdf no instalado (pip install pypdf). Sin auto-desencripcion.")
        return src_path
    try:
        reader = PdfReader(str(src_path))
    except Exception as e:
        print(f"  [pdf] pypdf no pudo leer: {e}")
        return src_path
    if not reader.is_encrypted:
        return src_path
    # Primero probar contrasena vacia: muchos PDFs tienen is_encrypted=True
    # por permissions-only encryption pero abren sin password (caso Cyndi).
    try:
        res = reader.decrypt("")
        if res != 0:
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            with open(dst_path, "wb") as fh:
                writer.write(fh)
            print(f"  [pdf] encriptado solo por permisos (password vacia). Desencriptado.")
            return dst_path
    except Exception:
        pass
    print(f"  [pdf] PROTEGIDO. Probando {len(ccs_candidatas)} CC(s) candidatas...")
    for cc in ccs_candidatas:
        if not cc:
            continue
        cc_str = str(cc).strip()
        if not cc_str:
            continue
        try:
            ok = reader.decrypt(cc_str)
            if ok != 0:
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                with open(dst_path, "wb") as fh:
                    writer.write(fh)
                print(f"  [pdf] desencriptado con CC (ultimos 3: ...{cc_str[-3:]})")
                return dst_path
        except Exception:
            continue
    return None


def _clasificar_extracto(datos: dict) -> tuple:
    """Retorna (estado, lista_vacios).
    estado: 'ok' | 'ILEGIBLE' | 'INCOMPLETO'
    """
    if not datos:
        return ("ILEGIBLE", CAMPOS_CRITICOS_EXTRACTO[:])
    vacios = [k for k in CAMPOS_CRITICOS_EXTRACTO if not datos.get(k)]
    if len(vacios) == len(CAMPOS_CRITICOS_EXTRACTO):
        return ("ILEGIBLE", vacios)
    if vacios:
        return ("INCOMPLETO", vacios)
    return ("ok", [])


# ============================================================
# PIPELINE POR CLIENTE
# ============================================================

def procesar_cliente(cfg, gc, drive, hs, ws_staging, idx, row: dict, dry_run: bool,
                     drive_upload=None, firmas_hs_genericas: set = None) -> dict:
    nombre = row["nombre"]
    credito = row["credito"]
    print(f"\n=== {nombre} | credito={credito} ===")
    resultado = {"nombre": nombre, "credito": credito, "ok": False, "detalle": ""}

    # Step 0: clasificar (informativo — leasing y hipotecario se procesan IGUAL)
    # Jose 2026-04-24: leasing habitacional 600 NO requiere tratamiento especial.
    # FRECH no es una traba — se maneja igual que hipotecario. La fórmula MIN(frech,interes)
    # quedo REVOCADA 2026-04-23 (ver project_leasing_habitacional.md y CHANGELOG).
    tipo = clasificar_credito(credito)
    if tipo == "leasing":
        print("  Leasing (600) -> procesar como hipotecario (R-DVV-09)")
    if tipo == "otro":
        print(f"  Credito no reconocido ({credito}). Skip.")
        resultado["detalle"] = "skip_credito_no_reconocido"
        return resultado

    # Step 1: Drive search
    print("  [drive] buscando extracto...")
    info = drive_client.buscar_extracto_cliente(drive, nombre)
    if not info:
        print("  [drive] NO encontrado -> skip")
        if not dry_run:
            _staging_update(ws_staging, row["row_idx"], idx, "SIN_EXTRACTO_DRIVE")
        resultado["detalle"] = "sin_extracto_drive"
        return resultado
    print(f"  [drive] folder={info['folder_name']}  pdf={info['pdf_name']}")

    # Step 2: Download
    with tempfile.TemporaryDirectory() as td:
        tmp_pdf = Path(td) / info["pdf_name"]
        drive_client.descargar_pdf(drive, info["pdf_id"], tmp_pdf)
        print(f"  [drive] descargado a {tmp_pdf}")

        # Step 3: HubSpot cascade PRIMERO (necesitamos CC para abrir PDFs protegidos)
        print("  [hubspot] matching...")
        hs_data = enriquecer_con_hubspot(hs, row.get("cc", ""), row.get("email", ""), nombre)
        if hs_data:
            print(f"  [hubspot] matched_by={hs_data.get('matched_by')} consultor={hs_data.get('consultor')}")
        else:
            print("  [hubspot] sin match (OK, consultor opcional)")

        # P6 retro 2026-04-24: si la firma (consultor+actividad+ingresos) de
        # HubSpot esta marcada como "generica repetida" (>=3 clientes con la
        # misma firma en esta corrida), ignoramos los datos cliente de HubSpot
        # y caemos a REGISTROS (datos reales por cliente). Preservamos cc/email/
        # phone/contact_id (esos siguen siendo validos para password y matching).
        if firmas_hs_genericas and hs_data:
            firma_actual = (
                (hs_data.get("consultor") or "").strip(),
                (hs_data.get("actividad_economica") or "").strip(),
                (hs_data.get("ingresos") or "").strip(),
            )
            if firma_actual in firmas_hs_genericas:
                print(f"  [HUBSPOT-GENERICO] firma repetida en >=3 clientes -> "
                      f"ignorando consultor/actividad/ingresos/abono de HubSpot, "
                      f"cascada caera a REGISTROS")
                # Vaciar SOLO los campos sospechosos. Mantener identificacion.
                hs_data["consultor"] = ""
                hs_data["actividad_economica"] = ""
                hs_data["ingresos"] = ""
                hs_data["abono"] = ""

        # Step 4: Password fallback con CC candidatas (STAGING + HubSpot)
        ccs_candidatas = []
        for c in [row.get("cc", ""), (hs_data or {}).get("cc", "")]:
            c = (c or "").strip()
            if c and c not in ccs_candidatas:
                ccs_candidatas.append(c)
        unlocked_path = Path(td) / ("unlocked_" + info["pdf_name"])
        pdf_usable = _desencriptar_pdf_si_protegido(tmp_pdf, ccs_candidatas, unlocked_path)
        if pdf_usable is None:
            print("  [pdf] PROTEGIDO y ninguna CC abre -> PDF_PROTEGIDO")
            if not dry_run:
                _staging_update(ws_staging, row["row_idx"], idx, "PDF_PROTEGIDO")
            resultado["detalle"] = "pdf_protegido"
            return resultado

        # Step 5: Extract (pdfplumber + vision fallback)
        cc_para_parser = ccs_candidatas[0] if ccs_candidatas else ""
        datos_pdf = extraer_pdf_hibrido(pdf_usable, cedula_fallback=cc_para_parser)
        # 2026-05-14: tracking del extractor usado, se anota en estado GENERADOS
        # y se usa para decidir auto-retry con Vision en R-DVV-11.
        extractor_uso = datos_pdf.get("_extractor_uso", "pdfplumber") if isinstance(datos_pdf, dict) else "pdfplumber"
        # Si en algun checkpoint se decide REVISION_MANUAL, se setea este string;
        # el Excel se genera igual y el estado final lo refleja.
        estado_revision_manual = None

        # Hard blockers: ILEGIBLE / INCOMPLETO
        estado_extracto, vacios = _clasificar_extracto(datos_pdf)
        if estado_extracto == "ILEGIBLE":
            print(f"  [extract] ILEGIBLE (vacios: {vacios})")
            if not dry_run:
                _staging_update(ws_staging, row["row_idx"], idx, "EXTRACTO_ILEGIBLE")
            resultado["detalle"] = "extracto_ilegible"
            return resultado
        if estado_extracto == "INCOMPLETO":
            print(f"  [extract] INCOMPLETO (faltan: {vacios})")
            if not dry_run:
                estado_msg = f"EXTRACTO_INCOMPLETO: {','.join(vacios)}"
                _staging_update(ws_staging, row["row_idx"], idx, estado_msg)
            resultado["detalle"] = f"extracto_incompleto:{vacios}"
            return resultado

        # Step 5.5: Enriquecer con REGISTROS (fallback cliente)
        reg_data = enriquecer_con_registros(gc, nombre, row.get("cc", ""))
        if reg_data:
            print(f"  [registros] hit consultor={reg_data.get('consultor')!r} "
                  f"ingresos={reg_data.get('ingresos')!r} "
                  f"abono={reg_data.get('abono')!r} "
                  f"actividad={reg_data.get('actividad_economica')!r}")
        else:
            print("  [registros] sin match")

        # Step 6: Build DatosClienteExcel
        datos, notas_cd = construir_datos(datos_pdf, hs_data, row, reg=reg_data)
        if notas_cd:
            resultado.setdefault("notas_crm", []).extend(notas_cd)

        # R-BCO-05 (2026-05-15, Jose): Bancolombia NO requiere ingresos
        # certificados (BANCOS_SIN_INGRESOS_REQUERIDOS). El Excel debe mostrar
        # ingresos=0 para evitar Mode B mixto_viable que asume ingresos minimos.
        # El proponedor_plazos ya respeta la lista, pero forzamos aqui para
        # garantizar que la celda B26 del Excel queda en 0.
        if datos.ingresos != 0:
            print(f"  [R-BCO-05] override ingresos: ${datos.ingresos:,.0f} -> $0 "
                  f"(Bancolombia no requiere ingresos certificados)")
            datos.ingresos = 0

        # M3 log enriquecido (2026-04-23): imprimir valores finales inyectados
        # al Excel para auditar sin abrir el archivo.
        print(f"  [datos-cliente] consultor={datos.consultor!r}"
              f" actividad={datos.actividad_economica!r}"
              f" ingresos=${datos.ingresos:,.0f}"
              f" abono_efect=${datos.abono_efectivo:,.0f}")
        print(f"  [datos-financ] cuota=${datos.cuota_mensual:,.0f}"
              f" tasa_ea={datos.tasa_ea:.4f}"
              f" saldo=${datos.saldo_capital:,.0f}"
              f" plazo_pend={datos.plazo_pendiente}m")
        print(f"  [datos-seguros] vida=${datos.seguro_vida:,.0f}"
              f" incendio=${datos.seguro_incendio:,.0f}"
              f" terremoto=${datos.seguro_terremoto:,.0f}"
              f" | cap_mes=${datos.capital_mensual:,.0f}"
              f" int_mes=${datos.interes_mensual:,.0f}")

        # M1: validar coherencia de datos extraidos antes de procesar
        m1_ok, m1_err, m1_warn = _m1.validar_datos_cliente(datos)
        for ln in _m1.formatear_reporte(m1_ok, m1_err, m1_warn).splitlines():
            print(f"  {ln}")
        if not m1_ok:
            resultado["detalle"] = "M1_FAIL: " + "; ".join(m1_err)
            resultado["ok"] = False
            _staging_update(ws_staging, row["row_idx"], idx,
                             "REVISION_MANUAL: M1 fallo")
            return resultado

        # R-DVV-07 NO APLICA a Bancolombia (politica especifica Davivienda).
        # 2026-05-15 (Jose): proyeccion 6a cuota es Davivienda-only.
        # Bancolombia no tiene ese concepto operativo. Skip silencioso.
        # (Funcion `proyectar_sexta_cuota` permanece definida en este archivo
        # por clone, pero NO se invoca aqui.)

        # Step 7a: Regla 9.3
        print("  [regla 9.3] abono extraordinario...")
        for n in aplicar_regla_93_abono_extraordinario(datos):
            print(f"    {n}")

        # P5 retro 2026-04-24: validar DIF.SIMULA post-9.3 contra ±$70k.
        # 2026-05-14 (Jose feedback caso ALVARO MAHECHA): el flujo viejo abortaba
        # el procesamiento (sin Excel). Ahora:
        #   1. Si DIF.SIMULA fuera tolerancia Y extractor fue pdfplumber:
        #      auto-retry con Gemini Vision (lee mejor plazo_pendiente, saldo, etc.)
        #   2. Re-aplicar Regla 9.3 y recalcular DIF.SIMULA
        #   3. Si Gemini lo arregla -> sigue normal, estado "pre-generado, gemini"
        #   4. Si NO lo arregla (o ya era Gemini) -> NO aborta: marca el estado
        #      `estado_revision_manual` y el Excel se genera igual (con datos
        #      finales). El analista lo abre, corrige a mano, guarda.
        # TOLERANCIA_DIF_SIMULA = ±$70k (config_reglas, MASTER_RULES §8.15).
        try:
            seg_total = (datos.seguro_vida + datos.seguro_incendio
                         + datos.seguro_terremoto)
            cap_sim, int_sim = _capital_intereses_simulador(
                datos.tasa_ea, datos.plazo_pendiente, datos.saldo_capital)
            dif_sim_final = datos.cuota_mensual - (cap_sim + int_sim + seg_total)
            if abs(dif_sim_final) > TOLERANCIA_DIF_SIMULA:
                msg = (f"DIF.SIMULA fuera tolerancia: ${dif_sim_final:,.0f} "
                       f"(|{abs(dif_sim_final):,.0f}| > ${TOLERANCIA_DIF_SIMULA:,.0f}).")
                print(f"  [DIF.SIMULA-CHECK] FAIL: {msg}")

                # 2026-05-14: Auto-retry con Gemini si extractor fue pdfplumber.
                retry_ok = False
                if extractor_uso == "pdfplumber":
                    try:
                        print("  [retry-gemini] DIF.SIMULA fuera tol con pdfplumber. "
                              "Intentando re-extraccion con Vision...")
                        # 2026-05-15: retry con banco + password para Bancolombia
                        _cedula_para_retry = (datos.cedula or "").strip()
                        datos_g = vision_extractor.extraer_con_vision(
                            pdf_usable, base={},
                            banco="BANCOLOMBIA", password=_cedula_para_retry,
                        )
                        # Mergear campos criticos al datos actual (DatosClienteExcel)
                        cambios_aplicados = []
                        for k_origen, attr_destino in [
                            ("cuota_mensual", "cuota_mensual"),
                            ("saldo_capital", "saldo_capital"),
                            ("cuotas_pendientes", "plazo_pendiente"),
                            ("plazo_inicial", "plazo_inicial"),
                            ("tasa_cobrada", "tasa_ea"),
                            ("seguro_vida", "seguro_vida"),
                            ("seguro_incendio", "seguro_incendio"),
                            ("seguro_terremoto", "seguro_terremoto"),
                            ("abonos_capital", "capital_mensual"),
                            ("intereses_corrientes", "interes_mensual"),
                        ]:
                            v_new = datos_g.get(k_origen)
                            v_old = getattr(datos, attr_destino, None)
                            if v_new not in (None, "", 0, 0.0) and v_new != v_old:
                                setattr(datos, attr_destino, v_new)
                                cambios_aplicados.append(
                                    f"{attr_destino}: {v_old}->{v_new}")
                        if cambios_aplicados:
                            print(f"    [retry-gemini] cambios: "
                                  f"{'; '.join(cambios_aplicados[:5])}"
                                  f"{'...' if len(cambios_aplicados) > 5 else ''}")
                        extractor_uso = "gemini"
                        # Re-aplicar Regla 9.3 con datos actualizados
                        for n in aplicar_regla_93_abono_extraordinario(datos):
                            print(f"    [retry-9.3] {n}")
                        # Recalcular DIF.SIMULA
                        seg_total_r = (datos.seguro_vida + datos.seguro_incendio
                                       + datos.seguro_terremoto)
                        cap_sim_r, int_sim_r = _capital_intereses_simulador(
                            datos.tasa_ea, datos.plazo_pendiente, datos.saldo_capital)
                        dif_sim_retry = datos.cuota_mensual - (cap_sim_r + int_sim_r + seg_total_r)
                        if abs(dif_sim_retry) <= TOLERANCIA_DIF_SIMULA:
                            print(f"  [retry-gemini] OK: DIF.SIMULA ahora "
                                  f"${dif_sim_retry:,.0f} dentro tolerancia")
                            dif_sim_final = dif_sim_retry
                            retry_ok = True
                        else:
                            print(f"  [retry-gemini] FAIL: DIF.SIMULA sigue "
                                  f"${dif_sim_retry:,.0f} fuera tolerancia")
                            dif_sim_final = dif_sim_retry
                    except Exception as exc:
                        print(f"  [retry-gemini] EXCEPCION: {exc}")

                if not retry_ok:
                    # NO aborta. Marca para estado final, sigue al PASO 7b/Excel.
                    gemini_tag = " (gemini)" if extractor_uso == "gemini" else ""
                    estado_revision_manual = (
                        f"REVISION_MANUAL: DIF.SIMULA ${dif_sim_final:,.0f}{gemini_tag}"
                    )
                    resultado["detalle"] = f"DIF_SIMULA_FUERA_TOL: ${dif_sim_final:,.0f}"
                    resultado.setdefault("notas_crm", []).append(
                        f"REVISION_MANUAL: DIF.SIMULA ${dif_sim_final:,.0f} "
                        f"fuera tolerancia ±$70k. Excel generado para revision "
                        f"manual del analista (corregir in-place si aplica)."
                    )
                    print(f"  [DIF.SIMULA-CHECK] Excel se generara igual; "
                          f"estado final: {estado_revision_manual}")
            else:
                print(f"  [DIF.SIMULA-CHECK] OK: ${dif_sim_final:,.0f} dentro tolerancia ±$70k")
        except Exception as exc:
            # 2026-05-14 (caso SARA VIVIANA): el except silenciaba excepciones reales
            # que dejaban el cliente con Excel pero datos malos. Ahora el WARN trae
            # contexto completo y se agrega a notas_crm para que el analista vea.
            import traceback as _tb
            print(f"  [DIF.SIMULA-CHECK] WARN: no se pudo validar ({type(exc).__name__}: {exc})")
            _tb.print_exc()
            resultado.setdefault("notas_crm", []).append(
                f"ALERTA: DIF.SIMULA check fallo con excepcion ({type(exc).__name__}). "
                f"Revisar manualmente — el cliente puede tener datos inconsistentes."
            )

        # Step 7b: Regla 9.4 (proponer plazos)
        print("  [regla 9.4] proponiendo plazos...")
        seg_tot = datos.seguro_vida + datos.seguro_incendio + datos.seguro_terremoto
        plazo_pag = max(0, datos.plazo_inicial - datos.plazo_pendiente)

        # R-DVV-18 (2026-05-05): Pre-check Ley 546 antes de llamar al proponedor.
        # Si el credito no tiene NINGUNA opcion legal de reduccion de plazo,
        # el estudio no es viable y no debe generarse. Esto evita el caso
        # Alexandra Bernal (29 cuotas, plazo_pagado < 5 anos): anio_min_legal
        # excede plazo_pendiente -> no existe ningun plazo que sea simultaneamente
        # una REDUCCION y cumpla con el minimo de 5 anos de la Ley 546/1999.
        _plazo_pend_anos_chk = datos.plazo_pendiente / 12.0
        _plazo_pag_anos_chk = plazo_pag / 12.0
        _anio_min_legal_chk = (
            0.5 if _plazo_pag_anos_chk >= 5.0
            else max(5.0 - _plazo_pag_anos_chk, 0.5)
        )
        if _anio_min_legal_chk >= _plazo_pend_anos_chk:
            _credito_total_anos = _plazo_pag_anos_chk + _plazo_pend_anos_chk
            _msg_546 = (
                f"NO_VIABLE_LEY_546: plazo_pend={_plazo_pend_anos_chk:.2f}a "
                f"< anio_min_legal={_anio_min_legal_chk:.2f}a. "
                f"Credito total ({_plazo_pag_anos_chk:.2f}+{_plazo_pend_anos_chk:.2f}"
                f"={_credito_total_anos:.2f}a) no alcanza los 5a minimos "
                f"de la Ley 546/1999. No existen opciones de reduccion legales."
            )
            print(f"  [R-DVV-18] BLOQUEADO: {_msg_546}")
            resultado["detalle"] = "NO_VIABLE_LEY_546"
            resultado["ok"] = False
            if not dry_run:
                _staging_update(ws_staging, row["row_idx"], idx,
                                f"REVISION_MANUAL: NO_VIABLE_LEY_546 "
                                f"(pend={_plazo_pend_anos_chk:.2f}a "
                                f"min_legal={_anio_min_legal_chk:.2f}a "
                                f"total={_credito_total_anos:.2f}a)")
            return resultado

        propuesta = proponer_plazos(
            plazo_pendiente_meses=datos.plazo_pendiente,
            tasa_ea=datos.tasa_ea,
            saldo=datos.saldo_capital,
            seguros_totales=seg_tot,
            ingresos_cliente=datos.ingresos,
            banco=datos.banco,
            es_vis=("VIS" in (datos.actividad_economica or "").upper()),
            abono_objetivo_min=max(0, datos.abono_efectivo - 50000),
            abono_objetivo_max=datos.abono_efectivo + 50000,
            plazo_pagado_meses=plazo_pag,
        )
        datos.plazos_anos = propuesta.plazos_anos
        print(f"    plazos={propuesta.plazos_anos} metodo={propuesta.metodo}")
        # M3 log enriquecido: verificar orden descendente
        if len(propuesta.plazos_anos) >= 2:
            orden_ok = all(propuesta.plazos_anos[i] >= propuesta.plazos_anos[i+1]
                           for i in range(len(propuesta.plazos_anos)-1))
            print(f"    orden_descendente={'OK' if orden_ok else 'QUEBRADO'}")

        # Step 8: Generar Excel
        if dry_run:
            print("  [dry-run] no genero Excel ni upload")
            resultado["ok"] = True
            resultado["detalle"] = "dry_run_ok"
            return resultado

        print("  [excel] generando...")
        populator = ExcelPopulator(cfg["template"])
        try:
            output = populator.crear_estudio(datos, cfg["salida"])
        except PermissionError as e:
            # Excel previo abierto en Office bloquea sobreescritura.
            # Mejor abortar con mensaje accionable que generar Excel con naming alternativo
            # (rompe MASTER_RULES §12.1 + §17.1 una versión por cliente).
            archivo = getattr(e, "filename", None) or str(e)
            msg = (f"EXCEL_LOCKED: Excel previo abierto en Office: {archivo}. "
                   f"Cerrar el archivo y re-correr "
                   f"`py pipeline_davivienda.py --nombre \"{datos.nombre[:30]}\" --force`.")
            print(f"  [excel] BLOQUEO: {msg}")
            resultado["ok"] = False
            resultado["detalle"] = msg[:200]
            return resultado
        ocultar_hoja_bd(output)
        print(f"    {output}")

        # M2: validar celdas canonicas del Excel generado
        m2_ok, m2_err, m2_warn = _m2.validar_excel(output, datos)
        for ln in _m2.formatear_reporte(m2_ok, m2_err, m2_warn).splitlines():
            print(f"  {ln}")
        if not m2_ok:
            resultado.setdefault("notas_crm", []).append(
                "ALERTA M2: Excel generado con discrepancias en celdas canonicas. "
                "Revisar manualmente antes de entregar al cliente."
            )

        # Step 9: Upload Drive §4.2 (usa OAuth user si esta configurado; SA fallback)
        print("  [drive] upload §4.2...")
        drv = drive_upload if drive_upload is not None else drive
        uploaded = drive_client.upload_to_folder(
            drv, Path(output),
            folder_id=drive_client.DRIVE_FOLDER_ANALISTAS_RW,
        )
        link = uploaded.get("webViewLink", "")
        print(f"    uploaded id={uploaded.get('id')} link={link}")

        # Step 10: Update GENERADOS (estado + link + nota_crm consolidada)
        # 2026-05-14 (Jose feedback): estado dinamico segun extractor + revision.
        #   - "pre-generado"          : pdfplumber solo, sin alerta
        #   - "pre-generado, gemini"  : Gemini intervino (fallback inicial o retry)
        #   - "REVISION_MANUAL: DIF.SIMULA $X (gemini)" : R-DVV-11 disparo
        # El analista revisa, corrige in-place el Excel, marca Estado=Excel generado.
        if estado_revision_manual is not None:
            estado_final_staging = estado_revision_manual
        else:
            tag_gemini = ", gemini" if extractor_uso == "gemini" else ""
            estado_final_staging = f"pre-generado{tag_gemini}"
        notas_crm_final = " | ".join(resultado.get("notas_crm", [])).strip()
        _staging_update(ws_staging, row["row_idx"], idx, estado_final_staging,
                         link=link, nota_crm=notas_crm_final)
        print(f"  [GENERADOS] estado={estado_final_staging!r}")
        if notas_crm_final:
            print(f"  [GENERADOS] nota CRM escrita en columna L: {notas_crm_final[:120]}...")

        # OK incluso si REVISION_MANUAL — el Excel se entrega al analista.
        resultado["ok"] = True
        resultado["detalle"] = (
            estado_revision_manual or f"ok | link={link}"
        )
        resultado["output"] = str(output)
        resultado["drive_link"] = link
    return resultado


# ============================================================
# MAIN
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", default="", help="Procesar solo el cliente cuyo nombre contenga este substring")
    ap.add_argument("--credito", default="", help="Procesar solo el credito especificado")
    ap.add_argument("--max", type=int, default=0, help="Limite de clientes a procesar (0=todos)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="Re-procesar aunque ESTADO sea 'Excel generado'")
    args = ap.parse_args()

    # Cloud Routines: materializa credenciales desde env vars antes que
    # cualquier modulo trate de leer archivos. Sin efecto en local Windows
    # (cero overwrite si los archivos existen).
    from cloud_bootstrap import ensure_credentials_from_env, is_cloud_env
    bootstrap = ensure_credentials_from_env()
    if is_cloud_env():
        print(f"[pipeline_davivienda] CLOUD env detected — bootstrap: {bootstrap}")

    cfg = cargar_config()
    print(f"[pipeline_davivienda] template={cfg['template']}")
    print(f"[pipeline_davivienda] salida={cfg['salida']}")

    # Integridad PESOS.xlsx: bloquea ejecucion si el template fue alterado fuera
    # del flujo de control (ver config_reglas.PESOS_TEMPLATE_SHA256).
    # 2026-05-12: verify_pesos_template importado a top-level (era inline).
    ok_template, msg_template = verify_pesos_template(PROJECT_ROOT)
    print(f"[pipeline_davivienda] {msg_template}")
    if not ok_template:
        print("[pipeline_davivienda] ABORT: template corrupto. Si el cambio fue "
              "intencional, regenera el hash en config_reglas.py y registra el "
              "cambio en CHANGELOG.")
        return 2

    gc, drive = drive_client.get_clients()
    hs = HubSpotClient.from_config()

    # Upload a Drive §4.2 requiere OAuth user (SA cae con 403 storageQuotaExceeded
    # en Gmail personal — MASTER_RULES §4.5 / §16.6). Si OAuth falla, abortar con
    # mensaje accionable en lugar de generar una EXCEPTION por cliente al hacer
    # fallback al SA. Bug post-mortem 2026-05-07: 14 EXCEPTION HTTP 403 históricas.
    drive_upload = None
    if not _HAS_OAUTH:
        print("[pipeline_davivienda] FATAL: oauth_drive no disponible. Instalar/restaurar "
              "credentials/oauth_token.json. Ver MOM_DAVIVIENDA §7 troubleshooting.")
        return 3
    try:
        drive_upload = get_oauth_drive()
        print("[pipeline_davivienda] OAuth user drive activo (uploads §4.2 = humano)")
    except Exception as e:
        print(f"[pipeline_davivienda] FATAL: OAuth no disponible ({e}).")
        print("[pipeline_davivienda] El SA NO puede subir a §4.2 (storageQuotaExceeded en")
        print("[pipeline_davivienda] Gmail personal). Ejecutar `py drive_oauth_setup.py` para")
        print("[pipeline_davivienda] re-autenticar antes de continuar (MASTER_RULES §16.6).")
        return 3

    ws, header, body, idx = _abrir_staging(gc)
    pendientes = _filtrar_pendientes_davivienda(
        body, idx,
        nombre_filter=args.nombre,
        credito_filter=args.credito,
        force=args.force,
    )
    if args.max > 0:
        pendientes = pendientes[: args.max]

    if not pendientes:
        print("[pipeline_davivienda] sin pendientes Davivienda en STAGING")
        return 0

    print(f"[pipeline_davivienda] {len(pendientes)} pendiente(s) encontrados")

    # P6 retro 2026-04-24: pre-detectar firmas HubSpot genericas (>=3 clientes
    # con misma triple consultor+actividad+ingresos = template por defecto).
    # Para esos clientes el procesador caera a REGISTROS.
    print("[pipeline_davivienda] pre-detectando firmas HubSpot genericas...")
    try:
        firmas_hs_gen = detectar_hubspot_genericos(hs, pendientes, umbral=3)
        if firmas_hs_gen:
            print(f"  -> {len(firmas_hs_gen)} firma(s) repetida(s) detectada(s); "
                  f"clientes con esas firmas usaran REGISTROS")
            for f in firmas_hs_gen:
                print(f"     firma: consultor={f[0]!r} actividad={f[1]!r} ingresos={f[2]!r}")
        else:
            print("  -> sin firmas repetidas, todos los clientes usan HubSpot normal")
    except Exception as exc:
        print(f"  -> no se pudo pre-detectar ({exc}); siguiendo con cascada normal")
        firmas_hs_gen = set()

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"pipeline_davivienda_{timestamp}.json"
    resultados = []
    for p in pendientes:
        try:
            r = procesar_cliente(cfg, gc, drive, hs, ws, idx, p, args.dry_run,
                                  drive_upload=drive_upload,
                                  firmas_hs_genericas=firmas_hs_gen)
        except Exception as e:
            print(f"  ERROR procesando {p['nombre']}: {e}")
            traceback.print_exc()
            r = {"nombre": p["nombre"], "credito": p["credito"], "ok": False,
                 "detalle": f"exception: {e}"}
            if not args.dry_run:
                try:
                    _staging_update(ws, p["row_idx"], idx, f"ERROR: {str(e)[:60]}")
                except Exception:
                    pass
        resultados.append(r)

    log_path.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in resultados if r.get("ok"))
    print(f"\n[pipeline_davivienda] OK={ok}/{len(resultados)}  log={log_path}")
    return 0 if ok == len(resultados) else 1



if __name__ == "__main__":
    sys.exit(main())

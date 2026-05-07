# -*- coding: utf-8 -*-
"""
config_reglas.py — MejorAhora SAS · 2026-04-24
================================================
FUENTE ÚNICA DE CONSTANTES de reglas de negocio.

Antes: umbrales hardcodeados dispersos en proponedor_plazos.py,
pipeline_davivienda.py, validar_extraccion_davivienda.py, etc.

Ahora: todos centralizados aquí. Cambiar 1 valor aquí actualiza
TODAS las referencias en el sistema.

Si una regla NO está en este archivo, NO existe en el sistema.
Si necesitas agregar una nueva, ADD aquí + import donde se use.

Documentación maestra: MASTER_RULES.md (raíz proyecto).
"""
from __future__ import annotations

# ============================================================
# PREFIJOS DAVIVIENDA (R-DVV-08)
# ============================================================
PREFIJOS_HIPOTECARIO = ("570", "571")
PREFIJOS_LEASING = ("600",)
BANCOS_SEXTA_CUOTA = ("DAVIVIENDA", "DAVIBANK")  # R-DVV-07

# ============================================================
# TOLERANCIAS Y UMBRALES (Reglas 9.x + R-DVV)
# ============================================================
# Regla 9.3 — abono extraordinario
TOLERANCIA_SUMA_CUOTA = 70_000.0  # ±$70k

# R-DVV-11 — DIF.SIMULA post-9.3
TOLERANCIA_DIF_SIMULA = 70_000.0  # ±$70k → REVISION_MANUAL si excede

# R-DVV-04 — saldo capital mínimo razonable
SALDO_MIN_HIPOTECARIO_ACTIVO = 1_000_000.0  # < $1M = sospecha saldo parcial

# M1 coherencia cuota vs (seg+cap+int)
TOLERANCIA_M1_WARN = 70_000.0       # > $70k = warning
TOLERANCIA_M1_ERROR = 500_000.0     # > $500k = error (salvo R-DVV-06 detectado)

# R-DVV-06 G2 — discrepancia seguros aplicados vs +Seguros inferior
UMBRAL_G2_DISCREPANCIA_SEGUROS = 10_000.0

# R-DVV-06 G1 — duplicación cuota
TOLERANCIA_G1_CUOTA_DUPLICADA = 0.05  # ratio 5%

# R-DVV-06 G3 — suma agregada
TOLERANCIA_G3_SUMA_DUPLICADA = 0.10  # ratio 10%

# ============================================================
# PROPONEDOR DE PLAZOS (Reglas 9.4 + §3a-3e)
# ============================================================
# §3c — piso abono OPC 1 tiered por saldo
PISO_ABONO_SALDO_BAJO = 100_000.0   # saldo < $300M
PISO_ABONO_SALDO_ALTO = 200_000.0   # saldo >= $300M
SALDO_THRESHOLD_TIER = 300_000_000.0

# §3d — diff entre opciones consecutivas
DIFF_OPCIONES_DEFAULT = 100_000.0
DIFF_OPCIONES_PLAZO_CHICO = 70_000.0
PLAZO_CHICO_MESES = 60  # < 60m permite usar diff $70k

# Granularidad operativa proponedor (NO floor legal — ver Ley 546)
PLAZO_MINIMO_PRACTICO_ANOS = 0.5  # = 6 meses

# Mode B mixto_viable
RATIO_NO_VIS = 0.29  # banco pide 30%, -1pp colchón
RATIO_VIS = 0.39     # banco pide 40%, -1pp colchón
TOPE_INGRESOS_FACTOR = 1.10

# ============================================================
# HUBSPOT GENÉRICO REPETIDO (R-DVV-12)
# ============================================================
UMBRAL_HUBSPOT_GENERICO = 3  # >=3 clientes con misma firma → genérica

# ============================================================
# VERTEX AI / GEMINI VISION
# ============================================================
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"  # Jose: NO bajar a flash sin autorización
GCP_PROJECT = "mejorahora-automations"
GCP_LOCATION = "us-central1"
MAX_OUTPUT_TOKENS_VISION = 8192  # Subido desde 2048 tras truncado Fernando

# ============================================================
# STAGING / SHEETS
# ============================================================
SHEET_BD_ID = "1_9FUAo8cSrLDWAkJlNoy29Cmyh9ojXwnW6zbvhGsESA"  # ÚNICA BD VÁLIDA
SHEET_BD_NOMBRE = "BASE PARA ESTUDIOS OK"
SHEET_PESTANA_DESTINO = "STAGING"  # Nunca REVISION ni producción directa

# Lista negra (sheets prohibidas — NUNCA usar)
SHEET_BD_PROHIBIDAS = (
    "1UbQ_Ghb0dmeCWAmEJNdFGkBsbK6PNWr6T48Pi-nTdd8",
    "1fsop9wgv1HvRxREnYQGopR7d3TSUhlIFU4bm6QQ0ykM",
)

# Drive folders
DRIVE_FOLDER_EXTRACTOS_RO = "17hN5TDiQ3Ozop-xT6g4OYAyQrZkZT0os"  # READ-ONLY
DRIVE_FOLDER_ANALISTAS_RW = "1UVsQtyzQHEpfRlcjUrq8gBsXgEqABoym"  # Excel destino

# Estados STAGING (normalizados con _norm())
ESTADOS_SKIP_DEFAULT = ("excel generado", "procesado", "completado", "realizado")
# NOTA: "pendiente frech" YA NO bloquea (R-DVV-09 leasing=hipotecario)

# ============================================================
# NAMING / FORMATO
# ============================================================
EXCEL_NAMING_TEMPLATE = "ESTUDIO {nombre}-{fecha}.xlsx"  # nombre MAYUSCULAS, fecha DD.MM.AA

# ============================================================
# TERMINOLOGÍA OBLIGATORIA (Ley 546 / branding)
# ============================================================
TERMINOLOGIA_PROHIBIDA = ("asesores", "vendedores", "refinanciar", "reescriturar", "extender plazo")
TERMINOLOGIA_OFICIAL = ("consultores", "optimizar", "reducir plazo", "reducir intereses")

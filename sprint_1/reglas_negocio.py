"""
reglas_negocio.py
==================
Constantes y reglas de negocio MejorAhora SAS.
Fuente: REGLAS_NEGOCIO_MEJORAHORA.md
"""

# ============================================================
# SUBSIDIOS
# ============================================================

TIPO_SUBSIDIO_FRECH = "FRECH"
TIPO_SUBSIDIO_HABITAT = "HABITAT"  # 48 meses, nuevo 2024+
TIPO_SUBSIDIO_REGIONAL = "REGIONAL"  # similar a HABITAT
TIPO_SUBSIDIO_NINGUNO = "NINGUNO"

MESES_MAXIMOS_SUBSIDIO = {
    TIPO_SUBSIDIO_FRECH: 84,     # 7 anos (Ley 546/99)
    TIPO_SUBSIDIO_HABITAT: 48,   # 4 anos (nuevo)
    TIPO_SUBSIDIO_REGIONAL: 48,  # 4 anos (similar habitat)
    TIPO_SUBSIDIO_NINGUNO: 0,
}

# ============================================================
# BANCOS - reglas especiales
# ============================================================

# Bancos donde el INTERES del extracto viene INFLADO con el FRECH.
# Para que SUMA CUOTA cuadre: interes_real = interes_extracto - frech
BANCOS_INTERES_CON_FRECH = {
    "FNA (Fondo Nacional del Ahorro)",
    "FNA",
    "CAJA SOCIAL",
    "BANCO CAJA SOCIAL",
    # Bancolombia es "a veces" - se detecta por SUMA CUOTA y se alerta
}
BANCOS_INTERES_CON_FRECH_CONDICIONAL = {
    "BANCOLOMBIA",
    "BANCOLOMBIA L",
}

# Bancos que NO exigen certificar ingresos en reduccion de plazo.
# Para estos: no se muestra "Ingresos requeridos" en el estudio.
BANCOS_SIN_INGRESOS_REQUERIDOS = {
    "BANCOLOMBIA",
    "BANCOLOMBIA L",
    "CAJA SOCIAL",
    "BANCO CAJA SOCIAL",
    "LA HIPOTECARIA",
}

# ============================================================
# RATIOS CUOTA / INGRESOS
# ============================================================

RATIO_VIS = 0.39      # 39% para creditos VIS (Vivienda Interes Social)
RATIO_NO_VIS = 0.29   # 29% default

MARCADORES_VIS = {
    "VIS",
    "VIS DAVIVIENDA",
}

# ============================================================
# HONORARIOS
# ============================================================

HONORARIOS_MINIMO = 1_800_000    # Minimo en pesos (con IVA incluido)
HONORARIOS_UMBRAL = 30_000_000    # Bajo este monto, se cobra minimo
HONORARIOS_PORCENTAJE = 0.06      # 6% del ahorro si supera umbral

# ============================================================
# VALIDACIONES
# ============================================================
# 2026-05-07: removidas DIF_SIMULA_TOLERANCIA y SUMA_CUOTA_TOLERANCIA
# (eran codigo muerto, ningun import las usaba). Ademas SUMA_CUOTA_TOLERANCIA
# estaba stale en $10k cuando el valor canonico desde 2026-04-24 es $70k
# universal (MASTER_RULES §8.15). Para tolerancias usar:
#   from config_reglas import TOLERANCIA_SUMA_CUOTA, TOLERANCIA_DIF_SIMULA

# Umbral para detectar MORA: si cuota_real / PMT_teorico supera este ratio,
# probablemente el cliente esta pagando cuota + mora
RATIO_MORA_UMBRAL = 1.5

# Umbral para detectar ABONO EXTRA: si PMT_teorico / cuota_real supera,
# probablemente hubo abono a capital que redujo la cuota
RATIO_ABONO_EXTRA_UMBRAL = 1.4

# Colchon de seguridad aplicado en proyecciones (celda U8)
COLCHON_SEGURIDAD = 15_000

# ============================================================
# PLAZOS
# ============================================================

# Plazos por defecto si plazo pendiente >= 14 anos (todos caben)
PLAZOS_DEFAULT = [13.5, 12.0, 11.0, 10.0, 9.0, 8.5]

# Limite minimo PRACTICO de plazo en anos (granularidad del proponedor).
# Jose 2026-04-24: Ley 546 NO impone 4 anos minimo. Ley 546 dice:
#   credito_total (pagado + restante) >= 5 anos.
# Si el cliente ya pago >= 5 anos del credito, puede pagarlo en cualquier
# plazo restante (1 mes incluso). El minimo de 0.5 anos es solo granularidad
# operativa del proponedor (medios anios = paso minimo).
PLAZO_MINIMO_ANOS = 0.5

# Minimo 1 ano de diferencia entre opciones consecutivas
PLAZO_PASO_MINIMO = 1.0

# Paso default cuando el plazo pendiente permite opciones amplias
PLAZO_PASO_DEFAULT = 2.0  # de 2 en 2 anos (ej: 20, 18, 16, 14, 12, 10)

# ============================================================
# MAPEO BD columnas
# ============================================================

COL_BD = {
    "nombre": 1,
    "credito": 2,
    "banco": 6,
    "consultor": 13,
    "cedula": 18,
    "amortizacion": 19,  # PESOS / UVR
    "tipo": 20,          # Hipotecario / Leasing
    "cuota": 21,         # NETA (con FRECH ya descontado)
    "plazo_inicial": 22,
    "plazo_pendiente": 23,
    "tasa_ea": 24,       # Cobrada
    "frech": 25,
    "seguro_vida": 26,
    "seguro_incendio": 27,   # + otros seguros (desempleo, etc)
    "seguro_terremoto": 28,
    "capital_mensual": 29,
    "interes_mensual": 30,   # En FNA/Caja Social viene con FRECH sumado
    "capital_adeudado": 31,
    "abono_efectivo": 32,
    "ingresos": 33,
    "actividad_economica": 34,
}

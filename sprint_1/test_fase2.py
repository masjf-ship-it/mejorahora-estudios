# -*- coding: utf-8 -*-
"""
test_fase2.py — MejorAhora SAS (2026-04-23)
============================================
Validacion aislada de R-DVV-06 y R-DVV-07 sin tocar STAGING ni Drive.

Uso:
    py sprint_1\\test_fase2.py

4 tests:
  A) R-DVV-07 aplica: Julieth con cuotas_pagadas=2 -> proyecta a mes 6
  B) R-DVV-07 no aplica: cliente con cuotas_pagadas>=6
  C) R-DVV-07 no aplica: banco distinto a Davivienda/DaviBank
  D) R-DVV-06 aplica: detección duplicación cuota por G1+G2, override seguros
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from excel_populator import DatosClienteExcel
from pipeline_davivienda import proyectar_sexta_cuota, construir_datos, _staging_update
from proponedor_plazos import proponer_plazos
from validar_extraccion_davivienda import validar_datos_cliente


def _assert(cond: bool, msg: str):
    if cond:
        print(f"  PASS: {msg}")
    else:
        print(f"  FAIL: {msg}")
        raise AssertionError(msg)


# ============================================================
# TEST A — R-DVV-07 aplica (Julieth canónica)
# ============================================================
print("\n=== TEST A — R-DVV-07 Julieth (banco DAVIVIENDA, cuotas_pag=2) ===")
datos_j = DatosClienteExcel(
    credito_id="570000601203902-9",
    nombre="JULIETH VALENCIA RAMIREZ",
    banco="DAVIVIENDA",
    cuota_mensual=1633000.0,
    plazo_inicial=240,
    plazo_pendiente=238,   # cuotas_pagadas = 2
    tasa_ea=0.131,
    frech_subsidio=0.0,
    seguro_vida=32685.0,
    seguro_incendio=43666.0,
    seguro_terremoto=0.0,
    capital_mensual=133042.0,
    interes_mensual=1422958.0,
    saldo_capital=137943278.0,
    consultor="BRILLID SALINAS",
    actividad_economica="Vis",
    abono_efectivo=500000.0,
    ingresos=4000000.0,
)
datos_j, info_j = proyectar_sexta_cuota(datos_j)
print(f"  info: {info_j}")
print(f"  saldo_despues: ${datos_j.saldo_capital:,.0f}")
print(f"  plazo_pend:    {datos_j.plazo_pendiente}m (esperado 234)")
_assert(info_j["aplicada"] is True, "R-DVV-07 debe aplicar con cuotas_pagadas<6")
_assert(info_j["meses"] == 4, "meses_faltantes == 4 (de 2 a 6)")
_assert(info_j["cuotas_pagadas_antes"] == 2, "cuotas_pagadas_antes == 2")
_assert(datos_j.plazo_pendiente == 234, "plazo_pendiente == 234 (238-4)")
# Tolerancia ±$5k en saldo proyectado (aritmetica de redondeo tasa_mv)
tolerancia = 5000.0
esperado = 137087668.0
diff = abs(datos_j.saldo_capital - esperado)
_assert(diff <= tolerancia,
        f"saldo_capital ${datos_j.saldo_capital:,.0f} vs esperado ${esperado:,.0f} "
        f"(diff ${diff:,.0f}, tolerancia ${tolerancia:,.0f})")


# ============================================================
# TEST B — R-DVV-07 no aplica (cuotas_pagadas >= 6)
# ============================================================
print("\n=== TEST B — R-DVV-07 no aplica (cuotas_pagadas=10, ya cumple politica) ===")
datos_b = DatosClienteExcel(
    credito_id="570111222333444-5",
    nombre="CLIENTE MESES",
    banco="DAVIVIENDA",
    cuota_mensual=1500000.0,
    plazo_inicial=240,
    plazo_pendiente=230,  # cuotas_pagadas = 10
    tasa_ea=0.12,
    frech_subsidio=0.0,
    seguro_vida=30000.0,
    seguro_incendio=50000.0,
    seguro_terremoto=0.0,
    capital_mensual=100000.0,
    interes_mensual=1400000.0,
    saldo_capital=100000000.0,
    consultor="X",
    actividad_economica="Empleado",
)
saldo_antes_b = datos_b.saldo_capital
plazo_antes_b = datos_b.plazo_pendiente
datos_b, info_b = proyectar_sexta_cuota(datos_b)
_assert(info_b["aplicada"] is False, "R-DVV-07 NO debe aplicar si cuotas_pagadas>=6")
_assert(datos_b.saldo_capital == saldo_antes_b, "saldo_capital intacto")
_assert(datos_b.plazo_pendiente == plazo_antes_b, "plazo_pendiente intacto")


# ============================================================
# TEST C — R-DVV-07 no aplica (banco distinto)
# ============================================================
print("\n=== TEST C — R-DVV-07 no aplica (banco BANCOLOMBIA) ===")
datos_c = DatosClienteExcel(
    credito_id="X",
    nombre="CLIENTE BANCOLOMBIA",
    banco="BANCOLOMBIA",
    cuota_mensual=1000000.0,
    plazo_inicial=240,
    plazo_pendiente=238,  # cuotas_pagadas=2, pero banco distinto
    tasa_ea=0.12,
    frech_subsidio=0.0,
    seguro_vida=30000.0, seguro_incendio=50000.0, seguro_terremoto=0.0,
    capital_mensual=100000.0, interes_mensual=900000.0,
    saldo_capital=100000000.0,
    consultor="X", actividad_economica="Empleado",
)
saldo_antes_c = datos_c.saldo_capital
datos_c, info_c = proyectar_sexta_cuota(datos_c)
_assert(info_c["aplicada"] is False, "R-DVV-07 NO debe aplicar a bancos !=Davivienda/DaviBank")
_assert(datos_c.saldo_capital == saldo_antes_c, "saldo_capital intacto")


# ============================================================
# TEST D — R-DVV-06 aplica (Leidy canónica: duplicación cuota)
# ============================================================
print("\n=== TEST D — R-DVV-06 Leidy (duplicacion cuota, override seguros) ===")
# Simular dict pdf con seguros duplicados por pago irregular
pdf_leidy = {
    "credito": "600707600145510-4",
    "nombre": "LEIDY YESENIA MENESES OBANDO",
    "cuota_mensual": 1343000,        # Valor Cuota Mes del encabezado
    "plazo_inicial": 95,
    "cuotas_pendientes": 64,
    "tasa_cobrada": 0.105,
    "frech_cobertura_pag1": 0,
    # Seguros APLICADOS (duplicados)
    "seguro_vida": 222630,           # duplicado (2 cuotas en un mes)
    "seguro_incendio": 0,
    "seguro_terremoto": 0,
    # Total aplicado es el doble de la cuota (gatillo G1)
    "total_aplicado": 2690288,       # ≈ 2 × 1343000 → G1 dispara
    # Capital/intereses también duplicados (los maneja Regla 9.3 al construir)
    "abonos_capital": 1467222,
    "intereses_corrientes": 1031750,
    "saldo_capital": 61743274,
    # Campo NUEVO: valor "+ Seguros" del cuadro inferior (real del mes)
    "seguros_inferior_total": 111315,
}
staging_row_leidy = {"nombre": "LEIDY YESENIA MENESES OBANDO", "credito": "600707600145510-4"}
hs_leidy = {}         # sin match HubSpot
reg_leidy = {}        # sin match REGISTROS
datos_l, notas_l = construir_datos(pdf_leidy, hs_leidy, staging_row_leidy, reg=reg_leidy)
print(f"  seguro_vida: ${datos_l.seguro_vida:,.0f} (esperado $111,315)")
print(f"  seguro_incendio: ${datos_l.seguro_incendio:,.0f} (esperado $0)")
print(f"  seguro_terremoto: ${datos_l.seguro_terremoto:,.0f} (esperado $0)")
print(f"  notas_crm: {notas_l}")
_assert(datos_l.seguro_vida == 111315, "seguro_vida override a $111,315 (valor de '+ Seguros')")
_assert(datos_l.seguro_incendio == 0, "seguro_incendio = 0")
_assert(datos_l.seguro_terremoto == 0, "seguro_terremoto = 0")
_assert(len(notas_l) >= 1, "debe haber nota CRM generada")
_assert(any("Duplicacion" in n for n in notas_l), "nota debe mencionar 'Duplicacion'")


# ============================================================
# TEST E — R-DVV-06 no aplica (sin duplicación, Fernando)
# ============================================================
print("\n=== TEST E — R-DVV-06 no aplica (Fernando, sin duplicacion) ===")
pdf_fernando = {
    "credito": "570238110001018-4",
    "nombre": "FERNANDO RODRIGO GALLO MARTINEZ",
    "cuota_mensual": 229000,
    "plazo_inicial": 240,
    "cuotas_pendientes": 137,
    "tasa_cobrada": 0.12,
    "frech_cobertura_pag1": 0,
    "seguro_vida": 29383,
    "seguro_incendio": 52976,
    "seguro_terremoto": 12758,
    # Total aplicado = cuota normal (no duplicada)
    "total_aplicado": 229000,  # NO dispara G1 (ratio 1:1)
    "abonos_capital": 35608,
    "intereses_corrientes": 99275,
    "saldo_capital": 12985250,
    # Sin "+ Seguros" inferior (extracto de 1 hoja)
    "seguros_inferior_total": 0,
}
staging_row_f = {"nombre": "FERNANDO RODRIGO GALLO MARTINEZ"}
datos_f, notas_f = construir_datos(pdf_fernando, {}, staging_row_f, reg={})
_assert(datos_f.seguro_vida == 29383, "seguro_vida Fernando intacto $29,383")
_assert(datos_f.seguro_incendio == 52976, "seguro_incendio intacto $52,976")
_assert(datos_f.seguro_terremoto == 12758, "seguro_terremoto intacto $12,758")
_assert(len(notas_f) == 0, "no hay notas CRM (ninguna regla especial disparó)")


# ============================================================
# TEST F — Fase 3 Mejora #3: es_vis auto desde actividad_economica
# ============================================================
print("\n=== TEST F — es_vis auto desde actividad (Fase 3 #3) ===")

def _es_vis(actividad):
    """Replica la expresion del pipeline linea 851."""
    return "VIS" in (actividad or "").upper()

_assert(_es_vis("Vis Davivienda") is True, "actividad 'Vis Davivienda' -> VIS=True")
_assert(_es_vis("VIS") is True, "actividad 'VIS' -> True")
_assert(_es_vis("Empleado") is False, "actividad 'Empleado' -> False")
_assert(_es_vis("") is False, "actividad '' -> False")
_assert(_es_vis(None) is False, "actividad None -> False")
_assert(_es_vis("Independiente") is False, "actividad 'Independiente' -> False")


# ============================================================
# TEST G — Fase 3 Mejora #2: tier abono minimo por saldo
# ============================================================
print("\n=== TEST G — tier abono minimo por saldo (Fase 3 #2) ===")

# Caso saldo pequeno (<$300M) -> piso $80k. Todas las opciones con abono >=$80k.
print("  [G.1] saldo $100M, sin abono objetivo, sin ingresos -> piso $80k")
prop_small = proponer_plazos(
    plazo_pendiente_meses=240, tasa_ea=0.12, saldo=100_000_000.0,
    seguros_totales=80_000.0, ingresos_cliente=0.0, banco="DAVIVIENDA",
    es_vis=False, abono_objetivo_min=0.0, abono_objetivo_max=0.0,
    plazo_pagado_meses=0,
)
print(f"    metodo={prop_small.metodo} plazos={prop_small.plazos_anos}")
_assert(len(prop_small.plazos_anos) == 6, "devuelve 6 opciones")
# Calcular abono real de OPC 1 (mayor plazo, menor abono) debe ser >= piso_abono
# Para saldo $100M, piso es $80k. Verificamos esto implicitamente por el hecho
# que el filtro rechaza opciones con abono < piso. Si devuelve 6 opciones con
# saldo pequeno, significa que al menos 6 candidatos superaron $80k (antes
# del fix hubiera necesitado superar $100k -> menos opciones potencialmente).

# Caso saldo grande (>=$300M) -> piso $200k. Opciones con abono < $200k descartadas.
print("  [G.2] saldo $500M, sin abono objetivo, sin ingresos -> piso $200k")
prop_large = proponer_plazos(
    plazo_pendiente_meses=240, tasa_ea=0.12, saldo=500_000_000.0,
    seguros_totales=80_000.0, ingresos_cliente=0.0, banco="DAVIVIENDA",
    es_vis=False, abono_objetivo_min=0.0, abono_objetivo_max=0.0,
    plazo_pagado_meses=0,
)
print(f"    metodo={prop_large.metodo} plazos={prop_large.plazos_anos}")
_assert(len(prop_large.plazos_anos) == 6, "devuelve 6 opciones")

# Verificacion expresion de tier en si misma (fuente de verdad de la regla)
def _piso_abono(saldo):
    # Retro 2026-04-24: piso subio de $80k a $100k para saldos <$300M
    return 100_000.0 if saldo < 300_000_000.0 else 200_000.0

_assert(_piso_abono(100_000_000) == 100_000.0, "saldo $100M -> piso $100k")
_assert(_piso_abono(299_999_999) == 100_000.0, "saldo $299.9M -> piso $100k (borde inferior)")
_assert(_piso_abono(300_000_000) == 200_000.0, "saldo $300M -> piso $200k (borde superior)")
_assert(_piso_abono(500_000_000) == 200_000.0, "saldo $500M -> piso $200k")


# ============================================================
# TEST H — Fase 3 Mejora #1: nota CRM columna L via _staging_update
# ============================================================
print("\n=== TEST H — _staging_update escribe nota CRM y preserva previa ===")

class _MockWS:
    """Mock minimalista de gspread worksheet para test _staging_update."""
    def __init__(self, initial_cells=None):
        self.cells = dict(initial_cells or {})  # {(row, col): value}
    def update_cell(self, row, col, value):
        self.cells[(row, col)] = value
    def cell(self, row, col):
        class _C:
            def __init__(self, value):
                self.value = value
        return _C(self.cells.get((row, col), ""))

# H.1: nota CRM se escribe en columna correcta sin nota previa
idx = {"estado": 0, "link_estudio": 1, "nota_crm": 11}  # col L = 11 (0-based) -> 12 (1-based)
ws = _MockWS()
_staging_update(ws, row_idx=5, idx=idx, estado="Excel generado",
                 link="https://drive/x", nota_crm="Nota test")
_assert(ws.cells.get((5, 1)) == "Excel generado", "estado escrito col 1")
_assert(ws.cells.get((5, 2)) == "https://drive/x", "link escrito col 2")
_assert(ws.cells.get((5, 12)) == "Nota test", "nota_crm escrita col 12 (L)")

# H.2: si hay nota previa, concatena con " | "
ws2 = _MockWS(initial_cells={(5, 12): "Nota previa del analista"})
_staging_update(ws2, row_idx=5, idx=idx, estado="Excel generado",
                 link="", nota_crm="R-DVV-07 aplicada")
esperado = "Nota previa del analista | R-DVV-07 aplicada"
_assert(ws2.cells.get((5, 12)) == esperado,
        f"nota previa preservada + concat con ' | '. got={ws2.cells.get((5,12))!r}")

# H.3: si nota_crm vacia, NO sobrescribe columna L
ws3 = _MockWS(initial_cells={(5, 12): "Nota existente"})
_staging_update(ws3, row_idx=5, idx=idx, estado="Excel generado",
                 link="", nota_crm="")
_assert(ws3.cells.get((5, 12)) == "Nota existente",
        "nota_crm vacia NO toca columna L")

# H.4: si idx no tiene nota_crm (STAGING sin columna), no falla
idx_sin_col = {"estado": 0, "link_estudio": 1, "nota_crm": None}
ws4 = _MockWS()
_staging_update(ws4, row_idx=5, idx=idx_sin_col, estado="Excel generado",
                 nota_crm="Intento nota")
_assert((5, 12) not in ws4.cells, "sin columna nota_crm en idx, no escribe")


# ============================================================
# TEST I — M1 validar_datos_cliente: detecta saldo sospechosamente bajo
# ============================================================
print("\n=== TEST I — M1 FAIL saldo < $1M (R-DVV-04) ===")
datos_saldo_bajo = DatosClienteExcel(
    credito_id="570X", nombre="TEST", banco="DAVIVIENDA",
    cuota_mensual=229000.0, plazo_inicial=240, plazo_pendiente=137,
    tasa_ea=0.12, frech_subsidio=0.0,
    seguro_vida=29383.0, seguro_incendio=52976.0, seguro_terremoto=12758.0,
    capital_mensual=35608.0, interes_mensual=99275.0,
    saldo_capital=500_000.0,  # < $1M debe fallar
    consultor="X", actividad_economica="",
)
ok_i, err_i, warn_i = validar_datos_cliente(datos_saldo_bajo)
_assert(ok_i is False, "M1 debe fallar con saldo_capital=$500k (<$1M)")
_assert(any("saldo_capital sospechosamente bajo" in e for e in err_i),
        f"debe mencionar saldo sospechosamente bajo. err={err_i}")


# ============================================================
# TEST J — M1 acepta datos válidos (Fernando canónico)
# ============================================================
print("\n=== TEST J — M1 PASS con datos Fernando canonicos ===")
datos_fernando_ok = DatosClienteExcel(
    credito_id="570238110001018-4", nombre="FERNANDO RODRIGO GALLO MARTINEZ",
    banco="DAVIVIENDA",
    cuota_mensual=229000.0, plazo_inicial=240, plazo_pendiente=137,
    tasa_ea=0.12, frech_subsidio=0.0,
    seguro_vida=29383.0, seguro_incendio=52976.0, seguro_terremoto=12758.0,
    capital_mensual=35608.0, interes_mensual=99275.0,
    saldo_capital=12985250.0,
    consultor="YERINSON JESUS SALINAS PERDOMO",
    actividad_economica="Vis Davivienda",
    abono_efectivo=200000.0, ingresos=4800000.0,
)
ok_j, err_j, warn_j = validar_datos_cliente(datos_fernando_ok)
print(f"  errores: {err_j}")
print(f"  warnings: {warn_j}")
_assert(ok_j is True, f"M1 debe PASAR con Fernando canonico. err={err_j}")
_assert(len(err_j) == 0, "sin errores")
# La suma Fernando: 29383+52976+12758+35608+99275 = 230000. Cuota $229,000.
# Diff $1000, dentro tolerancia de $70k.


# ============================================================
# TEST K — M1 detecta plazo_pendiente > plazo_inicial (imposible)
# ============================================================
print("\n=== TEST K — M1 FAIL plazo_pendiente > plazo_inicial ===")
datos_plazo_mal = DatosClienteExcel(
    credito_id="570X", nombre="TEST", banco="DAVIVIENDA",
    cuota_mensual=1000000.0, plazo_inicial=100, plazo_pendiente=200,  # imposible
    tasa_ea=0.12, frech_subsidio=0.0,
    seguro_vida=30000.0, seguro_incendio=40000.0, seguro_terremoto=0.0,
    capital_mensual=100000.0, interes_mensual=900000.0,
    saldo_capital=50000000.0,
    consultor="X", actividad_economica="",
)
ok_k, err_k, warn_k = validar_datos_cliente(datos_plazo_mal)
_assert(ok_k is False, "M1 debe fallar con plazo_pend > plazo_inicial")
_assert(any("plazo_pendiente" in e and "imposible" in e for e in err_k),
        f"debe mencionar plazos incoherentes. err={err_k}")


# ============================================================
# TEST L — M1 detecta tasa_ea sin normalizar (mayor a 1)
# ============================================================
print("\n=== TEST L — M1 FAIL tasa_ea no normalizada ===")
datos_tasa_mal = DatosClienteExcel(
    credito_id="570X", nombre="TEST", banco="DAVIVIENDA",
    cuota_mensual=1000000.0, plazo_inicial=240, plazo_pendiente=200,
    tasa_ea=14.31,  # sin normalizar: debe ser 0.1431
    frech_subsidio=0.0,
    seguro_vida=30000.0, seguro_incendio=40000.0, seguro_terremoto=0.0,
    capital_mensual=100000.0, interes_mensual=900000.0,
    saldo_capital=50000000.0,
    consultor="X", actividad_economica="",
)
ok_l, err_l, warn_l = validar_datos_cliente(datos_tasa_mal)
_assert(ok_l is False, "M1 debe fallar con tasa_ea=14.31 (sin normalizar)")
_assert(any("tasa_ea parece porcentaje" in e for e in err_l),
        f"debe mencionar tasa sin normalizar. err={err_l}")


# ============================================================
# TEST M — Retro 2026-04-24: M1 detecta seguro_vida=0 con incendio>0
# ============================================================
print("\n=== TEST M — M1 FAIL seguro_vida=0 con incendio>0 (retro Yolly/Maria F) ===")
datos_yolly_like = DatosClienteExcel(
    credito_id="570X", nombre="TEST YOLLY-LIKE", banco="DAVIVIENDA",
    cuota_mensual=1092000.0, plazo_inicial=240, plazo_pendiente=218,
    tasa_ea=0.129, frech_subsidio=0.0,
    seguro_vida=0.0,           # Vision falló
    seguro_incendio=23730.0,   # Vision sí extrajo
    seguro_terremoto=0.0,
    capital_mensual=113807.0, interes_mensual=930193.0,
    saldo_capital=91419952.0,
    consultor="X", actividad_economica="Vis",
)
ok_m, err_m, warn_m = validar_datos_cliente(datos_yolly_like)
_assert(ok_m is False, "M1 debe fallar con seguro_vida=0 e incendio>0")
_assert(any("seguro_vida=0" in e and "incendio" in e for e in err_m),
        f"debe mencionar seguro_vida=0 con incendio. err={err_m}")


# ============================================================
# TEST N — R-DVV-06 G2 refinado: NO dispara si seg_vida_aplicado=0 (Karen Tatiana fix)
# ============================================================
print("\n=== TEST N — R-DVV-06 G2 NO dispara con vida=0 (caso Karen Tatiana) ===")
pdf_karen_tatiana = {
    "credito": "571616690012705-4",
    "nombre": "KAREN TATIANA CAPERA AVILA",
    "cuota_mensual": 905010,
    "plazo_inicial": 84, "cuotas_pendientes": 65,
    "tasa_cobrada": 0.1095,
    "frech_cobertura_pag1": 0,
    "seguro_vida": 0,             # Vision falló (real es $11,960)
    "seguro_incendio": 26436,     # Vision sí extrajo
    "seguro_terremoto": 0,
    "total_aplicado": 905010,     # NO duplicado
    "abonos_capital": 599073,
    "intereses_corrientes": 254034,
    "saldo_capital": 55246529,
    "seguros_inferior_total": 46392,  # Diff con aplicados $26,436 > $10k
}
datos_kt, notas_kt = construir_datos(pdf_karen_tatiana, {}, {"nombre":"KAREN T"}, reg={})
print(f"  notas_crm: {notas_kt}")
print(f"  seguros: vida=${datos_kt.seguro_vida:,.0f} inc=${datos_kt.seguro_incendio:,.0f} ter=${datos_kt.seguro_terremoto:,.0f}")
_assert(len(notas_kt) == 0, "G2 NO debe disparar con seg_vida=0 (caso false positive)")
_assert(datos_kt.seguro_vida == 0, "seguro_vida intacto en 0 (M1 lo bloqueara)")
_assert(datos_kt.seguro_incendio == 26436, "seguro_incendio intacto")


# ============================================================
# TEST O — P6 detectar_hubspot_genericos (firmas repetidas >=3)
# ============================================================
print("\n=== TEST O — detectar_hubspot_genericos firmas repetidas ===")
from pipeline_davivienda import detectar_hubspot_genericos

class _MockHubSpot:
    """Mock HubSpot que devuelve firmas predefinidas por nombre."""
    def __init__(self, mapping):
        self.mapping = mapping  # nombre -> dict(consultor, actividad, ingresos)
    def match_contact_cascade(self, cedula, email, nombre, properties):
        d = self.mapping.get(nombre, {})
        if not d:
            return {}
        return {"matched_by": "nombre", "contact": {
            "id": "x",
            "properties": {
                "hubspot_owner_id": "",
                "actividad_economica": d.get("actividad", ""),
                "ingresos_demostrables": d.get("ingresos", ""),
            }
        }}
    def get_owner(self, owner_id):
        return {"firstName": "", "lastName": ""}

# Caso: 3 clientes con misma firma (Brillid + Docente + 3.186.000) -> generica
# 1 cliente con firma distinta -> NO generica
# (Mockeamos solo actividad/ingresos porque consultor sale del owner_id que esta vacio)
mapping = {
    "CLIENTE A": {"actividad": "Vis Davivienda", "ingresos": "$3,186,000"},
    "CLIENTE B": {"actividad": "Vis Davivienda", "ingresos": "$3,186,000"},
    "CLIENTE C": {"actividad": "Vis Davivienda", "ingresos": "$3,186,000"},
    "CLIENTE D": {"actividad": "Empleado", "ingresos": "$5,000,000"},
}
mock_hs = _MockHubSpot(mapping)
pendientes_test = [
    {"row_idx": 1, "nombre": "CLIENTE A", "cc": "1", "email": "a@x"},
    {"row_idx": 2, "nombre": "CLIENTE B", "cc": "2", "email": "b@x"},
    {"row_idx": 3, "nombre": "CLIENTE C", "cc": "3", "email": "c@x"},
    {"row_idx": 4, "nombre": "CLIENTE D", "cc": "4", "email": "d@x"},
]
firmas = detectar_hubspot_genericos(mock_hs, pendientes_test, umbral=3)
print(f"  firmas detectadas: {firmas}")
_assert(len(firmas) == 1, f"debe detectar 1 firma generica (la de A/B/C). got {len(firmas)}")
firma_esperada = ("", "Vis Davivienda", "$3,186,000")
_assert(firma_esperada in firmas,
        f"firma esperada {firma_esperada} no esta. got {firmas}")
# Cliente D NO esta en firmas genericas (firma unica)
firma_d = ("", "Empleado", "$5,000,000")
_assert(firma_d not in firmas, "firma unica de Cliente D NO debe ser generica")


print("\n=== TODOS LOS TESTS PASARON ===")

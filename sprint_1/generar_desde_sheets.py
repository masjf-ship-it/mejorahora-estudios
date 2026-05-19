#!/usr/bin/env python3
"""
generar_desde_sheets.py
========================
Orquestador del flujo canonico (2026-04-16):

    Google Sheets BD (snapshot CSV)
            |
            v
    sheets_loader.cargar_por_credito()   -> DatosClienteExcel
            |
            v
    proponedor_plazos.proponer_plazos()  -> 6 plazos en anos
            |
            v
    ExcelPopulator.crear_estudio()       -> ESTUDIO {NOMBRE}.{FECHA}.xlsx
            |
            v
    post-proceso: eliminar hoja BD del xlsx de salida

Este script NO modifica el codigo legado (excel_populator, reglas_negocio,
generar_estudio). Es refactor aditivo: nuevo punto de entrada que convive
con crear_desde_bd().

Uso CLI:
    python generar_desde_sheets.py --credito 570000170024315-7
    python generar_desde_sheets.py --credito XXX --abono-min 200000 --abono-max 300000
    python generar_desde_sheets.py --credito XXX --csv ../bank_rules/davivienda_snapshot_2026-04-16.csv
"""

import argparse
import configparser
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from sheets_loader import cargar_por_credito, detectar_vis
from proponedor_plazos import proponer_plazos, _ea_a_mv, _pmt
from excel_populator import ExcelPopulator


# ============================================================
# REGLAS DE AJUSTE POST-CARGA (universales, todos los bancos)
# Ver MASTER_RULES.md §8.15 — TOLERANCIA_* centralizadas en config_reglas.py
# ============================================================
# 2026-05-07: deduplicado del literal local. Constante canonica en config.
from config_reglas import TOLERANCIA_SUMA_CUOTA  # noqa: F401


def _capital_intereses_simulador(tasa_ea: float, plazo_pend_meses: int,
                                  saldo: float) -> tuple:
    """Calcula (capital_mes, intereses_mes) del primer mes segun simulador PMT.

    Formula:
        intereses_mes_1 = saldo * tasa_mv
        pmt             = PMT(tasa_mv, n, saldo)
        capital_mes_1   = pmt - intereses_mes_1

    Se usa para aplicar Regla 9.3 (abono extraordinario detectado via
    divergencia entre valores BD/extracto y simulador).
    """
    if plazo_pend_meses <= 0 or saldo <= 0 or tasa_ea <= 0:
        return (0.0, 0.0)
    tasa_mv = _ea_a_mv(tasa_ea)
    intereses = saldo * tasa_mv
    pmt = _pmt(tasa_mv, plazo_pend_meses, saldo)
    capital = pmt - intereses
    return (capital, intereses)


def aplicar_regla_92_seguros(datos, seguros_total_override: float) -> list:
    """Regla 9.2: Seguros discrepantes -> consolidar total en Vida, I/T = 0.

    Se aplica cuando el analista pasa un override explicito via CLI.
    Retorna lista de notas aplicadas.
    """
    notas = []
    if seguros_total_override <= 0:
        return notas
    prev_v = datos.seguro_vida
    prev_i = datos.seguro_incendio
    prev_t = datos.seguro_terremoto
    datos.seguro_vida = seguros_total_override
    datos.seguro_incendio = 0.0
    datos.seguro_terremoto = 0.0
    notas.append(
        "[Regla 9.2] Seguros override: V=${:,.0f} I=${:,.0f} T=${:,.0f} "
        "-> V=${:,.0f} I=$0 T=$0".format(
            prev_v, prev_i, prev_t, seguros_total_override))
    return notas


def aplicar_regla_93_abono_extraordinario(datos,
                                           tolerancia: float = TOLERANCIA_SUMA_CUOTA) -> list:
    """Regla 9.3: Abono extraordinario detectado -> reemplazar capital/intereses
    del extracto por los del simulador cuando la SUMA CUOTA queda fuera
    de la tolerancia +-70k.

    Formula del Excel:
        SUMA CUOTA (C12)  = cuota - (capital_extracto + intereses_extracto + seguros)
        DIF.SIMULA (D12)  = cuota - (capital_simulador + intereses_simulador + seguros)

    Si |SUMA CUOTA| > tolerancia => el extracto tiene huella de abono extra
    (capital desplazado). Se reemplazan capital/intereses por los del
    simulador para que C12 quede dentro de tolerancia.

    IMPORTANTE (Jose 2026-04-17): Los seguros NO se calculan ni se ajustan
    automaticamente. El valor correcto de seguros debe venir de:
      a) BD (si la skill procesar-extractos registro los seguros del PDF
         post-abono correctamente), o
      b) Flag CLI --seguros-override X con el valor real del extracto.
    Nunca calcular seguros = cuota - PMT (eso es inventar un numero para
    forzar SUMA CUOTA=$0). La diferencia residual (ej. -$16.445 en Martha)
    es real y debe conservarse porque refleja la integridad del extracto.

    Retorna lista de notas aplicadas.
    """
    notas = []
    seguros = (datos.seguro_vida + datos.seguro_incendio +
               datos.seguro_terremoto)
    cap_bd = datos.capital_mensual
    int_bd = datos.interes_mensual
    cap_sim, int_sim = _capital_intereses_simulador(
        datos.tasa_ea, datos.plazo_pendiente, datos.saldo_capital)

    suma_cuota_bd = datos.cuota_mensual - (cap_bd + int_bd + seguros)
    # FUTURO R-DVV-22 (FRECH) — punto-gancho documentado, NO implementado
    # (decision Jose 2026-05-16: esperar mas casos). Si se automatiza: cuando
    # datos.frech_subsidio > 0 y datos.interes_mensual == 0 (Davivienda),
    # usar (int_sim - frech) aqui y en el gate de pipeline_davivienda.py.
    # Ver MOM_DAVIVIENDA.md R-DVV-22 (numeros caso SARA). Hoy: int_sim crudo.
    dif_simula = datos.cuota_mensual - (cap_sim + int_sim + seguros)

    notas.append(
        "[Regla 9.3] Check BD: cap=${:,.0f} int=${:,.0f} | "
        "SIM: cap=${:,.0f} int=${:,.0f}".format(
            cap_bd, int_bd, cap_sim, int_sim))
    notas.append(
        "[Regla 9.3] SUMA CUOTA (BD)=${:,.0f} | DIF.SIMULA=${:,.0f} | "
        "tolerancia=+-${:,.0f}".format(
            suma_cuota_bd, dif_simula, tolerancia))

    if abs(suma_cuota_bd) > tolerancia:
        # Divergencia => posible abono extraordinario. Reemplazar por simulador.
        datos.capital_mensual = cap_sim
        datos.interes_mensual = int_sim
        nuevo_suma = datos.cuota_mensual - (cap_sim + int_sim + seguros)
        notas.append(
            "[Regla 9.3] APLICADA: |SUMA CUOTA|=${:,.0f} > tolerancia. "
            "Reemplazados capital/intereses por simulador. "
            "Nuevo SUMA CUOTA=${:,.0f} (seguros intactos, diferencia real).".format(
                abs(suma_cuota_bd), nuevo_suma))
    else:
        notas.append(
            "[Regla 9.3] OK: SUMA CUOTA dentro de tolerancia, no se ajusta.")
    return notas


# ============================================================
# CONFIG
# ============================================================

def cargar_config():
    config = configparser.ConfigParser()
    config_path = SCRIPT_DIR / "config.ini"
    if config_path.exists():
        config.read(str(config_path), encoding="utf-8")
    template = config.get(
        "RUTAS", "template",
        fallback=str(SCRIPT_DIR.parent / "PESOS.xlsx"),
    )
    salida = config.get(
        "RUTAS", "salida",
        fallback=str(SCRIPT_DIR.parent / "estudios_generados"),
    )
    return {
        "template": os.path.abspath(template),
        "salida": os.path.abspath(salida),
    }


def csv_por_defecto(banco: str = "davivienda") -> str:
    """Ruta al snapshot CSV del banco indicado.

    LEGACY — solo ruta manual-CLI (`generar_desde_sheets.py --credito X`).
    La PRODUCCION (pipeline_davivienda/pipeline_bancolombia via run_pipeline)
    NO usa esto: carga desde Google Sheets/STAGING, no de CSV snapshot.
    El `2026-04-16` es un snapshot historico fijo (no se actualiza); para
    Bancolombia ese archivo no existe -> pasar --csv explicito si se usa
    esta herramienta manual.
    """
    return str(
        SCRIPT_DIR.parent / "bank_rules" /
        f"{banco.lower()}_snapshot_2026-04-16.csv"
    )


# ============================================================
# POST-PROCESO: ocultar hoja BD del xlsx generado
# ============================================================

def ocultar_hoja_bd(xlsx_path: str) -> bool:
    """Oculta la hoja 'BD' mediante manipulacion directa del ZIP.
    Retorna True si se oculto, False si no existia.

    NOTA: se usa 'ocultar' (sheet state='hidden') en vez de 'eliminar' porque
    openpyxl.save() descarta las imagenes embebidas (logos de la empresa) al
    re-guardar el xlsx. La manipulacion directa del ZIP preserva todo el
    contenido binario (imagenes, drawings, estilos).
    """
    import zipfile
    import shutil
    import tempfile
    from xml.etree import ElementTree as ET

    NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    ET.register_namespace('', NS_MAIN)
    ET.register_namespace('r', NS_R)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.xlsx')
    os.close(tmp_fd)

    try:
        with zipfile.ZipFile(xlsx_path, 'r') as zin:
            names = zin.namelist()
            wb_xml = zin.read('xl/workbook.xml')
            wb_root = ET.fromstring(wb_xml)
            sheets_elem = wb_root.find(f'{{{NS_MAIN}}}sheets')

            if sheets_elem is None:
                return False

            bd_sheet_elem = None
            sheet_list = list(sheets_elem.findall(f'{{{NS_MAIN}}}sheet'))
            for sheet in sheet_list:
                if sheet.get('name') == 'BD':
                    bd_sheet_elem = sheet
                    break

            if bd_sheet_elem is None:
                return False

            # No se puede ocultar la hoja activa (primera). Si BD es la primera,
            # la movemos al final antes de ocultar.
            if sheet_list[0] == bd_sheet_elem:
                sheets_elem.remove(bd_sheet_elem)
                sheets_elem.append(bd_sheet_elem)

            bd_sheet_elem.set('state', 'hidden')

            new_wb_xml = (
                b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                + ET.tostring(wb_root, encoding='UTF-8')
            )

            with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for name in names:
                    if name == 'xl/workbook.xml':
                        zout.writestr(name, new_wb_xml)
                    else:
                        zout.writestr(name, zin.read(name))

        shutil.move(tmp_path, xlsx_path)
        return True
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# Alias retrocompatible: mantiene el nombre antiguo apuntando a la nueva impl.
eliminar_hoja_bd = ocultar_hoja_bd


# ============================================================
# PIPELINE
# ============================================================

def generar(
    credito_id: str,
    csv_path: str,
    template_path: str,
    carpeta_salida: str,
    abono_min: float = 0,
    abono_max: float = 0,
    plazos_manuales=None,
    fecha: str | None = None,
    quitar_bd: bool = True,
    seguros_override: float = 0.0,
    aplicar_93: bool = True,
) -> dict:
    """Ejecuta el pipeline completo y devuelve un reporte."""
    # 1) Cargar datos del CSV
    print(f"[1/5] Cargando credito {credito_id} desde {csv_path}")
    datos = cargar_por_credito(credito_id, csv_path)
    es_vis = detectar_vis(datos.actividad_economica, "")

    print(f"      Cliente: {datos.nombre}")
    print(f"      Banco: {datos.banco} | VIS: {es_vis}")
    print(f"      Saldo: ${datos.saldo_capital:,.0f} | "
          f"Cuota: ${datos.cuota_mensual:,.0f}")
    print(f"      Plazo pend: {datos.plazo_pendiente} meses | "
          f"Tasa EA: {datos.tasa_ea*100:.2f}%")
    print(f"      Ingresos: ${datos.ingresos:,.0f} | "
          f"Abono efectivo: ${datos.abono_efectivo:,.0f}")

    # 1.5) Reglas universales de ajuste post-carga (MASTER_RULES.md §8)
    # (ESTADO_PROYECTO NO es fuente de reglas — ver CLAUDE.md jerarquia docs)
    notas_reglas = []
    print(f"[2/5] Aplicando reglas de ajuste (9.2 y 9.3)...")
    if seguros_override > 0:
        notas_reglas.extend(aplicar_regla_92_seguros(datos, seguros_override))
    if aplicar_93:
        notas_reglas.extend(aplicar_regla_93_abono_extraordinario(datos))
    for n in notas_reglas:
        print(f"      {n}")

    # 2) Proponer plazos
    print(f"[3/5] Proponiendo 6 plazos...")
    seguros = (datos.seguro_vida + datos.seguro_incendio +
               datos.seguro_terremoto)

    # Abono objetivo: CLI override > abono_efectivo como min
    abono_min_efectivo = abono_min if abono_min > 0 else datos.abono_efectivo
    abono_max_efectivo = abono_max if abono_max > 0 else datos.abono_efectivo

    plazo_pagado_meses = max(0, datos.plazo_inicial - datos.plazo_pendiente)
    propuesta = proponer_plazos(
        plazo_pendiente_meses=datos.plazo_pendiente,
        tasa_ea=datos.tasa_ea,
        saldo=datos.saldo_capital,
        seguros_totales=seguros,
        ingresos_cliente=datos.ingresos,
        banco=datos.banco,
        es_vis=es_vis,
        abono_objetivo_min=abono_min_efectivo,
        abono_objetivo_max=abono_max_efectivo,
        plazos_manuales=plazos_manuales,
        plazo_pagado_meses=plazo_pagado_meses,
    )
    print(f"      Metodo: {propuesta.metodo}")
    print(f"      Plazos (anos): {propuesta.plazos_anos}")
    for n in propuesta.notas:
        print(f"      - {n}")

    # 3) Inyectar plazos en DatosClienteExcel y generar Excel
    datos.plazos_anos = propuesta.plazos_anos
    print(f"[4/5] Generando Excel desde template {template_path}")
    populator = ExcelPopulator(template_path)
    output_path = populator.crear_estudio(datos, carpeta_salida, fecha)
    print(f"      Archivo: {output_path}")

    # 4) Post-proceso: ocultar hoja BD (preserva logos)
    bd_oculta = False
    if quitar_bd:
        print(f"[5/5] Ocultando hoja BD del xlsx (preserva logos)...")
        bd_oculta = ocultar_hoja_bd(output_path)
        print(f"      BD oculta: {bd_oculta}")

    return {
        "credito_id": datos.credito_id,
        "nombre": datos.nombre,
        "banco": datos.banco,
        "es_vis": es_vis,
        "output_path": output_path,
        "metodo_plazos": propuesta.metodo,
        "plazos_anos": propuesta.plazos_anos,
        "notas_plazos": propuesta.notas,
        "notas_reglas": notas_reglas,
        "bd_oculta": bd_oculta,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Genera estudio Excel desde Google Sheets BD (flujo canonico 2026-04-16)"
    )
    parser.add_argument("--credito", required=True,
                        help="Numero de credito (ej. 570000170024315-7)")
    parser.add_argument("--csv", default=None,
                        help="Ruta al CSV snapshot (default: davivienda)")
    parser.add_argument("--banco", default="davivienda",
                        help="Banco para localizar el CSV por defecto")
    parser.add_argument("--output", default=None,
                        help="Carpeta de salida (default: config.ini -> ../estudios_generados)")
    parser.add_argument("--template", default=None,
                        help="Ruta al PESOS.xlsx (default: config.ini -> ../PESOS.xlsx)")
    parser.add_argument("--abono-min", type=float, default=0,
                        help="Abono objetivo minimo (override)")
    parser.add_argument("--abono-max", type=float, default=0,
                        help="Abono objetivo maximo (override)")
    parser.add_argument("--plazos", default=None,
                        help="Plazos manuales en anos, separados por coma: '12,10,8,6,5,4'")
    parser.add_argument("--fecha", default=None,
                        help="Fecha del estudio en DD.MM.YY (default: hoy)")
    parser.add_argument("--keep-bd", action="store_true",
                        help="NO eliminar la hoja BD del xlsx de salida")
    parser.add_argument("--seguros-override", type=float, default=0.0,
                        help="Regla 9.2: total seguros (va todo a Vida, I/T=0)")
    parser.add_argument("--no-regla-93", action="store_true",
                        help="Desactivar Regla 9.3 (abono extraordinario auto)")
    args = parser.parse_args()

    cfg = cargar_config()
    template = args.template or cfg["template"]
    salida = args.output or cfg["salida"]
    csv_path = args.csv or csv_por_defecto(args.banco)

    if not os.path.exists(template):
        print(f"ERROR: template no encontrado: {template}")
        sys.exit(2)
    if not os.path.exists(csv_path):
        print(f"ERROR: CSV no encontrado: {csv_path}")
        sys.exit(2)

    plazos_manuales = None
    if args.plazos:
        plazos_manuales = [float(x.strip()) for x in args.plazos.split(",") if x.strip()]

    print()
    print("=" * 60)
    print("   MejorAhora SAS - Estudio desde Google Sheets BD")
    print("=" * 60)
    print()

    try:
        reporte = generar(
            credito_id=args.credito,
            csv_path=csv_path,
            template_path=template,
            carpeta_salida=salida,
            abono_min=args.abono_min,
            abono_max=args.abono_max,
            plazos_manuales=plazos_manuales,
            fecha=args.fecha,
            quitar_bd=not args.keep_bd,
            seguros_override=args.seguros_override,
            aplicar_93=not args.no_regla_93,
        )
    except Exception as e:
        print(f"\nERROR en pipeline: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 60)
    print("  OK - Estudio generado")
    print("=" * 60)
    print(f"  Cliente: {reporte['nombre']}")
    print(f"  Banco:   {reporte['banco']} (VIS: {reporte['es_vis']})")
    print(f"  Metodo:  {reporte['metodo_plazos']}")
    print(f"  Plazos:  {reporte['plazos_anos']}")
    print(f"  Archivo: {reporte['output_path']}")
    print()


if __name__ == "__main__":
    main()

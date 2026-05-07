"""
sheets_loader.py
=================
Lee el CSV snapshot de la hoja banco de Google Sheets BD (MejorAhora SAS)
y devuelve un DatosClienteExcel listo para usar con excel_populator.

Fuente de verdad: extracto PDF. BD Google Sheets es respaldo.
Este modulo solo lee y normaliza lo que hay en BD hoy.

Mapeo 42 columnas reales del Sheet BASE PARA ESTUDIOS OK - hoja "davivienda"
(validado 2026-04-16). Ver PLAN_REFACTOR_SHEETS_2026-04-16.md.
"""

import csv
import re
from pathlib import Path
from typing import Optional

# Importar el dataclass existente para no duplicar
from excel_populator import DatosClienteExcel


# ============================================================
# MAPEO 42 COLUMNAS REALES (Sheet "davivienda" 2026-04-16)
# ============================================================
# Indices 1-based (como aparecen en el CSV)

COL = {
    "nombre": 1,
    "segundo_titular": 2,
    "acceso_hubspot": 3,
    "prioridad": 4,
    "credito": 5,
    "fecha_solicitud": 6,
    "estado": 7,
    "fecha_completo_info": 8,
    "banco": 9,
    "nota_consultor": 10,
    "referenciador": 11,
    "nota_crm": 12,
    "notas": 13,
    "est_generado": 14,
    "equipo": 15,
    "consultor": 16,
    "fecha_notas": 17,
    "cronograma_end": 18,
    "estudio": 19,
    "extracto": 20,
    "cedula": 21,
    "amortizacion": 22,
    "tipo": 23,
    "cuota_mensual": 24,
    "plazo_inicial": 25,
    "plazo_pendiente": 26,
    "tasa": 27,
    "frech": 28,
    "seguro_vida": 29,
    "seguro_incendio": 30,
    "seguro_terremoto": 31,
    "capital_mensual": 32,
    "interes_mensual": 33,
    "capital_adeudado": 34,
    "abono_efectivo": 35,
    "ingresos": 36,
    "actividad_economica": 37,
    "email": 38,
    "telefono": 39,
    "ciudad": 40,
    "reasignados": 41,
    "mensaje": 42,
}


# ============================================================
# NORMALIZACION
# ============================================================

def parse_moneda(valor) -> float:
    """Convierte '$200,000' o '200000' o '2.750.000' a float.
    Textos no numericos ('Acorde al estado del Credito', 'N/A', 'NAN') -> 0.
    """
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s or s.upper() in {"N/A", "NAN", "NULL", "NONE"}:
        return 0.0
    # Quitar $, espacios, comillas
    s = s.replace("$", "").replace(" ", "").replace('"', "").strip()
    # Si contiene letras (ej. "Acorde al estado del Credito") -> no numerico
    if re.search(r"[A-Za-zÀ-ÿ]", s):
        return 0.0
    # Reemplazar coma decimal por punto si hay un solo "coma"
    # Caso: "200,000" (miles) vs "12,60" (decimal)
    # Heuristica: si hay . y , -> . es miles, , es decimal (formato LatAm)
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # Solo coma. Heuristica:
        # - Si empieza con "0," -> SIEMPRE decimal (ej "0,1275" -> 0.1275)
        # - Si 3+ digitos despues de coma -> miles (ej "200,000" -> 200000)
        # - Si 1-2 digitos despues -> decimal (ej "12,60" -> 12.60)
        before = s.split(",")[0].strip()
        after = s.split(",")[-1]
        if before in ("0", "00", "000", ""):
            s = s.replace(",", ".")  # 0,1275 -> 0.1275
        elif len(after) >= 3:
            s = s.replace(",", "")  # 200,000 -> 200000
        else:
            s = s.replace(",", ".")  # 12,60 -> 12.60
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_tasa_ea(valor) -> float:
    """Normaliza tasa EA.
    BD tiene 2 formatos:
      - Porcentaje: '12,60' -> 0.1260
      - Decimal: '0,1275' -> 0.1275
    Regla: si parsed >= 1 -> dividir entre 100.
    """
    val = parse_moneda(valor)
    if val <= 0:
        return 0.0
    return val / 100.0 if val >= 1.0 else val


def parse_entero(valor) -> int:
    """Convierte '240', '240.0' a int. Nulos -> 0."""
    if valor is None:
        return 0
    s = str(valor).strip()
    if not s or s.upper() in {"N/A", "NAN", "NULL"}:
        return 0
    s = s.replace(",", "").replace(".", "").replace(" ", "")
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return 0


def detectar_vis(actividad_economica: str, tipo: str = "") -> bool:
    """True si la actividad indica VIS (ratio 39%)."""
    upper = (actividad_economica or "").upper().strip()
    tipo_upper = (tipo or "").upper().strip()
    marcadores = {"VIS", "VIS DAVIVIENDA", "VIVIENDA INTERES SOCIAL"}
    for m in marcadores:
        if m in upper or m in tipo_upper:
            return True
    return False


# ============================================================
# LECTURA
# ============================================================

def cargar_filas(csv_path: str) -> list[dict]:
    """Lee el CSV y devuelve lista de dicts indexados por nombre de columna."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV no encontrado: {csv_path}")

    rows = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)  # primera fila = encabezados
        for raw in reader:
            if not raw or not any(raw):
                continue
            # Padding si la fila tiene menos columnas
            while len(raw) < 42:
                raw.append("")
            fila = {}
            for nombre, idx in COL.items():
                fila[nombre] = raw[idx - 1] if idx - 1 < len(raw) else ""
            rows.append(fila)
    return rows


def buscar_por_credito(rows: list[dict], credito_id: str) -> Optional[dict]:
    """Busca fila por numero de credito (comparacion normalizada)."""
    target = str(credito_id).strip()
    for row in rows:
        if str(row.get("credito", "")).strip() == target:
            return row
    return None


def fila_a_datos(fila: dict) -> DatosClienteExcel:
    """Convierte una fila normalizada a DatosClienteExcel."""
    nombre = (fila.get("nombre") or "").strip()
    banco = (fila.get("banco") or "DAVIVIENDA").strip().upper()
    actividad = (fila.get("actividad_economica") or "").strip()

    return DatosClienteExcel(
        credito_id=str(fila.get("credito", "")).strip(),
        nombre=nombre,
        banco=banco,
        cuota_mensual=parse_moneda(fila.get("cuota_mensual")),
        plazo_inicial=parse_entero(fila.get("plazo_inicial")),
        plazo_pendiente=parse_entero(fila.get("plazo_pendiente")),
        tasa_ea=parse_tasa_ea(fila.get("tasa")),
        frech_subsidio=parse_moneda(fila.get("frech")),
        seguro_vida=parse_moneda(fila.get("seguro_vida")),
        seguro_incendio=parse_moneda(fila.get("seguro_incendio")),
        seguro_terremoto=parse_moneda(fila.get("seguro_terremoto")),
        capital_mensual=parse_moneda(fila.get("capital_mensual")),
        interes_mensual=parse_moneda(fila.get("interes_mensual")),
        saldo_capital=parse_moneda(fila.get("capital_adeudado")),
        consultor=(fila.get("consultor") or "").strip(),
        actividad_economica=actividad,
        abono_efectivo=parse_moneda(fila.get("abono_efectivo")),
        ingresos=parse_moneda(fila.get("ingresos")),
        plazos_anos=None,  # lo llena el propuestor
    )


def cargar_por_credito(credito_id: str, csv_path: str) -> DatosClienteExcel:
    """Atajo: lee CSV + busca credito + devuelve DatosClienteExcel."""
    rows = cargar_filas(csv_path)
    fila = buscar_por_credito(rows, credito_id)
    if fila is None:
        disponibles = [r.get("credito", "?") for r in rows]
        raise ValueError(
            f"Credito '{credito_id}' no encontrado en {csv_path}. "
            f"Disponibles: {disponibles}"
        )
    return fila_a_datos(fila)


# ============================================================
# CLI de diagnostico
# ============================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python sheets_loader.py <credito_id> [ruta_csv]")
        sys.exit(1)

    credito = sys.argv[1]
    csv_path = sys.argv[2] if len(sys.argv) > 2 else (
        Path(__file__).resolve().parent.parent / "bank_rules" /
        "davivienda_snapshot_2026-04-16.csv"
    )

    datos = cargar_por_credito(credito, str(csv_path))
    print(f"Cliente: {datos.nombre}")
    print(f"Credito: {datos.credito_id}")
    print(f"Banco: {datos.banco}")
    print(f"Cuota: ${datos.cuota_mensual:,.0f}")
    print(f"Plazo pendiente: {datos.plazo_pendiente} meses "
          f"({datos.plazo_pendiente/12:.2f} anos)")
    print(f"Tasa EA: {datos.tasa_ea:.4f} ({datos.tasa_ea*100:.2f}%)")
    print(f"FRECH: ${datos.frech_subsidio:,.0f}")
    print(f"Seguros: V${datos.seguro_vida:,.0f} + "
          f"I${datos.seguro_incendio:,.0f} + "
          f"T${datos.seguro_terremoto:,.0f}")
    print(f"Saldo capital: ${datos.saldo_capital:,.0f}")
    print(f"Abono efectivo: ${datos.abono_efectivo:,.0f}")
    print(f"Ingresos: ${datos.ingresos:,.0f}")
    print(f"Actividad: {datos.actividad_economica}")
    print(f"Es VIS: {detectar_vis(datos.actividad_economica, '')}")
    print(f"Consultor: {datos.consultor}")

#!/usr/bin/env python3
"""
listar_pendientes_hoy.py
=========================
Consulta REGISTROS de la Sheet "BASE PARA ESTUDIOS OK" y devuelve
la lista REAL de clientes a procesar hoy segun el flujo oficial.

Filtros (AND):
    ESTADO  IN {Pendiente, Pte. Validar Yenny, Mora}
    BANCO   IN {Davivienda, Caja Social, Bancolombia}

Salidas:
    - Impresion en pantalla (tabla legible)
    - CSV en outputs/pendientes_hoy_YYYY-MM-DD.csv (para alimentar el pipeline)

Uso:
    py listar_pendientes_hoy.py
    py listar_pendientes_hoy.py --banco davivienda   (filtra un solo banco)
    py listar_pendientes_hoy.py --estado pendiente   (filtra un solo estado)
"""

import argparse
import csv
import sys
import unicodedata
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

SHEET_ID = "1_9FUAo8cSrLDWAkJlNoy29Cmyh9ojXwnW6zbvhGsESA"
WORKSHEET_SRC = "REGISTROS"          # fuente de verdad (solo lectura)
WORKSHEET_DST = "STAGING"            # destino operativo oficial (propuestas del pipeline)
CREDS = ROOT_DIR / "credentials" / "sheets_sa.json"
OUTPUT_DIR = ROOT_DIR / "outputs"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Indices verificados 2026-04-20 (memoria project_pipeline_diario_estudios)
COL_NOMBRE = 0   # A
COL_CREDITO = 4  # E
COL_FECHA = 5    # F
COL_ESTADO = 6   # G
COL_BANCO = 8    # I
COL_NOTA = 9     # J
COL_ESTUDIO = 18 # S
COL_EXTRACTO = 19 # T
COL_CC = 20      # U
COL_AMORTIZACION = 21 # V  (valores: pesos, uvr, vacio)

MESES_ES = {
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6,
    "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "sep": 9, "sept": 9, "septiembre": 9,
    "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11, "dic": 12, "diciembre": 12,
}

ESTADOS_VALIDOS = {"pendiente", "pte validar yenny", "mora"}
# Estados EXCLUIDOS del pipeline (estudio ya realizado o flujo distinto):
#   - "Pendiente NOTA consultor" = estudio hecho, solo falta nota en CRM (Yenny)
ESTADOS_EXCLUIDOS = {"pendiente nota consultor", "realizado", "cancelado"}
BANCOS_VALIDOS = {"davivienda", "caja social", "bancolombia"}
# Moneda/amortizacion — solo PESOS (Jose 2026-04-21): UVR no se procesa por ahora.
# Vacio se INCLUYE (tolerancia: puede ser registro incompleto pero valido).
AMORTIZACION_VALIDA = {"pesos"}
AMORTIZACION_EXCLUIDA = {"uvr"}


def normalizar(s: str) -> str:
    """Lowercase + sin tildes + sin puntuacion + espacios colapsados."""
    if not s:
        return ""
    s = str(s).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    # Reemplazar signos/separadores por espacio para que matches por tokens funcionen
    for ch in [".", ",", ";", ":", "-", "_", "/", "\\", "|", "(", ")", "*"]:
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    return s


def tokens(s: str) -> set:
    """Set de palabras de una cadena normalizada."""
    return set(normalizar(s).split())


def parse_fecha_solicitud(s: str):
    """Parsea 'dd-mmm', 'dd/mm/yyyy', 'dd-mes-yyyy' y variantes colombianas.
    Retorna date o None si no parsea. None -> se ordena al final.
    Ano por defecto = ano actual (2026) si solo viene dd-mmm."""
    if not s:
        return None
    n = normalizar(s)
    # yyyy-mm-dd / dd/mm/yyyy / dd-mm-yyyy con numeros
    import re
    m = re.match(r"^(\d{1,2})[\s/\-](\d{1,2})[\s/\-](\d{2,4})$", n)
    if m:
        d, mm, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            from datetime import date as _d
            return _d(y, mm, d)
        except ValueError:
            return None
    # dd-mmm / dd-mmm-yyyy
    m = re.match(r"^(\d{1,2})\s+([a-z]+)(?:\s+(\d{2,4}))?$", n)
    if m:
        d = int(m.group(1))
        mes_str = m.group(2)[:4].rstrip()  # "sept" -> "sep" via MESES_ES
        mm = MESES_ES.get(m.group(2), MESES_ES.get(m.group(2)[:3]))
        if not mm:
            return None
        y = int(m.group(3)) if m.group(3) else date.today().year
        if y < 100:
            y += 2000
        try:
            from datetime import date as _d
            return _d(y, mm, d)
        except ValueError:
            return None
    return None


def estado_match(valor: str, filtro: set, incluir_vacio: bool = True) -> bool:
    """ESTADO vacio se incluye (decision Jose 2026-04-20).
    Match por TOKENS (set subset), tolerante a variantes "Pendiente-Nota-Consultor",
    "Pendiente Nota: consultor", "Pendiente de Nota al Consultor", etc.
    Exclusion tiene prioridad sobre inclusion."""
    n_tokens = tokens(valor)
    # --- EXCLUSION ---
    for ex in ESTADOS_EXCLUIDOS:
        ex_tokens = tokens(ex)
        if ex_tokens and ex_tokens.issubset(n_tokens):
            return False
    # --- VACIO ---
    if not n_tokens:
        return incluir_vacio
    # --- INCLUSION ---
    for e in filtro:
        e_tokens = tokens(e)
        if e_tokens and e_tokens.issubset(n_tokens):
            return True
    return False


def banco_match(valor: str, filtro: set) -> bool:
    n = normalizar(valor)
    for b in filtro:
        if b in n:
            return True
    return False


def amortizacion_match(valor: str) -> bool:
    """Solo PESOS. UVR se excluye. Vacio se incluye (tolerancia)."""
    n = normalizar(valor)
    if not n:
        return True  # vacio = tolerancia
    if n in AMORTIZACION_EXCLUIDA:
        return False
    return n in AMORTIZACION_VALIDA


def abrir_sheet():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("ERROR: instalar dependencias -> py -m pip install gspread google-auth")
        sys.exit(2)

    if not CREDS.exists():
        print(f"ERROR: credenciales no encontradas: {CREDS}")
        sys.exit(2)

    creds = Credentials.from_service_account_file(str(CREDS), scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    return sh


def cargar_registros(sh):
    ws = sh.worksheet(WORKSHEET_SRC)
    return ws.get_all_values()


def dedup_por_credito(pendientes: list, creditos_presentes: set) -> list:
    """Filtra pendientes excluyendo los cuyo N° credito ya esta en STAGING.

    Funcion pura para garantizar idempotencia: re-ejecutar listar_pendientes
    nunca debe duplicar filas con el mismo N° credito. Ver test_fase2.py TEST P.

    Args:
        pendientes: lista de dicts con clave "credito".
        creditos_presentes: set de strings (N° credito ya presentes en STAGING).

    Returns:
        Lista filtrada de pendientes; solo los nuevos.
    """
    return [p for p in pendientes if str(p.get("credito", "")).strip() not in creditos_presentes]


def publicar_en_staging(sh, pendientes: list):
    """Appendea pendientes en STAGING respetando el esquema existente.

    Mapea cada campo por NOMBRE de columna (no por posicion) al header real.
    NO hace clear() — preserva filas que ya Yenny tenga en proceso.
    Escribe solo en la primera fila vacia (NOMBRE CLIENTE sin contenido).
    """
    ws = sh.worksheet(WORKSHEET_DST)
    todas = ws.get_all_values()
    if not todas:
        print(f"ERROR: STAGING vacia (ni siquiera header). Aborta para no corromper.")
        return

    header_real = todas[0]
    body = todas[1:]

    # Mapeo nombre-columna -> indice (normalizado)
    def norm_h(s):
        return normalizar(s)
    idx_por_nombre = {norm_h(h): i for i, h in enumerate(header_real)}

    # Busco nombres esperados (tolerante a variantes)
    def buscar(*candidatos):
        for c in candidatos:
            k = norm_h(c)
            for nk, i in idx_por_nombre.items():
                if k == nk or k in nk or nk in k:
                    return i
        return None

    col = {
        "nombre":    buscar("NOMBRE CLIENTE", "NOMBRE"),
        "credito":   buscar("Numero de Credito", "NUMERO DE CREDITO"),
        "fecha":     buscar("Fecha de Solicitud"),
        "estado":    buscar("ESTADO"),
        "banco":     buscar("BANCO"),
        "nota":      buscar("Nota de Consultor", "Nota Consultor"),
        "cc":        buscar("CC"),
    }
    faltantes = [k for k, v in col.items() if v is None and k not in ("cc",)]
    if faltantes:
        print(f"ERROR: STAGING no tiene columnas esperadas: {faltantes}")
        print(f"Header actual: {header_real}")
        return

    # Detectar primera fila realmente vacia + N° creditos ya presentes (dedup)
    n_header = 1
    primera_vacia_idx = None
    creditos_presentes = set()
    for i, row in enumerate(body):
        val_nombre = row[col["nombre"]] if col["nombre"] < len(row) else ""
        val_cred = row[col["credito"]] if col["credito"] < len(row) else ""
        if not str(val_nombre).strip() and primera_vacia_idx is None:
            primera_vacia_idx = i
        if str(val_cred).strip():
            creditos_presentes.add(str(val_cred).strip())
    if primera_vacia_idx is None:
        primera_vacia_idx = len(body)  # appendear al final

    # Dedup: excluir pendientes cuyo N° credito ya este en STAGING
    pendientes_antes = len(pendientes)
    pendientes = dedup_por_credito(pendientes, creditos_presentes)
    n_dedup = pendientes_antes - len(pendientes)
    if n_dedup:
        print(f"[DEDUP] {n_dedup} pendientes ya estan en STAGING por N° credito, skip.")
    if not pendientes:
        print("[STAGING] nada nuevo que appendear tras dedup.")
        return

    start_row = n_header + primera_vacia_idx + 1  # 1-based en Sheets

    # Construyo las filas a escribir: ancho = ancho del header; solo lleno columnas mapeadas
    ancho = len(header_real)
    filas_out = []
    for p in pendientes:
        row = [""] * ancho
        row[col["nombre"]] = p["nombre"]
        row[col["credito"]] = p["credito"]
        row[col["fecha"]] = p["fecha_solicitud"]
        row[col["estado"]] = p["estado"]
        row[col["banco"]] = p["banco"]
        row[col["nota"]] = p["nota_consultor"]
        if col["cc"] is not None:
            row[col["cc"]] = p["cc"]
        filas_out.append(row)

    # Asegurar espacio
    filas_necesarias = start_row + len(filas_out) - 1
    if ws.row_count < filas_necesarias:
        ws.add_rows(filas_necesarias - ws.row_count + 10)

    end_row = start_row + len(filas_out) - 1
    rng = f"A{start_row}:{gspread_col_letter(ancho)}{end_row}"
    ws.update(values=filas_out, range_name=rng)

    print(f"\n[STAGING] {len(filas_out)} filas appendeadas en rango {rng}")
    print(f"          URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")


def gspread_col_letter(n: int) -> str:
    """1-based index to column letter (1=A, 27=AA)."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--banco", help="filtra un banco especifico (davivienda/caja social/bancolombia)")
    parser.add_argument("--estado", help="filtra un estado especifico")
    parser.add_argument("--no-csv", action="store_true", help="no exporta CSV, solo imprime")
    parser.add_argument("--no-staging", action="store_true",
                        help="no publica en STAGING (solo imprime y exporta CSV)")
    args = parser.parse_args()

    filtro_estados = {normalizar(args.estado)} if args.estado else ESTADOS_VALIDOS
    filtro_bancos = {normalizar(args.banco)} if args.banco else BANCOS_VALIDOS

    print("=" * 72)
    print("   MejorAhora SAS - Pendientes del dia para procesar")
    print(f"   Sheet: BASE PARA ESTUDIOS OK / {WORKSHEET_SRC} -> {WORKSHEET_DST}")
    print(f"   Filtro ESTADO: {sorted(filtro_estados)}")
    print(f"   Filtro BANCO:  {sorted(filtro_bancos)}")
    print(f"   Filtro MONEDA: {sorted(AMORTIZACION_VALIDA)} (UVR excluido)")
    print("=" * 72)

    sh = abrir_sheet()
    filas = cargar_registros(sh)
    if not filas:
        print("Sheet vacia.")
        return

    header = filas[0]
    body = filas[1:]
    print(f"Filas totales en REGISTROS: {len(body)}")

    pendientes = []
    for i, row in enumerate(body, start=2):  # +2 porque row 1 = header, body empieza en sheet row 2
        def safe(idx):
            return row[idx] if idx < len(row) else ""

        estado = safe(COL_ESTADO)
        banco = safe(COL_BANCO)
        amortizacion = safe(COL_AMORTIZACION)

        if not estado_match(estado, filtro_estados):
            continue
        if not banco_match(banco, filtro_bancos):
            continue
        if not amortizacion_match(amortizacion):
            continue

        pendientes.append({
            "sheet_row": i,
            "nombre": safe(COL_NOMBRE),
            "cc": safe(COL_CC),
            "credito": safe(COL_CREDITO),
            "banco": banco,
            "estado": estado,
            "amortizacion": amortizacion,
            "fecha_solicitud": safe(COL_FECHA),
            "nota_consultor": safe(COL_NOTA),
            "estudio": safe(COL_ESTUDIO),
            "extracto": safe(COL_EXTRACTO),
        })

    print(f"\nPendientes encontrados: {len(pendientes)}\n")

    if not pendientes:
        print("(ningun cliente cumple los criterios del dia)")
        return

    # Orden canonico (Jose 2026-04-21): MISMO ORDEN QUE REGISTROS.
    # Preservar sheet_row (2-based) para que STAGING refleje el orden exacto
    # en que aparecen los clientes en la pestana REGISTROS.
    # Se mantiene _fecha_dt calculada por si se usa downstream (proponedor/priorizacion).
    from datetime import date as _d
    MAX_DATE = _d(9999, 12, 31)
    for p in pendientes:
        p["_fecha_dt"] = parse_fecha_solicitud(p["fecha_solicitud"]) or MAX_DATE
    pendientes.sort(key=lambda p: p["sheet_row"])

    print(f"{'#':<3} {'BANCO':<13} {'ESTADO':<25} {'NOMBRE':<40} {'CC':<13} {'CREDITO':<20}")
    print("-" * 120)
    for idx, p in enumerate(pendientes, start=1):
        print(f"{idx:<3} {p['banco'][:12]:<13} {p['estado'][:24]:<25} {p['nombre'][:39]:<40} {p['cc'][:12]:<13} {p['credito'][:19]:<20}")

    # Resumen por banco
    print("\nResumen por banco:")
    from collections import Counter
    c_banco = Counter(normalizar(p["banco"]) for p in pendientes)
    for b, n in sorted(c_banco.items()):
        print(f"  {b:<15} {n:>3}")

    c_estado = Counter(normalizar(p["estado"]) for p in pendientes)
    print("\nResumen por estado:")
    for e, n in sorted(c_estado.items()):
        print(f"  {e:<25} {n:>3}")

    # Export CSV
    if not args.no_csv:
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_path = OUTPUT_DIR / f"pendientes_hoy_{date.today().isoformat()}.csv"
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(pendientes[0].keys()))
            w.writeheader()
            w.writerows(pendientes)
        print(f"\nCSV exportado: {out_path}")

    # Publicar en STAGING (destino operativo oficial)
    if not args.no_staging:
        publicar_en_staging(sh, pendientes)


if __name__ == "__main__":
    main()

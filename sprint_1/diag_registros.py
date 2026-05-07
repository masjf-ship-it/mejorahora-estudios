#!/usr/bin/env python3
"""
diag_registros.py
==================
Diagnostico rapido de REGISTROS:
  1. Lista TODOS los headers (indice + nombre) — para encontrar columna Amortizacion
  2. Cuenta pendientes segun filtros del pipeline
  3. Muestra valores unicos de la columna 'Amortizacion' (si existe)
  4. Diagnostica por que STAGING quedo vacia tras ultimo run

Uso:
    python sprint_1\diag_registros.py > diag_registros.txt 2>&1
    type diag_registros.txt
"""

import sys
import unicodedata
from pathlib import Path
from collections import Counter

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

SHEET_ID = "1_9FUAo8cSrLDWAkJlNoy29Cmyh9ojXwnW6zbvhGsESA"
CREDS = ROOT_DIR / "credentials" / "sheets_sa.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def normalizar(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    for ch in [".", ",", ";", ":", "-", "_", "/", "\\", "|", "(", ")", "*"]:
        s = s.replace(ch, " ")
    return " ".join(s.split())


def col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    import gspread
    from google.oauth2.service_account import Credentials

    print("=" * 80)
    print(f"  DIAG REGISTROS — {SHEET_ID}")
    print("=" * 80)

    if not CREDS.exists():
        print(f"ERROR: credenciales no encontradas: {CREDS}")
        sys.exit(2)

    creds = Credentials.from_service_account_file(str(CREDS), scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    # ---------- PESTANAS ----------
    print("\n[1] Pestanas (worksheets):")
    for ws in sh.worksheets():
        print(f"    - {ws.title:<30} rows={ws.row_count:>5}  cols={ws.col_count:>3}  gid={ws.id}")

    # ---------- HEADERS REGISTROS ----------
    print("\n[2] Headers de REGISTROS (todos los cols):")
    ws_reg = sh.worksheet("REGISTROS")
    header = ws_reg.row_values(1)
    for i, h in enumerate(header):
        letter = col_letter(i + 1)
        marker = "  <-- POSIBLE AMORTIZACION" if "amort" in normalizar(h) else ""
        marker += "  <-- POSIBLE UVR/PESOS" if ("uvr" in normalizar(h) or "pesos" in normalizar(h) or "moneda" in normalizar(h) or "tipo" in normalizar(h)) else ""
        print(f"    col {i:>3} ({letter:>3}): {h!r}{marker}")

    # ---------- PENDIENTES ----------
    print("\n[3] Pendientes segun filtros pipeline:")
    filas = ws_reg.get_all_values()
    body = filas[1:]
    print(f"    Total filas (sin header): {len(body)}")

    ESTADOS_VALIDOS = {"pendiente", "pte validar yenny", "mora"}
    ESTADOS_EXCLUIDOS = {"pendiente nota consultor", "realizado", "cancelado"}
    BANCOS_VALIDOS = {"davivienda", "caja social", "bancolombia"}

    COL_NOMBRE = 0
    COL_CREDITO = 4
    COL_ESTADO = 6
    COL_BANCO = 8

    def estado_ok(v: str) -> bool:
        n = set(normalizar(v).split())
        for ex in ESTADOS_EXCLUIDOS:
            t = set(normalizar(ex).split())
            if t and t.issubset(n):
                return False
        if not n:
            return True
        for e in ESTADOS_VALIDOS:
            t = set(normalizar(e).split())
            if t and t.issubset(n):
                return True
        return False

    def banco_ok(v: str) -> bool:
        nv = normalizar(v)
        return any(b in nv for b in BANCOS_VALIDOS)

    pendientes = []
    for i, row in enumerate(body, start=2):
        def safe(idx):
            return row[idx] if idx < len(row) else ""
        if not estado_ok(safe(COL_ESTADO)):
            continue
        if not banco_ok(safe(COL_BANCO)):
            continue
        pendientes.append({
            "row": i,
            "nombre": safe(COL_NOMBRE),
            "credito": safe(COL_CREDITO),
            "estado": safe(COL_ESTADO),
            "banco": safe(COL_BANCO),
        })

    print(f"    Pendientes que PASAN filtros (estado+banco): {len(pendientes)}")
    if pendientes:
        print("    Primeros 30:")
        for p in pendientes[:30]:
            print(f"      row={p['row']:<5} {p['nombre'][:35]:<36} banco={p['banco'][:15]:<16} estado={p['estado'][:20]:<20} credito={p['credito']}")
        print()
        print("    Resumen por banco:")
        for b, n in Counter(normalizar(p["banco"]) for p in pendientes).most_common():
            print(f"      {b:<20} {n:>3}")
        print("    Resumen por estado:")
        for e, n in Counter(normalizar(p["estado"]) for p in pendientes).most_common():
            print(f"      {e:<30} {n:>3}")

    # ---------- STAGING ESTADO ACTUAL ----------
    print("\n[4] STAGING — estado actual:")
    ws_st = sh.worksheet("STAGING")
    st_all = ws_st.get_all_values()
    print(f"    Filas totales en STAGING (incluye header): {len(st_all)}")
    if st_all:
        st_header = st_all[0]
        print(f"    Header STAGING: {st_header[:10]}... (total {len(st_header)} cols)")
        # Contar cuantas filas NO-header tienen NOMBRE CLIENTE con texto
        body_st = st_all[1:]
        con_nombre = sum(1 for r in body_st if r and str(r[0]).strip())
        print(f"    Filas con NOMBRE CLIENTE != vacio: {con_nombre}")
        if con_nombre > 0:
            print("    Primeras 5 con contenido:")
            cnt = 0
            for j, r in enumerate(body_st, start=2):
                if r and str(r[0]).strip():
                    print(f"      row={j}  nombre={r[0][:35]}")
                    cnt += 1
                    if cnt >= 5:
                        break

    # ---------- COLUMNA AMORTIZACION (si existe) ----------
    print("\n[5] Valores unicos de columnas 'Amortizacion' / 'UVR' / 'Pesos' / 'Moneda' / 'Tipo':")
    for i, h in enumerate(header):
        nh = normalizar(h)
        if any(kw in nh for kw in ("amort", "uvr", "pesos", "moneda", "tipo")):
            letter = col_letter(i + 1)
            vals = Counter(normalizar(row[i]) if i < len(row) else "" for row in body)
            print(f"    col {i} ({letter}): {h!r}")
            for v, n in vals.most_common(15):
                print(f"        {v!r:<30} {n:>5}")

    print("\n" + "=" * 80)
    print("  FIN DIAGNOSTICO")
    print("=" * 80)


if __name__ == "__main__":
    main()

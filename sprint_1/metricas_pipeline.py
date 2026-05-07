#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
metricas_pipeline.py — MejorAhora SAS · 2026-05-07
====================================================
Agrega los logs JSON del pipeline (`_logs/pipeline_davivienda_*.json`) en una
metrica semanal que apoya el criterio "5 dias sin errores antes de escalar a
Bancolombia" (ESTADO_PROYECTO §3 / §7, MASTER_RULES §14.1).

Uso:
    py metricas_pipeline.py                    # ultimos 7 dias, output a stdout
    py metricas_pipeline.py --dias 14          # ventana custom
    py metricas_pipeline.py --out _logs/...    # guarda reporte a archivo
    py metricas_pipeline.py --json             # output JSON estructurado

Genera reporte texto por defecto. JSON util para dashboards externos.
Stdlib only — no requiere instalar nada.

Scheduled task sugerido (semanal lunes 09:00):
    schtasks /create /tn "MejorAhora\\Metricas Semanales" \\
       /tr "py \"C:\\Users\\JOSE A\\Desktop\\ESTUDIOS CLAUDE\\sprint_1\\metricas_pipeline.py\" --out \"C:\\Users\\JOSE A\\Desktop\\ESTUDIOS CLAUDE\\_logs\\metricas_semanal.txt\"" \\
       /sc WEEKLY /d MON /st 09:00 /ru "JOSE A" /f
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
LOGS_DIR = PROJECT_ROOT / "_logs"

# Patron del nombre de archivo: pipeline_davivienda_YYYYMMDD_HHMMSS.json
_RE_LOG = re.compile(r"^pipeline_davivienda_(\d{8})_(\d{6})\.json$")

# Categorias de fallo (string-match en campo "detalle")
CATEGORIAS_FALLO = [
    ("REVISION_MANUAL", ["REVISION_MANUAL", "revision_manual"]),
    ("NO_VIABLE_LEY_546", ["NO_VIABLE_LEY_546"]),
    ("PDF_PROTEGIDO", ["pdf_protegido", "PDF_PROTEGIDO"]),
    ("EXTRACTO_ILEGIBLE", ["EXTRACTO_ILEGIBLE", "ilegible"]),
    ("EXTRACTO_INCOMPLETO", ["EXTRACTO_INCOMPLETO", "incompleto"]),
    ("M1_FAIL", ["M1-FAIL", "m1_fail", "[M1-validar]"]),
    ("DIF_SIMULA_FAIL", ["DIF.SIMULA", "DIF_SIMULA"]),
    ("BANCO_NO_TRABAJADO", ["BANCO_NO_TRABAJADO", "skip_leasing"]),
    ("EXCEPTION", ["exception:", "Exception"]),
    ("OTHER", []),  # bucket por defecto
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Metricas semanales del pipeline Davivienda")
    ap.add_argument("--dias", type=int, default=7, help="Ventana en dias (default 7)")
    ap.add_argument("--out", type=str, default="", help="Guardar reporte a archivo")
    ap.add_argument("--json", action="store_true", help="Output JSON estructurado")
    ap.add_argument("--logs-dir", type=str, default="", help="Override LOGS_DIR")
    return ap.parse_args()


def listar_logs_en_ventana(logs_dir: Path, dias: int, hoy: dt.date | None = None) -> list[Path]:
    """Lista archivos pipeline_davivienda_*.json dentro de los ultimos N dias."""
    if hoy is None:
        hoy = dt.date.today()
    desde = hoy - dt.timedelta(days=dias - 1)
    if not logs_dir.exists():
        return []
    out = []
    for p in logs_dir.iterdir():
        m = _RE_LOG.match(p.name)
        if not m:
            continue
        try:
            fecha = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        if desde <= fecha <= hoy:
            out.append(p)
    return sorted(out)


def categorizar_detalle(detalle: str) -> str:
    """Mapea 'detalle' del registro a una categoria."""
    if not detalle:
        return "OTHER"
    d_low = detalle.lower()
    for nombre, patrones in CATEGORIAS_FALLO:
        if nombre == "OTHER":
            continue
        for pat in patrones:
            if pat.lower() in d_low:
                return nombre
    return "OTHER"


def cargar_resultados(paths: list[Path]) -> list[dict]:
    """Lee JSON files y retorna lista plana con resultados por cliente."""
    todos: list[dict] = []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[metricas] WARN no se pudo leer {p.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, list):
            continue
        m = _RE_LOG.match(p.name)
        if not m:
            continue
        fecha = m.group(1)  # YYYYMMDD
        for r in data:
            if not isinstance(r, dict):
                continue
            r["_fecha_log"] = fecha
            r["_archivo_log"] = p.name
            todos.append(r)
    return todos


def agregar(resultados: list[dict]) -> dict:
    """Agrega metricas globales y por dia."""
    total = len(resultados)
    ok = sum(1 for r in resultados if r.get("ok"))
    fail = total - ok
    cat_counter: Counter[str] = Counter()
    por_dia: dict[str, dict] = defaultdict(lambda: {"total": 0, "ok": 0, "fail": 0, "categorias": Counter()})

    for r in resultados:
        cat = categorizar_detalle(r.get("detalle", "")) if not r.get("ok") else "OK"
        if not r.get("ok"):
            cat_counter[cat] += 1
        d = r.get("_fecha_log", "?")
        por_dia[d]["total"] += 1
        if r.get("ok"):
            por_dia[d]["ok"] += 1
        else:
            por_dia[d]["fail"] += 1
            por_dia[d]["categorias"][cat] += 1

    # Convertir counters a dicts ordenados para serializacion
    por_dia_clean = {}
    for d in sorted(por_dia):
        v = por_dia[d]
        por_dia_clean[d] = {
            "total": v["total"],
            "ok": v["ok"],
            "fail": v["fail"],
            "categorias": dict(v["categorias"]),
        }

    return {
        "total_clientes": total,
        "ok": ok,
        "fail": fail,
        "tasa_exito": (ok / total) if total else 0.0,
        "categorias_fallo": dict(cat_counter),
        "por_dia": por_dia_clean,
    }


def formatear_reporte(metrica: dict, dias: int, paths: list[Path]) -> str:
    fecha_run = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Metricas semanales pipeline Davivienda — {fecha_run}",
        f"# Ventana: ultimos {dias} dias  ·  archivos JSON analizados: {len(paths)}",
        "",
    ]
    if not metrica["total_clientes"]:
        lines.append("(sin datos en la ventana — pipeline no corrio o logs ausentes)")
        return "\n".join(lines)

    tot = metrica["total_clientes"]
    ok = metrica["ok"]
    fail = metrica["fail"]
    pct = metrica["tasa_exito"] * 100

    lines.append(f"Total clientes procesados: {tot}")
    lines.append(f"  OK (Excel generado):     {ok}  ({pct:.1f}%)")
    lines.append(f"  FAIL:                    {fail}  ({100 - pct:.1f}%)")
    lines.append("")

    # Criterio "Cero errores antes de escalar"
    dias_sin_fail = 0
    dias_con_fail = []
    for fecha, v in sorted(metrica["por_dia"].items(), reverse=True):
        if v["fail"] == 0 and v["total"] > 0:
            dias_sin_fail += 1
        elif v["fail"] > 0:
            dias_con_fail.append((fecha, v["fail"]))
            break  # racha de OK se rompe

    lines.append(f"Racha actual sin fallos (mas reciente -> atras): {dias_sin_fail} dia(s)")
    lines.append("Criterio ESTADO §3: 5 dias consecutivos sin errores -> avanzar a Bancolombia")
    if dias_sin_fail >= 5:
        lines.append(f"  -> CRITERIO CUMPLIDO ({dias_sin_fail}/5)")
    else:
        lines.append(f"  -> aun NO ({dias_sin_fail}/5)")
    if dias_con_fail:
        lines.append(f"  Ultimo dia con fallos: {dias_con_fail[0][0]} ({dias_con_fail[0][1]} fallo(s))")
    lines.append("")

    if metrica["categorias_fallo"]:
        lines.append("Categorias de fallo (acumulado en la ventana):")
        for cat, n in sorted(metrica["categorias_fallo"].items(), key=lambda x: -x[1]):
            lines.append(f"  {cat:25s} {n}")
        lines.append("")

    lines.append("Desglose por dia:")
    lines.append(f"  {'Fecha':12s} {'Total':>6s} {'OK':>6s} {'Fail':>6s}  Top categoria fallo")
    for fecha in sorted(metrica["por_dia"]):
        v = metrica["por_dia"][fecha]
        if v["categorias"]:
            top = max(v["categorias"].items(), key=lambda x: x[1])
            top_str = f"{top[0]} ({top[1]})"
        else:
            top_str = "-"
        lines.append(
            f"  {fecha:12s} {v['total']:>6d} {v['ok']:>6d} {v['fail']:>6d}  {top_str}"
        )
    lines.append("")
    lines.append("Fuente de datos:")
    for p in paths:
        lines.append(f"  - _logs/{p.name}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    logs_dir = Path(args.logs_dir).resolve() if args.logs_dir else LOGS_DIR
    paths = listar_logs_en_ventana(logs_dir, args.dias)
    resultados = cargar_resultados(paths)
    metrica = agregar(resultados)

    if args.json:
        out_text = json.dumps(metrica, ensure_ascii=False, indent=2)
    else:
        out_text = formatear_reporte(metrica, args.dias, paths)

    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
        print(f"[metricas] reporte guardado en {args.out}")
    else:
        print(out_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

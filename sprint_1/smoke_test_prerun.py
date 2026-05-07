#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_test_prerun.py — MejorAhora SAS · 2026-05-07
==================================================
Defensa proactiva: chequea preconditions del pipeline ANTES de procesar
pendientes. Si algo falla aqui, el pipeline NO arranca (evita generar 14
EXCEPTION ruidosas por cliente como hubo en 2026-04 a 2026-05 con OAuth
revocado).

Chequeos (en orden, fail-fast):
  1. Imports criticos disponibles (pdfplumber, openpyxl, gspread, google-*)
  2. credentials/sheets_sa.json existe y es JSON valido
  3. credentials/oauth_token.json existe (uploads §4.2)
  4. sprint_1/config.ini existe con [HUBSPOT] token con formato pat-*
  5. PESOS.xlsx hash OK (config_reglas.verify_pesos_template)
  6. test_fase2.py 16/16 PASS (golden suite) — opcional con --skip-tests

Uso:
    py smoke_test_prerun.py                      # full check
    py smoke_test_prerun.py --skip-tests         # sin correr golden
    py smoke_test_prerun.py --json               # output JSON

Exit codes:
    0 — todo OK
    1 — fallas detectadas (ver output)

Integracion sugerida en run_pipeline.bat:
    py sprint_1\\smoke_test_prerun.py >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [pipeline] smoke_test_prerun fallo, abortando >> "%LOG%"
        exit /b 4
    )
"""
from __future__ import annotations

import argparse
import configparser
import importlib
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Modulos runtime que el pipeline necesita
IMPORTS_REQUIRED = [
    "pdfplumber",
    "openpyxl",
    "gspread",
    "google.auth",
    "googleapiclient.discovery",
]

# Vertex AI es opcional (fallback Gemini); si no esta, log pero no falla
IMPORTS_OPTIONAL = [
    "google.cloud.aiplatform",
]


def check_imports() -> list[str]:
    issues = []
    for mod in IMPORTS_REQUIRED:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            issues.append(f"IMPORT REQUIRED falla: {mod} ({exc})")
    return issues


def check_optional_imports() -> list[str]:
    warnings = []
    for mod in IMPORTS_OPTIONAL:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            warnings.append(f"opcional ausente: {mod} ({exc}) — Vertex Vision fallback no disponible")
    return warnings


def check_credentials() -> list[str]:
    issues = []
    sa_path = PROJECT_ROOT / "credentials" / "sheets_sa.json"
    if not sa_path.exists():
        issues.append(f"credenciales SA ausentes: {sa_path}")
    else:
        try:
            sa_data = json.loads(sa_path.read_text(encoding="utf-8"))
            if "client_email" not in sa_data or "private_key" not in sa_data:
                issues.append(f"sheets_sa.json sin campos esperados (client_email/private_key)")
        except Exception as exc:
            issues.append(f"sheets_sa.json no es JSON valido: {exc}")

    oauth_path = PROJECT_ROOT / "credentials" / "oauth_token.json"
    if not oauth_path.exists():
        issues.append(
            f"oauth_token.json ausente: {oauth_path}. "
            f"El pipeline NO puede subir a Drive §4.2 sin OAuth user. "
            f"Correr `py drive_oauth_setup.py` (MASTER_RULES §16.6)."
        )
    return issues


def check_hubspot_config() -> list[str]:
    issues = []
    cfg_path = SCRIPT_DIR / "config.ini"
    if not cfg_path.exists():
        issues.append(f"config.ini ausente: {cfg_path}")
        return issues
    cfg = configparser.ConfigParser()
    try:
        cfg.read(cfg_path, encoding="utf-8")
    except Exception as exc:
        issues.append(f"config.ini ilegible: {exc}")
        return issues
    if "HUBSPOT" not in cfg:
        issues.append("config.ini sin seccion [HUBSPOT]")
        return issues
    token = cfg["HUBSPOT"].get("token", "").strip()
    if not token:
        issues.append("[HUBSPOT] token vacio")
    elif not token.startswith("pat-"):
        issues.append(f"[HUBSPOT] token con formato invalido (esperado 'pat-*', got {token[:8]}...)")
    return issues


def check_pesos_template() -> list[str]:
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from config_reglas import verify_pesos_template
    except Exception as exc:
        return [f"config_reglas.py no importable: {exc}"]
    ok, msg = verify_pesos_template(PROJECT_ROOT)
    if not ok:
        return [f"PESOS.xlsx integridad: {msg}"]
    return []


def check_golden_suite() -> list[str]:
    """Corre `py sprint_1/test_fase2.py` y reporta si NO pasa 16/16."""
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "test_fase2.py")],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return ["test_fase2.py timeout (>120s)"]
    except Exception as exc:
        return [f"test_fase2.py no pudo ejecutarse: {exc}"]
    if result.returncode != 0:
        tail = (result.stdout or "")[-500:]
        return [f"test_fase2.py exit={result.returncode}. Tail: {tail!r}"]
    if "TODOS LOS TESTS PASARON" not in result.stdout:
        return ["test_fase2.py corrio pero no marco 'TODOS LOS TESTS PASARON'"]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-tests", action="store_true",
                    help="Omitir test_fase2.py (mas rapido)")
    ap.add_argument("--json", action="store_true",
                    help="Output JSON estructurado")
    args = ap.parse_args()

    checks = [
        ("imports_required", check_imports),
        ("credentials", check_credentials),
        ("hubspot_config", check_hubspot_config),
        ("pesos_template", check_pesos_template),
    ]
    if not args.skip_tests:
        checks.append(("golden_suite", check_golden_suite))

    results: dict[str, list[str]] = {}
    for name, fn in checks:
        try:
            results[name] = fn()
        except Exception as exc:
            results[name] = [f"check abortado: {exc}"]

    warnings = check_optional_imports()

    total_issues = sum(len(v) for v in results.values())

    if args.json:
        print(json.dumps({
            "issues": results,
            "warnings": warnings,
            "total_issues": total_issues,
            "ok": total_issues == 0,
        }, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("SMOKE TEST PRE-PIPELINE — MejorAhora")
        print("=" * 60)
        for name, issues in results.items():
            status = "OK" if not issues else f"FAIL ({len(issues)})"
            print(f"  [{status}] {name}")
            for i in issues:
                print(f"      - {i}")
        if warnings:
            print("  WARNINGS:")
            for w in warnings:
                print(f"      - {w}")
        print("=" * 60)
        if total_issues == 0:
            print("  RESULT: OK — pipeline puede arrancar")
        else:
            print(f"  RESULT: FAIL — {total_issues} problema(s). NO arrancar pipeline.")

    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

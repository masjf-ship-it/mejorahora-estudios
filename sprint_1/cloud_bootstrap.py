# -*- coding: utf-8 -*-
"""
cloud_bootstrap.py — MejorAhora SAS · 2026-05-07
==================================================
Bootstrap de credenciales desde environment variables para Cloud Routines.

Comportamiento:
  - LOCAL (Windows con credentials/ en disco): no hace nada, los archivos
    ya existen y los scripts los leen directo. Cero impacto.
  - CLOUD (Linux Anthropic VM, sin credentials/): si las env vars estan
    definidas, las materializa como archivos en las rutas esperadas
    (credentials/sheets_sa.json, credentials/oauth_token.json,
    sprint_1/config.ini). Permite que el pipeline corra sin cambios.

Env vars esperadas en Cloud (config en claude.ai/code → entorno):
  MEJORAHORA_SA_JSON              JSON completo del Service Account
  MEJORAHORA_OAUTH_TOKEN_JSON     JSON completo del oauth_token.json
  MEJORAHORA_HUBSPOT_TOKEN        Token HubSpot 'pat-*'

Uso:
  from cloud_bootstrap import ensure_credentials_from_env
  ensure_credentials_from_env()  # llamar al inicio de main()
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
SA_PATH = CREDENTIALS_DIR / "sheets_sa.json"
OAUTH_PATH = CREDENTIALS_DIR / "oauth_token.json"
CONFIG_INI_PATH = SCRIPT_DIR / "config.ini"


def is_cloud_env() -> bool:
    """True si estamos corriendo en una Cloud Routine de Claude Code."""
    return os.environ.get("CLAUDE_CODE_REMOTE", "").lower() == "true"


def ensure_credentials_from_env(force: bool = False) -> dict:
    """Materializa credenciales desde env vars si los archivos no existen.

    Args:
        force: si True, sobreescribe archivos existentes con env vars
               (util para rotacion de creds en cloud).

    Returns:
        dict con summary: {'sa': bool, 'oauth': bool, 'hubspot': bool, 'cloud': bool}
        cada bool indica si se escribio el archivo en este run.
    """
    summary = {"sa": False, "oauth": False, "hubspot": False, "cloud": is_cloud_env()}

    # Crear credentials/ si no existe (cloud)
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    # Service Account JSON
    sa_env = os.environ.get("MEJORAHORA_SA_JSON", "").strip()
    if sa_env and (force or not SA_PATH.exists()):
        try:
            # Validar que sea JSON valido antes de escribir
            json.loads(sa_env)
            SA_PATH.write_text(sa_env, encoding="utf-8")
            summary["sa"] = True
        except json.JSONDecodeError as exc:
            print(f"[cloud_bootstrap] WARN: MEJORAHORA_SA_JSON no es JSON valido: {exc}")

    # OAuth token JSON
    oauth_env = os.environ.get("MEJORAHORA_OAUTH_TOKEN_JSON", "").strip()
    if oauth_env and (force or not OAUTH_PATH.exists()):
        try:
            json.loads(oauth_env)
            OAUTH_PATH.write_text(oauth_env, encoding="utf-8")
            summary["oauth"] = True
        except json.JSONDecodeError as exc:
            print(f"[cloud_bootstrap] WARN: MEJORAHORA_OAUTH_TOKEN_JSON no es JSON valido: {exc}")

    # HubSpot token (formato config.ini)
    hubspot_env = os.environ.get("MEJORAHORA_HUBSPOT_TOKEN", "").strip()
    if hubspot_env and (force or not CONFIG_INI_PATH.exists()):
        if not hubspot_env.startswith("pat-"):
            print(f"[cloud_bootstrap] WARN: MEJORAHORA_HUBSPOT_TOKEN no empieza con 'pat-': {hubspot_env[:8]}...")
        # Formato esperado por hubspot_client.from_config()
        config_content = (
            "[HUBSPOT]\n"
            f"token = {hubspot_env}\n"
        )
        CONFIG_INI_PATH.write_text(config_content, encoding="utf-8")
        summary["hubspot"] = True

    return summary


if __name__ == "__main__":
    # Smoke test manual
    import sys
    s = ensure_credentials_from_env()
    print(f"[cloud_bootstrap] cloud={s['cloud']} sa_written={s['sa']} "
          f"oauth_written={s['oauth']} hubspot_written={s['hubspot']}")
    # Verificar que los archivos esten presentes (los originales o los recien creados)
    missing = []
    if not SA_PATH.exists():
        missing.append(str(SA_PATH))
    if not OAUTH_PATH.exists():
        missing.append(str(OAUTH_PATH))
    if not CONFIG_INI_PATH.exists():
        missing.append(str(CONFIG_INI_PATH))
    if missing:
        print(f"[cloud_bootstrap] FAIL: archivos faltantes:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)
    print("[cloud_bootstrap] OK: todas las credenciales presentes")
    sys.exit(0)

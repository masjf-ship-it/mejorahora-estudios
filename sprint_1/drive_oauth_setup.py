# -*- coding: utf-8 -*-
"""
drive_oauth_setup.py — MejorAhora SAS
======================================
One-time setup: ejecuta consent flow OAuth, guarda refresh_token persistente
en `credentials/oauth_token.json`. Correr una sola vez; despues el pipeline
usa el token automaticamente.

Usa InstalledAppFlow (google-auth-oauthlib) con flujo de codigo por copia
manual (no requiere servidor local, funciona en cualquier entorno).

Prerrequisitos:
  1) pip install google-auth-oauthlib
  2) credentials/oauth_client.json creado (Desktop app del GCP Console)
  3) Usuario agregado como "Usuario de prueba" en pantalla de consentimiento
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OAUTH_CLIENT = PROJECT_ROOT / "credentials" / "oauth_client.json"
OAUTH_TOKEN = PROJECT_ROOT / "credentials" / "oauth_token.json"

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main():
    if not OAUTH_CLIENT.exists():
        print(f"ERROR: no existe {OAUTH_CLIENT}")
        print("Debe existir el JSON con client_id y client_secret del GCP Console")
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: falta instalar google-auth-oauthlib")
        print("  py -m pip install google-auth-oauthlib")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CLIENT), SCOPES)
    # Usa servidor local efimero - abre navegador automaticamente
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        authorization_prompt_message=(
            "Se abrira tu navegador. Loguea con reducciondecreditos2@gmail.com "
            "(dueno del folder Drive §4.2) y acepta el acceso.\n"
            "Si te dice 'App no verificada': click en Avanzado > Ir a MejorAhora Pipeline (no seguro)."
        ),
        success_message="Listo. Puedes cerrar esta pestana y volver al terminal.",
        access_type="offline",
    )
    OAUTH_TOKEN.write_text(creds.to_json(), encoding="utf-8")
    print(f"[OK] Token guardado en {OAUTH_TOKEN}")

    # Smoke test inmediato
    from googleapiclient.discovery import build
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    about = drive.about().get(fields="user(emailAddress)").execute()
    print(f"[OK] Autenticado como: {about['user']['emailAddress']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

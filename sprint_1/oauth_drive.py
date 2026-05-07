# -*- coding: utf-8 -*-
"""
oauth_drive.py — MejorAhora SAS
================================
OAuth user delegation para Google Drive. Resuelve el 403 storageQuotaExceeded
del Service Account (que no puede crear archivos en MyDrive de una cuenta
personal de Gmail).

Arquitectura hibrida:
  - Service Account: Sheets (STAGING, BD) + Drive reads (descarga extractos)
  - OAuth user:      Drive uploads (crea Excel en §4.2 bajo el dueño humano)

Archivos:
  credentials/oauth_client.json  (client_id + client_secret, del GCP Console)
  credentials/oauth_token.json   (refresh_token, generado al correr consent)

Uso:
  from oauth_drive import get_oauth_drive
  drive_user = get_oauth_drive()
  drive_user.files().create(...)   # uploads como reducciondecreditos2@gmail.com
"""
from __future__ import annotations

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OAUTH_CLIENT = PROJECT_ROOT / "credentials" / "oauth_client.json"
OAUTH_TOKEN = PROJECT_ROOT / "credentials" / "oauth_token.json"

SCOPES_OAUTH = ["https://www.googleapis.com/auth/drive.file"]


def _load_creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not OAUTH_TOKEN.exists():
        raise FileNotFoundError(
            f"No existe {OAUTH_TOKEN}. Corre primero: py drive_oauth_setup.py"
        )
    creds = Credentials.from_authorized_user_file(str(OAUTH_TOKEN), SCOPES_OAUTH)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            OAUTH_TOKEN.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError(
                "Token OAuth invalido y sin refresh_token. Re-corre drive_oauth_setup.py"
            )
    return creds


def get_oauth_drive():
    """Retorna un Drive v3 service autenticado con OAuth user (no SA)."""
    from googleapiclient.discovery import build
    creds = _load_creds()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_to_folder_oauth(drive, local_path: Path, folder_id: str,
                            nombre_destino: str = None,
                            mime_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") -> dict:
    """Sube archivo a Drive usando el drive OAuth user (propiedad del humano)."""
    from googleapiclient.http import MediaFileUpload

    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"No existe archivo local {local_path}")

    body = {
        "name": nombre_destino or local_path.name,
        "parents": [folder_id],
    }
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
    return drive.files().create(
        body=body,
        media_body=media,
        fields="id, name, webViewLink",
        supportsAllDrives=True,
    ).execute()


if __name__ == "__main__":
    import sys
    try:
        drive = get_oauth_drive()
        about = drive.about().get(fields="user(emailAddress)").execute()
        print(f"[oauth_drive] OK. Autenticado como: {about['user']['emailAddress']}")
    except Exception as e:
        print(f"[oauth_drive] ERROR: {e}")
        sys.exit(1)

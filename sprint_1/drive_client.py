# -*- coding: utf-8 -*-
"""
drive_client.py — MejorAhora SAS
=================================
Cliente minimo para Google Drive + Sheets via Service Account.

Responsabilidades:
  - Autenticar con `credentials/sheets_sa.json`
  - Buscar carpeta del cliente en Drive §4.1 (folder extractos, READ-ONLY)
  - Descargar PDF extracto a path temporal local
  - Subir Excel generado a Drive §4.2 (folder analistas)

Scopes usados:
  - https://www.googleapis.com/auth/spreadsheets  (gspread)
  - https://www.googleapis.com/auth/drive         (search+download+upload)

Folders canonicos (MASTER_RULES §4):
  §4.1 READ-ONLY extractos: 17hN5TDiQ3Ozop-xT6g4OYAyQrZkZT0os
  §4.2 WRITE analistas:     1UVsQtyzQHEpfRlcjUrq8gBsXgEqABoym

BD unica (MASTER_RULES §3):
  1_9FUAo8cSrLDWAkJlNoy29Cmyh9ojXwnW6zbvhGsESA
"""
from __future__ import annotations

import io
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CREDS_PATH = PROJECT_ROOT / "credentials" / "sheets_sa.json"

# Folders y Sheet canonicos — fuente unica config_reglas.py (MASTER_RULES §4 + §3.1).
# 2026-05-07: deduplicado de literals locales que estaban tambien aqui.
from config_reglas import (  # noqa: E402
    DRIVE_FOLDER_EXTRACTOS_RO,
    DRIVE_FOLDER_ANALISTAS_RW,
    SHEET_BD_ID as SHEET_ID_BD,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ============================================================
# AUTH
# ============================================================

def get_clients():
    """Retorna (gspread_client, drive_v3_service).

    Lanza FileNotFoundError si `credentials/sheets_sa.json` no existe.
    """
    if not CREDS_PATH.exists():
        raise FileNotFoundError(
            f"No se encontro service account key en {CREDS_PATH}. "
            "Descargar desde GCP y colocar en `credentials/sheets_sa.json`."
        )

    from google.oauth2.service_account import Credentials
    import gspread
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_file(str(CREDS_PATH), scopes=SCOPES)
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return gc, drive


# ============================================================
# NORMALIZACION DE NOMBRES
# ============================================================

def _strip_accents(s: str) -> str:
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize_nombre(s: str) -> str:
    """Normaliza nombre para matching: uppercase, sin tildes, espacios simples."""
    s = _strip_accents((s or "").strip().upper())
    s = re.sub(r"\s+", " ", s)
    return s


def _escape_q(s: str) -> str:
    """Escapa valor para query Drive API v3."""
    return (s or "").replace("\\", "\\\\").replace("'", "\\'")


# ============================================================
# BUSQUEDA DE EXTRACTO
# ============================================================

def buscar_carpeta_cliente(drive, nombre_cliente: str,
                            parent_folder_id: str = DRIVE_FOLDER_EXTRACTOS_RO) -> Optional[dict]:
    """Busca carpeta del cliente en Drive §4.1 por nombre (matching tolerante).

    Estrategia:
      1. Match exacto por nombre normalizado (MAYUSCULAS sin tildes)
      2. Si no match, fallback `name contains` con primeros 2 tokens

    Retorna: {'id', 'name'} o None
    """
    if not nombre_cliente:
        return None

    target_norm = _normalize_nombre(nombre_cliente)

    # Listar carpetas hijas del parent
    q = (
        f"'{parent_folder_id}' in parents "
        "and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )

    page_token = None
    candidates_contains = []
    while True:
        resp = drive.files().list(
            q=q,
            fields="nextPageToken, files(id, name)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        for f in resp.get("files", []):
            name_norm = _normalize_nombre(f.get("name", ""))
            if name_norm == target_norm:
                return {"id": f["id"], "name": f["name"]}
            # Fallback candidato: folder contiene todos los tokens del target
            tokens = [t for t in target_norm.split() if len(t) >= 3]
            if tokens and all(t in name_norm for t in tokens):
                candidates_contains.append({"id": f["id"], "name": f["name"]})

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # Si hay exactamente un candidato por contiene-tokens, devolverlo
    if len(candidates_contains) == 1:
        return candidates_contains[0]
    # Si hay multiples, retornar None para que el orquestador decida (log + skip)
    return None


def buscar_pdf_extracto_en_carpeta(drive, folder_id: str) -> Optional[dict]:
    """Busca el PDF de extracto dentro de la carpeta del cliente.

    Preferencia:
      1. Nombre contiene 'EXTRACTO' (case-insensitive)
      2. Unico PDF en la carpeta

    Retorna: {'id', 'name', 'size'} o None
    """
    q = (
        f"'{folder_id}' in parents "
        "and mimeType='application/pdf' "
        "and trashed=false"
    )
    resp = drive.files().list(
        q=q,
        fields="files(id, name, size, modifiedTime)",
        pageSize=100,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    if not files:
        return None

    # Preferir PDFs con "EXTRACTO" en el nombre
    con_extracto = [f for f in files if "EXTRACTO" in f["name"].upper()]
    if con_extracto:
        # Si hay varios, tomar el mas reciente
        con_extracto.sort(key=lambda f: f.get("modifiedTime", ""), reverse=True)
        return con_extracto[0]

    # Si solo hay un PDF, usarlo
    if len(files) == 1:
        return files[0]

    # Varios PDFs sin "EXTRACTO" -> ambiguo
    return None


def buscar_extracto_cliente(drive, nombre_cliente: str) -> Optional[dict]:
    """Convenience: busca carpeta + PDF en un solo paso.

    Retorna: {'folder_id', 'folder_name', 'pdf_id', 'pdf_name'} o None.
    """
    folder = buscar_carpeta_cliente(drive, nombre_cliente)
    if not folder:
        return None
    pdf = buscar_pdf_extracto_en_carpeta(drive, folder["id"])
    if not pdf:
        return None
    return {
        "folder_id": folder["id"],
        "folder_name": folder["name"],
        "pdf_id": pdf["id"],
        "pdf_name": pdf["name"],
    }


# ============================================================
# DESCARGA
# ============================================================

def descargar_pdf(drive, file_id: str, dest_path: Path) -> Path:
    """Descarga PDF a dest_path. Retorna Path del archivo descargado."""
    from googleapiclient.http import MediaIoBaseDownload

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    request = drive.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


# ============================================================
# UPLOAD
# ============================================================

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def upload_to_folder(drive, local_path: Path, folder_id: str = DRIVE_FOLDER_ANALISTAS_RW,
                      nombre_destino: Optional[str] = None,
                      mime_type: str = MIME_XLSX,
                      reemplazar_existente: bool = True) -> dict:
    """Sube archivo local a carpeta destino en Drive.

    2026-05-15 (Jose feedback caso 2 Excels mismo credito): por defecto, si ya
    existe un archivo con el mismo nombre en `folder_id`, reemplaza su contenido
    (drive.files().update) en vez de crear duplicado. Para forzar duplicados
    explicitamente, pasar `reemplazar_existente=False`.

    Esto elimina el problema de "2 Excels del mismo cliente con fechas distintas"
    que pasaba cuando el pipeline corre 2x el mismo dia (manual + programado).
    Combinado con el filename que incluye credito_corto, multiples creditos del
    mismo cliente conviven correctamente y solo se reemplaza el del MISMO credito.

    Retorna: {'id', 'name', 'webViewLink'}
    """
    from googleapiclient.http import MediaFileUpload

    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"No existe archivo local {local_path}")

    name_final = nombre_destino or local_path.name

    if reemplazar_existente:
        # Buscar archivo con mismo nombre en folder. Escapar nombre para query.
        name_q = name_final.replace("\\", "\\\\").replace("'", "\\'")
        q = (
            f"'{folder_id}' in parents "
            f"and name='{name_q}' "
            "and trashed=false"
        )
        existing = drive.files().list(
            q=q,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute().get("files", [])
        if existing:
            file_id = existing[0]["id"]
            media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
            updated = drive.files().update(
                fileId=file_id,
                media_body=media,
                fields="id, name, webViewLink",
                supportsAllDrives=True,
            ).execute()
            return updated

    # Crear nuevo (no existia previo o reemplazar_existente=False)
    body = {
        "name": name_final,
        "parents": [folder_id],
    }
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
    created = drive.files().create(
        body=body,
        media_body=media,
        fields="id, name, webViewLink",
        supportsAllDrives=True,
    ).execute()
    return created


# ============================================================
# SMOKE TEST
# ============================================================

def _smoke_test(nombre_cliente: str):
    gc, drive = get_clients()
    print(f"[drive_client] SA cargado OK, scopes={SCOPES}")
    print(f"[drive_client] Buscando carpeta de: {nombre_cliente}")
    info = buscar_extracto_cliente(drive, nombre_cliente)
    if not info:
        print("  -> NO ENCONTRADO")
        return 1
    print(f"  folder: {info['folder_name']} ({info['folder_id']})")
    print(f"  pdf:    {info['pdf_name']} ({info['pdf_id']})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python drive_client.py '<NOMBRE CLIENTE>'")
        sys.exit(2)
    sys.exit(_smoke_test(sys.argv[1]))

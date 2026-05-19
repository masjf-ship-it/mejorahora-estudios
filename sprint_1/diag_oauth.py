# -*- coding: utf-8 -*-
"""
diag_oauth.py — MejorAhora SAS
================================
Diagnostico de OAuth Drive. Corre con:
    py diag_oauth.py > diag_oauth.txt 2>&1
Luego pega diag_oauth.txt a Claude.
"""
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OAUTH_TOKEN = PROJECT_ROOT / "credentials" / "oauth_token.json"
OAUTH_CLIENT = PROJECT_ROOT / "credentials" / "oauth_client.json"

# 2026-05-16 (Audit N): single-source. El folder ID y el scope estaban
# hardcoded aqui Y en config_reglas/oauth_drive (riesgo: el diagnostico
# revisaba el folder equivocado si el canonico cambiaba; MASTER_RULES §8.15
# + higiene de IDs §3.4/§17.12). Ahora se importan de la fuente unica.
sys.path.insert(0, str(SCRIPT_DIR))
from config_reglas import DRIVE_FOLDER_ANALISTAS_RW
from oauth_drive import SCOPES_OAUTH

print("=" * 60)
print("DIAGNOSTICO OAuth Drive — MejorAhora SAS")
print("=" * 60)

# PASO 1: Archivos
print("\n[1] Archivos de credenciales:")
print(f"  oauth_token.json  : {'OK' if OAUTH_TOKEN.exists() else 'FALTA'} ({OAUTH_TOKEN})")
print(f"  oauth_client.json : {'OK' if OAUTH_CLIENT.exists() else 'FALTA'} ({OAUTH_CLIENT})")

# PASO 2: Leer token
print("\n[2] Contenido del token:")
try:
    import json
    token_data = json.loads(OAUTH_TOKEN.read_text(encoding="utf-8"))
    print(f"  expiry         : {token_data.get('expiry', 'NO ENCONTRADO')}")
    print(f"  refresh_token  : {'SI (len=' + str(len(token_data.get('refresh_token','') or '')) + ')' if token_data.get('refresh_token') else 'NO'}")
    print(f"  scopes         : {token_data.get('scopes', [])}")
    print(f"  client_id      : {(token_data.get('client_id','')[:20] + '...') if token_data.get('client_id') else 'NO'}")
except Exception as e:
    print(f"  ERROR leyendo token: {e}")
    sys.exit(1)

# PASO 3: Import google.oauth2
print("\n[3] Importando google.oauth2.credentials:")
try:
    from google.oauth2.credentials import Credentials
    print("  OK")
except ImportError as e:
    print(f"  FALTA: {e}")
    print("  Solucion: pip install google-auth")
    sys.exit(1)

# PASO 4: Import google.auth.transport.requests
print("\n[4] Importando google.auth.transport.requests:")
try:
    from google.auth.transport.requests import Request
    print("  OK")
except ImportError as e:
    print(f"  FALTA: {e}")
    print("  Solucion: pip install google-auth requests")
    sys.exit(1)

# PASO 5: Cargar credenciales
print("\n[5] Cargando Credentials desde archivo:")
try:
    creds = Credentials.from_authorized_user_file(str(OAUTH_TOKEN), SCOPES_OAUTH)
    print(f"  valid   : {creds.valid}")
    print(f"  expired : {creds.expired}")
    print(f"  has_refresh_token: {bool(creds.refresh_token)}")
except Exception as e:
    print(f"  ERROR: {e}")
    sys.exit(1)

# PASO 6: Refresh si expirado
if not creds.valid:
    print("\n[6] Token expirado. Intentando refresh...")
    try:
        creds.refresh(Request())
        print("  REFRESH OK")
        print(f"  nuevo expiry: {creds.expiry}")
        # Guardar token renovado
        OAUTH_TOKEN.write_text(creds.to_json(), encoding="utf-8")
        print("  Token guardado en disco.")
    except Exception as e:
        print(f"  REFRESH FALLO: {e}")
        print("\n  CAUSA PROBABLE: el cliente OAuth fue revocado o no tiene permiso.")
        print("  SOLUCION: correr drive_oauth_setup.py para re-autenticar.")
        sys.exit(1)
else:
    print("\n[6] Token valido, no necesita refresh.")

# PASO 7: Import googleapiclient
print("\n[7] Importando googleapiclient.discovery:")
try:
    from googleapiclient.discovery import build
    print("  OK")
except ImportError as e:
    print(f"  FALTA: {e}")
    print("  Solucion: pip install google-api-python-client")
    sys.exit(1)

# PASO 8: Build Drive service
print("\n[8] Construyendo Drive service OAuth:")
try:
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    print("  OK")
except Exception as e:
    print(f"  ERROR: {e}")
    sys.exit(1)

# PASO 9: Verificar identidad
print("\n[9] Verificando identidad autenticada:")
try:
    about = drive.about().get(fields="user(emailAddress,displayName)").execute()
    user = about.get("user", {})
    print(f"  email        : {user.get('emailAddress')}")
    print(f"  displayName  : {user.get('displayName')}")
except Exception as e:
    print(f"  ERROR: {e}")
    sys.exit(1)

# PASO 10: Verificar acceso al folder analistas
print("\n[10] Verificando acceso al folder analistas (§4.2):")
try:
    resp = drive.files().list(
        q=f"'{DRIVE_FOLDER_ANALISTAS_RW}' in parents and trashed=false",
        fields="files(id,name)",
        pageSize=5,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    print(f"  Acceso OK — {len(files)} archivo(s) visibles (mostrando max 5)")
    for f in files[:5]:
        print(f"    - {f['name']}")
except Exception as e:
    print(f"  ERROR accediendo folder: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("RESULTADO: OAuth Drive OPERATIVO")
print("El pipeline puede subir a Drive como usuario humano.")
print("=" * 60)

#!/usr/bin/env bash
# ============================================================
# MejorAhora — Pipeline Multi-Banco (espejo Linux de run_pipeline.bat)
# Para ejecucion en Cloud Routines (Anthropic) o cualquier Linux.
# Corre secuencialmente:
#   PASO 0    smoke_test
#   PASO 1a   REGISTROS -> STAGING Davivienda
#   PASO 1b   REGISTROS -> STAGING Bancolombia (2026-05-15)
#   PASO 2a   pipeline_davivienda
#   PASO 2b   pipeline_bancolombia (2026-05-15)
# Logs: _logs/scheduled_YYYYMMDD.txt (MASTER_RULES §18.4)
# ============================================================
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="$BASE/_logs"
mkdir -p "$LOGDIR"

# ---------------------------------------------------------
# SSL/TLS — Cloud Routines tienen proxy TLS de Anthropic con CA propia.
# httplib2 lee su CA bundle al IMPORT desde HTTPLIB2_CA_CERTS env var,
# por eso lo seteamos AQUI antes de cualquier python.
# (cloud_bootstrap.py tambien lo setea, redundante pero defensivo.)
# ---------------------------------------------------------
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && [ -f /etc/ssl/certs/ca-certificates.crt ]; then
  export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
  export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
  export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
  export HTTPLIB2_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
fi

STAMP=$(date +%Y%m%d)
LOG="$LOGDIR/scheduled_${STAMP}.txt"
TS() { date +"%Y-%m-%d %H:%M:%S"; }

{
  echo ""
  echo "===================================================="
  echo "[$(TS)] INICIO pipeline Davivienda (cloud/linux)"
  echo "===================================================="
} >> "$LOG"

# ---------------------------------------------------------
# PASO -1: pip install (en Cloud Routines el setup script
# corre antes del clone del repo y no encuentra requirements.txt,
# por eso lo hacemos aqui despues del clone).
#
# --break-system-packages: PEP 668 / Debian "externally managed env"
# requiere este flag para instalar sobre paquetes del sistema en el
# container de Anthropic Cloud Routines. Sin esto pip aborta con
# "error: externally-managed-environment" o conflicto packaging RECORD.
# En Windows (run_pipeline.bat) este flag no aplica.
# ---------------------------------------------------------
echo "[$(TS)] PASO -1: pip install -r sprint_1/requirements.txt" >> "$LOG"
# --break-system-packages: PEP 668 (Debian externally-managed)
# --ignore-installed: el sistema tiene 'packaging' como dpkg y no puede desinstalarlo
#   (RECORD ausente); con --ignore-installed pip omite el uninstall step.
pip install --quiet --break-system-packages --ignore-installed -r "$BASE/sprint_1/requirements.txt" >> "$LOG" 2>&1
RC_PIP=$?
echo "[$(TS)] PASO -1 exit=$RC_PIP" >> "$LOG"
if [ $RC_PIP -ne 0 ]; then
  echo "[$(TS)] ABORT: pip install fallo, no se puede ejecutar pipeline" >> "$LOG"
  exit 5
fi

cd "$BASE/sprint_1"

# ---------------------------------------------------------
# PASO 0: Smoke test pre-pipeline
# ---------------------------------------------------------
echo "[$(TS)] PASO 0: smoke_test_prerun --skip-tests" >> "$LOG"
python smoke_test_prerun.py --skip-tests >> "$LOG" 2>&1
RC0=$?
echo "[$(TS)] PASO 0 exit=$RC0" >> "$LOG"
if [ $RC0 -ne 0 ]; then
  echo "[$(TS)] ABORT: smoke_test fallo, no se ejecutan PASO 1 ni 2" >> "$LOG"
  exit 4
fi

echo "" >> "$LOG"

# ---------------------------------------------------------
# PASO 1a: REGISTROS -> STAGING Davivienda (con dedup)
# ---------------------------------------------------------
echo "[$(TS)] PASO 1a: listar_pendientes_hoy --banco davivienda" >> "$LOG"
python listar_pendientes_hoy.py --banco davivienda >> "$LOG" 2>&1
RC1A=$?
echo "[$(TS)] PASO 1a exit=$RC1A" >> "$LOG"

echo "" >> "$LOG"

# ---------------------------------------------------------
# PASO 1b: REGISTROS -> STAGING Bancolombia (con dedup) — 2026-05-15
# Procesa pendientes Bancolombia en paralelo. Mismo Sheets, mismo dedup logic.
# Si Davivienda falla, Bancolombia sigue corriendo (son independientes).
# ---------------------------------------------------------
echo "[$(TS)] PASO 1b: listar_pendientes_hoy --banco bancolombia" >> "$LOG"
python listar_pendientes_hoy.py --banco bancolombia >> "$LOG" 2>&1
RC1B=$?
echo "[$(TS)] PASO 1b exit=$RC1B" >> "$LOG"

echo "" >> "$LOG"

# ---------------------------------------------------------
# PASO 2a: pipeline E2E Davivienda
#   Hipotecario (570/571) y Leasing (600) procesan iguales (R-DVV-09)
# ---------------------------------------------------------
echo "[$(TS)] PASO 2a: pipeline_davivienda" >> "$LOG"
python pipeline_davivienda.py >> "$LOG" 2>&1
RC2A=$?
echo "[$(TS)] PASO 2a exit=$RC2A" >> "$LOG"

echo "" >> "$LOG"

# ---------------------------------------------------------
# PASO 2b: pipeline E2E Bancolombia — 2026-05-15
# PDFs Bancolombia vienen protegidos por contraseña (cedula del titular).
# El pipeline pasa cedula_fallback de STAGING al extractor (pdfplumber+Gemini).
# Corre AUN SI Davivienda fallo (procesos independientes en runtime/Sheets).
# ---------------------------------------------------------
echo "[$(TS)] PASO 2b: pipeline_bancolombia" >> "$LOG"
python pipeline_bancolombia.py >> "$LOG" 2>&1
RC2B=$?
echo "[$(TS)] PASO 2b exit=$RC2B" >> "$LOG"

{
  echo ""
  echo "[$(TS)] FIN pipeline PASO0=$RC0 PASO1a=$RC1A PASO1b=$RC1B PASO2a=$RC2A PASO2b=$RC2B"
} >> "$LOG"

# Exit code combinado: bitwise OR -> falla si CUALQUIERA de los dos pipelines fallo.
# RC2A=0 RC2B=0 -> 0 (todo OK)
# RC2A=1 RC2B=0 -> 1 (Davivienda fallo, Bancolombia OK)
# RC2A=0 RC2B=2 -> 2 (Davivienda OK, Bancolombia fallo)
# RC2A=1 RC2B=2 -> 3 (ambos fallaron)
exit $((RC2A | RC2B))

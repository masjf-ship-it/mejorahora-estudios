#!/usr/bin/env bash
# ============================================================
# MejorAhora — Pipeline Davivienda (espejo Linux de run_pipeline.bat)
# Para ejecucion en Cloud Routines (Anthropic) o cualquier Linux.
# Corre: PASO 0 smoke_test → PASO 1 listar_pendientes → PASO 2 pipeline.
# Logs: _logs/scheduled_YYYYMMDD.txt (MASTER_RULES §18.4)
# ============================================================
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="$BASE/_logs"
mkdir -p "$LOGDIR"

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
pip install --quiet --break-system-packages -r "$BASE/sprint_1/requirements.txt" >> "$LOG" 2>&1
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
# PASO 1: REGISTROS -> STAGING (con dedup)
# ---------------------------------------------------------
echo "[$(TS)] PASO 1: listar_pendientes_hoy --banco davivienda" >> "$LOG"
python listar_pendientes_hoy.py --banco davivienda >> "$LOG" 2>&1
RC1=$?
echo "[$(TS)] PASO 1 exit=$RC1" >> "$LOG"

echo "" >> "$LOG"

# ---------------------------------------------------------
# PASO 2: pipeline E2E
#   Hipotecario (570/571) y Leasing (600) procesan iguales (R-DVV-09)
# ---------------------------------------------------------
echo "[$(TS)] PASO 2: pipeline_davivienda" >> "$LOG"
python pipeline_davivienda.py >> "$LOG" 2>&1
RC2=$?

{
  echo ""
  echo "[$(TS)] FIN pipeline PASO0=$RC0 PASO1=$RC1 PASO2=$RC2"
} >> "$LOG"

exit $RC2

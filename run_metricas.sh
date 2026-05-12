#!/usr/bin/env bash
# ============================================================
# MejorAhora — Metricas semanales (wrapper Linux para Cloud Routines)
#
# Agrega `_logs/pipeline_davivienda_*.json` de los ultimos N dias
# (default 7) en un reporte texto. Soporta el criterio "5 dias sin
# errores antes de escalar a Bancolombia" (ESTADO_PROYECTO §3,
# MASTER_RULES §14.1).
#
# Uso local:
#     bash run_metricas.sh                # 7 dias, output a stdout + log
#     bash run_metricas.sh 14             # 14 dias
#
# Cloud Routines: idempotente. Solo lee logs; no escribe en Sheets/Drive.
# ============================================================
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="$BASE/_logs"
mkdir -p "$LOGDIR"

DIAS="${1:-7}"
STAMP=$(date +%Y%m%d)
LOG="$LOGDIR/metricas_semanal_${STAMP}.txt"
TS() { date +"%Y-%m-%d %H:%M:%S"; }

{
  echo ""
  echo "===================================================="
  echo "[$(TS)] INICIO metricas semanal (ventana ${DIAS} dias)"
  echo "===================================================="
} >> "$LOG"

cd "$BASE/sprint_1"

# Materializa credenciales si estamos en cloud (no estrictamente necesario
# porque metricas solo lee logs locales, pero deja la huella en caso de
# que en el futuro el script consulte Sheets/HubSpot).
if [ -f "cloud_bootstrap.py" ]; then
  python cloud_bootstrap.py >> "$LOG" 2>&1 || true
fi

# Reporte texto (legible)
python metricas_pipeline.py --dias "$DIAS" --out "$LOG" >> "$LOG" 2>&1
RC=$?

{
  echo ""
  echo "[$(TS)] FIN metricas semanal exit=$RC log=$LOG"
} >> "$LOG"

# Echo final tambien a stdout para que Cloud Routine capture en su transcript
tail -50 "$LOG"

exit $RC

@echo off
REM ============================================================
REM MejorAhora - Pipeline Davivienda (Windows Task Scheduler)
REM Dispara el pipeline diario. Flujo:
REM   PASO 1: listar_pendientes_hoy.py  -> popula STAGING desde REGISTROS
REM   PASO 2: pipeline_davivienda.py    -> procesa STAGING y genera Excels
REM Logs: _logs\scheduled_YYYYMMDD.txt  (MASTER_RULES §18.4)
REM Fix 2026-04-25: (1) ruta _logs corregida, (2) PASO 1 agregado
REM ============================================================

setlocal

set BASE=C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE
set LOGDIR=%BASE%\_logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM Log fijo (append). Usamos PowerShell para evitar problemas de locale en %date%.
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"`) do set STAMP=%%i
set LOG=%LOGDIR%\scheduled_%STAMP%.txt

echo. >> "%LOG%"
echo ==================================================== >> "%LOG%"
echo [%date% %time%] INICIO pipeline Davivienda >> "%LOG%"
echo ==================================================== >> "%LOG%"

cd /d "%BASE%\sprint_1"

REM ---------------------------------------------------------
REM PASO 1: Publicar pendientes de REGISTROS -> STAGING
REM         (con dedup: no duplica si ya estan en STAGING)
REM ---------------------------------------------------------
echo [%date% %time%] PASO 1: listar_pendientes_hoy --banco davivienda >> "%LOG%"
py listar_pendientes_hoy.py --banco davivienda >> "%LOG%" 2>&1
set RC1=%ERRORLEVEL%
echo [%date% %time%] PASO 1 exit=%RC1% >> "%LOG%"

echo. >> "%LOG%"

REM ---------------------------------------------------------
REM PASO 2: Orquestador E2E - procesa pendientes en STAGING
REM         Hipotecario (570/571) y Leasing (600) identicos (R-DVV-09)
REM ---------------------------------------------------------
echo [%date% %time%] PASO 2: pipeline_davivienda >> "%LOG%"
py pipeline_davivienda.py >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%

echo. >> "%LOG%"
echo [%date% %time%] FIN pipeline PASO1=%RC1% PASO2=%RC% >> "%LOG%"

endlocal
exit /b %RC%

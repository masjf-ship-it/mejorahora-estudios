@echo off
REM ============================================================
REM MejorAhora - Pipeline Multi-Banco (Windows Task Scheduler)
REM Dispara el pipeline diario. Flujo:
REM   PASO 0  : smoke_test_prerun
REM   PASO 1a : listar_pendientes_hoy --banco davivienda  -> STAGING
REM   PASO 1b : listar_pendientes_hoy --banco bancolombia -> STAGING (2026-05-15)
REM   PASO 2a : pipeline_davivienda.py    -> procesa STAGING DVV
REM   PASO 2b : pipeline_bancolombia.py   -> procesa STAGING BCO (2026-05-15)
REM Logs: _logs\scheduled_YYYYMMDD.txt  (MASTER_RULES §18.4)
REM Fix 2026-04-25: (1) ruta _logs corregida, (2) PASO 1 agregado
REM Fix 2026-05-15: Multi-banco - agregado Bancolombia (Patron 3 Module-per-Bank)
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
REM PASO 0: Smoke test pre-pipeline (B5 retro 2026-05-07)
REM   Valida creds, OAuth, hash PESOS, deps. Si falla, aborta
REM   ANTES de procesar (evita 14 EXCEPTIONS por cliente como
REM   pasaba pre-fix OAuth).
REM ---------------------------------------------------------
echo [%date% %time%] PASO 0: smoke_test_prerun --skip-tests >> "%LOG%"
py smoke_test_prerun.py --skip-tests >> "%LOG%" 2>&1
set RC0=%ERRORLEVEL%
echo [%date% %time%] PASO 0 exit=%RC0% >> "%LOG%"
if not "%RC0%"=="0" (
    echo [%date% %time%] ABORT: smoke_test fallo, no se ejecutan PASO 1 ni 2 >> "%LOG%"
    endlocal
    exit /b 4
)

echo. >> "%LOG%"

REM ---------------------------------------------------------
REM PASO 1a: Publicar pendientes Davivienda REGISTROS -> STAGING
REM          (con dedup: no duplica si ya estan en STAGING)
REM ---------------------------------------------------------
echo [%date% %time%] PASO 1a: listar_pendientes_hoy --banco davivienda >> "%LOG%"
py listar_pendientes_hoy.py --banco davivienda >> "%LOG%" 2>&1
set RC1A=%ERRORLEVEL%
echo [%date% %time%] PASO 1a exit=%RC1A% >> "%LOG%"

echo. >> "%LOG%"

REM ---------------------------------------------------------
REM PASO 1b: Publicar pendientes Bancolombia REGISTROS -> STAGING (2026-05-15)
REM          (con dedup: no duplica si ya estan en STAGING)
REM ---------------------------------------------------------
echo [%date% %time%] PASO 1b: listar_pendientes_hoy --banco bancolombia >> "%LOG%"
py listar_pendientes_hoy.py --banco bancolombia >> "%LOG%" 2>&1
set RC1B=%ERRORLEVEL%
echo [%date% %time%] PASO 1b exit=%RC1B% >> "%LOG%"

echo. >> "%LOG%"

REM ---------------------------------------------------------
REM PASO 2a: Orquestador E2E Davivienda - procesa pendientes STAGING DVV
REM          Hipotecario (570/571) y Leasing (600) identicos (R-DVV-09)
REM ---------------------------------------------------------
echo [%date% %time%] PASO 2a: pipeline_davivienda >> "%LOG%"
py pipeline_davivienda.py >> "%LOG%" 2>&1
set RC2A=%ERRORLEVEL%
echo [%date% %time%] PASO 2a exit=%RC2A% >> "%LOG%"

echo. >> "%LOG%"

REM ---------------------------------------------------------
REM PASO 2b: Orquestador E2E Bancolombia - procesa STAGING BCO (2026-05-15)
REM          PDFs Bancolombia protegidos con CC del titular (R-BCO-02).
REM          Corre AUN SI Davivienda fallo (procesos independientes).
REM ---------------------------------------------------------
echo [%date% %time%] PASO 2b: pipeline_bancolombia >> "%LOG%"
py pipeline_bancolombia.py >> "%LOG%" 2>&1
set RC2B=%ERRORLEVEL%
echo [%date% %time%] PASO 2b exit=%RC2B% >> "%LOG%"

echo. >> "%LOG%"
echo [%date% %time%] FIN pipeline PASO0=%RC0% PASO1a=%RC1A% PASO1b=%RC1B% PASO2a=%RC2A% PASO2b=%RC2B% >> "%LOG%"

REM Exit code: falla si CUALQUIERA de los pipelines fallo.
REM En cmd no hay OR bitwise directo facil; usamos max() simplificado.
set RC=0
if not "%RC2A%"=="0" set RC=%RC2A%
if not "%RC2B%"=="0" set RC=%RC2B%

endlocal & exit /b %RC%

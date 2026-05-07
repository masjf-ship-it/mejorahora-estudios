@echo off
REM -------------------------------------------------------------------
REM run_maintenance.bat  —  entry point Windows Task Scheduler
REM Corre maintenance_60min.py con --apply y redirige salida a _logs/
REM -------------------------------------------------------------------

setlocal
set "PROJECT_ROOT=C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE"
set "SCRIPT=%PROJECT_ROOT%\maintenance\maintenance_60min.py"
set "LOGS=%PROJECT_ROOT%\_logs"

if not exist "%LOGS%" mkdir "%LOGS%"

REM Timestamp a prueba de locale via PowerShell
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"`) do set "TS=%%i"
set "OUT=%LOGS%\mant_run_%TS%.txt"

cd /d "%PROJECT_ROOT%"
py "%SCRIPT%" > "%OUT%" 2>&1
set RC=%ERRORLEVEL%

if %RC% NEQ 0 (
  echo [%DATE% %TIME%] maintenance_60min FAILED rc=%RC% >> "%LOGS%\mant.log"
)

endlocal & exit /b %RC%

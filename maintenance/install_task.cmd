@echo off
REM -------------------------------------------------------------------
REM install_task.cmd — registra las scheduled tasks de mantenimiento.
REM
REM Cadencia 2026-05-07: 12h. Crea DOS tareas:
REM   MejorAhora\Mantenimiento AM   DAILY 07:00
REM   MejorAhora\Mantenimiento PM   DAILY 19:00
REM
REM IMPORTANTE: si ya existe la tarea legacy "MejorAhora\Mantenimiento 60min"
REM (cadencia horaria, era workaround Cowork), este script la borra primero.
REM Ver MASTER_RULES.md §15 para el contexto completo.
REM -------------------------------------------------------------------
setlocal
set "TASK_AM=MejorAhora\Mantenimiento AM"
set "TASK_PM=MejorAhora\Mantenimiento PM"
set "TASK_LEGACY=MejorAhora\Mantenimiento 60min"
set "BAT=C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\maintenance\run_maintenance.bat"

echo === Migracion mantenimiento horario -^> 12h (2026-05-07) ===
echo.

REM Borrar tarea legacy si existe (silencioso si no existe)
echo Verificando tarea legacy "%TASK_LEGACY%"...
schtasks /query /tn "%TASK_LEGACY%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   encontrada — borrando...
    schtasks /delete /tn "%TASK_LEGACY%" /f >nul 2>&1
    echo   legacy borrada.
) else (
    echo   no existe — OK.
)
echo.

REM AM (07:00 — antes del pipeline AM 08:30)
echo Registrando: %TASK_AM% (DAILY 07:00)
schtasks /create ^
  /tn "%TASK_AM%" ^
  /tr "\"%BAT%\"" ^
  /sc DAILY ^
  /st 07:00 ^
  /rl LIMITED ^
  /f
if %ERRORLEVEL% NEQ 0 (
  echo ERROR registrando %TASK_AM%
  exit /b 1
)
echo.

REM PM (19:00 — antes del pipeline PM 20:30)
echo Registrando: %TASK_PM% (DAILY 19:00)
schtasks /create ^
  /tn "%TASK_PM%" ^
  /tr "\"%BAT%\"" ^
  /sc DAILY ^
  /st 19:00 ^
  /rl LIMITED ^
  /f
if %ERRORLEVEL% NEQ 0 (
  echo ERROR registrando %TASK_PM%
  exit /b 1
)
echo.

echo === OK. Tareas activas: ===
schtasks /query /tn "%TASK_AM%" /fo LIST | findstr /i "TaskName Next Run Time"
schtasks /query /tn "%TASK_PM%" /fo LIST | findstr /i "TaskName Next Run Time"
echo.
echo Ejecucion manual inmediata:
echo   schtasks /run /tn "%TASK_AM%"
echo.
echo Para deshabilitar:
echo   schtasks /change /tn "%TASK_AM%" /disable
echo   schtasks /change /tn "%TASK_PM%" /disable
echo.
echo Para borrar ambas:
echo   schtasks /delete /tn "%TASK_AM%" /f
echo   schtasks /delete /tn "%TASK_PM%" /f
endlocal

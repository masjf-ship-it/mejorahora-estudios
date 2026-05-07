@echo off
REM -------------------------------------------------------------------
REM install_task.cmd — registra la scheduled task Windows (una sola vez)
REM
REM Task name: MejorAhora\Mantenimiento 60min
REM Schedule:  cada 60 minutos, indefinido, arranca al iniciar sesion
REM -------------------------------------------------------------------
setlocal
set "TASK_NAME=MejorAhora\Mantenimiento 60min"
set "BAT=C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\maintenance\run_maintenance.bat"

echo Registrando tarea: %TASK_NAME%
echo Script:            %BAT%
echo Frecuencia:        cada 60 min
echo.

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%BAT%\"" ^
  /sc MINUTE ^
  /mo 60 ^
  /rl LIMITED ^
  /f

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo ERROR: no se pudo registrar la tarea. Verifica permisos.
  exit /b 1
)

echo.
echo OK. Consulta con:
echo   schtasks /query /tn "%TASK_NAME%" /v /fo LIST
echo.
echo Ejecucion manual inmediata:
echo   schtasks /run /tn "%TASK_NAME%"
echo.
echo Para deshabilitar:
echo   schtasks /change /tn "%TASK_NAME%" /disable
echo.
echo Para borrar:
echo   schtasks /delete /tn "%TASK_NAME%" /f
endlocal

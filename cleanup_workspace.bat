@echo off
REM ============================================================
REM MejorAhora - Cleanup workspace
REM Mueve .txt de diagnosticos/tests antiguos a _archivo_analisis\logs_historicos\
REM NO BORRA: solo mueve. Si algo se necesita, esta alli.
REM Preserva: requirements*.txt, *.md, *.py, *.xlsx, *.csv
REM ============================================================

setlocal

set BASE=C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE
set DEST=%BASE%\_archivo_analisis\logs_historicos

if not exist "%DEST%\raiz" mkdir "%DEST%\raiz"
if not exist "%DEST%\sprint_1" mkdir "%DEST%\sprint_1"

echo.
echo === Moviendo diagnosticos de RAIZ ===
cd /d "%BASE%"
for %%F in (diag.txt pending.txt dryrun_dav.txt run_dav.txt limpiar_test.txt append_sandra.txt test_post_rotate.txt test_sheet1.txt test_sheet2.txt test_real_1.txt test_real_2.txt test_real_3.txt test_audit.txt) do (
    if exist "%%F" (
        echo   - %%F
        move /y "%%F" "%DEST%\raiz\" >nul
    )
)

echo.
echo === Moviendo diagnosticos de sprint_1 ===
cd /d "%BASE%\sprint_1"
for %%F in (diagnostico_print.txt diagnostico_completo.txt diag_out.txt diag_post_regen.txt diag_final.txt regen_log.txt diag_regimen_E.txt diag_sandy_E.txt diag_dayanna.txt diag_dayanna_modoB.txt diag_eideli.txt diag_leidy.txt diag_sandra.txt out_dry.txt out_sync.txt out_pendientes.txt out_header.txt sync_dry_run.txt pilot_fernando_diag.txt) do (
    if exist "%%F" (
        echo   - %%F
        move /y "%%F" "%DEST%\sprint_1\" >nul
    )
)

REM pilot_diag.txt de HOY: se preserva en sprint_1 por ser validacion de Fernando.
REM El log oficial nuevo va en logs\scheduled_YYYYMMDD.txt.

echo.
echo === Listo. Archivos movidos a: ===
echo   %DEST%
echo.
echo Siguen en su sitio: requirements.txt, requirements_sheets.txt, *.md, *.py, *.xlsx, *.csv, pilot_diag.txt (hoy)

endlocal

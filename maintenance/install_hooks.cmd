@echo off
REM ============================================================
REM MejorAhora — Instalador de pre-commit hooks (B10)
REM Configura git para usar .githooks/ (versionado) como hooks path.
REM Ejecutar UNA SOLA VEZ por clone del repo.
REM
REM Uso:
REM     maintenance\install_hooks.cmd
REM
REM Para desactivar (no recomendado):
REM     git config --unset core.hooksPath
REM ============================================================

setlocal
set BASE=%~dp0\..
cd /d "%BASE%"

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo ERROR: este directorio no es un repo git.
    exit /b 1
)

git config core.hooksPath .githooks
if errorlevel 1 (
    echo ERROR: no se pudo configurar core.hooksPath.
    exit /b 1
)

echo [install_hooks] core.hooksPath -^> .githooks
echo [install_hooks] Hooks activos:
dir /b .githooks

echo.
echo Smoke test (drift checker via hook helper):
python ".githooks\pre-commit" 2>nul
if errorlevel 1 (
    echo [install_hooks] Smoke test reporto problemas. Ver salida arriba.
    exit /b 0
)

echo.
echo [install_hooks] Hooks instalados. El proximo 'git commit' los ejecutara.

endlocal

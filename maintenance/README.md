# maintenance/ — Protocolo 12h MejorAhora Estudios

Ver `MASTER_RULES.md` §15 para la especificacion completa.

**Cadencia:** 2× dia (07:00 AM y 19:00 PM). Antes era horario cuando MejorAhora
operaba en Cowork; reducido el 2026-05-07 (Claude Code persiste memoria en docs
versionados, no requiere backups frecuentes ni STEP 7 de auditoria de memoria).

## Archivos

| Archivo | Rol |
|---|---|
| `maintenance.py` | Script principal del ciclo (antes `maintenance_60min.py`) |
| `whitelist.txt` | Archivos permitidos en raiz (configurable) |
| `run_maintenance.bat` | Entry point de Windows Task Scheduler |
| `install_task.cmd` | Registra las tareas AM/PM (correr una vez) |
| `install_hooks.cmd` | Activa pre-commit hook `.githooks/pre-commit` (B10) |
| `README.md` | Este archivo |

## Primera ejecucion (dry-run) — recomendado

```cmd
cd "C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE"
python maintenance\maintenance.py --dry-run
```

Esto crea `_logs/mant.log` + posible `_logs/anomalies_*.txt` pero **no mueve ni copia nada**.
Revisa el reporte. Si OK, corre con `--apply`:

```cmd
python maintenance\maintenance.py
```

## Registrar las tareas programadas (una sola vez)

```cmd
maintenance\install_task.cmd
```

- Borra la tarea legacy `MejorAhora\Mantenimiento 60min` si existe (era horaria).
- Crea `MejorAhora\Mantenimiento AM` (DAILY 07:00) y `MejorAhora\Mantenimiento PM` (DAILY 19:00).
- Cada una corre `run_maintenance.bat` que ejecuta `maintenance.py`.

## Gestion

```cmd
schtasks /query /tn "MejorAhora\Mantenimiento AM" /v /fo LIST
schtasks /run   /tn "MejorAhora\Mantenimiento AM"
schtasks /change /tn "MejorAhora\Mantenimiento AM" /disable
schtasks /change /tn "MejorAhora\Mantenimiento AM" /enable
schtasks /delete /tn "MejorAhora\Mantenimiento AM" /f
```

(Repetir con `Mantenimiento PM` segun necesite.)

## Que hace cada ciclo

1. **Backup** — copia archivos canonicos (`MASTER_RULES.md`, `MOM_DAVIVIENDA.md`,
   `ESTADO_PROYECTO.md`, `CLAUDE.md`, `CHANGELOG.md`, `PESOS.xlsx`,
   `sprint_1/*.py`, `sprint_1/docs/*.md`, `automation/apps_script/*.gs`,
   `maintenance/*`) a `_backups/YYYY-MM-DD_HHMM/`.
2. **Rotacion** — conserva las ultimas **30 carpetas** (`RETENTION_N`, ~15 dias a 2 corridas/dia).
   Tambien rota logs JSON `_logs/pipeline_davivienda_*.json` con mas de 30 dias.
3. **Diff** — verifica archivos requeridos + `[HUBSPOT] token` en `config.ini` + ausencia de IDs lista negra §3.4.
4. **Reporte** — si hay anomalias, escribe `_logs/anomalies_<ts>.txt`.
5. **Limpieza** — mueve archivos sueltos en raiz NO whitelisted a `_archivo/YYYY-MM/`.
6. **Log** — append a `_logs/mant.log`.
7. **STEP 8 drift checker** — verifica coherencia entre docs (header vs footer
   de version, ESTADO § cita versiones reales) y codigo (hash PESOS,
   `RETENTION_N` consistente, refs canonicos existen). Solo reporta.

**STEP 7 anterior** (auditoria memoria operativa Claude) eliminado el 2026-05-07.
Era workaround para el "olvido" de Cowork; en Claude Code la memoria son
archivos versionados (CLAUDE.md, MASTER_RULES, CHANGELOG) que no requieren
auditoria externa.

## Modificar la whitelist

Editar `whitelist.txt`. Soporta `fnmatch`: `*.md`, `ROADMAP*.md`, etc.
Las carpetas NUNCA se mueven aunque no esten en la whitelist.

## Recuperar algo archivado por error

```cmd
move "_archivo\YYYY-MM\<archivo>" .
```

Todo lo movido queda en `_archivo/`, nada se borra.

## Recuperar de un backup

```cmd
dir _backups\
robocopy "_backups\<timestamp>\sprint_1" ".\sprint_1" /E
```

## Codigos de salida

- `0` — OK (con o sin anomalias reportadas)
- `1` — error critico (no pudo escribir logs)

## Logs

- `_logs/mant.log` — resumen de cada ciclo
- `_logs/mant_run_YYYYMMDD_HHMM.txt` — stdout+stderr completo de cada ejecucion
- `_logs/anomalies_YYYY-MM-DD_HHMM.txt` — solo cuando hay hallazgos

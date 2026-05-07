# maintenance/ — Protocolo 60min MejorAhora Estudios

Ver `MASTER_RULES.md` §18 para la especificacion completa.

## Archivos

| Archivo | Rol |
|---|---|
| `maintenance_60min.py` | Script principal del ciclo |
| `whitelist.txt` | Archivos permitidos en raiz (configurable) |
| `run_maintenance.bat` | Entry point de Windows Task Scheduler |
| `install_task.cmd` | Registra la scheduled task (correr una vez) |
| `README.md` | Este archivo |

## Primera ejecucion (dry-run) — recomendado

```cmd
cd "C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE"
python maintenance\maintenance_60min.py --dry-run
```

Esto crea `_logs/mant.log` + posible `_logs/anomalies_*.txt` pero **no mueve ni copia nada**.
Revisa el reporte. Si OK, corre con `--apply`:

```cmd
python maintenance\maintenance_60min.py
```

## Registrar la tarea programada (una sola vez)

```cmd
maintenance\install_task.cmd
```

Crea la tarea `MejorAhora\Mantenimiento 60min` que corre cada 60 min.

## Gestion

```cmd
schtasks /query /tn "MejorAhora\Mantenimiento 60min" /v /fo LIST
schtasks /run   /tn "MejorAhora\Mantenimiento 60min"
schtasks /change /tn "MejorAhora\Mantenimiento 60min" /disable
schtasks /change /tn "MejorAhora\Mantenimiento 60min" /enable
schtasks /delete /tn "MejorAhora\Mantenimiento 60min" /f
```

## Que hace cada ciclo

1. **Backup** — copia `MASTER_RULES.md`, `SOURCE_OF_TRUTH.md`, `PESOS.xlsx`, `sprint_1/*.py`, `config.ini`, bank_rules, apps_script, maintenance a `_backups/YYYY-MM-DD_HHMM/`.
2. **Rotacion** — conserva las ultimas 336 carpetas (2 semanas).
3. **Diff** — verifica que existan archivos requeridos + `[HUBSPOT] token` en `config.ini` + ausencia de IDs de la lista negra.
4. **Reporte** — si hay anomalias, escribe `_logs/anomalies_<ts>.txt`.
5. **Limpieza** — mueve archivos sueltos en raiz NO whitelisted a `_archivo/YYYY-MM/`.
6. **Log** — append a `_logs/mant.log`.

## Modificar la whitelist

Editar `whitelist.txt`. Soporta `fnmatch`: `*.md`, `ROADMAP*.md`, etc.
Las carpetas NUNCA se mueven aunque no esten en la whitelist (§18.7 MASTER_RULES).

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

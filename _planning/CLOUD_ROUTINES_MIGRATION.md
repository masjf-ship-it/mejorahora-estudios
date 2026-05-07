# Cloud Routines Migration — pipeline 24/7 sin PC encendida

**Versión:** 1.0 · 2026-05-07
**Rol:** Plan de migración del pipeline Davivienda + mantenimiento desde Windows Task Scheduler hacia Anthropic Cloud Routines (Claude Code).
**Política:** Documento vive bajo `_planning/`. Se actualiza durante la ejecución; se archiva a `_archivo/` cuando todo está migrado y validado 5 días sin errores.

---

## Por qué

Hoy todo corre en Windows Task Scheduler (`run_pipeline.bat` AM/PM, `Mantenimiento AM/PM`). Si Jose apaga la PC: el pipeline NO procesa pendientes, no se generan backups, no se valida drift.

Cloud Routines de Claude Code (Research Preview, plan Max ya contratado) ejecutan en una VM de Anthropic sin depender de la PC del usuario. Plan Max permite ~15 runs/día — uso real esperado: 4 runs/día (pipeline AM, pipeline PM, mantenimiento AM, mantenimiento PM) → cabe holgado.

**Estado feature:** Research Preview. Mantener Windows Tasks como fallback hasta validar 5 días consecutivos sin errores.

---

## Constraints técnicos confirmados

| Punto | Realidad |
|---|---|
| Acceso al código | Routine clona desde git remoto en cada ejecución |
| Plataforma | VM Linux ephemeral, 4 vCPU / 16 GB RAM / 30 GB disco |
| Python | 3.x con pip + PyPI accesible — pdfplumber/openpyxl/gspread/google-* OK |
| Filesystem | Clone del repo + disco local ephemeral por run (NO persistente entre runs) |
| Frecuencia mín | 1 hora |
| Acceso PC local | NINGUNO. No `C:\Users\JOSE A\...`, no `_backups/` local, no `_logs/` local |
| Permisos | NO hay permission picker — la routine corre 100% autónoma. El prompt debe ser self-contained |
| Logs | Cada run es una sesión Claude Code visible en `claude.ai/code/routines` |

---

## Pre-requisitos (Jose ejecuta, Claude documenta/asiste)

### 1. Git remoto privado (BLOQUEADOR #1)

- ✅ Pre-flight: scan de los 5 commits actuales no encontró credenciales committeadas.
- 📋 Acción Jose: crear repo `mejorahora-estudios` (privado) en GitHub.com.
- 📋 Acción Claude: `git remote add origin <url>` + `git push -u origin claude/kind-shaw-2be195` + `git push origin main`.

### 2. Credenciales en la nube (BLOQUEADOR #2)

Tres archivos sensibles que hoy están gitignored y NO entran al repo:
- `credentials/sheets_sa.json` — Service Account
- `credentials/oauth_token.json` — OAuth user para Drive §4.2
- `sprint_1/config.ini` — token HubSpot `pat-*`

**Decisión pendiente:** cómo exponerlas a la routine. Tres caminos:

| Estrategia | Pros | Contras |
|---|---|---|
| **A. Env vars en config del entorno Cloud** | Más simple. Pegas una vez. | Visibles a quien edite el entorno. |
| **B. Migrar a Workspace SA con cuota propia (B3 Ola 3)** | Cero mantenimiento OAuth (problema crónico). Una sola SA en lugar de SA + OAuth. | Requiere dominio Google Workspace. ~1-2h migración. |
| **C. Vault externo (GCP Secret Manager)** | Profesional. Audit trail. Rotación de claves. | Más complejidad. La routine debe `gcloud secrets versions access` al inicio. |

**Recomendación:** A para arrancar (simple), migrar a B en una segunda fase si OAuth sigue dando problemas. C solo si el cliente lo requiere por compliance.

### 3. Adaptaciones de código

- `run_pipeline.bat` → reescribir como `run_pipeline.sh` (Linux). El contenido es trivial: smoke_test → listar_pendientes → pipeline.
- `pipeline_davivienda.py` → ya usa `Path(__file__).resolve().parent` así que cross-platform. Verificar que ningún `subprocess` invoque `.bat` o `cmd.exe`.
- `maintenance.py` → en la nube ya no tiene `_backups/` local — git remote ES el backup. Reducir a:
  - Drift checker (sigue valiendo).
  - Rotar logs viejos en Drive (si llegamos a centralizar logs en Drive).
  - Skip backup local (no aplica).
- `smoke_test_prerun.py` → adaptar paths esperados; en la nube las creds vienen de env vars, no de `credentials/*.json`.

### 4. Setup script del entorno Claude Code

Comando único que la routine corre 1×/cache (~7 días):
```bash
pip install -r sprint_1/requirements.txt
```

---

## Mapa de tareas Windows → Cloud Routines

| Windows Task | Hora | Frecuencia | Cloud Routine equivalente |
|---|---|---|---|
| `MejorAhora\Pipeline Davivienda AM` | 08:30 | Daily | `pipeline_davivienda_am` (cron `30 8 * * *`) |
| `MejorAhora\Pipeline Davivienda PM` | 20:30 | Daily | `pipeline_davivienda_pm` (cron `30 20 * * *`) |
| `MejorAhora\Mantenimiento AM` | 07:00 | Daily | `maintenance_am` (cron `0 7 * * *`) — solo drift + rotación logs Drive |
| `MejorAhora\Mantenimiento PM` | 19:00 | Daily | `maintenance_pm` (cron `0 19 * * *`) — idem |

= 4 runs/día. Caben en el plan Max (~15/día).

---

## Plan ejecutable (cuando los pre-requisitos estén)

### Fase 1 — Bootstrap

1. ✅ Pre-flight scan: 0 leaks confirmado.
2. ⏳ Jose crea repo GitHub privado.
3. ⏳ Claude: `git remote add origin <url>` + push de `claude/kind-shaw-2be195` + (con permiso) merge a `main` y push.
4. ⏳ Verificar que el push esté completo en GitHub UI.

### Fase 2 — Adaptación código

5. Crear `run_pipeline.sh` espejo de `run_pipeline.bat`.
6. Crear `maintenance/run_maintenance.sh` espejo de `run_maintenance.bat`.
7. Adaptar `pipeline_davivienda.py::main()` para leer creds de env vars con fallback a archivo (compatibilidad local + nube).
8. Adaptar `smoke_test_prerun.py` para detectar entorno cloud y validar env vars en lugar de archivos.
9. Reducir `maintenance.py` en modo cloud (skip backup local, ejecutar drift + log rotation).
10. Tests: `test_fase2.py` 16/16 + pytest 18/18 + smoke en local sin tocar nada.

### Fase 3 — Configurar Cloud Routines

11. Subir env vars al config del entorno Cloud Code:
    - `MEJORAHORA_HUBSPOT_TOKEN=pat-...`
    - `MEJORAHORA_SA_JSON=<contenido del sheets_sa.json escapado>`
    - `MEJORAHORA_OAUTH_TOKEN_JSON=<contenido del oauth_token.json>`
12. Crear setup script: `pip install -r sprint_1/requirements.txt`.
13. Crear las 4 routines vía UI Claude Code (`claude.ai/code/routines`):
    - Cada una con su prompt self-contained (ej. `cd /workspace && bash run_pipeline.sh`).
    - Cron schedule según tabla arriba.

### Fase 4 — Validación

14. Smoke test: ejecutar manualmente cada routine 1×, verificar:
    - Routine completa sin errores
    - El JSON `_logs/pipeline_davivienda_*.json` se commitea de vuelta al repo (o se sube a Drive)
    - El Excel se genera y sube a Drive §4.2 correctamente
    - El STAGING se actualiza en Sheets
15. Comparar output vs run local de la misma fecha.
16. Si OK: dejar las routines activas + Windows Tasks en paralelo durante 5 días.
17. Si 5 días sin discrepancias: deshabilitar Windows Tasks. Migración completa.

### Fase 5 — Cleanup

18. Documentar en MASTER_RULES §22 cómo es la nueva arquitectura productiva.
19. Mover este plan a `_archivo/2026-XX/CLOUD_ROUTINES_MIGRATION.md`.
20. Bumpear MASTER_RULES + CHANGELOG.

---

## Riesgos identificados

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Routine timeout antes de procesar todos los pendientes | Bajo (5-30 min < límites VM) | Limitar `--max 50` por run, encadenar runs si hace falta |
| OAuth token expira durante la corrida | Medio | Ya está mitigado por el smoke_test_prerun + fix Bug A; en la nube hay que probar refresh con creds en env var |
| Env vars expuestas a quien edite el entorno | Medio | Limitar acceso al entorno Cloud; en B3 (Workspace SA) se elimina OAuth |
| Cambio en Research Preview API rompe routines | Medio | Mantener Windows Tasks como fallback 6 meses; suscribirse a release notes Claude Code |
| Conflictos git al pushear logs JSON desde routine concurrente | Bajo | Routines no corren en paralelo (cron diferenciado); aún así, en la routine `git pull --rebase` antes de push |
| Discrepancias output local vs cloud | Bajo | Fase 4 valida antes de cortar |

---

## Decisiones pendientes

- [ ] Nombre del repo (sugerido: `mejorahora-estudios`) — Jose decide.
- [ ] Estrategia de credenciales (A/B/C) — Jose decide tras leer los pros/contras arriba.
- [ ] ¿Logs JSON suben al repo (commit en cada run) o a Drive folder dedicado? — Decisión de arquitectura.
- [ ] ¿Mantener Windows Tasks 5 días como fallback o cortar de una? — Recomendación: paralelo 5 días.

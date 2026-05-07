# Cloud Routines — Setup paso a paso para Jose

**Versión:** 1.0 · 2026-05-07
**Pre-requisito:** repo en GitHub con la rama `main` ya pusheada (✅ hecho).

Esta guía te lleva de cero a 4 routines corriendo. Tiempo estimado: 30-45 min.

---

## Paso 1 — Cambiar default branch a main (1 min)

1. Ve a **https://github.com/masjf-ship-it/mejorahora-estudios/settings/branches**
2. En "Default branch": clic en el icono ⇄
3. Selecciona **`main`** del dropdown → "Update"
4. Confirma "I understand, update the default branch"

---

## Paso 2 — Subir credenciales como env vars en Claude Code (5 min)

Necesitas exponer 3 secretos a la routine. NO se commitean al repo, viven en el config del entorno Claude Code.

### A. Service Account JSON

Abre `C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\credentials\sheets_sa.json` con Notepad y copia TODO el contenido (es un JSON largo).

### B. OAuth token JSON

Abre `C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\credentials\oauth_token.json` con Notepad y copia TODO el contenido.

### C. HubSpot token

Abre `C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\sprint_1\config.ini` con Notepad. Copia solo el valor después de `token = ` (la cadena `pat-na2-...`).

### Subirlos a Claude Code

1. Ve a **https://claude.ai/code**
2. En "Environments" o "Settings" del proyecto, agrega 3 variables:

| Nombre exacto | Valor |
|---|---|
| `MEJORAHORA_SA_JSON` | (pega el JSON completo del paso A) |
| `MEJORAHORA_OAUTH_TOKEN_JSON` | (pega el JSON completo del paso B) |
| `MEJORAHORA_HUBSPOT_TOKEN` | (pega el `pat-...` del paso C) |

> El código `cloud_bootstrap.py` lee estas 3 env vars y materializa los archivos en runtime — sin esto, la routine falla en el smoke test.

---

## Paso 3 — Crear las 4 routines (15 min)

En **claude.ai/code/routines** → "New routine":

### Routine 1: Pipeline AM
| Campo | Valor |
|---|---|
| Name | `MejorAhora Pipeline AM` |
| Repo | `masjf-ship-it/mejorahora-estudios` |
| Branch | `main` |
| Schedule (cron) | `30 8 * * *` (diario 08:30 hora del servidor — verifica timezone) |
| Setup script | `pip install -r sprint_1/requirements.txt` |
| Prompt | `Run the daily pipeline: bash run_pipeline.sh. Report success/failure summary at the end.` |

### Routine 2: Pipeline PM
Igual a la 1 pero:
- Name: `MejorAhora Pipeline PM`
- Schedule: `30 20 * * *`

### Routine 3: Mantenimiento AM (opcional en cloud)
| Campo | Valor |
|---|---|
| Name | `MejorAhora Mantenimiento AM` |
| Schedule | `0 7 * * *` |
| Prompt | `Run: python maintenance/maintenance.py. Report drift findings if any.` |

> En cloud, el mantenimiento solo corre drift checker + reporte (backup local skip automáticamente porque el filesystem es efímero, código ya lo detecta vía `CLAUDE_CODE_REMOTE`).

### Routine 4: Mantenimiento PM
Igual a la 3, schedule `0 19 * * *`.

---

## Paso 4 — Smoke test inicial (5 min)

1. En claude.ai/code/routines → selecciona "MejorAhora Pipeline AM" → "Run now" (manual trigger).
2. Mira los logs en vivo. Espera ver:
   - `[smoke_test] CLOUD env — bootstrap: {'sa': True, 'oauth': True, 'hubspot': True, ...}`
   - `[pipeline_davivienda] CLOUD env detected — bootstrap: ...`
   - `PESOS.xlsx integridad OK`
   - `[pipeline_davivienda] OAuth user drive activo`
3. Si falla, lee el output del smoke_test y arregla la env var correspondiente.

---

## Paso 5 — Validación 5 días en paralelo (5 días pasivo)

- Las routines corren a sus horarios.
- Las Windows Tasks AM/PM siguen activas en tu PC como **fallback**.
- Compara: ¿generan los mismos Excel? ¿el STAGING se actualiza correctamente?
- Si 5 días sin discrepancias → **deshabilitar Windows Tasks** (`schtasks /change /tn "MejorAhora\\Pipeline Davivienda AM" /disable`).

---

## Cómo monitoreas

- **Cada run** aparece en `claude.ai/code/routines` con su transcript completo.
- **Errores**: Claude Code te puede notificar (configurar en preferencias de routines).
- **Métricas semanales**: corre manualmente `python sprint_1/metricas_pipeline.py --dias 7` cuando quieras (se puede hacer otra routine semanal lunes 09:00).

---

## Si algo sale mal

| Síntoma | Causa probable | Fix |
|---|---|---|
| `[smoke_test] FAIL: credenciales SA ausentes` | Env var `MEJORAHORA_SA_JSON` no configurada o JSON inválido | Re-pegar el contenido del archivo, validar con jsonlint.com |
| `FATAL: OAuth no disponible` | Token OAuth expirado/revocado | En tu PC: `py drive_oauth_setup.py`, copiar nuevo `oauth_token.json` y actualizar env var en Claude Code |
| `HubSpot token vacío` | `MEJORAHORA_HUBSPOT_TOKEN` no configurada | Pegar token `pat-*` |
| `pip install` falla | Conflicto deps | Revisar `sprint_1/requirements.txt` y los logs del setup script |
| Routine timeout | Pipeline procesa demasiados clientes | Limitar con `--max 50` en el prompt |

---

## Después de migrar

- Mantén Windows Tasks **deshabilitadas pero no eliminadas** durante 30 días por si hay que rollback.
- Cada cambio al pipeline ahora es: edit local → commit → push a `main` → la próxima routine ya corre el código nuevo.
- El pre-commit hook bloquea commits que rompan tests, así que el código nunca llega roto a producción.

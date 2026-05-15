# Cloud Routines — Setup paso a paso para Jose

**Versión:** 2.1 · 2026-05-15
**Pre-requisito:** repo en GitHub con la rama `main` ya pusheada (✅ hecho).

## ⚠️ IMPORTANTE — Cambio de plan Anthropic Max → Pro (2026-05-15)

Plan **Pro** otorga **5 ejecuciones/día** (no 15 como Max). Configuración ajustada:

| Rutina | Estado | Razón |
|---|---|---|
| MejorAhora Pipeline AM (9:00 GMT-5) | ✅ Activa diaria | Crítica — procesa pendientes mañana |
| MejorAhora Pipeline PM (20:30 GMT-5) | ✅ Activa diaria | Crítica — procesa pendientes tarde |
| MejorAhora Mantenimiento AM (7:00 GMT-5) | ✅ Activa diaria | Drift checker + reporte 1x/día |
| **MejorAhora Mantenimiento PM (19:00 GMT-5)** | 🔴 **PAUSADA permanente** | Liberar cuota para Pipeline PM y manuales |
| MejorAhora Metricas Semanal (Lunes 9:00) | ✅ Activa semanal | 1x/semana |

**Cuota diaria con esta config:**
- Martes-Domingo: 3 programadas / 5 → **2 manuales disponibles**
- Lunes: 4 programadas / 5 → **1 manual disponible**

Si necesitas re-procesar un cliente con `--force` o disparar manual, ten en cuenta esta cuota.

Esta guía te lleva de cero a 5 routines corriendo. Tiempo estimado: 30-45 min
(la primera vez tomó ~90 min con 7 smoke tests porque descubrimos 6 fixes
infra que ahora están documentados — si rehaces esto desde cero hoy son 30 min).

---

## Paso 1 — Cambiar default branch a main (1 min)

1. Ve a **https://github.com/masjf-ship-it/mejorahora-estudios/settings/branches**
2. En "Default branch": clic en el icono ⇄
3. Selecciona **`main`** del dropdown → "Update"
4. Confirma "I understand, update the default branch"

---

## Paso 2 — Crear entorno "MejorAhora" con 3 env vars (5-10 min)

Las 3 credenciales viven como variables del **entorno** (no de la routine individual),
para reusarlas en las 5 routines.

### A. Service Account JSON

Abre `C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\credentials\sheets_sa.json` y copia TODO el contenido.

### B. OAuth token JSON

Abre `C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\credentials\oauth_token.json` y copia TODO el contenido.

### C. HubSpot token

Abre `C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\sprint_1\config.ini`. Copia solo el valor después de `token = ` (la cadena `pat-na1-...`).

### Crear el entorno en Claude Code

1. Ve a **https://claude.ai/code/routines**, click "Nueva rutina" → en el formulario, click el dropdown "Entorno" → "Añadir entorno".
2. Llena el dialog "Nuevo entorno en la nube":
   - **Nombre:** `MejorAhora`
   - **Acceso a la red:** `Completo` ⚠️ **CRÍTICO — ver troubleshooting #6**
   - **Variables de entorno** (formato .env, una por línea):
     ```
     MEJORAHORA_SA_JSON='<pega el JSON completo del paso A, en una sola línea>'
     MEJORAHORA_OAUTH_TOKEN_JSON='<pega el JSON completo del paso B, en una sola línea>'
     MEJORAHORA_HUBSPOT_TOKEN=pat-na1-<el resto del token, sin comillas>
     ```
     - Los 2 JSON van entre **comillas simples** porque contienen comillas dobles
     - El HubSpot token NO lleva comillas
   - **Script de configuración:** déjalo **vacío** ⚠️ **CRÍTICO — ver troubleshooting #1**

3. Click "Crear entorno".

> ⚠️ Anti-pattern descartado: NO pongas `pip install -r sprint_1/requirements.txt`
> en el script de configuración. Corre antes del clone del repo y falla. El pip
> install vive ahora en `run_pipeline.sh` (PASO -1) y `run_metricas.sh`.

> ⚠️ El warning de la UI ("Son visibles para cualquiera que use este entorno:
> no añadas secretos ni credenciales") aplica solo si compartes el entorno con
> otros. En tu workspace personal solo TÚ tienes acceso — es OK.

---

## Paso 3 — Crear las 5 routines (15 min)

En **claude.ai/code/routines** → "Nueva rutina":

### Routine 1: Pipeline AM
| Campo | Valor |
|---|---|
| Name | `MejorAhora Pipeline AM` |
| Repo | `masjf-ship-it/mejorahora-estudios` |
| Branch | `main` |
| Entorno | `MejorAhora` |
| Activador | Programación → Diario → 09:00 GMT-5 |
| Setup script | **vacío** (el pip install vive en run_pipeline.sh) |
| Prompt | (ver más abajo) |

**Prompt sugerido:**
```
Ejecuta el pipeline diario de Davivienda corriendo:
bash run_pipeline.sh

Despues de la ejecucion:
1. Lee el archivo _logs/scheduled_$(date +%Y%m%d).txt para revisar el resultado
2. Cuenta cuantos clientes se procesaron OK y cuantos fallaron
3. Reporta un resumen breve (3-5 lineas) del exit code, archivos generados,
   y cualquier ALERTA M2 o REVISION_MANUAL

NO hagas commits, NO modifiques codigo, NO instales paquetes nuevos.
Si run_pipeline.sh sale con exit 4 (smoke_test fail) o exit 3 (OAuth fatal),
reporta el problema de inmediato pero no intentes arreglarlo.
```

### Routine 2: Pipeline PM
Igual a la 1 pero:
- Name: `MejorAhora Pipeline PM`
- Activador: Diario → 20:30 GMT-5

### Routine 3: Mantenimiento AM
| Campo | Valor |
|---|---|
| Name | `MejorAhora Mantenimiento AM` |
| Entorno | `MejorAhora` |
| Activador | Diario → 07:00 GMT-5 |
| Prompt | `Run: python maintenance/maintenance.py. Report drift findings if any.` |

> En cloud, el mantenimiento solo corre drift checker + reporte (backup local
> skip automáticamente porque el filesystem es efímero, código ya lo detecta
> vía `CLAUDE_CODE_REMOTE`).

### Routine 4: Mantenimiento PM
Igual a la 3, activador: Diario → 19:00 GMT-5.

### Routine 5: Métricas Semanal (B5 — soporte criterio "5 días clean")
| Campo | Valor |
|---|---|
| Name | `MejorAhora Metricas Semanal` |
| Entorno | `MejorAhora` |
| Activador | Programación → **Semanal** → Lunes → 09:00 GMT-5 |
| Prompt | (ver más abajo) |

**Prompt sugerido:**
```
Ejecuta el reporte semanal de metricas del pipeline Davivienda corriendo:
bash run_metricas.sh 7

Despues de la ejecucion:
1. Lee el archivo _logs/metricas_semanal_$(date +%Y%m%d).txt
2. Reporta un resumen breve (3-5 lineas) con:
   - Total clientes procesados en los ultimos 7 dias
   - Success rate (% OK / total)
   - Top 3 categorias de fallo (REVISION_MANUAL, M1_FAIL, etc.)
   - Status del criterio "5 dias clean" (ESTADO_PROYECTO §3 / MASTER_RULES §14.1)

NO hagas commits, NO modifiques codigo, NO instales paquetes nuevos.
Si run_metricas.sh sale con exit != 0, reporta el problema pero no intentes arreglarlo.
```

---

## Paso 4 — Smoke test inicial (10 min)

1. En `claude.ai/code/routines` → selecciona "MejorAhora Pipeline AM" → "Ejecutar ahora".
2. Mira los logs en vivo. Espera ver (en orden):
   - `[$(TS)] PASO -1: pip install -r sprint_1/requirements.txt` (sin errores)
   - `[$(TS)] PASO 0: smoke_test_prerun --skip-tests`
   - `[smoke_test] CLOUD env — bootstrap: {'sa': True, 'oauth': True, 'hubspot': True, ...}`
   - `PESOS.xlsx integridad OK`
   - `[pipeline_davivienda] CLOUD env detected — bootstrap: ...`
   - `[pipeline_davivienda] OAuth user drive activo`
   - `Procesando cliente X/N: NOMBRE`
3. El smoke test tarda 1-15 min según cuántos clientes pendientes haya.
4. Si **falla en PASO -1 (pip)**: ver troubleshooting #1-3.
5. Si **falla con SSL CERTIFICATE_VERIFY_FAILED**: ver troubleshooting #4-5.
6. Si **falla con "Could not open requirements file"**: el setup script del
   entorno está mal. Vaciarlo (Paso 2 punto 2 último item).

---

## Paso 5 — Validación 5 días en paralelo (5 días pasivo)

- Las 4 routines diarias (Pipeline AM/PM + Mant AM/PM) corren a sus horarios.
- Las Windows Tasks AM/PM siguen activas en tu PC como **fallback**.
- Compara: ¿generan los mismos Excel? ¿el STAGING se actualiza correctamente?
- La Routine 5 (Métricas Semanal, lunes 9:00) te da el reporte agregado.
- Si **5 días sin discrepancias** → puedes:
  - **Deshabilitar Windows Tasks**: `schtasks /change /tn "MejorAhora\\Pipeline Davivienda AM" /disable` (y PM)
  - **Privatizar repo GitHub** (Settings → Danger Zone → Change visibility → Make private)

> Mantén Windows Tasks **deshabilitadas pero no eliminadas** durante 30 días
> por si hay que rollback.

---

## Cómo monitoreas

- **Cada run** aparece en `claude.ai/code/routines` con su transcript completo.
- **Errores**: Claude Code te puede notificar (configurar en preferencias de routines).
- **Métricas semanales**: la Routine 5 las dispara lunes 9:00. También puedes correr local:
  `bash run_metricas.sh 7`

---

## Troubleshooting — síntomas y fixes (descubiertos los 6 en sesión 2026-05-12)

| # | Síntoma | Causa raíz | Fix |
|---|---|---|---|
| 1 | `Setup script failed with exit code 1. Could not open requirements file: 'sprint_1/requirements.txt'` | El setup script corre ANTES del git clone, no encuentra el archivo. | Vaciar el setup script del entorno. El pip install vive en `run_pipeline.sh` (PASO -1) y `run_metricas.sh`. |
| 2 | `error: externally-managed-environment` | PEP 668: Debian de Cloud Routines tiene Python externally-managed. | Ya resuelto: `run_pipeline.sh` usa `pip install --break-system-packages`. |
| 3 | `Cannot uninstall packaging 24.0, RECORD file not found` | `packaging` instalado via dpkg (sistema), pip no puede desinstalar. | Ya resuelto: `pip install ... --ignore-installed`. |
| 4 | `SSL: CERTIFICATE_VERIFY_FAILED — self-signed certificate in chain` al conectar a googleapis.com | Cloud Routines tienen proxy TLS de Anthropic con CA propia. `certifi` (Python default) no la incluye. | Ya resuelto: `run_pipeline.sh` exporta `SSL_CERT_FILE` + `REQUESTS_CA_BUNDLE` + `HTTPLIB2_CA_CERTS` apuntando a `/etc/ssl/certs/ca-certificates.crt` (CA del sistema, sí incluye Anthropic). |
| 5 | Aplicaste el fix #4 dentro de Python (cloud_bootstrap.py) y SIGUE el error SSL | `httplib2` cachea su CA bundle al IMPORT desde la env var `HTTPLIB2_CA_CERTS`. Si la seteas dentro de Python ya es tarde. | El fix tiene que ser a **nivel shell** ANTES de `python ...`. Ver `run_pipeline.sh` líneas 11-22. |
| 6 | Acceso a la red en "De confianza" empeora el SSL | "De confianza" rutea por proxy adicional de Anthropic. | Cambiar a "Completo" en el dialog del entorno (Paso 2). |
| 7 | `[smoke_test] FAIL: credenciales SA ausentes` | Env var `MEJORAHORA_SA_JSON` mal configurada (no es JSON válido, o falta comilla simple). | Re-pegar el JSON entre comillas simples `'...'`, validar con jsonlint.com primero. |
| 8 | `FATAL: OAuth no disponible — invalid_grant` | Token OAuth expirado/revocado por Google (después de ~6 meses sin uso). | En tu PC: `py drive_oauth_setup.py`, copiar nuevo `oauth_token.json` y actualizar env var `MEJORAHORA_OAUTH_TOKEN_JSON` en el entorno. |
| 9 | Routine timeout antes de procesar todos los pendientes | Pipeline procesa demasiados clientes en una corrida. | Agregar `--max 50` en el prompt para limitar. |

---

## Después de migrar

- Mantén Windows Tasks **deshabilitadas pero no eliminadas** durante 30 días.
- Cada cambio al pipeline ahora es: edit local → commit → push a `main` → la próxima routine ya corre el código nuevo (Cloud Routines clonan `main` cada ejecución).
- El pre-commit hook bloquea commits que rompan tests, así que el código nunca llega roto a producción.
- **Rotación de credenciales** (cada ~3 meses): regenera el JSON correspondiente, actualiza la env var en el entorno "MejorAhora" desde `claude.ai/code` → la próxima ejecución usa la nueva.

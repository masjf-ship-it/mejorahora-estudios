# Configuración pendiente — Jose (5 minutos)

**Status:** las 4 routines existen pero los pipelines van a fallar mañana porque les faltan las 3 credenciales como variables de entorno.

**El sistema bloqueó que Claude pegara los secretos automáticamente** (protección de seguridad). Tienes que hacerlo tú. Son 5 min.

---

## Paso a paso

### 1. Abre la app de Claude Code → Routines → "MejorAhora Pipeline AM"

### 2. Click ✏️ Editar (arriba a la derecha)

### 3. Click el botón **"Default"** (al lado del repositorio, abajo del cuadro de instrucciones)

### 4. Click **"+ Añadir entorno"** del dropdown

### 5. Se abre el formulario "Nuevo entorno en la nube". Llena así:

**Nombre:** `MejorAhora`

**Acceso a la red:** dejar "De confianza" (default)

**Variables de entorno:** abre los siguientes archivos en Notepad y arma el bloque pegando exactamente esto:

```
MEJORAHORA_SA_JSON='[PEGAR_AQUI_TODO_EL_CONTENIDO_DE_credentials/sheets_sa.json]'
MEJORAHORA_OAUTH_TOKEN_JSON='[PEGAR_AQUI_TODO_EL_CONTENIDO_DE_credentials/oauth_token.json]'
MEJORAHORA_HUBSPOT_TOKEN=[PEGAR_AQUI_SOLO_EL_VALOR_pat-XXX_DE_sprint_1/config.ini]
```

**IMPORTANTE — comillas simples para los JSON:**
- El JSON tiene comillas dobles internas. Envuelve TODO el JSON con **comillas simples** `'...'`
- Para el HubSpot token (sin JSON): pégalo SIN comillas

**Archivos a abrir en Notepad:**
- `C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\credentials\sheets_sa.json` — copia TODO (Ctrl+A) → pega entre las comillas simples de `MEJORAHORA_SA_JSON='...'`
- `C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\credentials\oauth_token.json` — copia TODO → pega entre las comillas simples de `MEJORAHORA_OAUTH_TOKEN_JSON='...'`
- `C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\sprint_1\config.ini` — solo el valor después de `token = ` (la cadena `pat-na2-...`) → pega después del `=` en `MEJORAHORA_HUBSPOT_TOKEN=`

**Tip si los JSON tienen líneas separadas:** no pasa nada, pégalo tal cual. El formulario acepta JSON con saltos de línea siempre que esté entre comillas simples.

**Script de configuración:** pega esto en el otro campo:

```bash
#!/bin/bash
pip install -r sprint_1/requirements.txt
```

### 6. Click **"Crear entorno"**

### 7. Vuelves al formulario "Editar rutina". El dropdown de entorno ahora muestra "Default" — cámbialo:

- Click el dropdown
- Selecciona **"MejorAhora"** (el que acabas de crear)
- Click **"Guardar"** abajo

### 8. **Repite la asignación del entorno** en las otras 3 routines:
- MejorAhora Pipeline PM → Editar → Entorno: MejorAhora → Guardar
- MejorAhora Mantenimiento AM → Editar → Entorno: MejorAhora → Guardar
- MejorAhora Mantenimiento PM → Editar → Entorno: MejorAhora → Guardar

> El entorno se crea UNA vez, pero hay que asignarlo a cada routine.

### 9. **Smoke test:** click "Ejecutar ahora" en "MejorAhora Pipeline AM". Debe correr `pip install` + `bash run_pipeline.sh`. Mira los logs.

---

## Si el run falla con error de credenciales

Verifica:
1. Los JSON están dentro de comillas simples `'...'`
2. El SA tiene `client_email` y `private_key`
3. El OAuth tiene `refresh_token`
4. El HubSpot empieza con `pat-`

Si todo está bien y aún falla, mándame screenshot del error.

---

## Después de validar

Una vez los pipelines corren OK:
1. Vuelve al repo en GitHub → Settings → Danger Zone → Change visibility → **Privatizar**
2. Las routines siguen funcionando porque ya tienen la conexión OAuth cacheada
3. Deshabilita las Windows Tasks: `schtasks /change /tn "MejorAhora\Pipeline Davivienda AM" /disable` y `/PM`
4. Sistema 100% en cloud ✅

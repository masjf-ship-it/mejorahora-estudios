# MejorAhora SAS — Pipeline de Estudios Hipotecarios

Automatización PDF → Excel para estudios financieros de optimización de créditos hipotecarios. Hoy operativo para **Davivienda**, otros bancos en backlog.

## Quick start

```cmd
:: Instalar dependencias (una sola vez)
cd sprint_1
pip install -r requirements.txt

:: Activar pre-commit hook (una sola vez)
cd ..
maintenance\install_hooks.cmd

:: Registrar tareas Windows AM/PM (una sola vez)
maintenance\install_task.cmd

:: Correr pipeline manualmente
run_pipeline.bat
```

## Documentación canónica (orden de autoridad)

1. [`MOM_DAVIVIENDA.md`](MOM_DAVIVIENDA.md) — reglas específicas Davivienda. **Gana sobre MASTER_RULES en contradicción.**
2. [`MASTER_RULES.md`](MASTER_RULES.md) — reglas generales del proyecto (todos los bancos).
3. [`sprint_1/config_reglas.py`](sprint_1/config_reglas.py) — fuente única de constantes numéricas.
4. [`ESTADO_PROYECTO.md`](ESTADO_PROYECTO.md) — dashboard / roadmap (no es fuente de reglas).
5. [`CHANGELOG.md`](CHANGELOG.md) — traza histórica.
6. [`MANUAL_EXTRACTO_BANCOS.md`](MANUAL_EXTRACTO_BANCOS.md) — cheatsheet por banco.
7. [`CLAUDE.md`](CLAUDE.md) — orientación para Claude Code (pointer corto, no duplica reglas).

## Arquitectura en una línea

`REGISTROS (Sheet humano)` → `STAGING (Sheet pipeline)` → `pipeline_davivienda.py` → `Excel (PESOS.xlsx template)` → `Drive §4.2 (analistas)` → `STAGING update con link`

Detalle E2E (17 pasos): MASTER_RULES §6.

## Componentes principales

| Pieza | Archivo | Rol |
|---|---|---|
| Pipeline E2E | [`sprint_1/pipeline_davivienda.py`](sprint_1/pipeline_davivienda.py) | Orquestador por cliente |
| Publicador STAGING | [`sprint_1/listar_pendientes_hoy.py`](sprint_1/listar_pendientes_hoy.py) | REGISTROS → STAGING |
| Extractor PDF | [`sprint_1/extract_davivienda_pdf.py`](sprint_1/extract_davivienda_pdf.py) | pdfplumber primary |
| Vision fallback | [`sprint_1/vision_extractor.py`](sprint_1/vision_extractor.py) | Vertex AI Gemini si pdfplumber falla |
| HubSpot client | [`sprint_1/hubspot_client.py`](sprint_1/hubspot_client.py) | Datos de cliente |
| Proponedor plazos | [`sprint_1/proponedor_plazos.py`](sprint_1/proponedor_plazos.py) | Mode A + Mode B + Régimen E |
| Excel populator | [`sprint_1/excel_populator.py`](sprint_1/excel_populator.py) | Inyecta datos en `PESOS.xlsx` |
| Validador M1 | [`sprint_1/validar_extraccion_davivienda.py`](sprint_1/validar_extraccion_davivienda.py) | Pre-Excel |
| Validador M2 | [`sprint_1/validar_excel_generado.py`](sprint_1/validar_excel_generado.py) | Post-Excel |
| Smoke test | [`sprint_1/smoke_test_prerun.py`](sprint_1/smoke_test_prerun.py) | Pre-condiciones antes del pipeline |
| Métricas | [`sprint_1/metricas_pipeline.py`](sprint_1/metricas_pipeline.py) | Agrega `_logs/pipeline_*.json` |
| Tests golden | [`sprint_1/test_fase2.py`](sprint_1/test_fase2.py) | 16/16 PASS (A–P), script lineal |
| Tests pytest | [`sprint_1/tests/`](sprint_1/tests/) | 18/18 PASS (parcial migración) |
| Mantenimiento | [`maintenance/maintenance.py`](maintenance/maintenance.py) | 12h cycle (AM/PM) |
| Pre-commit hook | [`.githooks/pre-commit`](.githooks/pre-commit) | Bloquea secrets, blacklist IDs, syntax, drift |

## Comandos comunes

```cmd
:: Pipeline producción (corre tareas Windows AM/PM automáticamente)
run_pipeline.bat

:: Pipeline manual / debugging
cd sprint_1
py listar_pendientes_hoy.py --banco davivienda
py pipeline_davivienda.py --dry-run --max 3
py pipeline_davivienda.py --nombre "FERNANDO" --force

:: Tests
py sprint_1\test_fase2.py             :: 16/16 PASS golden suite
py -m pytest sprint_1/tests/ -v       :: 18/18 PASS pytest suite

:: Métricas semanales
py sprint_1\metricas_pipeline.py --dias 7

:: Validación pre-pipeline
py sprint_1\smoke_test_prerun.py

:: OAuth re-auth (cuando falla con invalid_grant)
cd sprint_1
py diag_oauth.py > diag_oauth.txt 2>&1
py drive_oauth_setup.py

:: Mantenimiento manual (dry-run primero)
py maintenance\maintenance.py --dry-run
py maintenance\maintenance.py
```

## Output convention (MASTER_RULES §18)

**Siempre redirigir output a archivo. Nunca pedir screenshots de consola.**

```cmd
py <script>.py > diag_<contexto>.txt 2>&1
```

## Estado del proyecto

- **Davivienda:** ✅ Operativo (`pipeline_davivienda.py`, R-DVV-01..18)
- **Bancolombia:** 🟡 Pendiente — esperar 5 días sin errores en Davivienda
- **Caja Social, FNA, Banco de Bogotá, AV Villas:** ⚪ Backlog

Ver [ESTADO_PROYECTO.md](ESTADO_PROYECTO.md) para detalle.

## Política de actualización de reglas

Cualquier cambio de regla obliga (MASTER_RULES §19):

1. Editar `MASTER_RULES.md` o `MOM_<BANCO>.md` (no solo chat)
2. Borrar la regla vieja contradictoria del doc canónico (no marcadores `[REVOCADA]`)
3. Registrar en `CHANGELOG.md` la transición vieja → nueva
4. Bumpear versión del doc
5. Reconciliar con `sprint_1/config_reglas.py` si cambia constante
6. Reconciliar con `sprint_1/test_fase2.py` o `sprint_1/tests/` si cambia assert

El pre-commit hook bloquea drift.

## Privacidad y seguridad

- Tokens y credenciales **nunca** se commitean (`.gitignore` + pre-commit hook).
- Excel de estudios = propiedad MejorAhora; nunca a carpetas cliente, solo Drive §4.2.
- Cumplimiento Habeas Data (Ley 1581 de 2012).
- Vertex AI Gemini procesa páginas de PDF — modelo `gemini-2.5-pro` (no bajar a flash sin autorización).

## Contacto técnico

Mantenedor: Jose (`reducciondecreditos2@gmail.com`).

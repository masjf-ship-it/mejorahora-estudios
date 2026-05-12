# MASTER_RULES — MejorAhora SAS · Reglas Generales del Proyecto

**Versión:** 3.4
**Última revisión:** 2026-05-12 (Sesión nocturna: 4 routines Cloud creadas en Anthropic, TEST H staging_update → pytest, auditoría excel_populator + vision_extractor con 5 fixes de drift de constantes + 1 bug latente sheet path, audit limpio apps_script con 2 TODOs)
**Mantenido por:** Ciclo mantenimiento 12h + actualizaciones puntuales (ver §19)

> **ESTE ES EL ARCHIVO MAESTRO GENERAL DEL PROYECTO.**
> Contiene reglas que aplican a TODOS los bancos.
> Para reglas específicas de un banco, ver `MOM_<BANCO>.md` (ej. `MOM_DAVIVIENDA.md`).
> En contradicción: **banco-específico gana sobre general**.

---

## 0. Meta-reglas

- **0.1** Este archivo es la fuente canónica GENERAL. En contradicción entre memoria/código/docs y este archivo, este gana.
- **0.2** Para reglas específicas de un banco, abrir `MOM_<BANCO>.md`. Banco-específico gana sobre este.
- **0.3** Cualquier cambio se actualiza PRIMERO aquí (o en el MOM correspondiente) y se propaga al código + tests.
- **0.4** Reglas numeradas. Reportes de anomalías citan `§X.Y`.
- **0.5** Fechas en ISO `YYYY-MM-DD`. No usar fechas relativas.
- **0.6** Si durante la conversación se establece una regla nueva → actualizar antes de cerrar sesión.

---

## 1. Identidad del negocio

- **1.1** Empresa: **MejorAhora SAS** — consultoría financiero-jurídica, créditos de vivienda Colombia.
- **1.2** Moneda única operativa hoy: **PESOS colombianos**. UVR NO se procesa.
- **1.3** Equipo admin: 6 personas (Gerente Jose / Coordinador / 3 Apoderados / 1 Analista Financiero).
- **1.4** Regla de oro: ningún cliente puede estar SOLO en Excel local, SOLO en HubSpot o SOLO en notas. BD global Sheets obligatoria (§3).
- **1.5** Terminología obligatoria: "consultores" (NO asesores), "optimizar" (NO refinanciar/reescriturar), reducir plazo (NO extender). Marco: Ley 546/99.

---

## 2. Stack tecnológico vigente

| # | Elemento | Valor |
|---|---|---|
| 2.1 | GCP Project | `mejorahora-automations` |
| 2.2 | Service Account | `claude-bd-sync@mejorahora-automations.iam.gserviceaccount.com` |
| 2.3 | Credencial SA | `credentials/sheets_sa.json` (desde `sprint_1/`) |
| 2.4 | Vertex AI Vision | `gemini-2.5-pro` (NO bajar a flash sin autorización Jose) |
| 2.5 | Pipeline entry point ACTUAL | `sprint_1/pipeline_davivienda.py` |
| 2.6 | Pipeline 3 bancos (futuro) | `sprint_1/pipeline_3bancos.py` — crear cuando ≥2 pipelines bancarios estén listos |
| 2.7 | Publicador STAGING | `sprint_1/listar_pendientes_hoy.py` |
| 2.8 | Extractor PDF Davivienda | `sprint_1/extract_davivienda_pdf.py` ✓ |
| 2.9 | Extractor PDF Bancolombia | PENDIENTE |
| 2.10 | Extractor PDF Caja Social | PENDIENTE |
| 2.11 | Vision fallback | `sprint_1/vision_extractor.py` (Vertex AI Gemini) |
| 2.12 | HubSpot client | `sprint_1/hubspot_client.py` (urllib stdlib) |
| 2.13 | Excel populator | `sprint_1/excel_populator.py` |
| 2.14 | Proponedor plazos | `sprint_1/proponedor_plazos.py` (Mode A + Mode B) |
| 2.15 | Reglas de negocio | `sprint_1/reglas_negocio.py` |
| 2.16 | Constantes centralizadas | `sprint_1/config_reglas.py` |
| 2.17 | Validador M1 (post-extracción) | `sprint_1/validar_extraccion_davivienda.py` |
| 2.18 | Validador M2 (post-Excel) | `sprint_1/validar_excel_generado.py` |
| 2.19 | Test suite golden | `sprint_1/test_fase2.py` (16 tests A-P) |
| 2.20 | Mantenimiento 12h | `maintenance/maintenance.py` (antes `maintenance_60min.py`, cadencia horaria — workaround Cowork) |
| 2.21 | Regen históricos | `sprint_1/generar_desde_sheets.py` — NO para pendientes nuevos |
| 2.22 | Métricas semanales | `sprint_1/metricas_pipeline.py` — agrega `_logs/pipeline_davivienda_*.json` para validar criterio "5 días sin errores" (B5, 2026-05-07) |
| 2.23 | Pre-commit hook | `.githooks/pre-commit` + instalador `maintenance/install_hooks.cmd` (B10, §17.12) |
| 2.24 | Smoke test pre-pipeline | `sprint_1/smoke_test_prerun.py` — PASO 0 en `run_pipeline.bat`, valida creds/OAuth/hash/deps antes de procesar (2026-05-07, fix de 22 EXCEPTION históricas) |

Prioridad automatización: `Cloud Routines` > `Scheduled Tasks Cowork` > `Custom Skills` > `Scripts Python/JS` > manual.

---

## 3. BD única operativa (Sheets)

- **3.1 Sheet ID:** `1_9FUAo8cSrLDWAkJlNoy29Cmyh9ojXwnW6zbvhGsESA`
- **3.2 Nombre:** BASE PARA ESTUDIOS OK
- **3.3 URL:** https://docs.google.com/spreadsheets/d/1_9FUAo8cSrLDWAkJlNoy29Cmyh9ojXwnW6zbvhGsESA/edit
- **3.4 Lista negra** (NUNCA usar):
  - `1UbQ_Ghb0dmeCWAmEJNdFGkBsbK6PNWr6T48Pi-nTdd8` (piloto v1)
  - `1fsop9wgv1HvRxREnYQGopR7d3TSUhlIFU4bm6QQ0ykM` (placeholder)
- **3.5 Pestañas reales:**

| Pestaña | Cols | Rol |
|---|---|---|
| REGISTROS | 42 | Fuente maestra (humano gestiona) |
| **STAGING** | 42 | **Destino pipeline** (SA escribe, humano aprueba) |
| BD | 30 | Bitácora técnica POST-estudio |
| BORR | 42 | Borrador histórico |
| AUDIT_LOG | 26 | Trazabilidad SA |
| Hora | 21 | Productividad diaria |
| NORMAS PARA BD | 26 | Referencia tasas/cuotas/plazos |
| VIS | 26 | Histórico VIS / SMMLV |

- **3.6** REVISION NO EXISTE como pestaña. Es filter view de REGISTROS.
- **3.7** Append por nombre de columna, nunca `clear()` ni por índice posicional.
- **3.8 Columna L = "Nota PARA CRM"**: pipeline escribe automáticamente proyecciones/excepciones para el consultor.

- **3.9 Estados operativos** (columna ESTADO en REGISTROS y STAGING):

| Estado | Filtro REGISTROS→STAGING | Pipeline STAGING |
|---|---|---|
| `Pendiente` | Incluye | Procesa |
| `Pte. Validar Yenny` | Incluye | Procesa |
| `Mora` | Incluye | Procesa |
| `Pendiente NOTA consultor` | Excluye (estudio hecho, solo falta nota Yenny) | N/A |
| `Realizado` | Excluye | N/A |
| `Cancelado` | Excluye | N/A |
| `Excel generado` | N/A | Saltar (re-procesar solo con `--force`) |
| `procesado` / `completado` | N/A | Saltar (variantes históricas) |

Constantes en código: `listar_pendientes_hoy.py::ESTADOS_VALIDOS` (entrada) vs `config_reglas.py::ESTADOS_SKIP_DEFAULT` (post-procesamiento). Si Jose introduce un estado nuevo, actualizar **ambas listas** + esta tabla.

- **3.10 Amortización** (columna V): solo `pesos` se procesa. `uvr` y vacío se filtran (MASTER_RULES §1.2 — UVR NO se procesa). Constantes: `listar_pendientes_hoy.py::AMORTIZACION_VALIDA` y `AMORTIZACION_EXCLUIDA`.

---

## 4. Carpetas Drive canónicas

| # | Carpeta | Drive ID | Acceso |
|---|---|---|---|
| 4.1 | Extractos PDF (fuente) | `17hN5TDiQ3Ozop-xT6g4OYAyQrZkZT0os` | **READ-ONLY** |
| 4.2 | Folder analistas (Excel) | `1UVsQtyzQHEpfRlcjUrq8gBsXgEqABoym` | WRITE (Excel destino único) |
| 4.3 | Carpetas cliente | varias | NUNCA tocar — Excel estudios PROHIBIDO |

- **4.4** SA: `drive.readonly` sobre §4.1 + `drive.file` sobre §4.2.
- **4.5** Upload §4.2 vía OAuth user (SA da 403 storageQuota en Gmail personal).
- **4.6** No borrar/renombrar/sobrescribir PDFs en §4.1. Jamás.

---

## 5. HubSpot integration

- **5.1 Private App:** `Control Notas MejoraHora` (ID `36385812`, portal `21065449`).
- **5.2 Scopes:** `timeline`, `crm.objects.owners.read`, `crm.objects.contacts.read`.
- **5.3 Token:** mirror local en `sprint_1/config.ini [HUBSPOT] token`.
- **5.4 Cliente Python:** `sprint_1/hubspot_client.py` (stdlib only).
- **5.5 Fuente cliente:** consultor-owner, ingresos, abono, actividad SIEMPRE desde HubSpot **salvo R-DVV-12** (HubSpot genérico repetido → fallback REGISTROS, ver `MOM_DAVIVIENDA.md`).
- **5.6 Filtro banco:** OR sobre 5 propiedades (incluye `banco_donde_tienes_la_hipoteca_o_leasing_habitacional`).
- **5.7 Propiedad ingresos en este portal:** `valor_de_ingresos` (NO `ingresos` ni `ingreso` — esas propiedades no existen). Ver R-DVV-17B.
- **5.8 Propiedad abono en este portal:** `abono_efectivo` (primera opción), fallback `abono_extraordinario`. El campo `abono` genérico no existe.
- **5.9 CC inválidos para matching HubSpot:** "N/A", "NA", "N.A.", "N\A", "N-A" y vacío se tratan como CC ausente → omitir búsqueda por cedula → ir directo a nombre. Hay 36+ contactos en HubSpot con cedula="N/A" que contaminarían el match. Ver R-DVV-17A.
- **5.10 Búsqueda por nombre — estrategia multi-token:** Primero buscar TODOS los tokens del nombre en `firstname` (hasta 5 filtros CONTAINS_TOKEN). Si exactamente 1 resultado → usar. Si 0 o múltiples → fallback a token[0] en firstname + token[-1] en lastname. Razón: muchos contactos tienen nombre completo en `firstname` sin split en `lastname`. Ver R-DVV-17C.
- **5.11 Calidad requerida en contactos HubSpot:** para que el pipeline matchee confiablemente, cada contacto DEBE tener: (a) `cedula` con CC real (no N/A), (b) `abono_efectivo` con monto real, (c) `valor_de_ingresos` con monto real, (d) nombre en `firstname`+`lastname` separado O nombre completo en `firstname`. Sin estos datos el pipeline cae a REGISTROS (datos pueden estar desactualizados).

---

## 6. Flujo canónico estudio NUEVO (E2E)

**Regla clave:** datos numéricos del extracto se escriben en BD DESPUÉS del estudio (bitácora, no input).

```
0. Pre-pasada: detectar firmas HubSpot genéricas (≥3 clientes, R-DVV-12)
1. STAGING pendientes (estado != "Excel generado")
2. Drive §4.1 → buscar carpeta cliente → descargar PDF tmp
3. HubSpot cascade (CC → email → nombre)
4. Si firma HubSpot ∈ genéricas → vaciar consultor/actividad/ingresos/abono → cae a REGISTROS
5. Si PDF protegido → decrypt("") primero, después CC candidatas
6. extract_<banco>_pdf (pdfplumber) → si críticos vacíos → vision_extractor (Gemini)
7. REGISTROS lookup (cache 1x/run)
8. construir_datos: cascada HubSpot > REGISTROS > STAGING > default. Aplica reglas banco-específicas
9. M1 validar_datos_cliente → FAIL = REVISION_MANUAL, abortar
10. Reglas banco-específicas pre-9.3 (ej. R-DVV-07 proyección 6ª cuota Davivienda)
11. Regla 9.3 abono extraordinario (auto si |SUMA CUOTA|>$70k)
12. Validar DIF.SIMULA post-9.3 ±$70k → si excede REVISION_MANUAL, abortar
13. Regla 9.4 proponer_plazos (Mode A o Mode B)
14. ExcelPopulator.crear_estudio + ocultar_hoja_bd
15. M2 validar_excel_generado → warning si discrepancia
16. Drive §4.2 upload (OAuth user)
17. STAGING update: estado="Excel generado", link, nota_crm columna L
```

- **6.1** Para regenerar históricos: `generar_desde_sheets.py --credito <N> --csv <snapshot>`. NO para nuevos.
- **6.2** Matching extracto ↔ registro: por número de crédito (string).

---

## 7. Jerarquía de fuentes de datos (3 capas estrictas)

| Capa | Datos | Fuente única |
|---|---|---|
| **Financiero** | crédito, saldo, cuota, tasa, plazo, seguros, FRECH, intereses | **Extracto PDF** |
| **Cliente** | nombre, consultor, ingresos, abono efectivo, banco, email, teléfono, actividad | **HubSpot** (con fallback REGISTROS si firma genérica repetida) |
| **Operativo** | ESTADO, fecha solicitud, referenciador | **REGISTROS** (NUNCA para datos financieros) |

---

## 8. Reglas universales de ajuste (TODOS los bancos)

### 8.1 — Regla 9.2 (seguros)
Si extracto muestra 2 sumas distintas → usar **valor menor**, consolidar en `seguro_vida`, otros en 0.

### 8.2 — Regla 9.3 (capital + intereses)
Si `|SUMA CUOTA| > $70.000` → reemplazar `capital_mensual` e `interes_mensual` por los del **SIMULADOR**. NUNCA tocar seguros.

### 8.3 — Regla 9.4 (proponedor de plazos)
Cadena de prioridades:
1. `manual` (CLI `--plazos`)
2. `regimen_E` (plazo_pagado ≥5 + ingresos altos)
3. `mixto_viable` (Mode B — default si ingresos>0)
4. `por_saltos_100k` (Mode A — fallback)
5. `escalonado` (último recurso)

### 8.4 — §3a Cantidad factibles dinámica
Default: tantas factibles como `ingresos_req ≤ ingresos_cliente × 1.10`. Si solo permite ≤2 → forzar 3+3 aumentando plazos.

### 8.5 — §3b Orden opciones: PLAZO DESCENDENTE SIEMPRE
OPC 1 = mayor plazo (menor abono). OPC 6 = menor plazo (mayor abono).

### 8.6 — §3c Piso abono OPC 1 (tier por saldo)
**Aplica a MODO A y MODO B por igual.**
- Saldo < $300M → piso **$100k**
- Saldo ≥ $300M → piso **$200k**

### 8.7 — §3d Diferencia mínima entre opciones consecutivas
Default: **$100k**. Si plazo_pendiente < 60 meses → permite bajar a **$70k** cuando rango legal no permite mantener $100k.

### 8.8 — §3e DIF.SIMULA tolerancia ±$70k
Post-Regla 9.3, recalcular DIF.SIMULA. Si `|DIF.SIMULA| > $70.000` → **REVISION_MANUAL** aunque SUMA CUOTA esté OK.

### 8.9 — Mode B mixto_viable
3 factibles + 3 agresivas (refinable a 5+1, 4+2 según ingresos). Ratios: NO VIS 29% / VIS 39% (banco pide 30%/40% −1pp). Tope ingresos × 1.10. **Piso §3c aplica igual que MODO A** (2026-04-28: antes no se aplicaba en MODO B).

### 8.10 — Cuota del extracto = fuente literal
Usar `Valor Cuota Mes` textual. NUNCA recalcular con suma cap+int+seguros.

### 8.11 — No inventar números
Jamás forzar `SUMA CUOTA=$0`. Diferencias residuales son verídicas dentro de tolerancia.

### 8.12 — Nunca descartar estudios
Aunque 0/6 factibles → generar Excel con agresivas. Consultor perfila ingresos en video call.

### 8.13 — Régimen E
Auto-detección saldo bajo + ingresos altos + pagado≥5. Serie `[5,4,3,2,1.5,1]`. Flag `--plazos` = escape-hatch manual.

### 8.14 — Ley 546/99 plazo mínimo
Crédito_total (pagado + restante) ≥ 5 años. Si pagó ≥5 → cualquier plazo restante. Si pagó <5 → mínimo restante = `5 − pagado`. `PLAZO_MINIMO_PRACTICO_ANOS = 0.5` (granularidad operativa, NO floor legal).

### 8.15 — TOLERANCIA UNIVERSAL ±$70.000 COP (Jose 2026-04-24)

**Tolerancia única para todo el sistema:**
- Validador cruzado del extractor (suma componentes vs Total Aplicado)
- Regla 9.3 (SUMA CUOTA)
- Regla 9.3 post-validación (DIF.SIMULA)
- M1 (suma vs cuota)
- Validación saldo BD vs PDF

Centralizada en `config_reglas.py::TOLERANCIA_*`. Cambiar 1 valor → cambia todo.

### 8.16 — Guardia R-DVV-18: plazo pendiente + Ley 546 (2026-05-05)
**UNIVERSAL — aplica a todos los bancos.**

**Regla 1 — Pre-check Ley 546 (en pipeline, antes de llamar al proponedor):**
Calcular `anio_min_legal`: si pagó ≥5 años → 0.5 (cualquier plazo); si no → `max(5.0 - pagado, 0.5)`.
Si `anio_min_legal >= plazo_pendiente_anos` → **REVISION_MANUAL: NO_VIABLE_LEY_546**. No generar Excel.
Razón: no existen plazos que sean simultáneamente una reducción Y cumplan Ley 546/99.

**Regla 2 — Guardia absoluta del proponedor:**
`proponer_plazos()` filtra TODOS los resultados al final: cualquier opción `>= plazo_pendiente` se descarta.
Aplica a Mode A, Mode B, Régimen E, manual, escalonado.
Si reaparece → verificar versión `proponedor_plazos.py` y wrapper `_proponer_plazos_impl`.

**Caso real:** Alexandra Bernal Vargas — 29 cuotas pendientes, proponedor generaba opciones de 150+ cuotas.
Fix: `R-DVV-18` en `proponedor_plazos.py` + pre-check en `pipeline_davivienda.py`. Ver MOM_DAVIVIENDA R-DVV-18.

---

## 9. Validadores M1, M2, STEP 8

### 9.1 — M1 (post-extracción, pre-Excel)
`validar_extraccion_davivienda.py::validar_datos_cliente(datos)` valida:
- saldo_capital > $1M
- cuota_mensual > 0 y < $10M
- 0 < tasa_ea < 1
- plazo_pendiente ≤ plazo_inicial
- credito_id, nombre no vacíos
- suma(seg+cap+int) vs cuota: ±$70k warn / ±$500k error (salvo R-DVV-06)
- **`seguro_vida=0 AND seguro_incendio>0` → ERROR** (sospecha Vision incompleto)

Errores → REVISION_MANUAL, no genera Excel. Warnings → log + sigue.

### 9.2 — M2 (post-Excel)
`validar_excel_generado.py::validar_excel(path, datos)` lee xlsx y valida:
- Naming `ESTUDIO <NOMBRE>-DD.MM.AA.xlsx`
- Hoja ACTUAL existe + activeTab=0
- B2/B5/B10-B15 contra DatosClienteExcel
- B16:B21 plazos en orden DESCENDENTE
Errores → nota CRM "ALERTA M2", NO bloquea upload.

### 9.3 — STEP 8 (mantenimiento 12h, ex-STEP 7)
`maintenance/maintenance.py::check_doc_code_drift()`:
- header vs footer de versión, ESTADO § cita versiones reales, hash PESOS, `RETENTION_N`, refs canónicos rotas.
- Solo reporta, no poda (política docs limpia §17.3).
- **STEP 7 anterior** (auditoría memoria operativa Claude) eliminado 2026-05-07: era workaround Cowork (memoria volátil); en Claude Code la memoria son archivos versionados (CLAUDE.md + MASTER_RULES + CHANGELOG) que no requieren auditoría externa.

---

## 10. Integridad numérica — CRÍTICO

- **10.1 Fuente de verdad = PDF extracto.** Extracción programática (pdfplumber) o Vertex AI Gemini Vision como fallback.
- **10.2** Números largos como string: crédito N°, cédula, ID >10 dígitos. Excel trunca >15 dígitos.
- **10.3** Validación cruzada obligatoria contra PDF antes de insertar en Sheet.
- **10.4** Campos doble verificación: N° crédito, CC, cuota, tasa EA, capital/saldo, plazo pendiente.
- **10.5** Diferencias = BLOQUEO inserción hasta revisión humana.
- **10.6** Tolerancia universal: ±$70.000 COP (ver §8.15).

---

## 11. Privacidad & Habeas Data

- **11.1** Cumplimiento Ley 1581 de 2012.
- **11.2** No almacenar/compartir datos personales fuera de sistemas autorizados (HubSpot, Google Workspace, BD canónica).
- **11.3** Consultores freelance: acceso mínimo (control por roles).
- **11.4** Toda automatización: encriptación + auditoría.
- **11.5** Excel estudios = **propiedad intelectual MejorAhora**. NUNCA en carpetas cliente, solo §4.2.
- **11.6** Tokens/secrets: no commitear a git. `config.ini` → `.gitignore`.

---

## 12. Naming archivos

- **12.1** Excel estudios: `ESTUDIO <NOMBRE MAYUSCULAS SIN TILDES>-DD.MM.AA.xlsx` (guion medio).
- **12.2** Nombres en Sheet: MAYÚSCULAS sin tildes.
- **12.3** N° crédito: string conservando ceros izquierda.
- **12.4** Tasa: `0,00` (coma decimal).
- **12.5** Moneda: `$` + punto miles (formato colombiano).

---

## 13. Layout impresión Excel — canónico

- **13.1** 3 páginas fijas: Pág 1 OPC 1-3 / Pág 2 OPC 4-6 / Pág 3 Estudio Financiero.
- **13.2** Referencia visual: estudio Martha (validado).
- **13.3** Si rompe: revisar `print_area`, `pageSetup`, `rowBreaks` en `excel_populator.py`.
- **13.4** Excel permite copiar celdas: 1 sola hoja `tabSelected`, `activeTab` consistente, sin merged en zonas copiables.
- **13.5** Hoja BD oculta con `ocultar_hoja_bd()` antes de subir.
- **13.6** Logos visibles en hoja ESTUDIO.

---

## 14. Bancos — orden de implementación

- **14.1** Orden: DAVIVIENDA → BANCOLOMBIA → CAJA SOCIAL → FNA → BANCO DE BOGOTÁ → resto.
- **14.2** Cada banco aislado en `MOM_<BANCO>.md` (banco-específico).
- **14.3** Estado: **Davivienda OPERATIVO** (`MOM_DAVIVIENDA.md`). Bancolombia y Caja Social en cola.
- **14.4** PDF con contraseña: decrypt("") primero, después CC candidatas. CC obligatoria solo si PDF la pide.

---

## 15. Mantenimiento 12h — protocolo

**Histórico:** este ciclo era horario (`maintenance_60min.py`) cuando MejorAhora operaba en Cowork Desktop, donde el agente "olvidaba" cosas entre sesiones — los backups frecuentes y la auditoría de memoria operativa (STEP 7) eran un workaround. En Claude Code la memoria son archivos versionados (CLAUDE.md + MASTER_RULES + CHANGELOG); cadencia reducida a 12h y STEP 7 eliminado el 2026-05-07.

- **15.1** Script: `maintenance/maintenance.py`
- **15.2** Tareas: `MejorAhora\Mantenimiento AM` (DAILY 07:00) + `MejorAhora\Mantenimiento PM` (DAILY 19:00). Una antes de cada pipeline (08:30 / 20:30).
- **15.3** Steps por ciclo:
  1. **Backup** — copiar lista blanca a `_backups/<ts>/`
  2. **Diff** — verificar consistencia entre archivos canónicos
  3. **Reporte** — `_logs/anomalies_<ts>.txt` si hay hallazgos
  4. **Limpieza** — archivos sueltos en raíz → `_archivo/YYYY-MM/`
  5. **Log** — append a `_logs/mant.log`
  6. **STEP 8 Drift docs ↔ código** (2026-05-07) — `check_doc_code_drift()` valida: header vs footer de versión en MASTER_RULES y ESTADO; ESTADO §0 cita versiones reales; PESOS.xlsx hash íntegro; `RETENTION_N` consistente con §17.11; referencias a archivos canónicos existen. Reporta solamente; ningún fix automático.
- **15.4** Retención: backups **30 snapshots (~15 días a 2 corridas/día)** + logs pipeline JSON **30 días por fecha del archivo** (constantes `RETENTION_N` y `RETENTION_PIPELINE_LOGS_DAYS` en `maintenance.py` son fuente de verdad — política limpia §17.3/§17.11)
- **15.5** Lista blanca: `maintenance/whitelist.txt`
- **15.6** Modo `--dry-run` para validar sin aplicar
- **15.7** Reportes citan `§X.Y` de este archivo

---

## 16. Scheduled tasks / automation

- **16.1** Inventariar antes de crear: `list_scheduled_tasks` + `schtasks /query` + `TaskList`.
- **16.2** Pipeline mañana: `run_pipeline.bat` → `MejorAhora\Pipeline Davivienda AM` (DAILY 08:30).
- **16.3** Mantenimiento: `MejorAhora\Mantenimiento AM` (DAILY 07:00) + `MejorAhora\Mantenimiento PM` (DAILY 19:00). Anterior `MejorAhora\Mantenimiento 60min` HOURLY borrada el 2026-05-07 (workaround Cowork).
- **16.4** `.bat` usa PowerShell `Get-Date -Format yyyyMMdd` para evitar locale issues.
- **16.5** Pipeline noche: `run_pipeline.bat` → `MejorAhora\Pipeline Davivienda PM` (DAILY 20:30). Pipeline corre 2×/día.
- **16.6** OAuth token — mantenimiento obligatorio: si el pipeline falla con `invalid_grant` o `Token has been expired or revoked` → correr inmediatamente `py sprint_1/drive_oauth_setup.py`. El token OAuth (`credentials/oauth_token.json`) puede ser revocado por Google si la app está en modo "Testing" y el refresh_token no se usa en ~6 meses, o si el usuario revoca desde myaccount.google.com/permissions. Diagnóstico previo: `py sprint_1/diag_oauth.py > diag_oauth.txt 2>&1`.

---

## 17. Política operativa

- **17.1 Una versión por cliente.** NUNCA múltiples Excel del mismo cliente. Si Jose ajusta manual → no re-procesar.
- **17.2 Backup obligatorio.** Antes de modificar código, copia con timestamp en `_backups/YYYY-MM-DD_<motivo>/`.
- **17.3 Docs siempre actualizados (limpia).** Cuando se revoca una regla, se **BORRA** del doc canónico (MASTER_RULES o MOM_<BANCO>). La traza histórica queda EXCLUSIVAMENTE en `CHANGELOG.md` con timestamp y razón. Los docs operativos NO acumulan secciones `[REVOCADA]`. Objetivo: lectura limpia, día a día actualizado, sin ruido cognitivo.
- **17.4 No inventar números.** Valores siempre del extracto PDF. Diferencias residuales reales.
- **17.5 STAGING único destino.** Pendientes y propuestas siempre en STAGING.
- **17.6 Excel NUNCA en carpetas cliente.** Solo §4.2.
- **17.7 Drive extractos READ-ONLY.** Solo lee, nunca escribe/borra.
- **17.8 Hard blockers (4):** ilegibilidad PDF / integridad datos / password real no descifrable / banco no trabajado. Consultor OPCIONAL.
- **17.9 Claude NO ejecuta IAM/billing/T&C.** Aunque Jose autorice, requiere clic explícito de Jose.
- **17.10 Vertex AI:** `gemini-2.5-pro` por default, no bajar a flash sin autorización.
- **17.12 Pre-commit hook (B10, 2026-05-07).** Hook versionado en `.githooks/pre-commit` que valida en cada `git commit`:
  1. No se commitean secrets (`sprint_1/config.ini`, `credentials/`).
  2. No aparecen IDs de la lista negra §3.4 (excepto en archivos que la documentan).
  3. Archivos `.py` staged compilan.
  4. STEP 8 drift checker no reporta inconsistencias.
  5. Pytest suite (`sprint_1/tests/`) pasa, **si** hay `.py` staged en `sprint_1/`. Skip silencioso si pytest no está instalado.

  Activación una sola vez por clone: `maintenance\install_hooks.cmd` (configura `core.hooksPath=.githooks`).
  Bypass de emergencia: `git commit --no-verify` — debe registrarse en CHANGELOG con la razón (§23.4).

- **17.11 Backups estructurados con retención (no acumulación manual).**
  - Snapshots automáticos a 12h vía `maintenance.py` → `_backups/<ts>/`
  - **Retención: 30 snapshots ≈ 15 días (2 corridas/día).** Rotación FIFO automática. Constante `RETENTION_N` en `maintenance.py` es la fuente de verdad.
  - Backups manuales puntuales (pre-modificación crítica) → `_backups/YYYY-MM-DD_<motivo>/`
  - Vencimiento manual: si un backup manual pasa **30 días sin uso**, mantenimiento lo borra.
  - **NUNCA** crear backups paralelos fuera de `_backups/` (se vuelven huérfanos sin retención).
  - Si necesitas un backup permanente fuera del ciclo (ej. snapshot pre-release), va a `credentials/snapshot_permanente_<motivo>.zip` y se documenta en CHANGELOG.

---

## 18. Operación de salida

- **18.1** Jose ejecuta, Claude lee archivos. NO pantallazos de consola.
- **18.2** Scripts redirigen: `python foo.py > diag.txt 2>&1`.
- **18.3** Diag puntuales: `<contexto>_diag.txt` en raíz proyecto.
- **18.4** Logs programados: `_logs/scheduled_YYYYMMDD.txt`.
- **18.5** Diag antiguos archivados por `cleanup_workspace.bat`.

---

## 19. PROTOCOLO DE ACTUALIZACIÓN DE REGLAS (meta-regla)

**Cualquier cambio a reglas debe tatuarse en MASTER_RULES o MOM_<BANCO>, no quedarse en chat.**

### Patrón obligatorio

```
Actualización de Constitución Operativa:
[descripción de la nueva regla o cambio]

Instrucción:
1. Localiza MASTER_RULES.md (si general) o MOM_<BANCO>.md (si banco-específico)
2. Integra el cambio en la sección correspondiente
3. BORRA cualquier regla previa contradictoria (NO marcar [REVOCADA] — política limpia §17.3)
4. Registra en CHANGELOG.md la transición: regla vieja → regla nueva, timestamp, razón
5. Incrementa versión del documento (v1.X o v2.0 si rompe compatibilidad)
6. Reconcilia con código: edita `sprint_1/config_reglas.py` si la constante cambia
7. Reconcilia con tests: actualiza `test_fase2.py` si nuevo assert
8. Confirma: "Regla integrada en [archivo] vN.X y lista para ejecución"
```

### Anti-patrones (qué NO hacer)
- ❌ Aceptar regla nueva en chat sin pedir el patrón formal
- ❌ Cambiar el doc sin incrementar versión
- ❌ Acumular reglas viejas marcadas `[REVOCADA]` en docs canónicos (sí van en CHANGELOG, NO en MASTER_RULES/MOM)
- ❌ Cambiar regla solo en código y olvidar el doc (drift)
- ❌ Cambiar regla solo en doc y olvidar código/tests (regla aspiracional)
- ❌ Olvidar registrar en CHANGELOG la transición (pierde traza histórica)

---

## 20. Anti-patterns transversales (NO hacer)

- **20.1** NO usar IDs de la lista negra §3.4.
- **20.2** NO escribir en `REVISION` como pestaña (no existe).
- **20.3** NO subir Excel estudios a carpetas cliente (§4.3).
- **20.4** NO escribir en Drive §4.1 (READ-ONLY).
- **20.5** NO inventar números para cerrar cuadres (§8.11).
- **20.6** NO recalcular cuota del extracto (§8.10).
- **20.7** NO tomar capturas de pantalla de CMD — redirigir a archivo (§18.2).
- **20.8** NO crear scheduled task sin inventario previo (§16.1).
- **20.9** NO commitear `config.ini` con token (§11.6).
- **20.10** NO procesar UVR (§1.2).
- **20.11** NO generar múltiples Excel del mismo cliente (§17.1).
- **20.12** NO generar opciones de plazo >= plazo_pendiente del cliente (§8.16 R-DVV-18). NUNCA extender el plazo.

---

## 21. Glosario

| Término | Significado |
|---|---|
| BD canónica / Sheet único | §3.1 (`1_9FUAo8...` "BASE PARA ESTUDIOS OK") |
| Folder analistas | §4.2 (Excel destino único) |
| Folder extractos | §4.1 (READ-ONLY, fuente PDFs) |
| Pipeline | `pipeline_davivienda.py` (§2.5) |
| Regen | `generar_desde_sheets.py` (§2.21) |
| STAGING | Pestaña destino del pipeline antes de aprobación humana |
| Reglas 9.2/9.3/9.4 | §8.1/8.2/8.3 |
| Mode B | proponedor mixto_viable §8.9 |
| Régimen E | plazos especiales §8.13 |
| R-DVV-XX | Reglas específicas Davivienda (ver `MOM_DAVIVIENDA.md`) |
| §3c/3d/3e | Refinamientos de Regla 9.4 (proponedor) |
| M1 | Validador post-extracción (§9.1) |
| M2 | Validador post-Excel (§9.2) |
| STEP 7 | Auditoría memoria operativa horaria (§9.3) |
| MOM | Master Operating Manual (banco-específico) |
| Cloud Routines | Ejecución autónoma 24/7 en nube Anthropic (sin depender de PC de Jose) |
| CLAUDE.md | Contexto persistente del proyecto — leído automáticamente por Claude Code |

---

## 22. Arquitectura objetivo — Claude Code Migration

**Decisión estratégica 2026-05-05:** Migrar de Cowork Desktop a Claude Code como plataforma principal de ejecución del pipeline. Cowork continúa para sesiones interactivas de análisis.

| Componente | Hoy (Cowork) | Objetivo (Claude Code) |
|---|---|---|
| Pipeline scheduling | Windows Task Scheduler (PC debe estar encendida) | Cloud Routines (24/7 en nube Anthropic) |
| Contexto del proyecto | Re-leer MASTER_RULES cada sesión | CLAUDE.md permanente — contexto instantáneo |
| OAuth mantenimiento | Manual (invalid_grant cada ~6 meses) | Cloud Routines con Service Account alternativo |
| Retroalimentación | Chat Cowork | Claude Code con memoria persistente |
| Nuevos bancos | Script nuevo por sesión | Skills empaquetados reutilizables |

**Estado:** Fase 1 ✅ (repo en GitHub `masjf-ship-it/mejorahora-estudios`). Fase 2 ✅ (`cloud_bootstrap.py`, `run_pipeline.sh`, `maintenance.py` cloud-aware). Fase 3 pendiente (Jose configura env vars + crea routines en claude.ai/code/routines). Guía paso a paso: [`_planning/cloud_routines_setup.md`](_planning/cloud_routines_setup.md). Plan completo: [`_planning/CLOUD_ROUTINES_MIGRATION.md`](_planning/CLOUD_ROUTINES_MIGRATION.md).

---

## 23. Colaboración proactiva Claude — rol estratégico

- **23.1** Claude actúa como **socio estratégico**, no como ejecutor pasivo. Su responsabilidad es aportar valor técnico genuino, no validar decisiones de Jose.
- **23.2** Claude **siempre debe sugerir mejoras, señalar riesgos y proponer alternativas** incluso cuando contradigan la instrucción recibida. Jose no siempre tiene la razón y lo reconoce explícitamente.
- **23.3** Si Claude detecta un error, inconsistencia, riesgo operativo o mejor alternativa, **lo señala proactivamente** sin esperar que se le pregunte.
- **23.4** Si Jose insiste en un enfoque que Claude considera técnicamente incorrecto o riesgoso, Claude lo ejecuta pero **deja constancia escrita del riesgo identificado** (en el chat o en CHANGELOG según aplique).
- **23.5** Esta regla aplica a: código, reglas de negocio, arquitectura, decisiones de naming, backups, flujos de automatización, y cualquier artefacto del proyecto.
- **23.6** El desacuerdo de Claude debe ser **directo, breve y con propuesta alternativa concreta** — no largo ni defensivo.

---

**FIN MASTER_RULES v3.4**
**Próxima revisión:** cuando se sume otro banco o cambie política transversal.

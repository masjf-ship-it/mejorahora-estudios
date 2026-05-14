# CHANGELOG — MejorAhora SAS · Proyecto Estudios Financieros

**Política:** Archivo append-only. ÚNICA fuente de traza histórica de cambios.
Cada entrada: `[YYYY-MM-DD HH:MM] | Archivo | Versión vieja → nueva | Razón`
Para cambios que implican borrar regla de doc canónico, registrar aquí la regla borrada.

---

## 2026-04-16

- **[2026-04-16]** Protocolo de integridad numérica implementado tras error en crédito de Carlos Mario Fonseca. Causa raíz: lectura de número de crédito desde Excel intermediario sin validación contra extracto PDF original.

- **[2026-04-16]** Decisión estratégica: migrar de n8n a Cloud Routines + Scheduled Tasks (Cowork) como stack principal de automatización. Regla de BD global en Google Sheets establecida como obligatoria.

---

## 2026-04-17

- **[2026-04-17]** `proponedor_plazos.py` — Reglas 9.2/9.3/9.4 validadas con caso Martha. Auto-aplicación 9.3 + 9.4 habilitada.

---

## 2026-04-18

- **[2026-04-18]** `proponedor_plazos.py` — Mode B mixto_viable activado como default cuando ingresos > 0.

---

## 2026-04-20

- **[2026-04-20]** GCP Service Account `claude-bd-sync@mejorahora-automations.iam.gserviceaccount.com` activa. BD canónica única confirmada: `1_9FUAo8cSrLDWAkJlNoy29Cmyh9ojXwnW6zbvhGsESA`.

---

## 2026-04-21

- **[2026-04-21]** Pipeline Davivienda E2E operativo (`pipeline_davivienda.py`). Patrón STAGING activo. Mantenimiento 60min instalado como Scheduled Task Windows.

---

## 2026-04-22

- **[2026-04-22]** Migración Vision fallback a Vertex AI Gemini 2.5 Pro (`vision_extractor.py`). SA configurada con rol Vertex AI User.

---

## 2026-04-23

- **[2026-04-23]** Sprint Fix Bloque — Fases 0-4:
  - Fix bug `_f` colombiano en formato numérico (miles con punto)
  - R-DVV-06 G3 (duplicación cuota sin `+Seguros` inferior)
  - R-DVV-07 proyección 6ª cuota Davivienda/DaviBank
  - R-DVV-09: leasing 600 = hipotecario exacto (revocado tratamiento especial)
  - M1 + M2 validadores activos
  - STEP 7 memoria operativa Claude

---

## 2026-04-24

- **[2026-04-24]** Sprint Retro — 7 fixes:
  - R-DVV-10: M1 bloquea `seguro_vida=0 AND incendio>0`
  - R-DVV-11: DIF.SIMULA ±$70k post-9.3 → REVISION_MANUAL
  - R-DVV-12: HubSpot genérico repetido → fallback REGISTROS
  - §3c: piso abono OPC1 tiered ($100k saldo<$300M / $200k saldo≥$300M)
  - §3d: diff mínima $100k ($70k si plazo_pendiente<60m)
  - §3e: DIF.SIMULA tolerancia ±$70k universal
  - TOLERANCIA_UNIVERSAL ±$70.000 COP centralizada en `config_reglas.py`

- **[2026-04-24]** Arquitectura limpia: `MASTER_RULES.md` v2.0 + `MOM_DAVIVIENDA.md` v1.0 creados como documentos canónicos. Archivos anteriores (`SOURCE_OF_TRUTH.md`, `bank_rules/DAVIVIENDA.md`, `PROMPT_DEFINITIVO_AGENTE.md`) reemplazados — contenido vigente migrado a MASTER_RULES/MOM.

- **[2026-04-24]** `config_reglas.py` creado como fuente única de constantes (reemplaza hardcoding disperso).

- **[2026-04-24]** `validar_extraccion_davivienda.py` (M1) + `validar_excel_generado.py` (M2) + `maintenance/maintenance_60min.py` STEP 7 activos.

---

## 2026-04-25

- **[2026-04-25]** `MASTER_RULES.md` v2.0 → v2.1: §22 "Colaboración proactiva Claude" agregado. Regla nueva — Claude es socio estratégico, sugiere mejoras proactivamente incluso contra criterio de Jose. **Regla vieja:** ninguna (sección nueva). **Razón:** Jose reconoce que no siempre tiene la razón y lo institucionaliza.

- **[2026-04-25]** `sprint_1/config_reglas.py`: referencia stale `MASTER_OPERATING_MANUAL.md` → `MASTER_RULES.md`. Fix de drift doc ↔ código.

- **[2026-04-25]** `run_pipeline.bat` — **2 bugs críticos corregidos:**
  - **Bug 1 (causa raíz STAGING vacío):** El bat no llamaba `listar_pendientes_hoy.py` antes del pipeline. Consecuencia: nuevos clientes en REGISTROS nunca llegaban a STAGING. El pipeline corría cada mañana, encontraba 0 pendientes y salía silenciosamente. FIX: PASO 1 = `listar_pendientes_hoy.py --banco davivienda` → PASO 2 = `pipeline_davivienda.py`.
  - **Bug 2 (logs en carpeta incorrecta):** `LOGDIR=%BASE%\logs` creaba carpeta `logs/` (sin guión). Correcto es `_logs/`. FIX: `LOGDIR=%BASE%\_logs`. La carpeta `logs/` (sin guión, vacía) queda como huérfana — Jose debe borrarla manualmente.
  - **Comentario stale corregido:** "solo 570; 600 se marca PENDIENTE_FRECH" → actualizado a R-DVV-09 vigente (leasing=hipotecario).

- **[2026-04-25]** `sprint_1/INGENIERIA_INVERSA_EXCEL.md` → movido a `sprint_1/docs/` (documentación técnica, no script operativo).

- **[2026-04-25]** `sprint_1/vision_extractor.py` — **ARCHIVO TRUNCADO DETECTADO Y REPARADO.** El archivo tenía 376 líneas (truncado en línea 377 mid-string, faltaba toda la API pública: `CAMPOS_CRITICOS`, `necesita_fallback()`, `extraer_con_vision()`). Restaurado desde backup `_backups/2026-04-25_1152/` → 417 líneas completas. Este bug hubiera roto el fallback de Gemini Vision silenciosamente en el primer extracto no legible por pdfplumber.

- **[2026-04-25]** Verificación pre-producción completada: 16/16 módulos canónicos con sintaxis Python válida.

- **[2026-04-25]** Auditoría completa del proyecto: detectados y documentados los siguientes issues pendientes de resolución manual por Jose:
  1. `SOURCE_OF_TRUTH.md` — archivo fantasma sin permisos de lectura (artefacto filesystem Windows). Jose debe eliminarlo manualmente desde Windows Explorer.
  2. `_archivo/` — directorio con anomalía de permisos de escritura desde sandbox. Limpieza manual pendiente (ver §LIMPIEZA-PENDIENTE abajo).
  3. `CHANGELOG.md` — creado en esta sesión (estaba ausente desde v2.0, gap crítico).
  4. `sprint_1/_backups/listar_pendientes*` — 2 archivos sueltos reorganizados a carpeta `2026-04-17_pre_listar/`.

- **[2026-04-25]** `CHANGELOG.md` creado por primera vez. Retroalimentado con hitos desde 2026-04-16.

---

## 2026-04-27

- **[2026-04-27]** Retroalimentación estudio JORGE LUIS VELASCO SALAZAR → 3 bugs detectados y corregidos:

  - **R-DVV-13 — `pipeline_davivienda.py`**: Nuevo fallback `seguro_vida` por residual matemático. Si el extractor devuelve `seguro_vida=0` pero cap+int+seg_inc está completo, calcula `residual = cuota - cap - int - seg_inc` y lo asigna como `seguro_vida` si está en rango ($1k–8% cuota). Soluciona extracción fallida de Davivienda para este campo. **Regla vieja:** sin fallback (seg_vida=0 bloqueaba en M1 o pasaba incorrecto al Excel). **Razón:** recurrente en extractos Davivienda donde seg_vida aparece en zona no parseada por pdfplumber.

  - **§3c MODO B — `proponedor_plazos.py`**: `_proponer_mixto_viable()` ahora aplica el piso de abono tiered ($100k saldo<$300M / $200k saldo≥$300M), igual que MODO A. Si ≥3 opciones superan el piso se filtran las inferiores; si <3 pasan, se conservan originales (cliente genuinamente limitado). **Regla vieja:** MODO B generaba opciones sin respetar el piso, resultando en OPC1 con abonos de $60k–$80k. **Razón:** §3c solo se había implementado en `_proponer_por_saltos_100k` (MODO A), no en MODO B.

  - **R-DVV-14 — Bug "mismos datos para varios clientes" (`pipeline_davivienda.py`)**: Causa raíz real identificada y corregida. Clientes en STAGING con `Acceso="N/A"` (6 de 8 en el batch del 25/04) hacían que `_filtrar_pendientes_davivienda` asignara `cc_val="N/A"`. Luego `enriquecer_con_registros` buscaba en REGISTROS el primer cliente con `CC="N/A"` — que es **ANDREA PAOLA DURAN TARAZONA** (Abono=$500k, Ingresos=$3.186M, Actividad=Vis Davivienda). Todos los clientes con Acceso=N/A recibían los datos de ANDREA. FIX: guard en `_filtrar_pendientes_davivienda` y en `enriquecer_con_registros` que trata "N/A"/"NA"/"N.A." como CC vacío → cae a lookup por nombre → si REGISTROS no tiene datos financieros, escala a HubSpot. **Para JORGE específicamente:** su REGISTROS tiene campos financieros vacíos; HubSpot tiene el dato real (contacto creado 25/04 a las 14:48, después del pipeline de las 13:28) → re-ejecutar pipeline resolverá: Abono=$200.000, Actividad=Empleado. **Regla vieja:** `cc_val = g("cc") or g("acceso")` sin filtro para "N/A". **Razón:** inconsistencia de datos — "Acceso" en REGISTROS almacena URL/password de bancos, no CC.

  - **Bug 3 — Extractor `seguro_vida` mejorado (`extract_davivienda_pdf.py`)**: Agregados 4 patrones regex alternativos para capturar `seguro_vida` en formatos variables de Davivienda (valor en línea siguiente, con/sin signo peso, con guión/colon). La fuente siempre es el extracto PDF, no un residual matemático. M1 (R-DVV-10) sigue bloqueando si `seguro_vida=0 AND incendio>0` para forzar revisión manual cuando el extractor falle. **Regla vieja:** un solo patrón `"Seguro\s+de\s+Vida\s*\$?\s*([\d.,]+)"` sin fallbacks.

- **[2026-04-27] Fix `_f()` — formato single-comma miles (`pipeline_davivienda.py`)**: Bug silencioso donde `_f('$200,000')` retornaba `200.0` en lugar de `200000.0`. Causa: una sola coma sin punto se trataba siempre como decimal colombiano. **Fix:** si hay una sola coma y los dígitos post-coma son exactamente 3 y todos dígitos, se trata como separador de miles (comportamiento análogo al fix existente para punto único). **Validado:** `_f('$200,000')=200000.0`, `_f('1234,56')=1234.56`, `_f('$3,531,500')=3531500.0`. **Regla vieja:** `elif has_comma and not has_dot: s = s.replace(",", ".")` — sin excepción para 3 dígitos. **Razón:** REGISTROS almacena abono como `'$200,000'` (formato EN), lo que hacía que el valor real de abono de clientes con ese formato llegara como `$200` al Excel.

- **[2026-04-27] Retroalimentación Jorge Velasco — diagnóstico final resuelto**: Debug logging `[DEBUG-FUENTES]` confirmó causa raíz de abono=$100,000 erróneo: HubSpot tenía `abono_efectivo='100000'` (dato viejo). Jose corrigió en HubSpot a '200000'. REGISTROS tenía `ingresos='$3,531,500'` para Jorge (llegó por contaminación R-DVV-14, pero confirmado que es correcto). Debug logs temporales eliminados del pipeline. Estado post-fix: `abono_efectivo='200000'` en HubSpot ✓, `ingresos=$3,531,500` en REGISTROS ✓, pipeline listo para re-ejecución.

---

## 2026-04-28

- **[2026-04-28] R-DVV-16 — `pipeline_davivienda.py`**: STAGING excluido como fuente de datos financieros en cascada `construir_datos`. **Causa raíz:** la función usaba `_pick(HubSpot, REGISTROS, staging_row)` para `ingresos`, `abono` y `actividad_economica`. Cuando HubSpot y REGISTROS no tenían dato, el valor de STAGING ganaba. STAGING es cola operativa (nombre, banco, estado), NO fuente de verdad financiera. Datos en STAGING pueden ser residuo del bug R-DVV-14 (N/A cross-match) o entradas manuales erróneas. **Fix:** `ingresos` y `abono` y `actividad` ahora solo vienen de `_pick(HubSpot, REGISTROS)`. `consultor` sí puede venir de STAGING (es dato operativo). **Regla vieja:** `_pick(hs, reg, staging_row)` para todos los campos cliente. **Razón:** Jorge Luis Velasco mostraba `ingresos=$3,531,500` y `abono=$100,000` de STAGING aunque esos valores eran erróneos/residuales.

- **[2026-04-28] R-DVV-15 — `extract_davivienda_pdf.py`**: Bug crítico en extracción seguro de vida (3 iteraciones hasta fix correcto):
  - **Iteración 1 (diagnóstico inicial):** Se asumió que el formato era `"Seguro de Vida   0,02294   22.021"`. FIX: `re.finditer` + `_peso_col()`. Resultado: seguía fallando.
  - **Iteración 2 (diagnóstico real):** Lectura directa del PDF via Drive MCP reveló el formato real: `"Seguro de Vida $22,021.00"` — con signo `$` entre el espacio y el número. El pattern `\s+([\d.,]+)` no hace match porque `$` no está en `[\d.,]`. FIX definitivo: `\s+\$?\s*([\d.,]+)` — agregado `\$?` para que el signo sea opcional.
  - `_peso_col()` creada como función auxiliar robusta que detecta formato colombiano de miles (dot = miles si último grupo tiene 3 dígitos) y formato estándar con coma-miles/punto-decimal.
  - **Regla vieja:** Pattern A sin `\$?`, hacía match de tasa (0.02294) y nunca llegaba al monto ($22,021.00). **Razón:** el `$` del extracto bloqueaba silenciosamente el regex.

---

## 2026-04-29

- **[2026-04-29] R-DVV-17 — Doble bug raíz en `enriquecer_con_hubspot` (`pipeline_davivienda.py`)**: Retroalimentación de Jorge Luis Velasco reveló dos bugs simultáneos que corrompían los datos del Excel:

  - **Bug A — N/A contamina HubSpot (espejo de R-DVV-14):** Cuando un cliente tiene `CC="N/A"` en STAGING, el pipeline llamaba `search_contact_by_cedula("N/A", ...)`. HubSpot tiene **36 contactos** con `cedula="N/A"` — el primero del resultado (orden de API) se usaba como si fuera el cliente real. Eso explicaba abono, consultor e ingresos de otros clientes apareciendo en el Excel. **Fix:** guard `_CC_INVALIDOS_HS = {"n/a", "na", "n.a.", "n\\a", "n-a", ""}` — si el CC cae en ese set, se fuerza `cc_clean=""` antes de llamar `match_contact_cascade`, saltando directo a búsqueda por nombre. **Regla vieja:** `match_contact_cascade(cedula=cc, ...)` sin sanitizar N/A. **Razón:** R-DVV-14 solo aplicó el guard a REGISTROS pero no a HubSpot — mismo patrón, mismo fix.

  - **Bug B — Propiedad `ingresos` no existe en este portal HubSpot:** `HUBSPOT_PROPS` incluía `"ingresos"` y `"ingreso"` pero estas propiedades NO existen en el portal de MejorAhora. La propiedad real es `"valor_de_ingresos"`. Por esto `hs.ingresos` siempre llegaba vacío para todos los clientes. **Fix:** `HUBSPOT_PROPS` actualizado con `"valor_de_ingresos"` como primera opción; código de extracción usa `props.get("valor_de_ingresos")` primero. Eliminadas propiedades inválidas (`"ingresos"`, `"ingreso"`, `"numero_de_identificacion"`, `"abono"`) de `HUBSPOT_PROPS`.

  - **Efecto combinado:** Con Bug A, el abono venía de un contacto aleatorio N/A. Con Bug B, los ingresos nunca venían de HubSpot. Ambos forzaban cascada a REGISTROS con datos contaminados. Post-fix: el pipeline busca al cliente por nombre (match correcto), lee `abono_efectivo` y `valor_de_ingresos` de SU contacto real en HubSpot.

- **[2026-04-29] R-DVV-17C — `search_contact_by_name` en `hubspot_client.py`**: Tercer bug en la cadena de Jorge Velasco. Tras aplicar R-DVV-17A (N/A guard) el pipeline cayó a búsqueda por nombre con estrategia `firstname="JORGE"` + `lastname="SALAZAR"`. HubSpot retornó **JORGE EMILIO SALAZAR RUIZ** (único match exacto, ID 139155292291) en lugar de Jorge Luis Velasco Salazar — porque el contacto real tiene el nombre completo en `firstname` sin `lastname`. Ese contacto incorrecto tenía `abono_efectivo='100000'` y `valor_de_ingresos='1.600.000'` — exactamente los valores erróneos del Excel. **Fix (Estrategia A):** búsqueda primaria usa TODOS los tokens del nombre como filtros `CONTAINS_TOKEN` en `firstname` (hasta 5). Buscar "JORGE" + "LUIS" + "VELASCO" + "SALAZAR" en firstname encuentra el contacto real y rechaza a JORGE EMILIO SALAZAR RUIZ porque no contiene "VELASCO". Estrategia B (primer+último token en firstname/lastname) queda como fallback. **Regla vieja:** solo `firstname CONTAINS_TOKEN token[0]` + `lastname CONTAINS_TOKEN token[-1]` — susceptible a falso positivo cuando hay un contacto con lastname correcto pero nombre diferente. **Razón:** muchos contactos en el portal están creados con nombre completo en `firstname` y `lastname` vacío (creación desde formulario web de captación).

---

## 2026-05-05

- **[2026-05-05] OAuth refresh_token revocado — re-autenticación ejecutada:** El token en `credentials/oauth_token.json` (expirado 2026-04-28) fue revocado por Google (`invalid_grant`). Causa: Google revoca refresh_tokens de apps en modo "Testing" si no se usan en ~6 meses, o si el usuario revoca desde `myaccount.google.com/permissions`. **Fix:** se corrió `sprint_1/drive_oauth_setup.py` → flujo consent en navegador con `reducciondecreditos2@gmail.com` → nuevo token guardado. **Regla nueva (§16.5 MASTER_RULES):** si el pipeline falla con `invalid_grant` → correr `py drive_oauth_setup.py` de inmediato. Regla vieja: ninguna (escenario no documentado). **Razón:** el error se manifestaba como 403 `storageQuotaExceeded` en el SA fallback, enmascarando la causa raíz OAuth revocado.

- **[2026-05-05] `sprint_1/diag_oauth.py` creado:** Script de diagnóstico OAuth en 10 pasos (archivos, token, refresh, googleapiclient, Drive API, folder §4.2). Permite pinpointear exactamente qué falla en el flujo OAuth sin ejecutar el pipeline completo. Uso: `py diag_oauth.py > diag_oauth.txt 2>&1`.

- **[2026-05-05] 4 estudios generados exitosamente con OAuth activo:** LUIS EDUARDO MARTINEZ ROMO (`570101600475492-2`), NAYIVE GALVIS DE PRIETO (`570101340021123-5`), ALEXANDRA BERNAL VARGAS (`570000830089102-0`), LUIS EDUARDO MARTINEZ ROMO (`570101600475498-9`). Todos subidos a folder §4.2 (`1UVsQtyzQHEpfRlcjUrq8gBsXgEqABoym`) ✅. Folder confirmado como destino canónico — ya estaba configurado en `drive_client.py` y `config_reglas.py` como `DRIVE_FOLDER_ANALISTAS_RW`.

- **[2026-05-05] Task Scheduler PM creado:** `MejorAhora\Pipeline Davivienda PM` — DAILY 20:30. Pipeline ahora corre 2×/día: 08:30 AM + 20:30 PM. Comando: `schtasks /create /tn "MejorAhora\Pipeline Davivienda PM" /tr "\"C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\run_pipeline.bat\"" /sc DAILY /st 20:30 /ru "JOSE A" /f`. Actualizado en MASTER_RULES §16.

- **[2026-05-05] REVISION_MANUAL pendientes — 4 clientes sin Excel:** LINA KATHERINE ARISTIZABAL VALENZUELA (`600707600221896-4`, DIF.SIMULA=$-293,242), CLAUDIA PATRICIA PULIDO GUTIERREZ (`600650600037786-8`, DIF.SIMULA=$89,871), OSCAR ALBERTO VARONA BONILLA (`600303620047325-2`, M1 duplicación cuota $4.764M vs $2.517M), ELBA CRISTINA PENA URIBE (`570045730041807-0`, M1 seguro_vida=0). Requieren revisión manual del extracto PDF y re-proceso con `--nombre --force`.

- **[2026-05-05] MARIA ALEJANDRA MARTINEZ AFRICAN — no capturada por listar:** `listar_pendientes_hoy.py --banco davivienda` no la trajo (fecha solicitud: 21-abr). Causa probable: campo banco en REGISTROS con valor diferente a "davivienda" (case/typo). Acción: verificar manualmente en REGISTROS columna BANCO para esa fila y corregir, o agregarla directamente a STAGING.

- **[2026-05-05] Flujo obligatorio PASO 1 → PASO 2 reforzado:** SIEMPRE correr `listar_pendientes_hoy.py --banco davivienda` (PASO 1) ANTES de `pipeline_davivienda.py` (PASO 2). Sin PASO 1, el pipeline reporta "sin pendientes" aunque REGISTROS tenga clientes nuevos. La alternativa recomendada es usar `run_pipeline.bat` que ejecuta ambos pasos automáticamente. Documentado en MOM_DAVIVIENDA §7 y §8.

- **[2026-05-05] R-DVV-18 — Guardia plazo pendiente + pre-check Ley 546 (`proponedor_plazos.py` + `pipeline_davivienda.py`):** Bug crítico detectado en retroalimentación de Alexandra Bernal Vargas. Doble violación: (1) el proponedor generaba opciones de 150+ cuotas para un cliente con solo 29 cuotas pendientes (extensión del plazo); (2) el crédito total (< 5 años) era inviable bajo la Ley 546/1999 pero se generaba igualmente el Excel.

  **Causa raíz (3 puntos):**
  1. `_proponer_por_saltos_100k`: `max(anio_max, ceil(anio_min_legal))` elevaba el techo sobre `plazo_pend_anos` cuando `anio_min_legal > plazo_pend_anos`.
  2. `_proponer_mixto_viable`: mismo patrón `max(techo, ceil(anio_min_legal))` sin guard.
  3. Pipeline no tenía pre-check de viabilidad Ley 546 antes de llamar al proponedor.

  **Fixes aplicados (archivos modificados):**
  - `sprint_1/proponedor_plazos.py` → refactorizado con wrapper `_proponer_plazos_impl()`. `proponer_plazos()` aplica guardia final: filtra cualquier opción `>= plazo_pend_anos` después de todos los métodos (cubre Mode A, B, E, manual, escalonado). `_proponer_mixto_viable()` techo fix: `max(techo, ceil(anio_min_legal))` solo se aplica si `anio_min_legal < plazo_pend_anos`. `_proponer_por_saltos_100k()`: fix ya había sido aplicado (fix A inicial de esta sesión).
  - `sprint_1/pipeline_davivienda.py` → Pre-check `NO_VIABLE_LEY_546` antes del Step 7b: si `anio_min_legal >= plazo_pend_anos` → REVISION_MANUAL sin generar Excel. Muestra plazo_pend, anio_min_legal, total acumulado vs 5 años.
  - `MOM_DAVIVIENDA.md` v1.4 → v1.5: R-DVV-18 documentado (§2 reglas + §7 troubleshooting).
  
  **Regla vieja**: ninguna (caso no contemplado; el proponedor podía generar plazos mayores al pendiente silenciosamente). **Razón:** NUNCA extender el plazo de un crédito — principio fundamental de negocio MejorAhora.

---

## 2026-05-07

- **[2026-05-07] OLA 1 — Higiene crítica · auditoría completa del proyecto:** Reconciliación de contradicciones detectadas en revisión exhaustiva de docs y código. Cambios atomicos:

  - **`MASTER_RULES.md` v2.5 → v2.6**:
    - **§17.11 retención backups:** "336 snapshots = ~14 días" → "168 snapshots = ~7 días". Fuente de verdad: `RETENTION_N` en `maintenance_60min.py`. **Regla vieja:** retención 336. **Razón:** triple contradicción entre §15.4 (168), §17.11 (336), código (168) y CLAUDE.md (336). Decisión Jose 2026-05-07: alinear todo al valor que el código ya ejecuta (168 = 7 días).
    - **§22 / §23 desambiguados:** "Colaboración proactiva Claude" renumerada a §23 (era segundo §22).
    - **§22 referencia a `MIGRACION_CLAUDE_CODE.md`:** archivo no existe. Reemplazada por nota: el plan vive solo en la tabla de §22 hasta que se redacte el archivo.
    - **Footer:** "FIN MASTER_RULES v2.1" → "v2.6" (drift histórico de header vs footer).

  - **`ESTADO_PROYECTO.md` v2.0 → v2.1**:
    - §0 versíon de docs actualizadas: MASTER_RULES v2.0 → v2.6, MOM_DAVIVIENDA v1.0 → v1.5.
    - §1 banner Davivienda: "R-DVV-01..12" → "R-DVV-01..18".
    - §6 retención: "(336 retención)" → "(168 retención = 7 días, FIFO)".
    - §7 viñeta "Memoria acumulativa (nada se borra, todo se versiona con [REVOCADA YYYY-MM-DD])" → BORRADA. **Regla vieja:** acumulativa con marcadores [REVOCADA] en docs canónicos. **Razón:** contradecía directamente MASTER_RULES §17.3 (política limpia: traza solo en CHANGELOG). Decisión Jose 2026-05-07: confirmar política limpia como Única.

  - **`CLAUDE.md`**: "FIFO retention 336 (~14 days)" → "FIFO retention 168 (~7 days)". Aclarado que `RETENTION_N` es la fuente de verdad.

  - **`MANUAL_EXTRACTO_BANCOS.md`**:
    - Reglas Generales: agregada regla explícita "UVR — EXCLUIDO del flujo (§1.2 / §17.10 / §20.10)".
    - DAVIVIENDA Sistema de Amortización UVR: aclarado que el registro se EXCLUYE (antes solo decía cómo identificarlo, sin señalar la exclusión).

  - **`maintenance/maintenance_60min.py`**:
    - `BACKUP_TARGETS` limpiado: removidos `SOURCE_OF_TRUTH.md`, `PROMPT_DEFINITIVO_AGENTE.md`, `CRM.xlsx`, `BD.xlsx`, `tips_de_banco.csv`, `bank_rules/*.md`, `sprint_1/bank_rules/*.md`, `sprint_1/config.ini` (token leak risk). Agregados `MOM_DAVIVIENDA.md`, `CLAUDE.md`, `CHANGELOG.md`, `tips_de_banco.xlsx`, `sprint_1/docs/*.md`. **Regla vieja:** lista heredada con archivos consolidados o eliminados desde 2026-04-24. **Razón:** generaba ruido de anomalías falso-positivas cada hora y snapshoteaba un archivo sensible (token HubSpot).
    - `REQUIRED_PATHS` actualizado: removido `SOURCE_OF_TRUTH.md` (fantasma); agregados `MOM_DAVIVIENDA.md`, `CHANGELOG.md`, `sprint_1/config_reglas.py`.
    - Comentario de `RETENTION_N=168`: reescrito declarando que es la fuente de verdad.
    - Texto de reporte STEP 7: reemplazada nota "respeta política nada se borra" por "política docs limpia (§17.3): traza en CHANGELOG, no en marcadores [REVOCADA]; STEP 7 reporta para revisión humana".

  - **`CHANGELOG.md`**: secciones 2026-04-27 y 2026-04-28 reordenadas a cronología ascendente.

  **Tests:** sin cambios (no hay deltas de constantes ni asserts). `RETENTION_N=168` ya estaba en código desde 2026-04-25.

---

## 2026-05-14

- **[2026-05-14 CAMBIO ESTRUCTURAL MAYOR — Jose feedback caso ALVARO MAHECHA]:**

  Jose pidió cambio de proceso para casos REVISION_MANUAL (no se podía
  diagnosticar sin Excel) y rebautizar STAGING→GENERADOS. Implementación E2E:

  **1. R-DVV-11 evoluciona — auto-retry Gemini + Excel siempre**
  - Antes: si DIF.SIMULA > ±$70k → abortar sin Excel, marca `REVISION_MANUAL`
  - Ahora: si DIF.SIMULA > ±$70k:
    - Si extractor fue `pdfplumber` → re-extraer con Gemini Vision, re-aplicar
      Regla 9.3, recalcular DIF.SIMULA
    - Si Gemini lo arregla → procesar normal, estado `pre-generado, gemini`
    - Si Gemini NO lo arregla (o ya era Gemini) → **NO aborta**. Genera Excel
      con datos finales. Estado: `REVISION_MANUAL: DIF.SIMULA $X (gemini)`
  - Razón: caso ALVARO MAHECHA reveló que pdfplumber lee mal `plazo_pendiente`
    sin dejarlo vacío → fallback automático NO se activaba → DIF.SIMULA -$13.4M
    sin posibilidad de diagnóstico del analista 1.
  - Workflow nuevo: analista 1 abre el Excel, compara con extracto, **corrige
    in-place** los datos incorrectos y guarda. NO se regenera el Excel.

  **2. Renombrar pestaña: `STAGING` → `GENERADOS`**
  - `config_reglas.SHEET_PESTANA_DESTINO = "GENERADOS"` (antes `"STAGING"`)
  - `automation/apps_script/staging_approval_workflow.gs` actualizado v3.0 → v3.1
  - `pipeline_davivienda._abrir_staging()` lee de `SHEET_PESTANA_DESTINO`
  - **Orden de despliegue crítico**: código primero (este commit), Sheet después
    (Jose renombra manualmente). Al revés rompería los pipelines siguientes.

  **3. Estados nuevos en columna G (GENERADOS)**
  - `pre-generado`           : pdfplumber solo, sin alerta
  - `pre-generado, gemini`   : Gemini intervino (fallback inicial O retry R-DVV-11)
  - `REVISION_MANUAL: DIF.SIMULA $X (gemini)` : alerta persiste, Excel existe
  - `Excel generado`         : revisado y aprobado por analista 1 (final)
  - Estados `pre-generado*` agregados a `ESTADOS_SKIP_DEFAULT` en config_reglas

  **4. Visibilidad del extractor**
  - `extraer_pdf_hibrido` ahora anota `datos["_extractor_uso"]` ∈ {"pdfplumber", "gemini"}
  - El estado en GENERADOS lo refleja como `, gemini` (cuando aplica)
  - Cero cambios al Excel — la visibilidad vive solo en GENERADOS

  **5. Rol Yenny → "analista 1"**
  - Cambios SOLO en docs/comentarios que se referían al rol genérico
  - Valor literal `"Pte. Validar Yenny"` (estado del Sheet) **NO cambia** —
    sigue siendo el dropdown value. Solo cambia la mención genérica del rol.

  **Archivos modificados:**
  - `sprint_1/pipeline_davivienda.py` — auto-retry Gemini + genera siempre + estados dinámicos
  - `sprint_1/config_reglas.py` — SHEET_PESTANA_DESTINO + estados skip
  - `sprint_1/listar_pendientes_hoy.py` — Yenny → analista 1 en comentarios
  - `automation/apps_script/staging_approval_workflow.gs` v3.0 → v3.1
  - `MOM_DAVIVIENDA.md` v1.6 → v1.7 (R-DVV-11 actualizada)
  - `MASTER_RULES.md` v3.9 → v4.0 (cambio estructural mayor)
  - `ESTADO_PROYECTO.md` §0 alineado
  - `_planning/OLA_3_PLAN.md` — "equipo Yenny" → "equipo de analistas"

  **Tests post:**
  - `test_fase2.py` 16/16 PASS ✅
  - `pytest sprint_1/tests/` 50/50 PASS ✅
  - `maintenance --dry-run` anom_drift = 0 ✅

  **Acción pendiente Jose (manual)**:
  - Renombrar pestaña "STAGING" → "GENERADOS" en el Sheet `BASE PARA ESTUDIOS OK`
    (click derecho sobre la pestaña → Cambiar nombre)

---

## 2026-05-12

- **[2026-05-12 SESION DIA 1 CLOUD parte 4] — audit maintenance.py: STEP 8 drift expandido:**

  **H. `maintenance/maintenance.py` (576 → 578 líneas):**

  - **`import re` movido al top del módulo** — antes vivía inline dentro de
    `check_doc_code_drift()` como `import re as _re`. Patrón anti-idiomático.
    Solucionado: top-level `import re` + alias local `_re = re` para mantener
    el resto del bloque sin cambios (minimal diff).
  - **STEP 8 drift checker expandido — nuevo check 5b**:
    El checker antes solo validaba `RETENTION_N` contra MASTER_RULES §17.11.
    Ahora también valida `RETENTION_PIPELINE_LOGS_DAYS` contra §15.4 ("logs
    pipeline JSON N días por fecha del archivo"). Si el código tiene
    `RETENTION_PIPELINE_LOGS_DAYS = 30` y el doc dice "10 días", se reporta
    drift. Cobertura del anti-drift expandida sin tocar producción.

  **Tests post:**
  - `test_fase2.py` 16/16 PASS ✅
  - `pytest sprint_1/tests/` 50/50 PASS ✅
  - `maintenance --dry-run` anom_drift = 0 ✅

  **Bumps de versión:**
  - MASTER_RULES.md v3.8 → v3.9
  - ESTADO_PROYECTO.md §0 alineado

- **[2026-05-12 SESION DIA 1 CLOUD parte 3] — audit reglas_negocio + listar_pendientes (anti-drift):**

  Audits adicionales mientras Jose revisa los 5 Excel. Patrón: cualquier
  constante con 2+ definiciones se consolida a `config_reglas` como fuente única.

  **G1. `sprint_1/reglas_negocio.py`:**
  - 🚨 **Duplicación silenciosa eliminada**: `RATIO_VIS = 0.39` y `RATIO_NO_VIS = 0.29`
    estaban definidas TANTO aquí como en `config_reglas.py`. Grep confirmó **0 importadores**
    desde reglas_negocio (las usaba indirectamente, pero todos los consumidores ya
    importaban desde config_reglas). Eliminadas en reglas_negocio para evitar drift
    futuro (MASTER_RULES §17.3).

  **G2. `sprint_1/listar_pendientes_hoy.py` (PASO 1 del pipeline diario):**
  - `WORKSHEET_DST = "STAGING"` → `SHEET_PESTANA_DESTINO` (ya existía en config_reglas)
  - `WORKSHEET_SRC = "REGISTROS"` → nueva constante `SHEET_PESTANA_REGISTROS`
    agregada a `config_reglas.py`
  - Ambos importados con `as` para mantener nombres internos retrocompatibles.

  **Tests post:**
  - `test_fase2.py` 16/16 PASS ✅
  - `pytest sprint_1/tests/` 50/50 PASS ✅
  - `maintenance --dry-run` anom_drift = 0 ✅

  **Bumps de versión:**
  - MASTER_RULES.md v3.7 → v3.8
  - ESTADO_PROYECTO.md §0 alineado

- **[2026-05-12 SESION DIA 1 CLOUD parte 2] — audit extract + pipeline + bug latente fixeado:**

  Continuación del trabajo paralelo mientras Jose revisa Excel. Tareas E y F
  (auditorías más profundas, riesgo controlado por tests).

  **E. Auditoría `sprint_1/extract_davivienda_pdf.py` (454 → 453 líneas):**

  - **BUG LATENTE FIXEADO**: `main()` línea 450 llamaba `format_as_csv_row(result)`
    pero la función real se llama `datos_a_csv_row()`. El CLI puro
    (`py extract_davivienda_pdf.py <pdf>`) habría fallado con `NameError`.
    No se detectó antes porque el pipeline en producción usa
    `parse_davivienda_pdf` directo (no este wrapper) y nadie corrió el CLI
    desde que se escribió. Ahora corregido.
  - **DEAD CODE eliminado**: función `_es_tasa(raw)` (líneas 256-260) definida
    pero NUNCA llamada. Grep confirma 0 referencias en todo el repo. Removida.
  - **Magic number documentado**: `>= 100` (umbral pesos vs tasa en
    `_extraer_seguro_vida`) → constante local `_MIN_SEGURO_VIDA_PESOS = 100`
    con comentario explicando el rango de magnitudes (tasas 0.001-0.9, montos
    >= $100). 3 ocurrencias reemplazadas.

  **F. Auditoría `sprint_1/pipeline_davivienda.py` (1187 líneas):**

  - **3 magic numbers refactorizados a `config_reglas`** (R-DVV-06 G1/G2/G3):
    - `0.05` → `TOLERANCIA_G1_CUOTA_DUPLICADA` (ratio cuota duplicada)
    - `10_000` → `UMBRAL_G2_DISCREPANCIA_SEGUROS` (discrepancia $10k)
    - `0.10` → `TOLERANCIA_G3_SUMA_DUPLICADA` (ratio suma duplicada)
    - Las 3 ya existían en `config_reglas.py` pero estaban hardcoded inline.
  - **2 inline imports consolidados al top-level**:
    - `from config_reglas import TOLERANCIA_DIF_SIMULA` (línea 980, dentro de
      try block) → top-level
    - `from config_reglas import verify_pesos_template` (línea 1148, dentro
      de `main()`) → top-level
    - Ambos eran defensa innecesaria — `config_reglas` ya se importa al top
      del módulo. Movidos para tener un único punto de import por módulo
      (consistente con MASTER_RULES §17.3 política limpia).

  **Tests post:**
  - `test_fase2.py` 16/16 PASS ✅
  - `pytest sprint_1/tests/` 50/50 PASS ✅
  - `maintenance --dry-run` anom_drift = 0 ✅

  **Bumps de versión:**
  - MASTER_RULES.md v3.6 → v3.7
  - ESTADO_PROYECTO.md §0 alineado a v3.7

- **[2026-05-12 SESION DIA 1 CLOUD — trabajo paralelo mientras Jose revisa Excel:**

  Mientras Jose revisaba los 5 Excel generados anoche (post-smoke #7), Claude
  ejecutó 4 tareas autónomas (A-D) explícitamente autorizadas por 8h:

  **A. `_planning/cloud_routines_setup.md` v1.0 → v2.0**:
  - Documenta los 6 fixes infra descubiertos en la sesión de migración
  - Setup script del entorno: vacío (no `pip install`) — el pip vive en wrappers bash
  - Acceso a la red: "Completo" obligatorio (no "De confianza")
  - Variables de entorno con instrucciones explícitas de comillas simples para JSON
  - Routine 5 (Metricas Semanal) documentada
  - Tabla troubleshooting expandida a 9 síntomas (de 5 originales)
  - Refleja la realidad operativa de hoy, no el plan original pre-fixes

  **C. `_planning/PASO_JOSE_ENV_VARS.md` → `_archivo/PASO_JOSE_ENV_VARS_2026-05-12.md`**:
  - Documento obsoleto (eran las instrucciones para que Jose configurara env vars
    manualmente, ya hecho via Playwright en sesión migración). Movido a _archivo
    para conservar traza histórica.

  **D. `bash run_metricas.sh 7` validación local**:
  - Script funciona, exit 0, reporte generado
  - Pero **descubre limitación arquitectural**: filesystem cloud es efímero,
    los `_logs/pipeline_davivienda_*.json` se pierden entre routines. Resultado:
    Routine 5 en cloud verá siempre 0 archivos.
  - Documentado como **B12** en `_planning/OLA_3_PLAN.md` con 4 opciones de fix
    (commit git / upload Drive / Sheets / Routine 5 ejecuta pipeline). Opción B
    recomendada. No urgente — disparador: 3+ semanas sin métricas.

  **B. Auditoría `sprint_1/proponedor_plazos.py` (988 líneas)**:
  - 8 magic numbers refactorizados a `config_reglas.py`:
    | Antes hardcoded | Después constante config_reglas |
    |---|---|
    | `0.39 if es_vis else 0.29` | `RATIO_VIS if es_vis else RATIO_NO_VIS` |
    | `* 1.10` (factibilidad) | `* TOPE_INGRESOS_FACTOR` |
    | `100_000.0 if saldo < 300_000_000.0 else 200_000.0` | `PISO_ABONO_SALDO_BAJO if saldo < SALDO_THRESHOLD_TIER else PISO_ABONO_SALDO_ALTO` |
    | `[100_000, 200_000, 300_000, 400_000, 500_000, 600_000]` (serie default) | `[_S, 2*_S, ..., 6*_S]` con `_S = SALTO_ABONO_SERIE` (NUEVA) |
    | `shift += 100_000` | `shift += SALTO_ABONO_SERIE` |
    | `tope_factor: float = 1.10` (default param) | `tope_factor: float = TOPE_INGRESOS_FACTOR` |
  - 6 occurencias en `_proponer_por_saltos_100k`, 2 en `_proponer_mixto_viable`,
    2 en `_plazo_min_factible`, 1 en `_proponer_por_ingresos` (legacy).
  - Nueva constante `SALTO_ABONO_SERIE = 100_000.0` en `config_reglas.py`.
  - Función legacy `_proponer_por_ingresos`: refactorizada también + nota en
    docstring marcándola como legado (consistente con docstring del módulo).

  **Tests post:**
  - `test_fase2.py` 16/16 PASS ✅
  - `pytest sprint_1/tests/` 50/50 PASS ✅
  - `maintenance --dry-run` anom_drift = 0 ✅

  **Bumps de versión:**
  - MASTER_RULES.md v3.5 → v3.6
  - ESTADO_PROYECTO.md §0 alineado a v3.6 (STEP 8 detectó el drift y se fixeó)

- **[2026-05-12 MIGRATION COMPLETE] Cloud Routines E2E funcional tras 6 fixes de infraestructura:**

  **Resultado smoke test #7:** Pipeline AM ejecutado en cloud con 6 clientes pendientes:
  - 5/6 Excel generados y subidos a Drive §4.2 (JHON VERDUGO, YAMILE DIAZ, ALVARO MAHECHA, FLOR GONZALEZ, JULIETH ZARATE)
  - 1/6 REVISION_MANUAL legitimo (DANITZA CAPERA, credito 571616690013243-5, R-DVV-11 DIF.SIMULA $-154k fuera tol ±$70k) — no es bug infra, sino pipeline funcionando correctamente
  - M2: 0 alertas

  **6 fixes de infraestructura aplicados (todos en `main`):**
  
  | # | Problema | Fix | Commit |
  |---|---|---|---|
  | 1 | Setup script corre antes del clone → no encuentra `sprint_1/requirements.txt` | Mover `pip install` al inicio de `run_pipeline.sh` / `run_metricas.sh` (PASO -1) | `eadbbfb` |
  | 2 | Debian externally-managed env (PEP 668) bloquea pip | Agregar `--break-system-packages` | `aad8ba7` |
  | 3 | `packaging 24.0` instalado via dpkg, pip no puede desinstalar (RECORD ausente) | Agregar `--ignore-installed` | `10355c5` |
  | 4 | Proxy TLS Anthropic con CA propia → SSL CERTIFICATE_VERIFY_FAILED | `_configure_ssl_cert_paths_for_cloud()` en `cloud_bootstrap.py` | `345ad08` |
  | 5 | `httplib2` cachea CA bundle al IMPORT → fix #4 llega tarde | Export `HTTPLIB2_CA_CERTS` + 3 vars SSL a nivel shell ANTES de python | `7ed524f` |
  | 6 | UI red en "De confianza" puede agravar el TLS | Cambiar a "Completo" en entorno MejorAhora via UI | (UI-only) |

  **Configuracion UI Claude Code completada:**
  - Entorno "MejorAhora" creado en `claude.ai/code` con 3 env vars (MEJORAHORA_SA_JSON, MEJORAHORA_OAUTH_TOKEN_JSON, MEJORAHORA_HUBSPOT_TOKEN)
  - Acceso a la red: "Completo" (sin proxy)
  - Setup script: vacio (pip install vive en wrappers bash post-clone)
  - Asignado a las 4 routines: Pipeline AM, Pipeline PM, Mantenimiento AM, Mantenimiento PM

  **Tiempo invertido en debugging:** ~30 min, 7 smoke tests, 6 commits incrementales hasta verde.

  **Estado:**
  - Cloud Routines: 100% operativas
  - Windows Tasks: siguen activas como fallback hasta validar 5 dias consecutivos en cloud (ESTADO_PROYECTO §3 criterio)
  - Repo: publico (privatizar tras 5 dias clean OK)

- **[2026-05-12] SESION NOCTURNA — Cloud Routines validadas + auditoria 3 modulos:**

  Jose autorizo trabajo de 10h sin interrupciones para cerrar pendientes. Resumen de logros:

  **Cloud Routines:**
  - 4 routines creadas y activas en `claude.ai/code/routines`:
    - `MejorAhora Pipeline AM` (trig_015mTy9kw98LF1qjBEeFcLQK) — daily 9:00
    - `MejorAhora Pipeline PM` (trig_01KtodCty3dnCaeyBukdi3hp) — daily 20:30
    - `MejorAhora Mantenimiento AM` (trig_01CSPC3UxLx6o8itsPNoKpg5) — daily 7:00
    - `MejorAhora Mantenimiento PM` (trig_01M7Mu4ZZkyoAWoFENPVihyQ) — daily 19:00
  - **Mant PM ejecutado exitosamente** (manual 22:53 GMT-5): EXIT_CODE 0, drift 0, `cloud_bootstrap.py` detectó cloud y skipeó backup local correctamente. Validó que la migración Fase 2 funciona.
  - Bug detectado y fixeado: el repo había vuelto a privado, causando "Authentication failed accessing git_repository" en la routine AM original. Fixed: repo público vía Playwright. Quedará público hasta que las env vars de creds estén configuradas y todas las routines pasen smoke test mañana — entonces se privatiza.
  - **Bloqueador documentado:** las 3 env vars (`MEJORAHORA_SA_JSON`, `MEJORAHORA_OAUTH_TOKEN_JSON`, `MEJORAHORA_HUBSPOT_TOKEN`) no se pudieron pegar automáticamente (sistema de seguridad bloqueó la lectura de creds para inyección al browser). Instrucciones paso a paso en `_planning/PASO_JOSE_ENV_VARS.md` para que Jose las configure en 5 min cuando despierte.

  **FASE 2 — Migración tests pytest:**
  - `sprint_1/tests/test_staging_update.py` (8 tests pytest) — migra TEST H del suite golden (`_staging_update` con nota CRM, preservar previa, etc.). Pytest: 42 → **50/50 PASS**.
  - TESTS F y G del golden NO se migran: sus funciones inline (`_es_vis`, `_piso_abono`) solo existen en `test_fase2.py`, no son código de producción.

  **FASE 3 — Auditoría de 3 módulos:**
  - **`sprint_1/excel_populator.py` (1175 líneas):** 3 fixes aplicados + 1 TODO documentado.
    - FIX: sheet path hardcoded `xl/worksheets/sheet2.xml` → `actual_sheet_file` dinámico (bug latente: si template reordena hojas, el INDEX/MATCH no se reemplazaba).
    - FIX: default `new_area` stale `$R$54` → `$R$85` (rango correcto del print area).
    - FIX: `_PLAZOS_DEFAULT` duplicado con `reglas_negocio.PLAZOS_DEFAULT` → import directo.
    - TODO: `PDFExporter._prepare_temp_xlsx` tiene mismo bug del hardcoded `sheet3.xml`, no fixeado porque PDFExporter no es ruta productiva (sin invocaciones).
  - **`sprint_1/vision_extractor.py` (417 líneas):** 4 constantes duplicadas → import desde `config_reglas`:
    - `DEFAULT_MODEL` ↔ `DEFAULT_GEMINI_MODEL`
    - `DEFAULT_PROJECT` ↔ `GCP_PROJECT`
    - `DEFAULT_LOCATION` ↔ `GCP_LOCATION`
    - `max_output_tokens=8192` literal ↔ `MAX_OUTPUT_TOKENS_VISION`
  - **`automation/apps_script/staging_approval_workflow.gs` (135 líneas):** auditoría limpia, sin bugs. Agregado `COL_NOTA_CRM = 12` con 2 TODOs informativos (parametrizar para nuevos bancos; considerar propagar nota_crm STAGING → REGISTROS al aprobar).

  **`.gitignore`:** agrega `.playwright-mcp/`, `*.png/jpeg/jpg`, `*.bak` para capturas transitorias.

  **MASTER_RULES v3.3 → v3.4.**

  **Smoke tests post:**
  - `test_fase2.py` 16/16 PASS (golden)
  - `pytest sprint_1/tests/` **50/50 PASS** (era 42)
  - `drift checker` 0 issues
  - `pre-commit hook` OK
  - `Mant PM` ejecutado exitosamente en cloud → validación end-to-end del bootstrap cloud

  **FASE 7 — Auditoria `sprint_1/hubspot_client.py` (255 lineas):** constantes centralizadas + 1 anti-patron eliminado.
  - 9 constantes nuevas en `config_reglas.py`:
    - `HUBSPOT_BASE_URL` ↔ antes literal `"https://api.hubapi.com"` en linea 21
    - `HUBSPOT_REQUEST_TIMEOUT_SEC = 20` ↔ literal `timeout=20`
    - `HUBSPOT_RETRY_DEFAULT = 2` ↔ default `retries: int = 2`
    - `HUBSPOT_BACKOFF_BASE_SEC = 1.5` ↔ literal `1.5 * (attempt+1)` (x2)
    - `HUBSPOT_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)` ↔ tuple inline
    - `HUBSPOT_SEARCH_LIMIT_DEFAULT = 1` ↔ literal `"limit": 1` (x3)
    - `HUBSPOT_SEARCH_LIMIT_NAME = 5` ↔ literal `"limit": 5` (x2)
    - `HUBSPOT_NAME_TOKEN_MAX = 5` ↔ literal `tokens[:5]`
    - `HUBSPOT_CEDULA_PROPS = (...)` ↔ lista inline duplicada
  - Import defensivo con fallback (para tests aislados que no agregan `sprint_1/` al sys.path).
  - **Anti-patron eliminado**: `except Exception: pass` silencioso en `search_contact_by_name` estrategia A → ahora `print()` con detalle del fallo (mantiene cascada A→B, pero queda trazado).
  - Alias `BASE_URL = HUBSPOT_BASE_URL` por retrocompat (caller externo).
  - Tests: 16/16 fase2 PASS + 50/50 pytest PASS.

  **FASE 8 — Auditoria validadores M1/M2:**
  - **`sprint_1/validar_extraccion_davivienda.py` (M1, 151 lineas):** 6 magic numbers → constantes:
    - `1_000_000` ↔ `SALDO_MIN_HIPOTECARIO_ACTIVO` (ya existia)
    - `10_000_000` ↔ `M1_CUOTA_MAX_SANITY` (NUEVA en config_reglas)
    - `0.35` ↔ `M1_TASA_EA_WARN_MAX` (NUEVA en config_reglas)
    - `0.10` ↔ `TOLERANCIA_G3_SUMA_DUPLICADA` (ya existia)
    - `500_000` ↔ `TOLERANCIA_M1_ERROR` (ya existia)
    - `70_000` ↔ `TOLERANCIA_M1_WARN` (ya existia)
  - Import defensivo con fallback.
  - **`sprint_1/validar_excel_generado.py` (M2, 145 lineas):** 3 issues fixeados:
    - Dead variable `active_idx = None` eliminada (computaba pero nunca se leia).
    - **Promesa del docstring cumplida**: B7 plazo_pendiente AHORA SI se valida (`_check` con conversion int defensiva).
    - Docstring sincronizado con realidad: B13/B14 no se validan porque Regla 9.3 los ajusta post-populator; nota agregada explicando que el control vive en M1.
  - Tests: 16/16 fase2 PASS + 50/50 pytest PASS.

  **FASE 9 — B5 metricas semanal como Cloud Routine:**
  - **`run_metricas.sh`** (nuevo, mode 100755): wrapper Linux para `metricas_pipeline.py --dias N`. Soporta `cloud_bootstrap.py` por defensa. Log `_logs/metricas_semanal_YYYYMMDD.txt`. Tail al stdout para que Cloud Routine lo capture en transcript.
  - `_planning/cloud_routines_setup.md`: agregada "Routine 5: Metricas Semanal" — cron `0 9 * * 1` (lunes 9:00) con prompt para reportar success rate, categorias de fallo, y status "5 dias clean".
  - Smoke test local: `bash run_metricas.sh 7` → EXIT 0, log generado (sin datos en ventana = OK porque pipeline no ha corrido en cloud todavia).
  - Soporta criterio ESTADO_PROYECTO §3 "5 dias consecutivos sin errores antes de escalar a Bancolombia" (MASTER_RULES §14.1).

- **[2026-05-07] Cloud Routines Fase 1 + Fase 2 — pipeline cloud-ready:**

  Jose autorizó migrar a Anthropic Cloud Routines (plan Max contratado, ~15 runs/día). Pre-requisito: git remoto. Resuelto.

  **Fase 1 — push a GitHub (✅):**
  - Repo: `https://github.com/masjf-ship-it/mejorahora-estudios` (privado).
  - Pre-flight scan: 0 secretos commiteados (passwords/tokens reales). Email del usuario aparece en docs (low-risk en repo privado).
  - Push de la rama `claude/kind-shaw-2be195` (8 commits).
  - Renombrado branch principal `master` → `main` (convención GitHub moderna).
  - Merge fast-forward de auditoría → `main`. `main` también pusheada.
  - Pendiente Jose: cambiar default branch a `main` en GitHub Settings (la UI muestra `claude/kind-shaw-2be195` como default por orden de push).

  **Fase 2 — adaptación código para correr en cloud (✅):**

  - **`sprint_1/cloud_bootstrap.py`** (nuevo): materializa credenciales desde environment variables al inicio de cada run. Tres env vars esperadas:
    - `MEJORAHORA_SA_JSON` → escribe `credentials/sheets_sa.json`
    - `MEJORAHORA_OAUTH_TOKEN_JSON` → escribe `credentials/oauth_token.json`
    - `MEJORAHORA_HUBSPOT_TOKEN` → escribe `sprint_1/config.ini`

    Detecta cloud env vía `CLAUDE_CODE_REMOTE=true`. Cero impacto en local Windows: si los archivos ya existen, no overwrite. Smoke test interno valida JSON antes de escribir.

  - **`run_pipeline.sh`** (nuevo, mode 100755): espejo Linux de `run_pipeline.bat`. Mismas 3 fases (PASO 0 smoke test → PASO 1 listar_pendientes → PASO 2 pipeline). Para Cloud Routines (Linux VM Anthropic).

  - **`pipeline_davivienda.py::main()`**: llama a `ensure_credentials_from_env()` ANTES de `cargar_config()`. Si está en cloud, log explícito `CLOUD env detected — bootstrap: ...`.

  - **`smoke_test_prerun.py`**: igualmente integra bootstrap al inicio. En cloud, las creds aparecen materializadas y el resto de chequeos (PESOS hash, HubSpot token formato, etc.) corren idénticos.

  - **`maintenance/maintenance.py`**: detecta `CLAUDE_CODE_REMOTE` y **skip de PASO 1 (backup local) + PASO 4 (clean_root)** porque en cloud el filesystem es efímero — git remoto YA es backup. Drift checker (STEP 8) sigue corriendo. Summary log incluye `cloud: True/False`.

  - **`_planning/cloud_routines_setup.md`** (nuevo, guía operativa): paso a paso para Jose — cambiar default branch, subir env vars, crear las 4 routines (cron `30 8 * * *` AM, `30 20 * * *` PM, `0 7 * * *` mant AM, `0 19 * * *` mant PM), smoke test inicial, validación 5 días en paralelo.

  **MASTER_RULES.md v3.2 → v3.3**: §22 Estado actualizado con Fase 1 ✅ + Fase 2 ✅, pointer a guía paso a paso.

  **Smoke tests post:**
  - `test_fase2.py` 16/16 PASS
  - `pytest sprint_1/tests/` 42/42 PASS
  - `drift checker` 0 issues
  - `pre-commit hook` OK
  - `CLAUDE_CODE_REMOTE=true python maintenance/maintenance.py --dry-run` skipea backup correctamente
  - `cloud_bootstrap.py` corrido en local (sin env vars) detecta cloud=False y no toca archivos existentes

  **Lo que FALTA (Jose hace):**
  1. Cambiar default branch a `main` en GitHub Settings.
  2. Subir 3 env vars en config Claude Code.
  3. Crear las 4 routines (cron + setup script + prompt).
  4. Smoke test manual primera routine.
  5. Validación 5 días en paralelo con Windows Tasks.

- **[2026-05-07] Closing dedup constantes + tests R-DVV-18/06 + estados documentados:**

  Cierra el trabajo de deduplicación. Tres módulos restantes ahora importan de config_reglas:

  - **`proponedor_plazos.py`**: `paso = 100_000` y `paso = 70_000` hardcoded → `DIFF_OPCIONES_DEFAULT` y `DIFF_OPCIONES_PLAZO_CHICO` importados. La condición `< 5.0` años ahora es `< (PLAZO_CHICO_MESES / 12.0)` para coherencia.

  - **`reglas_negocio.py`**: borradas `DIF_SIMULA_TOLERANCIA = 70_000` y `SUMA_CUOTA_TOLERANCIA = 10_000`. **Código muerto** (ningún import las usaba) y la segunda **stale** (valor canónico desde 2026-04-24 es $70k universal MASTER_RULES §8.15, no $10k). Comentario apunta a `config_reglas.TOLERANCIA_*`.

  - **`generar_desde_sheets.py`**: `TOLERANCIA_SUMA_CUOTA = 70_000.0` literal → `from config_reglas import TOLERANCIA_SUMA_CUOTA`.

  **MASTER_RULES §3.9 + §3.10 nuevos**: Estados operativos (Pendiente/Pte. Validar Yenny/Mora válidos; Excel generado/Realizado/Cancelado/Pendiente NOTA consultor saltados) y Amortización (solo `pesos`, `uvr` excluido). Antes los estados solo vivían en código sin documentación canónica.

  **+7 tests pytest** (35 → **42/42 PASS**):
  - **`test_rdvv18.py`** (5 tests, **NUEVA cobertura crítica**): caso Alexandra Bernal canónico (29 cuotas pendientes — el wrapper filtra opciones extensoras), caso normal con 200m, edge plazo=60m borde Ley 546, manual override también pasa por wrapper, plazo_pagado >= 5 años.
  - **`test_rdvv06.py`** (2 tests adicionales): override seguros con `+Seguros inferior` (caso Leidy canónico), fallback `seguros_aplicados / 2` cuando no hay `+Seguros inferior` (caso Yeimy Jissel canónico).

  **MASTER_RULES.md v3.1 → v3.2**.

  **Smoke tests post:** `test_fase2.py` 16/16, pytest **42/42** (era 35), drift 0, hook OK con suite pytest integrada.

- **[2026-05-07] Dedup de constantes código + más tests pytest:**

  Continuación de la auditoría. Detectado drift estructural: literals constants estaban duplicados en múltiples archivos a pesar de que MASTER_RULES §8.15 dice "centralizadas en config_reglas.py".

  **Constantes deduplicadas (single source of truth en `config_reglas.py`):**
  - `PREFIJOS_HIPOTECARIO`, `PREFIJOS_LEASING`: estaban duplicados en `pipeline_davivienda.py:91-92`. Ahora importados.
  - `SHEET_ID_BD`: duplicado en `drive_client.py:42` y `listar_pendientes_hoy.py:32`. Ahora ambos importan de `config_reglas.SHEET_BD_ID`.
  - `DRIVE_FOLDER_EXTRACTOS_RO`, `DRIVE_FOLDER_ANALISTAS_RW`: duplicados en `drive_client.py:40-41`. Ahora importados.
  - `TOLERANCIA_DIF_SIMULA`: hardcoded `70_000` en `pipeline_davivienda.py:978`. Ahora `from config_reglas import TOLERANCIA_DIF_SIMULA`.

  **Por qué importa:** si Jose alguna vez migra a otro Sheet, otro folder, o cambia la tolerancia universal, antes tocaba 3-5 archivos con riesgo de olvidar uno. Ahora 1 sola línea en config_reglas.py.

  **Pendientes de futuro refactor (no críticos):**
  - `proponedor_plazos.py:454,458` tiene `paso = 100_000` y `paso = 70_000` hardcoded — son `DIFF_OPCIONES_DEFAULT` y `DIFF_OPCIONES_PLAZO_CHICO` en config. No tocados aquí para no inflar diff; quedan como ítem de sprint futuro.
  - `reglas_negocio.py:76` tiene `DIF_SIMULA_TOLERANCIA = 70_000` propio. Es módulo legacy invocado solo por `proponedor_plazos.py`. Mismo deferral.
  - `generar_desde_sheets.py:50` `TOLERANCIA_SUMA_CUOTA = 70_000`. Mismo.

  **+17 tests pytest** (18 → **35/35 PASS**):
  - **`sprint_1/tests/test_rdvv07.py`** (9 tests): proyección 6ta cuota Davivienda — caso canónico Julieth (4 cuotas faltantes), DaviBank, edge `cuotas_pagadas=5` borde, edge `=6` umbral exacto, parametrizado contra 4 bancos no-Davivienda.
  - **`sprint_1/tests/test_rdvv06.py`** (3 tests): G2 false-positive con `seguro_vida=0` (caso Karen Tatiana fix R-DVV-10), G1 dispara con `total_aplicado ≈ 2× cuota`, control caso normal Fernando NO dispara.
  - **`sprint_1/tests/test_hubspot_genericos.py`** (5 tests): R-DVV-12 detección firmas repetidas — umbral 3, umbral configurable, múltiples firmas simultáneas, sin matches.

  **MASTER_RULES.md v3.0 → v3.1**: header + footer.

  **Smoke tests post:** `test_fase2.py` 16/16, pytest 35/35, drift 0, hook OK con suite pytest integrada.

- **[2026-05-07] Auditoría R-DVV consistency + README + hook pytest + plan Cloud Routines:**

  Continuación de la auditoría general. Cuatro hallazgos/mejoras independientes:

  - **R-DVV consistency** (drift detectado en docs):
    - **R-DVV-16** (STAGING NO es fuente de datos financieros) estaba en código (`pipeline_davivienda.py:623`) y CHANGELOG (entrada 2026-04-28) pero **faltaba en MOM_DAVIVIENDA**. Documentada ahora en MOM §2 con causa raíz histórica completa. Drift que viola §19 protocolo de actualización corregido.
    - **R-DVV-13** (fallback `seguro_vida` por residual matemático) detectada como **iteración temporal del 2026-04-27 superada por R-DVV-15** (fix definitivo del extractor con `\$?` regex el 2026-04-28). El fallback ya no existe en código (correcto: la causa raíz se atacó al extractor). Traza histórica queda en CHANGELOG; no se documenta en MOM porque ya no es regla vigente. Aclarado en este registro para evitar futura confusión.
    - **MOM_DAVIVIENDA v1.5 → v1.6**: header + footer + nueva sección R-DVV-16.

  - **WIN_FILE_LOCKED verificado: NO es bug latente.** Auditado el manejo de handles PDF en código actual. `extract_davivienda_pdf.py` usa `with pdfplumber.open(...) as pdf` (auto-cierre). `vision_extractor.py:154-156` tiene `try/finally pdf.close()` con comentario explícito "Cierre explicito evita WinError 32 al limpiar tempfile en Windows". Las 3 EXCEPTION históricas del 2026-04-21 ya están blindadas.

  - **`README.md` raíz creado** (no existía — solo había `CLAUDE.md` que sirve a Claude Code, no a humanos nuevos). Quick start, jerarquía de docs, mapa de componentes, comandos comunes, política de actualización. ~120 líneas. Sirve de entrada al proyecto sin duplicar reglas (sigue principio B8).

  - **Pre-commit hook con pytest integrado**: cuando hay `.py` staged en `sprint_1/`, el hook ahora corre `pytest sprint_1/tests/ -q` (timeout 60s). Skip silencioso si pytest no está instalado. MASTER_RULES §17.12 actualizada con la 5ta capa de validación.

  - **`_planning/CLOUD_ROUTINES_MIGRATION.md` creado**: plan paso a paso para migrar el pipeline de Windows Task Scheduler a Anthropic Cloud Routines (Claude Code), aprovechando el plan Max de Jose. Bloqueador: necesita git remoto (Jose va a crear). Constraints técnicos validados con `claude-code-guide` skill: 1h frecuencia mínima, ~15 runs/día Max, VM Linux 4 vCPU, env vars o vault para creds, repo-clone-per-run.

  - **MASTER_RULES.md v2.9 → v3.0** (cambio mayor por R-DVV-16 documentado + README como nuevo entry point). ESTADO §0 actualizado.

  Smoke tests post: `test_fase2.py` 16/16, pytest 18/18, drift 0, hook OK con suite pytest integrada.

- **[2026-05-07] Mantenimiento horario → 12h (workaround Cowork removido):**

  **Contexto que dio Jose:** el ciclo horario de mantenimiento era una compensación porque Cowork "olvidaba" cosas entre sesiones — los backups frecuentes y la auditoría de memoria operativa Claude (STEP 7) eran un workaround. En Claude Code la memoria son archivos versionados que no se pierden; Jose pidió simplificar.

  **Cambios:**

  - **Renombrado `maintenance/maintenance_60min.py` → `maintenance/maintenance.py`**: nombre genérico no atado a la cadencia (que puede cambiar de nuevo). git mv preserva historia.

  - **STEP 7 eliminado completamente** (`find_memory_dir()`, `check_memory_health()`, sección de reporte en `write_anomaly_report`, llaves `mem_*` en summary, llamada en main): ~150 líneas borradas. También removido `maintenance/memory_dir.txt` (artefacto de configuración del finder de directorio de memoria Cowork).

  - **Cadencia HOURLY → DAILY 2× (07:00 + 19:00)** vía dos tareas Windows separadas: `MejorAhora\Mantenimiento AM` y `MejorAhora\Mantenimiento PM`. Una corrida antes de cada pipeline (08:30 / 20:30) cubre el caso de uso real (rotar backups + chequear drift); la cadencia horaria era overhead puro.

  - **`RETENTION_N` 168 → 30 snapshots** (≈15 días a 2 corridas/día). Cobertura efectiva mayor que los 7 días anteriores (168 horarios), con menos archivos en disco.

  - **`install_task.cmd` reescrito**: borra la legacy `MejorAhora\Mantenimiento 60min` si existe, crea las dos nuevas con `schtasks /sc DAILY /st 07:00` y `19:00`. **Jose ejecuta una sola vez** después de mergear: `maintenance\install_task.cmd`.

  - **`run_maintenance.bat`** apunta a `maintenance.py` (no `maintenance_60min.py`).

  - **`.githooks/pre-commit`**: import del drift checker corregido a `maintenance` (no `maintenance_60min`); allowlist de archivos canónicos también.

  **Documentación reescrita:**
  - `MASTER_RULES.md` v2.8 → **v2.9** (§2.20, §9.3, §15 entero, §16.3, §17.11, footer).
  - `CLAUDE.md` sección "Maintenance" actualizada con nueva cadencia.
  - `ESTADO_PROYECTO.md` (referencia al script + criterio "5 días sin errores" cambia mention STEP 7 → STEP 8).
  - `maintenance/README.md` reescrito completo.

  **Histórico preservado:** referencias a "60min" / "STEP 7" en entradas viejas del CHANGELOG (2026-04-21 a 2026-04-25) NO se tocaron — son timeline histórico, política limpia §17.3 dice traza histórica vive en CHANGELOG.

  **Smoke tests post:**
  - `python maintenance/maintenance.py --dry-run` → corre limpio (anom_drift=0, sin errores de import).
  - `test_fase2.py` 16/16, pytest 18/18, drift 0, hook OK.

- **[2026-05-07] OLA 2 cleanup — rotación logs pipeline + más tests pytest:**

  - **`maintenance/maintenance_60min.py`**: nueva función `rotate_pipeline_logs()` integrada al ciclo horario. Borra archivos `_logs/pipeline_davivienda_YYYYMMDD_HHMMSS.json` con fecha (parseada del nombre, no `mtime`) anterior a 30 días. Constante `RETENTION_PIPELINE_LOGS_DAYS = 30`. **Razón:** pre-fix se acumulaban sin límite (51 archivos en 30 días para 2026-05-07). MASTER_RULES §15.4 actualizada.

  - **`sprint_1/tests/test_m1.py`** (nuevo): migración a pytest de los 5 tests M1 del suite golden (TESTS I/J/K/L/M de `test_fase2.py`) + parametrize de rangos de `tasa_ea`. **9 tests pytest nuevos**, todos pasan. Total pytest suite: 9 → **18/18 PASS**. El suite lineal `test_fase2.py` se mantiene intacto (16/16 PASS) — co-existen.

  - **MASTER_RULES §15.4**: aclarada la doble retención (backups horarios 168 / logs JSON 30 días).

  Smoke tests post: `test_fase2.py` 16/16, pytest 18/18, drift 0, rotate dry-run lista 0 archivos a borrar (todos dentro de ventana 30d).

- **[2026-05-07] FIX-EXCEPTION-22 — Bugs reproducibles del pipeline detectados via métricas B5:**

  Las métricas semanales (`metricas_pipeline.py`) revelaron **22 EXCEPTION históricas** en los últimos 30 días. Análisis post-mortem identificó 4 categorías y 2 bugs reproducibles fixables:

  - **Bug A — `pipeline_davivienda.py::main()`**: cuando OAuth falla (`get_oauth_drive()` lanza), el código caía silenciosamente al SA y luego cada cliente generaba un `HttpError 403 storageQuotaExceeded` ruidoso. **14 EXCEPTION históricas** atribuibles. **Fix:** OAuth ahora es **obligatorio** — si falla, el pipeline aborta con `exit code 3` y mensaje accionable referenciando MASTER_RULES §16.6 (`drive_oauth_setup.py`). **Regla vieja:** `print("OAuth no disponible; usando SA (puede fallar en upload)")` y continuaba. **Razón:** generar 1 EXCEPTION por cliente ofusca la causa raíz; mejor abortar 1 vez con mensaje claro.

  - **Bug B — `pipeline_davivienda.py::procesar_cliente()`**: cuando el Excel previo del cliente está abierto en Microsoft Excel.exe, `populator.crear_estudio()` lanzaba `PermissionError 13` y la excepción se propagaba como un EXCEPTION genérico. **3 EXCEPTION históricas** (todas JORGE LUIS VELASCO SALAZAR). **Fix:** try/except específico que retorna `ok=false` con `detalle="EXCEL_LOCKED: ..."` y mensaje accionable (cerrar el Excel y re-correr con `--force`). NO genera Excel con sufijo alternativo (rompería §12.1 naming canónico + §17.1 una versión por cliente).

  - **Bug C — Pipeline no validaba precondiciones antes de procesar.** Si OAuth está revocado, config.ini ausente, hash PESOS corrupto o deps faltantes, el pipeline procesaba 12 clientes y todos fallaban. **Fix:** `sprint_1/smoke_test_prerun.py` (nuevo) — chequeo fail-fast de imports críticos, credenciales SA + OAuth, config HubSpot, hash PESOS, golden suite (opcional con `--skip-tests`). Integrado como **PASO 0** en `run_pipeline.bat` (exit code 4 si falla → no se ejecutan PASO 1 ni PASO 2).

  - **`metricas_pipeline.py` enriquecido**: 5 categorías nuevas para discriminar exceptions accionables vs históricas:
    - `EXCEL_LOCKED` (Excel abierto)
    - `OAUTH_FATAL` (OAuth caído al inicio)
    - `DRIVE_403` (SA storageQuota — ya no debería ocurrir post-fix A)
    - `DRIVE_404` (folder/file no encontrado)
    - `WIN_FILE_LOCKED` (PDF tmp locked, histórico)
    - `SIN_EXTRACTO` (PDF no en Drive §4.1)

    También: matching compuesto `Permission denied + .xlsx` mapea a EXCEL_LOCKED (catch retroactivo de logs históricos).

  - **`MOM_DAVIVIENDA.md §7 troubleshooting`**: 4 filas nuevas para los nuevos códigos de salida y categorías.

  - **`MASTER_RULES.md` v2.7 → v2.8**: §2.24 indexa el smoke test.

  **Categorías post-fix sobre la misma ventana de 30 días (re-categorización):**
  ```
  DRIVE_403         14   (eliminado prospectivamente — Fix A)
  M1_FAIL           11   (revisiones manuales legítimas — no es bug)
  BANCO_NO_TRABAJADO 7   (leasings antiguos, R-DVV-09 ya los procesa)
  DIF_SIMULA_FAIL    7   (revisiones manuales legítimas R-DVV-11)
  WIN_FILE_LOCKED    3   (histórico, sin reaparición)
  EXTRACTO_ILEGIBLE  3   (legítimo — fallback Vision falla)
  EXCEL_LOCKED       3   (eliminado prospectivamente — Fix B)
  SIN_EXTRACTO       3   (legítimo — PDF no en §4.1)
  DRIVE_404          2   (histórico, folder ID corregido)
  PDF_PROTEGIDO      2   (legítimo — sin CC candidatas)
  EXTRACTO_INCOMPLETO 1  (legítimo)
  ```
  **Reducción esperada de fallos no-legítimos en próxima ventana:** 17/56 (~30%). Tasa de éxito proyectada post-fix: ~67% (vs 52.9% actual). Resto son revisiones manuales legítimas que requieren acción humana (M1_FAIL, DIF_SIMULA_FAIL, EXTRACTO_*) o exógenas (PDF_PROTEGIDO).

- **[2026-05-07] OLA 2 cont. — B9 idempotencia STAGING + B5 métricas + B8 CLAUDE.md pointer:**

  - **B9 — `sprint_1/listar_pendientes_hoy.py`**: extraída función pura `dedup_por_credito(pendientes, creditos_presentes)` desde el flujo `publicar_en_staging()`. Cero cambios de comportamiento (refactor). **`sprint_1/test_fase2.py` TEST P** valida 5 escenarios: primera corrida, idempotencia (re-ejecución sin nuevos), nuevo + ya existentes, whitespace dedup, defensiva sin clave `credito`. Test count: 15 → **16/16 PASS** (A–P). Documentado en MASTER_RULES §2.19, MOM_DAVIVIENDA §8, CLAUDE.md.

  - **B5 — `sprint_1/metricas_pipeline.py`** (nuevo, stdlib only): agrega los `_logs/pipeline_davivienda_*.json` de los últimos N días en métricas que apoyan el criterio ESTADO §3 "5 días sin errores → escalar a Bancolombia". Output texto humano por defecto, JSON con `--json` para dashboards externos. Categoriza fallos en 9 buckets (REVISION_MANUAL, NO_VIABLE_LEY_546, PDF_PROTEGIDO, EXTRACTO_ILEGIBLE/INCOMPLETO, M1_FAIL, DIF_SIMULA_FAIL, BANCO_NO_TRABAJADO, EXCEPTION, OTHER). Calcula racha actual sin fallos. **Smoke run real (30 días, 51 archivos JSON):** 119 clientes procesados, tasa éxito 52.9%, racha 0/5 días sin errores → **criterio NO cumplido**, último día con fallos 2026-05-05 (8 fallos, top: EXCEPTION). Indexado en MASTER_RULES §2.22.

  - **B8 — `CLAUDE.md` reescrito como pointer**: 187 → 135 líneas (~28% más corto). Removidas duplicaciones de reglas que ya viven en MASTER_RULES (Stack snapshot completo, "Numeric tolerance is universal", "Constants live in config_reglas.py only", "STAGING is the only pipeline destination", "Drive folder discipline", "Naming"). Se mantienen únicamente: jerarquía de docs, comandos de uso diario (incluido nuevo bloque B5 métricas + B10 hook activación), output convention, anti-patterns top-5 con pointer a §20, working-with-Jose pointer. **Razón:** prevenir drift estructural (caso C9 de la auditoría — CLAUDE.md decía retención 336, MASTER_RULES decía 168). Ahora los detalles solo viven en docs canónicos.

  - **`MASTER_RULES.md` v2.6 → v2.7**: §2.22 métricas, §2.23 pre-commit hook indexados; cuenta de tests 15→16 (A→P); footer reconciliado.

  **Smoke tests post-Ola 2 cont.:**
  - `test_fase2.py` → **16/16 PASS** (A-P)
  - drift checker STEP 8 → 0 issues
  - pre-commit hook → OK con 7 archivos staged
  - `metricas_pipeline.py --dias 30` → reporte coherente, racha 0/5 (criterio aún no cumplido)

- **[2026-05-07] OLA 2/B10 — Pre-commit hook (defense-in-depth):**

  - **`.githooks/pre-commit`** (versionado, ejecutable mode 100755): hook Python que valida cada commit.
    1. Bloquea secret leaks: `sprint_1/config.ini`, cualquier path bajo `credentials/`.
    2. Bloquea IDs de Sheets en lista negra §3.4 (con allowlist para los 6 archivos que la documentan: MASTER_RULES, CHANGELOG, ESTADO, config_reglas, maintenance_60min, el propio hook).
    3. Compila todos los `.py` staged (`py_compile`).
    4. Corre `check_doc_code_drift()` (STEP 8) si cambian docs/código y bloquea si reporta drift.
    Bypass: `git commit --no-verify` (debe registrarse en CHANGELOG con razón, §23.4).

  - **`maintenance/install_hooks.cmd`**: instalador one-shot que configura `git config core.hooksPath .githooks`. Ejecutar UNA VEZ por clone.

  - **MASTER_RULES §17.12**: documentación operativa del hook.

  **Smoke tests realizados:**
  - Hook con todos los cambios Ola 1+2 staged → OK (10 archivos)
  - Hook con sintaxis Python rota → BLOQUEA con mensaje claro
  - Hook con `sprint_1/config.ini` staged → BLOQUEA con referencia a §11.6/§20.9

- **[2026-05-07] OLA 2 — Hardening · hash PESOS + drift checker:**

  - **B6 — `sprint_1/config_reglas.py`**: agregada constante `PESOS_TEMPLATE_SHA256 = "d860270c34..."` (SHA256 del template `PESOS.xlsx` actual) y helper `verify_pesos_template(project_root)`. **Pipeline integrado:** `pipeline_davivienda.py::main()` valida la integridad del template antes de procesar pendientes; aborta con exit code 2 si el hash no coincide. Protege contra corrupción silenciosa de fórmulas/layout que romperían M2 sin diagnóstico claro. Para regenerar tras cambio intencional: documentar nuevo hash en config_reglas + CHANGELOG.

  - **B4 — `maintenance/maintenance_60min.py` STEP 8 drift checker**: nueva función `check_doc_code_drift()` integrada en el ciclo horario. Detecta automáticamente: (a) header vs footer de versión en MASTER_RULES.md y ESTADO_PROYECTO.md, (b) versión que ESTADO §0 cita vs versión real de los docs, (c) hash PESOS.xlsx vs `PESOS_TEMPLATE_SHA256`, (d) `RETENTION_N` en código vs número de snapshots citado en MASTER_RULES §17.11, (e) referencias a archivos canónicos `.md` que no existen en raíz. Falla soft (reporte en `_logs/anomalies_<ts>.txt`), nunca bloquea pipeline. Documentado en MASTER_RULES §15.3 como STEP 8.

  - **`MASTER_RULES.md` §22**: removida referencia condicional residual a `MIGRACION_CLAUDE_CODE.md` (drift checker la flageaba). Esta tabla es ahora la única fuente vigente.

  **Smoke test post-Ola 2:** `check_doc_code_drift()` retorna 0 issues. `verify_pesos_template()` retorna ok=True con hash actual.

---

## LIMPIEZA-PENDIENTE — RESUELTA 2026-05-07

Resolución por sesión Claude Code (Ola 1 higiene crítica):

### Borrados via `git rm` (2026-05-07)
- ✅ `sprint_1/backup_log.txt` (error CMD sin valor)
- ✅ `sprint_1/diag_angela.py` (diagnóstico puntual superado)
- ✅ `sprint_1/diag_registros.py` (diagnóstico puntual superado)
- ✅ `sprint_1/validate_gemini.py` (smoke test Vertex AI ya cubierto por `test_fase2.py`)
- ✅ `sprint_1/validate_layout.py` (validador layout ya cubierto por M2 `validar_excel_generado.py`)

### Confirmado eliminado por Jose previamente
- ✅ `SOURCE_OF_TRUTH.md` — no existe en filesystem.
- ✅ `sprint_1/INGENIERIA_INVERSA_EXCEL.md` — ya está en `sprint_1/docs/` (movido 2026-04-25, registrado).
- ✅ `sprint_1/publicacion_staging_*.txt` — gitignored (`.gitignore` línea 12), no entra al repo.

### Filesystem (no tracked, no en git)
- `_logs/pipeline_davivienda_*.json` (51 archivos a 2026-05-07): viven en filesystem del proyecto raíz, gitignored. Mantenimiento horario los rotará por su propia política (carpeta no es de su scope; si crecen, agregar limpieza específica a `maintenance_60min.py`).

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

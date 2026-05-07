# MOM_DAVIVIENDA — Master Operating Manual · Banco Davivienda
**Versión:** 1.5 · 2026-05-05 (R-DVV-18: guardia plazo pendiente + NO_VIABLE_LEY_546)
**Específico de Davivienda. Para reglas generales del proyecto: ver `MASTER_RULES.md`.**

> **Precedencia:** banco-específico (este archivo) gana sobre general (MASTER_RULES) en caso de contradicción.
> **Pipeline:** `sprint_1/pipeline_davivienda.py`
> **Constantes centralizadas:** `sprint_1/config_reglas.py`
> **Tests:** `sprint_1/test_fase2.py` (16 tests A-P)

---

## 1. Identificación del banco

El extracto es Davivienda cuando aparece **cualquiera** de:
- Logo "DAVIVIENDA" en encabezado
- `NIT. 860.034.313-7`
- `Banco Davivienda S.A.`
- Título "Extracto Crédito Hipotecario" (formato Davivienda específico)

### 1.1 Bancos cubiertos por este MOM
- **Davivienda** (DAVIVIENDA)
- **DaviBank** — mismo grupo financiero, aplican reglas idénticas (R-DVV-07 incluida)

---

## 2. R-DVV: Reglas de Extracción Davivienda (15 reglas)

### R-DVV-01 — "Seguro Protección de Pagos" → seguro_terremoto
"Seguro Protección de Pagos" se SUMA al slot `seguro_terremoto`. El slot agrupa todo seguro no-vida no-incendio. Si solo aparece "Protección de Pagos" sin "Terremoto" → `seguro_terremoto = valor de Protección de Pagos`.

### R-DVV-02 — "Bonos a Capital" = capital mensual
`abonos_capital` = "Bonos a Capital" del extracto. **NUNCA** confundir con "Total Aplicado" (es el pago total mes).

### R-DVV-03 — Saldo capital = total, no parcial
`saldo_capital` = saldo TOTAL al corte (cuadro RESUMEN INFERIOR). Heurística: > $1,000,000 para hipotecario activo. NO tomar saldos parciales mensuales.

### R-DVV-04 — Validación cruzada (M1 obligatorio)
Ver `MASTER_RULES §9.1`. M1 valida antes de generar Excel:
- saldo_capital > $1M
- cuota_mensual > 0 y < $10M
- 0 < tasa_ea < 1
- plazo_pendiente ≤ plazo_inicial
- credito_id, nombre no vacíos
- suma(seg+cap+int) vs cuota: ±$70k warn / ±$500k error
- `seguro_vida=0 AND seguro_incendio>0` → ERROR (R-DVV-10)

### R-DVV-05 — Diccionario canónico Davivienda

| Etiqueta PDF | Campo JSON |
|---|---|
| Seguro de Vida | `seguro_vida` (CRÍTICO — siempre extraer si existe) |
| Seguro de Incendio y Anexos | `seguro_incendio` |
| Seguro de Terremoto | `seguro_terremoto` (base) |
| Seguro Protección de Pagos | SUMAR a `seguro_terremoto` |
| Bonos a Capital | `abonos_capital` |
| Intereses Corrientes | `intereses_corrientes` |
| Intereses de Mora | `intereses_mora` |
| Total Aplicado | `total_aplicado` (NO confundir con capital) |
| Valor Cuota Mes | `cuota_mensual` |
| "+ Seguros" cuadro inferior 2ª hoja | `seguros_inferior_total` |
| Tasa Interés Cte. Cobrada | `tasa_cobrada` (la que se usa en estudio) |
| Tasa Interés Cte. Pactada | `tasa_pactada` (referencia) |
| Saldo a [fecha] | `saldo_capital` (cuadro resumen inferior) |
| -Cobertura de Tasa | `frech_cobertura_pag1` (subsidio FRECH) |

### R-DVV-06 — Duplicación de cuota por mala pagaduría (3 gatillos OR)
Cuando cliente paga 2+ cuotas en un mes (mora):

**Detección:**
- **G1:** `total_aplicado ≈ 2 × cuota_mensual` (tolerancia ±5%)
- **G2:** `|seguros_aplicados − seguros_inferior_total| > $10k` **AND `seguro_vida_aplicado > 0`** (refinado para evitar falso positivo cuando Vision no extrae vida)
- **G3:** `(seg + cap + int) ≈ 2 × cuota_mensual` (tolerancia ±10%) — útil cuando Vision no extrae G1/G2

**Override seguros (cuando R-DVV-06 dispara):**
- Si `seguros_inferior_total > 0` → `seguro_vida = ese valor`, `incendio = 0`, `terremoto = 0`
- Si NO → `seguro_vida = seguros_aplicados / 2`, `incendio = 0`, `terremoto = 0`

**Capital/intereses:** los corrige Regla 9.3 automática (copia del simulador).

### R-DVV-07 — Proyección a 6ª cuota paga (Davivienda/DaviBank)
**Política banco:** no inicia proceso si cliente <6 cuotas pagadas. Pipeline proyecta como si ya estuviera en mes 6.

```python
if banco in {"DAVIVIENDA", "DAVIBANK"} and cuotas_pagadas < 6:
    tasa_mv = (1 + tasa_ea)**(1/12) - 1
    cuota = cuota_mensual_total  # incluye seguros (decisión Jose: simplicidad comercial)
    saldo = saldo_capital
    for _ in range(6 - cuotas_pagadas):
        interes = saldo * tasa_mv
        capital = cuota - interes
        saldo -= capital
    saldo_capital = saldo  # proyectado
    plazo_pendiente -= (6 - cuotas_pagadas)
    # NO tocar capital_mensual ni interes_mensual del mes actual
```

Nota CRM en columna L STAGING: "Proyección a 6ª cuota — política banco. Cliente actualmente en cuota N."

### R-DVV-08 — Prefijos válidos por tipo
- **Hipotecario:** `("570", "571")` → procesar E2E
- **Leasing:** `("600",)` → procesar IGUAL que hipotecario (ver R-DVV-09)
- **Consumo Garantía Hipotecaria:** `("590",)` → **NO APLICA** al flujo MejorAhora (excluir)
- **Otros prefijos** → "Crédito no reconocido", skip

### R-DVV-09 — Leasing = Hipotecario (sin tratamiento especial)
**Regla Jose:** Leasing habitacional (prefijo 600) se procesa **EXACTAMENTE IGUAL** que hipotecario. Mismo template, mismo proponedor, mismos honorarios. **FRECH NO es traba** — se lee del extracto y la plantilla calcula bien. **NUNCA** aplicar fórmula MIN(frech, interes) ni celdas G5/G6 (revocado 2026-04-23).

### R-DVV-10 — M1 bloquea seguro_vida=0 con incendio>0
Si Vision devuelve `seguro_vida=0 AND seguro_incendio>0` → M1 ERROR → REVISION_MANUAL. En extractos hipotecarios casi siempre existe seguro de vida (obligatorio).

### R-DVV-11 — DIF.SIMULA tolerancia ±$70k post-9.3
Después de Regla 9.3, recalcular DIF.SIMULA. Si `|DIF.SIMULA| > $70k` → REVISION_MANUAL aunque SUMA CUOTA esté OK. Atrapa casos como Gilma (cuota incoherente con plazo pendiente).

### R-DVV-12 — HubSpot genérico repetido → REGISTROS
Pre-pasada `detectar_hubspot_genericos(umbral=3)`: si ≥3 clientes en la corrida tienen misma firma `(consultor, actividad, ingresos)` desde HubSpot → marcar firmas genéricas. Para esos clientes, ignorar `consultor/actividad/ingresos/abono` de HubSpot y caer a REGISTROS. Mantener `cc/email/phone/contact_id` de HubSpot.

**Caso real 2026-04-24:** HubSpot devolvía "Brillid Lorena Salinas + Docente + $3,186,000" para 5+ clientes Davivienda VIS. Era template, no datos reales. REGISTROS tenía info correcta por cliente.

### R-DVV-17A — Guard CC inválido en HubSpot (2026-04-29)
36+ contactos en HubSpot tienen `cedula="N/A"` como valor por defecto (venían del formulario web). Si el pipeline buscaba por `cedula="N/A"`, obtenía un contacto aleatorio con datos incorrectos.

**Fix:** Constante `_CC_INVALIDOS_HS = {"n/a","na","n.a.","n\\a","n-a",""}` en `enriquecer_con_hubspot()`. Si CC cae en ese set → `cc_clean=""` → se salta búsqueda por cédula en HubSpot → va directo a búsqueda por nombre.

**Diferencia con R-DVV-14:** R-DVV-14 aplica el guard en REGISTROS (Google Sheets). R-DVV-17A aplica el mismo guard al matching con HubSpot API. Son complementarios.

**Caso real:** JORGE LUIS VELASCO SALAZAR (CC=N/A en STAGING) → sin fix, buscaba `cedula="N/A"` en HubSpot → traía contacto incorrecto con abono=$100k.

### R-DVV-17B — Propiedades reales del portal HubSpot MejorAhora (2026-04-29)
El portal HubSpot de MejorAhora tiene nombres de propiedades propios que NO coinciden con los genéricos de HubSpot.

**Propiedades REALES confirmadas:**
- Ingresos: `valor_de_ingresos` (NO `ingresos` ni `ingreso`)
- Abono: `abono_efectivo` (fallback: `abono_extraordinario`) (NO `abono`)
- Cédula: `cedula` (fallback: `identificacion`, `numero_de_cedula`)

**Fix:** `HUBSPOT_PROPS` actualizado. `enriquecer_con_hubspot()` lee `props.get("valor_de_ingresos")` primero. Si se agregan nuevas propiedades, verificar que existan en el portal vía HubSpot MCP `search_properties` antes de usar.

### R-DVV-17C — Búsqueda por nombre multi-token en firstname (2026-04-29)
Muchos contactos HubSpot de MejorAhora tienen el nombre completo en `firstname` y `lastname` vacío (creados vía formulario web). La búsqueda original `firstname=token[0]` + `lastname=token[-1]` retornaba falsos positivos si otro contacto tenía el mismo apellido.

**Caso real:** Buscar "JORGE LUIS VELASCO SALAZAR" con `firstname="JORGE"` + `lastname="SALAZAR"` retornó "JORGE EMILIO SALAZAR RUIZ" (contacto diferente, abono=$100k, ingresos=$1.6M).

**Fix — Estrategia A (principal):** `search_contact_by_name()` busca TODOS los tokens del nombre en `firstname` (CONTAINS_TOKEN para cada token, hasta 5). Si hay exactamente 1 resultado → correcto. Si 0 o múltiples → Estrategia B (fallback original). Con todos los tokens "JORGE"+"LUIS"+"VELASCO"+"SALAZAR" en firstname, solo el contacto real hace match completo.

**Regla:** No revertir a estrategia de un solo token. Si hay matching incorrecto por nombre, primero verificar si hay múltiples contactos con tokens similares en el portal.

### R-DVV-18 — Guardia de plazo pendiente + pre-check Ley 546 (2026-05-05)

**Problema detectado:** Alexandra Bernal Vargas (29 cuotas pendientes, plazo_pagado < 5 años). El proponedor generaba opciones de 150+ cuotas, **extendiendo** el plazo del crédito. Doble violación: (1) regla fundamental de negocio — NUNCA extender plazo; (2) Ley 546/1999 — el crédito total tiene < 5 años, no existen opciones legales de reducción.

**Causa raíz en `_proponer_por_saltos_100k` y `_proponer_mixto_viable`:**
```python
# BUG (línea ~344): max(anio_max, ceil(anio_min_legal))
# Cuando anio_min_legal (ej. 5 - 2.42 = 2.58 → ceil = 3) > plazo_pend_anos (2.42)
# → elevaba el techo a 3 años, SOBRE el plazo pendiente de 2.42 → opciones extensoras
```

**Fixes aplicados:**

**Fix A — Techo en `_proponer_por_saltos_100k` y `_proponer_mixto_viable`:**
```python
# ANTES: anio_max = max(anio_max, math.ceil(anio_min_legal))  # extensión silenciosa
# DESPUÉS:
if anio_min_legal < plazo_pend_anos:
    anio_max = max(anio_max, math.ceil(anio_min_legal))  # solo si no cruza el piso
```

**Fix B — Guardia absoluta en `proponer_plazos()` (wrapper R-DVV-18):**
`proponer_plazos()` ahora llama a `_proponer_plazos_impl()` internamente y filtra el resultado:
```python
validas = [p for p in resultado.plazos_anos if p < plazo_pend_anos]
# Cubre TODOS los métodos: Mode A, B, E, manual, escalonado
```

**Fix C — Pre-check `NO_VIABLE_LEY_546` en `pipeline_davivienda.py`:**
Antes de llamar al proponedor, el pipeline calcula `anio_min_legal` y verifica si hay opciones posibles:
```python
if anio_min_legal >= plazo_pend_anos:
    → REVISION_MANUAL: NO_VIABLE_LEY_546
    # Muestra plazo_pend, anio_min_legal, credito_total vs 5 años
```

**Regla operativa:** Si un cliente tiene plazo pendiente tan corto que `plazo_pagado + plazo_pendiente < 5 años` → no se genera estudio → REVISION_MANUAL con mensaje `NO_VIABLE_LEY_546`. El consultor debe informar al cliente que el crédito no es elegible para optimización bajo los parámetros legales actuales.

**Caso real:** Alexandra Bernal — plazo_pagado ≈ 0 meses (crédito casi nuevo), plazo_pendiente = 29 meses (2.42 años). Total = 2.42 años < 5 años mínimo Ley 546. Sin opciones legales de reducción.

### R-DVV-14 — CC="N/A" no es cédula válida (2026-04-28)
En STAGING, la columna `Acceso` almacena credenciales bancarias (URL/contraseña), no la cédula. Si `Acceso = "N/A"`, el pipeline usaba ese valor como CC de búsqueda en REGISTROS → encontraba al primer cliente con `CC="N/A"` literal (ANDREA PAOLA DURAN TARAZONA) → copiaba sus datos financieros a TODOS los clientes con Acceso=N/A. FIX: en `_filtrar_pendientes_davivienda` y `enriquecer_con_registros`, los valores "N/A"/"NA"/"N.A." se tratan como CC vacío → cae a búsqueda por nombre → si REGISTROS no tiene datos financieros, escala a HubSpot. **Nunca usar "N/A" como clave de búsqueda en ningún campo identificador.**

### R-DVV-15 — Extracción seguro de vida: formato colombiano de miles (2026-04-28)
El extracto Davivienda muestra en la misma línea: `"Seguro de Vida   0,02294   22.021"` donde `0,02294` es la tasa mensual y `22.021` es el monto en pesos (formato colombiano: punto = separador de miles → 22,021 pesos). El extractor capturaba el primer número (la tasa), resultando en `seguro_vida = 0.02294`. FIX: función `_extraer_seguro_vida()` detecta si el primer número es tasa (`< 1.0`) y toma el segundo. Función `_peso_col()` convierte formato colombiano correctamente: `22.021` → 22021 (si el último grupo post-punto tiene exactamente 3 dígitos, es separador de miles). **Regla general: nunca confiar en `float("22.021")` para montos colombianos — siempre usar `_peso_col()`.**

---

## 3. Mapa de campos por hoja del extracto

### Hoja 1 (encabezado)
| Campo | Etiqueta | Notas |
|---|---|---|
| Número crédito | "Extracto Crédito Hipotecario" o "No del crédito" | Formato `570XXXXXXXXXXX-N` |
| Nombre cliente | Después de "Apreciado Cliente" | Tal como aparece |
| Email | Línea bajo nombre | Tal como aparece |
| Valor cuota mes | `+ Valor Cuota Mes` | Cuota que paga el cliente |
| Plazo original | `Plazo` | Meses (típico 240, 180, 120) |
| Cuotas pendientes | `No. Cuotas Pdtes. Pago Total` | Plazo remanente |
| Cuotas pagadas | `No. Cuotas que se cancela` | NO confundir con pendientes |
| Tasa Pactada | `Tasa Interés Cte.Pactada` | Contractual original EA |
| Tasa Cobrada | `Tasa Interés Cte.Cobrada` | **Tasa a usar en estudio** |
| Documento | `Documento No:` | **Enmascarado `0000000000`** → tomar CC del CRM |

### Bloque FRECH (condicional, solo si activo)
Identificado por bloque `Detalle del pago a realizar`:
```
Valor Cuota Total          $XXX,XXX
-Cobertura de Tasa         $YYY,YYY   ← FRECH
Pago Mínimo Cliente        $ZZZ,ZZZ   ← Lo que paga el cliente
```

**Regla crítica:** si NO aparece `-Cobertura de Tasa`, cliente NO tiene FRECH activo (aunque exista diferencia Pactada-Cobrada — eso puede ser **descuento comercial** del banco).

### Hoja 2 (valores aplicados + saldo)
| Campo | Etiqueta | Bloque |
|---|---|---|
| Seguro Vida | `Seguro de Vida` | Valores Aplicados |
| Seguro Incendio + Terremoto | `Seguro de Incendio y Anexos` | Davivienda combina (terremoto separado raro) |
| Seguro Protección Pagos | `Seguro Protección de Pagos` | SUMA a terremoto (R-DVV-01) |
| Otros Cargos | `Otros Cargos *` | Costos judiciales |
| Intereses corrientes | `Intereses Corrientes` | Interés del periodo |
| Abonos a capital | `Abonos a Capital` | = `abonos_capital` (R-DVV-02) |
| Total Aplicado | `Total Aplicado` | Suma bruta antes de FRECH |
| Saldo fecha corte | `Saldo a: [fecha]` | **`saldo_capital`** (cuadro resumen inferior) |
| "+ Seguros" inferior | `+ Seguros` (cuadro resumen) | `seguros_inferior_total` (R-DVV-06) |

---

## 4. FRECH — reglas operativas

### 4.1 Identificación
- FRECH NO se deduce de diferencia Pactada vs Cobrada
- FRECH aparece LITERALMENTE como `-Cobertura de Tasa` (pág 1) y `Int. Cte Cobertura` (pág 2)
- Diferencia Pactada-Cobrada sin `-Cobertura de Tasa` = **descuento comercial** (común en Davivienda)

### 4.2 Tratamiento en proyecciones
- **Cuotas pagadas < 82:** mantener FRECH (refinanciamiento interno = mismo banco, no se pierde subsidio)
- **Cuotas pagadas ≥ 82:** calcular SIN FRECH (beneficio se acaba a 84 meses)

### 4.3 Descuento comercial Davivienda (sin FRECH)
| Escenario | Etiqueta extracto | Plazo del beneficio |
|---|---|---|
| FRECH activo | `-Cobertura de Tasa` explícito pág 1 | 84 meses desde desembolso |
| Descuento comercial | NO `-Cobertura de Tasa` (Pactada ≠ Cobrada) | Indefinido |
| Sin beneficio | Pactada = Cobrada | N/A |

**Tasa a usar siempre:** `Tasa Cobrada` (refleja el beneficio real).

---

## 5. PDFs protegidos Davivienda

- **5.1** Muchos extractos vienen encriptados.
- **5.2** Procedimiento: `decrypt("")` primero (muchos son permissions-only). Si falla → CC candidatas (STAGING + HubSpot).
- **5.3** Solo bloquear `PDF_PROTEGIDO` si TODAS las CCs candidatas fallan.

---

## 6. Casos canónicos de referencia

| Cliente | Crédito | Lección | Excel ID |
|---|---|---|---|
| Fernando Gallo | 570238110001018-4 | Bug `_f` colombiano + R-DVV-01..03 validados | `1g9wzJPvgoLG7abHmrQQbI01e1df-qc2e` |
| Leidy Yesenia | 600707600145510-4 | R-DVV-06 G1+G2+G3 (duplicación cuota leasing) | manual |
| Julieth Valencia | 570000601203902-9 | R-DVV-07 proyección 6ª cuota | manual |
| Karen Tatiana | 571616690012705-4 | R-DVV-06 G2 false positive (vida=0) → fix R-DVV-10 | manual |
| Yeimy Jissel | 570040770103677-3 | R-DVV-06 G3 puro (sin +Seguros) → seguros/2 | `1Oj52dJQAO26-YbVNNJ24xpZiCGMhHrE0` |
| Carlos Mora | 600808600124529-7 | Leasing 600 procesado igual hipotecario (R-DVV-09) | manual |
| Gilma Gelvez | 600404440025296-2 | DIF.SIMULA enorme → fix R-DVV-11 | `1jqPsuiH3gUicMLnt7IF7EdtffQ4GIrCo` |
| Yolly Ximena | 570101700077634-9 | seguro_vida=0 con incendio>0 → R-DVV-10 ahora bloquea | manual |
| María Fernanda | 570040770106548-3 | seguro_vida=0 → R-DVV-10 ahora bloquea | manual |
| Karen Lizeth | 570101700053924-2 | seguro_vida=0 → R-DVV-10 ahora bloquea | manual |

---

## 7. Troubleshooting Davivienda

| Síntoma | Causa probable | Acción |
|---|---|---|
| `429 RESOURCE_EXHAUSTED` Vertex | Rate limit Gemini | Esperar 5-10 min, re-correr `--nombre --force` |
| `[M1-validar] FAIL: seguro_vida=0` | Vision no extrajo vida (R-DVV-10) | Revisar PDF manual, ajustar |
| `[DIF.SIMULA-CHECK] FAIL` | Cuota incoherente con plazo pendiente | REVISION_MANUAL — caso límite o leasing terminando |
| `[R-DVV-18] BLOQUEADO: NO_VIABLE_LEY_546` | Plazo pendiente tan corto que total < 5 años (Ley 546) | REVISION_MANUAL — informar cliente que crédito no elegible para optimización |
| Opciones de plazos > plazo pendiente del cliente | Bug proponedor R-DVV-18 (ya corregido) | Si reaparece: verificar versión `proponedor_plazos.py` y guardia R-DVV-18 |
| `[R-DVV-06] G2 false positive` (vida=0) | Ya fixed (vida>0 requerido) | No debería pasar |
| `sin pendientes Davivienda en STAGING` | Estados ya en "Excel generado" O no se corrió PASO 1 | Correr `listar_pendientes_hoy.py --banco davivienda` primero, o usar `--force` |
| HubSpot data genérica | Fix R-DVV-12 activo | Verificar log `[HUBSPOT-GENERICO]` |
| Excel orden quebrado | Padding del populator + plazos<6 del proponedor | Caso edge, M2 lo marca |
| `invalid_grant: Token has been expired or revoked` | OAuth refresh_token revocado por Google | Correr `py drive_oauth_setup.py` → re-autenticar en navegador con reducciondecreditos2@gmail.com. Diagnóstico previo: `py diag_oauth.py > diag_oauth.txt 2>&1` |
| `FATAL: OAuth no disponible` (exit 3 nuevo, 2026-05-07) | Pipeline detectó OAuth roto al inicio y abortó SIN procesar (evita 14 EXCEPTIONS por cliente) | Correr `py drive_oauth_setup.py` → reintentar pipeline |
| `storageQuotaExceeded 403` en upload (histórico) | SA sin cuota — pre-fix OAuth obligatorio | Ya no debería pasar post-2026-05-07. Si reaparece, OAuth se cayó tras `get_oauth_drive()` (improbable). Ver diag_oauth.txt |
| `EXCEL_LOCKED` en detalle (exit 0 pero `ok=false`) | Excel previo abierto en Office (Microsoft Excel.exe) bloquea sobreescritura | Cerrar el archivo en Excel y re-correr `py pipeline_davivienda.py --nombre "X" --force` |
| `[smoke_test] FAIL` en PASO 0 (exit 4 nuevo) | Pre-condition rota: cred ausente, hash PESOS, config.ini, etc. | Leer `_logs/scheduled_YYYYMMDD.txt` PASO 0 — smoke_test reporta exactamente qué falla |
| Cliente no capturado por listar | Campo BANCO en REGISTROS no dice exactamente "davivienda" | Verificar columna BANCO en REGISTROS para esa fila. Corregir o agregar manualmente a STAGING |

---

## 8. Comandos clave

### Flujo completo diario (RECOMENDADO — ejecuta PASO 1 + PASO 2)
```cmd
"C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\run_pipeline.bat"
```
Log: `_logs\scheduled_YYYYMMDD.txt`

### PASO 1 — Publicar pendientes REGISTROS → STAGING
```cmd
cd "C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\sprint_1"
py listar_pendientes_hoy.py --banco davivienda
```
⚠️ **SIEMPRE correr ANTES del pipeline.** Sin este paso, el pipeline dice "sin pendientes" aunque REGISTROS tenga clientes nuevos.

### PASO 2 — Generar estudios desde STAGING
```cmd
cd "C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\sprint_1"
py pipeline_davivienda.py > diag_pipeline.txt 2>&1
```

Flags útiles:
- `--nombre "X"` — solo cliente cuyo nombre contenga X
- `--credito "X"` — solo crédito X
- `--max N` — limitar cantidad
- `--dry-run` — sin generar Excel ni updates
- `--force` — re-procesar aunque ESTADO=Excel generado

### OAuth — re-autenticar si token revocado
```cmd
cd "C:\Users\JOSE A\Desktop\ESTUDIOS CLAUDE\sprint_1"
py diag_oauth.py > diag_oauth.txt 2>&1   ← diagnóstico primero
py drive_oauth_setup.py                   ← re-autenticar si invalid_grant
```

### Test suite
```cmd
py sprint_1\test_fase2.py > diag_fase2.txt 2>&1
```
**Esperado:** 16/16 PASS (A-P).

---

**FIN MOM_DAVIVIENDA v1.5**
**Próxima revisión:** cuando aparezca caso nuevo no cubierto por R-DVV-01..18 o cambie política Davivienda.

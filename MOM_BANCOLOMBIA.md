# MOM_BANCOLOMBIA — Reglas operativas Bancolombia

**Versión:** 1.0 · 2026-05-15 (creación inicial)
**Autoridad:** En contradicción con `MASTER_RULES.md`, **este archivo gana** (regla banco-específica > regla general).

> Este archivo contiene las reglas específicas para procesar extractos del banco **Bancolombia** (Estado de Crédito Hipotecario en PESOS). Para reglas generales del proyecto, ver `MASTER_RULES.md`.

---

## 1. Identificación del extracto

Un PDF se considera Bancolombia si contiene cualquiera de:

- Texto literal `"BANCOLOMBIA"` (mayúsculas, sin acento)
- Encabezado `"Estado de Crédito Hipotecario en PESOS"` (puede tener encoding mojibake → `"Estado de Cr�dito"`)
- Dominio `"bancolombia.com"` en pie de página
- Texto `"DCF:defensor@bancolombia.com.co"`

Si NO matchea ninguno y el PDF tiene texto extractable → no es Bancolombia, error.

Si el PDF está **escaneado (sin texto)** → Vision fallback automático sin error.

---

## 2. PDFs protegidos por contraseña

**Bancolombia entrega los extractos PROTEGIDOS por contraseña**. La contraseña es:

> **La cédula del titular del crédito (sin guiones, sin puntos, sin separadores)**

Ejemplo: cédula `91.443.052` → password del PDF = `"91443052"`.

El pipeline pasa `cedula_fallback` desde STAGING al extractor, que lo usa como password en `pdfplumber.open(pdf, password=cedula)` y en `pypdfium2.PdfDocument(pdf, password=cedula)`.

Si la cédula es incorrecta o vacía → `ValueError` al abrir el PDF → estado `EXTRACTO_ILEGIBLE` en GENERADOS.

---

## 3. Campos del extracto Bancolombia (mapeo)

| Campo en PDF | Campo Python | Notas |
|---|---|---|
| `"SEÑOR(A): NOMBRE"` | `nombre` | MAYÚSCULAS, multilínea posible |
| `"Número de crédito 9NNNNNNNNNN"` | `credito` | Formato Bancolombia: número largo sin guión verificador (vs Davivienda `570NNN-N`) |
| Header tabla `"Saldo a la fecha en que se generó el extracto"` línea siguiente | `saldo_capital` | El último monto `$ X.XX` de la línea de valores |
| `"Valor a Pagar $ X"` | `valor_a_pagar` | Incluye mora si hay cuotas vencidas |
| `"Valor de la cuota sin seguros y sin comisiones"` | `valor_cuota_sin_seguros` | Cuota corriente sin seguros |
| `cuota_mensual` (calculada) | `valor_cuota_sin_seguros + seguros` | Cuota canónica del estudio (sin mora) |
| `"*Valor seguro vida $ X"` | `seguro_vida` | Asterisco opcional |
| `"*Valor seguro incendio $ X"` | `seguro_incendio` | |
| `"*Valor seguro terremoto $ X"` | `seguro_terremoto` | |
| `"Tasa interés cobrada X% EA"` | `tasa_cobrada` | **R-BCO-04: canónica del estudio** |
| `"Tasa interés pactada X% EA"` | `tasa_pactada` | Informativa |
| `"Tasa interés mora cobrada X%"` | `tasa_mora_cobrada` | NUNCA usar como tasa_cobrada |
| `"Tasa interés subsidiada X%"` | `tasa_subsidiada` | > 0 indica FRECH activo |
| `"Plazo total en meses"` | `plazo_inicial` | |
| `"Nro. cuotas pendientes para pago total"` | `cuotas_pendientes` | |
| `"Nro. cuota a cancelar"` | `cuotas_pagadas + 1` | |
| `"Nro. cuotas vencidas"` | `cuotas_vencidas` | > 0 = cliente en mora |
| `"Valor cuotas vencidas"` | `valor_cuotas_vencidas` | |
| `"Interés de mora"` | `interes_mora` | |
| `"Valor subsidio Gobierno"` | `frech_cobertura_pag1` | FRECH activo si > 0 |
| `"Valor cuota con subsidio"` | `pago_minimo_cliente` | Cuando hay FRECH |
| `"Plan: ... VIVDA VIS"` | `es_vis = True` | VIS: ratio 39% (Bancolombia VIS es atípico, no aplica ingresos) |
| `"Plan: ... VIVDA NOVIS"` | `es_vis = False` | NO VIS |
| Tabla "Movimientos Último Periodo" | `abonos_capital`, `intereses_corrientes`, `total_aplicado` | Suma columnas de la tabla |

---

## 4. Reglas R-BCO-XX

### R-BCO-01 — Identificación banco
Texto `"BANCOLOMBIA"` o encabezado `"Estado de Crédito Hipotecario"` o `"bancolombia.com"` → es Bancolombia.

### R-BCO-02 — Saldo capital
El campo `saldo_capital` se extrae del **header de la tabla** en la página 1, NO del texto en "Observaciones":

```
Fecha de Pago | Fecha en que se generó el extracto | Valor a Pagar | Saldo a la fecha en que se generó el extracto
2026/05/15    | 2026/04/30                          | $ 1,767,048.00 | $ 152,172,660.26
```

El último monto `$X` de la línea de valores es el saldo.

### R-BCO-03 — FRECH (subsidio Gobierno)
Bancolombia denomina `"Valor subsidio Gobierno"` al equivalente del FRECH de Davivienda. `tiene_frech = True` si:
- `frech_cobertura_pag1 > 0`, **O**
- `tasa_subsidiada > 0`, **O**
- `pago_minimo_cliente > 0` (Valor cuota con subsidio)

### R-BCO-04 — Tasa canónica
La tasa del estudio es **SIEMPRE** `Tasa interés cobrada` (campo `tasa_cobrada`). NUNCA:
- ❌ `Tasa interés pactada` (puede diferir si hubo FRECH)
- ❌ `Tasa interés mora cobrada` (penal, sólo si está en mora)
- ❌ `Tasa interés subsidiada` (subsidio termina)

Bancolombia Cte. Cobrada típica **8%-13% EA**. Mora ~14-20% EA.

### R-BCO-05 — Ingresos NO requeridos
Bancolombia **NO exige certificación de ingresos** para reducción de plazo (Ley 546 + política banco). El pipeline fuerza `datos.ingresos = 0` antes de generar Excel para evitar:
- Mode B mixto_viable activándose con valores fantasma
- Excel mostrando "Ingresos Requeridos" para el cliente

El proponedor de plazos respeta esto vía `reglas_negocio.BANCOS_SIN_INGRESOS_REQUERIDOS`. El override explícito en `pipeline_bancolombia.py` es defensa adicional.

### R-BCO-06 — Variantes nombre banco
Aceptar como Bancolombia tanto `"BANCOLOMBIA"` como `"BANCOLOMBIA L"` (Leasing). Ambos están en `reglas_negocio.BANCOS_INTERES_CON_FRECH_CONDICIONAL`.

### R-BCO-07 — Cuota mensual canónica
`cuota_mensual = valor_cuota_sin_seguros + seguro_vida + seguro_incendio + seguro_terremoto`

Esto **excluye mora** explícitamente. Si el cliente tiene mora (`cuotas_vencidas > 0`), `valor_a_pagar` viene inflado con la deuda atrasada — el estudio se hace con la cuota CORRIENTE.

### R-BCO-08 — Tabla "Movimientos Último Periodo"
La tabla en página 1 tiene columnas:
`Fecha | Descripción | Capital | Int.Corriente | Int.Mora | Vida | Incendio | Terremoto | Otros | Total`

`abonos_capital` = suma columna `Capital` (puede incluir "Abono Extra", "Beneficio Cuota Anticipada").
`intereses_corrientes` = suma columna `Int.Corriente`.
`total_aplicado` = suma columna `Total`.

### R-BCO-10b — Seguros todos $0 → forzar Gemini
Si los 3 seguros (vida + incendio + terremoto) están en `$0` después de pdfplumber → forzar Gemini. **Equivalente Bancolombia de R-DVV-10b**.

Probabilidad de 3 ceros legítimos en hipotecario Bancolombia ≈ 0% (seguros obligatorios).

### R-BCO-10c — Cuotas vencidas > 0 → forzar Gemini
Si `cuotas_vencidas > 0` → cliente en mora → estructura PDF distinta → forzar Gemini. **Equivalente Bancolombia de R-DVV-10c**.

El extractor setea `dias_mora = 30` cuando `cuotas_vencidas > 0` para activar el R-BCO-10c (Bancolombia no expone días explícitamente).

### R-BCO-10d — Tasa atípica > 13% → forzar Gemini
Si `tasa_cobrada > 13.0` (formato porcentaje) después de pdfplumber → probable confusión con Tasa Mora. Forzar Gemini. **Equivalente Bancolombia de R-DVV-10d**.

### R-BCO-11 — DIF.SIMULA tolerancia ±$70k post-9.3
Misma lógica que R-DVV-11. Si `|DIF.SIMULA| > $70k` post Regla 9.3:
1. Auto-retry con Gemini si extractor fue `pdfplumber`
2. Si Gemini lo arregla → estado `pre-generado, gemini`
3. Si no → Excel generado igual con estado `REVISION_MANUAL: DIF.SIMULA ... (gemini)`

### R-BCO-18 — Ley 546 (no extender plazo)
Misma regla R-DVV-18 — aplica a TODOS los hipotecarios en Colombia. No proponer plazos >= `plazo_pendiente`. Si `plazo_pendiente < 5 - plazo_pagado` años → NO_VIABLE_LEY_546.

### R-BCO-20 — Tasa canónica + M1 valida ≤ 13%
M1 (`validar_extraccion_bancolombia.py`) bloquea `tasa_ea > 13%` con mensaje "Probable confusion con Tasa Mora". Activa retry Gemini vía R-BCO-10d.

---

## 5. Reglas Davivienda que NO aplican a Bancolombia

| Regla | Aplica BCO | Razón |
|---|---|---|
| R-DVV-07 (proyección 6ª cuota) | ❌ NO | Política específica Davivienda (cuota 6 sin cuota completa por mora reciente). Bancolombia no tiene equivalente. |
| R-DVV-08 (prefijos 570/571/600) | ❌ NO | Bancolombia usa formato `9NNNNNNNNNN`. |
| R-DVV-17B (ingresos requeridos en Excel) | ❌ NO | R-BCO-05 inverso: ingresos = 0. |

Otras reglas (9.2, 9.3, 9.4, R-DVV-06 duplicación, R-DVV-11 DIF.SIMULA, R-DVV-18 Ley 546, R-DVV-10b/c/d Gemini retry) **SÍ aplican** a Bancolombia con sus equivalentes R-BCO-XX.

---

## 6. Casos canónicos validados

| Cliente | Crédito | Caso | Resultado pdfplumber |
|---|---|---|---|
| MARISOL SANCHEZ SALGUERO | 90000386475 | VIS, sin FRECH, sin mora | ✅ Extracción completa OK |
| YANINE MANUEL NAVARRO ACEVEDO | 90000102858 | NOVIS, sin FRECH, con mora (1 cuota vencida) | ✅ Extracción completa OK, dias_mora=30 inferido |
| ANYI YORMARY VILLALBA BAQUERO | (CC 1074158213) | Con FRECH, PDF escaneado | ⚠️ pdfplumber retorna texto vacío → Vision fallback obligatorio |

---

**FIN MOM_BANCOLOMBIA v1.0**

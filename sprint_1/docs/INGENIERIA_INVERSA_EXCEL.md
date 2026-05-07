# Ingeniería Inversa del Excel MejorAhora SAS — Análisis + Cuestionario

**Fecha:** 14 abril 2026
**Archivos analizados:** `PESOS.xlsx` (original subido por Jose) vs actual en Desktop
**Resultado comparación:** Datos idénticos, fórmulas idénticas. Diferencia 1.579 bytes = metadata inofensiva (timestamps). **Yo NO modifiqué el archivo; solo inserto filas nuevas en BD y escribo valores directos en las celdas B2:B26 de ACTUAL cuando genero un estudio nuevo.**

---

## 1. Arquitectura del Excel

El workbook tiene 11 hojas. Jose me pidió concentrarme en 3: **BD**, **ACTUAL**, **ESTUDIO**. Las 6 hojas `PESOS (1)` a `PESOS (6)` son tablas de amortización auxiliares (una por cada opción de plazo 1-6). La hoja `SIN` es una variante del estudio sin FRECH. `BANCOS` es un catálogo de referencia.

```
┌──────┐   ┌────────┐   ┌─────────┐   ┌──────────┐
│  BD  │──▶│ ACTUAL │◀──│ ESTUDIO │◀──│ PESOS(n) │
└──────┘   └────────┘   └─────────┘   └──────────┘
                │                              ▲
                │  alimenta PMT, tasa, saldo   │
                └──────────────────────────────┘
```

---

## 2. Hoja BD — Base de datos de créditos

**Dimensiones:** 42 columnas × 2.649 filas máx. Headers en fila 1, índices numéricos en fila 2, datos desde fila 3.

### 2.1 Mapa de columnas (confirmado contra tu archivo)

| Col | Letra | Header | Tipo | Obligatorio |
|---:|:--|---|---|:-:|
| 1 | A | Nombre | str | Sí |
| 2 | B | **# Crédito** | int/str | **Sí (clave)** |
| 6 | F | Banco | str | Sí |
| 13 | M | Consultor | str | - |
| 18 | R | Cédula | str/int | - |
| 19 | S | Amortización | PESOS/UVR | Sí |
| 20 | T | Tipo (Hipotecario/Leasing) | str | Sí |
| 21 | U | Cuota (CON FRECH descontado) | float | Sí |
| 22 | V | Plazo Inicial (meses) | int | Sí |
| 23 | W | Plazo Pendiente (meses) | int | Sí |
| 24 | X | Tasa (EA decimal, ej 0.107 = 10.7%) | float | Sí |
| 25 | Y | FRECH (valor subsidio mensual $) | int | - |
| 26 | Z | S. Vida | int | - |
| 27 | AA | S. Incendio | int | - |
| 28 | AB | S. Terremoto | int | - |
| 29 | AC | Capital Mensual | float | Sí |
| 30 | AD | Interés Mensual | float | Sí |
| 31 | AE | Capital Adeudado (saldo actual) | float | Sí |
| 32 | AF | Abono Efectivo | float | - |
| 33 | AG | Ingresos demostrables | float | - |
| 34 | AH | Actividad Económica | str | - |

### 2.2 Tabla estructurada

BD está declarada como **Tabla estructurada `Tabla_BD`**. Por eso ACTUAL busca con:
```
=INDEX(Tabla_BD[#All], MATCH(B2, Tabla_BD[[#All],['# Crédito]], 0), N)
```

---

## 3. Hoja ACTUAL — Panel del cliente

Ancho 13 columnas (A:M), alto 378 filas. Zona activa: A1:M26.

### 3.1 Bloque 1 (A:B) — Datos del cliente (INPUT / lookup)

| Celda | Etiqueta | Fórmula / Valor | Color | Observación |
|---|---|---|---|---|
| B2 | CREDITO N° | (input manual, se escribe aquí) | 🟡 amarillo | Clave de búsqueda |
| B3 | Titular | INDEX col 1 | | Auto |
| B4 | Banco | INDEX col 6 | 🟡🔵 amarillo+azul | Auto |
| B5 | Cuota | INDEX col 21 | | **Cuota con FRECH descontado** |
| B6 | Plazo Total | INDEX col 22 | 🟡 | |
| B7 | Plazo Pendiente | INDEX col 23 | | |
| B8 | Tasa Cobrada | INDEX col 24 | 🟡 | EA decimal |
| B9 | Frech | INDEX col 25 | | Valor $ |
| B10 | S. Vida | INDEX col 26 | 🟡 | |
| B11 | S. Incendio | INDEX col 27 | | |
| B12 | S. Terremoto | INDEX col 28 | 🟡 | |
| **B13** | **Capital Extracto** | INDEX col 29 | 🟢 **verde** | Capital mensual del extracto |
| **B14** | **Intereses Extracto** | INDEX col 30 | 🔴 **rojo** | Interés mensual del extracto |
| B15 | Saldo Capital | INDEX col 31 | | |
| B16-B21 | OPCION 1-6 | 13.5, 12, 11, 10, 9, 8.5 | 🟡 | Años (valores hardcoded) |
| B22 | CONSULTOR | INDEX col 13 | 🟡 | |
| B23 | ACTIVIDAD ECON | INDEX col 34 | 🟡 | |
| B24 | DIFERENCIA | =M7 | | **= DIF.SIMULA, ver abajo** |
| B25 | ABONO EFECTIVO | INDEX col 32 | | |
| **B26** | **INGRESOS** | INDEX col 33 | 🟢 **verde** | |

### 3.2 Bloque 2 (C:D) — Validaciones y cálculos intermedios

| Celda | Etiqueta | Fórmula | Qué mide |
|---|---|---|---|
| C7 | - | `=B7/12` | Plazo pendiente en años |
| C10 | (oculta) | `=B10+B11+B12+B13+B14` | **Suma = Seguros+Capital+Intereses del extracto** |
| C11 | "SUMA CUOTA" | (etiqueta) | |
| **C12** | **SUMA CUOTA (valor)** | **`=B5-C10`** 🟡 | **Cuota - (Seg+Cap+Int). Ideal = 0** |
| C13 | - | `=G19` | Abono capital mes 1 simulador |
| C14 | - | `=H19` | Interés mes 1 simulador |
| C16-C21 | OPCION 1-6 cuota | refs a ESTUDIO! | 🟡 Cuotas proyectadas |
| D7 | CUOTAS PAG | `=J5` 🔴 rojo | Cuotas pagas = PlazoTotal - PlazoPend |
| D9 | PLAZO T.N. | `=(D7/12)+B21` | Plazo nuevo en años |
| D11 | "DIF.SIMULA" | (etiqueta) | |
| **D12** | **DIF.SIMULA (valor)** | **`=B24`** 🟡 | **Ver explicación abajo** |
| D13 | - | `=IF(OR(B4=B33,B23=A32),0.39,0.29)` | Ratio cuota/ingreso (39% ó 29%) |
| D16-D21 | OPCION 1-6 ingresos req | refs a ESTUDIO!I15,L15,O15,I43,L43,O43 | 🟡 Ingresos requeridos |

### 3.3 Bloque 3 (E:K) — Motor de amortización (simulador)

| Celda | Qué es | Fórmula |
|---|---|---|
| E1 | Fecha estudio | `=TODAY()` |
| G4 | Plazo total | `=B6` |
| G5 | Cuotas pagas | `=G4-G9` |
| G6 | Tasa EA | `=B8` |
| **G7** | **Saldo capital** | `=B15` |
| **G8** | **Tasa mensual (MV)** | `=K14` |
| **G9** | **Plazo pendiente** | `=B7` |
| G12 | Total seguros | `=G13+G14` |
| G13 | S. Vida ref | `=B10` |
| G14 | S. Incendio+Terremoto | `=(B11+B12)` |
| K14 | Tasa Nominal MV | `=(1+K16)^(1/12)-1` |
| K15 | Tasa Nominal Anual MV | `=K14*12` |
| K16 | TEA | `=G6` |
| **K19** | **Cuota simulador CON seguros** | `=J19+I19` |

### 3.4 Tabla de amortización del simulador (E17:K26+)

Filas 18-378 calculan mes a mes:
- F: saldo capital restante
- G: abono capital = I - H
- H: interés mes = F*G8 (saldo anterior × tasa mensual)
- **I: PMT** = `IF(ROUND(F prev,0)=0, 0, PMT($G$8, $G$9, -$G$7))` ← **CUOTA SIMULADOR SIN SEGUROS, FIJA**
- J: seguros fijos = G13+G14
- K: cuota total = I+J ← cuota simulador CON seguros

**I19 es la cuota PMT calculada con plazo PENDIENTE.**

### 3.5 Celdas laterales (M:M) — DIFERENCIA clave

| Celda | Fórmula | Qué significa |
|---|---|---|
| K1 | `=B5` | Cuota extracto |
| K2 | `=B14` | Intereses del extracto |
| K3 | `=B13` | Capital del extracto |
| H2 | `=G5*K1` | Dinero pagado (cuotas pagas × cuota) |
| H3 | `=B9` | FRECH valor |
| **M7** | **`=(K1+H3)-K19`** | **DIF.SIMULA real** |

### 3.6 La VERDADERA fórmula de DIF.SIMULA (M7)

**`DIF.SIMULA = (Cuota_Extracto + FRECH) − K19`**

Donde:
- `Cuota_Extracto` = lo que aparece en el extracto (ya con FRECH descontado)
- `FRECH` = subsidio mensual
- `K19` = PMT_teórico(plazo_pend) + seguros fijos

**Interpretación:** compara la cuota **bruta del banco** (lo que cobrarían sin subsidio) con la cuota **teórica** del simulador (PMT con plazo pendiente actual + seguros). Si la diferencia es grande, algo no cuadra: puede ser abono extra a capital, sistema de amortización diferente, o FRECH mal cargado.

### 3.7 La fórmula de SUMA CUOTA (C12)

**`SUMA CUOTA = Cuota_Extracto − (S.Vida + S.Incendio + S.Terremoto + Capital_Mensual + Interés_Mensual)`**

**Interpretación:** valida que los datos del extracto sumen bien. Si C12 ≈ 0, todo cuadra. Si ≠ 0, falta un concepto (seguro de desempleo, otro seguro de vivienda, gasto administrativo) o hay un dato mal capturado.

### 3.8 Colores en ACTUAL — qué significan

| Color | RGB | Ejemplo | Mi interpretación |
|---|---|---|---|
| 🟡 Amarillo | `FFF9D745` | B2, B4, B6, B8, B10, B12, B16-B21, B22, B23, D12, C16-C21, C7 | **Celdas de input o que el consultor debe revisar** |
| 🔵 Azul | `FF0070C0` | B4 | **Banco** (posible: realce visual del banco) |
| 🟢 Verde | `FF00B050` | B13 (Capital), B26 (Ingresos), C22 | **Datos críticos financieros** |
| 🔴 Rojo oscuro | `FFC00000` | B14 (Intereses) | **Dato clave: intereses mensuales** |
| 🔴 Rojo | `FFFF0000` | D7 (Cuotas pagas) | Alerta / antigüedad |
| 🟡 Amarillo claro | `FFFFFF00` | C12, D12, B23 | **Celdas de validación (SUMA CUOTA y DIF.SIMULA)** |
| 🟡 Amarillo 2 | `FFF8DB02` | ESTUDIO (beneficios) | Destaque en estudio |

---

## 4. Hoja ESTUDIO — Panel comercial al cliente

Zona activa: B1:U54. Hoja **impresa a PDF** (área A1:R54).

### 4.1 Estructura de 2 grupos (Opciones 1-3 y 4-6)

| Filas | Contenido |
|---|---|
| 1-4 | Encabezado + "LEY DE VIVIENDA 546 1999" |
| 5-16 | Tabla OPCION #1 / #2 / #3 (cols I, L, O) |
| 17-28 | FRECH, honorarios, documentación |
| 29-50 | OPCION #4 / #5 / #6 (espejo) |

### 4.2 Fórmulas clave de opciones 1-3

| Fila | Columna I (OP #1) | Significado |
|---|---|---|
| I6 | "OPCIÓN #1" | |
| I7 | `=I8/12` | Años |
| I8 | `=ACTUAL!J7` | Meses = plazo_opcion × 12 |
| **I9** | **`='PESOS (1)'!F19+H10-B21+U8`** | **Cuota nueva (con seguros y ajustes)** |
| I10 | `=F10` | Intereses mes extracto (ref) |
| J10 | `=G10+I11` | Ajuste |
| K10 | `=H10` | |
| **I11** | **`=I9-F9`** | **Participación adicional a capital 🟡** |
| I12 | `=SUM('PESOS (1)'!F19:F378)+(H10*I8)-U5+(I8*U8)` | **Total a pagar proyectado** |
| I13 | `=F13` | Capital a pagar = saldo actual |
| I14 | `=I12-I13` | Intereses a pagar |
| I15 | `=IF(OR(E4=BANCOS!D5,D6,D12), 0, …)` | **Ingresos requeridos (excluye Bancolombia, Caja Social, La Hipotecaria)** |
| I17 | `=I18/12` | Años reducidos |
| I18 | `=F8-I8` | **Cuotas reducidas** |
| I19 | `=F14-I14` | **Dinero ahorrado en intereses** |
| K19 | `=I19/F14` | % ahorro |

### 4.3 El FRECH y honorarios (filas 21-22)

| Celda | Contenido |
|---|---|
| F21 | 84 (cuotas totales del FRECH por ley) |
| G21 | `=ACTUAL!J5` (cuotas pagas) |
| H21 | `=F21-G21` (cuotas restantes de FRECH) |
| U5 | `=B21*H21` (FRECH total a ahorrar con opción 6) |
| U7 | `=ACTUAL!M7` (**trae DIF.SIMULA**) |
| **U8** | **`=U7+15000`** 🟡 | **"APLICAR" — ajuste de la cuota proyectada** |
| I22 | `=IF(I19<30000000, 1800000, I19*0.06)` | **Honorarios: 6% del ahorro o mínimo $1.800.000** |

### 4.4 Interpretación del "SIMULADOR" grande que ves en negro

Ese recuadro grande **es celda `ACTUAL!K19`** (cuota simulador con seguros) mostrada con formato llamativo. O en algunos estudios es `ESTUDIO!F9` (cuota extracto) según la vista. **Este es uno de los puntos que te voy a preguntar (ver cuestionario).**

---

## 5. El valor que tú reportas (Cubillos, DIF.SIMULA = −101.760)

Con los datos de tu BD actual para Cubillos:
- B5 = 692.611,56
- B9 (FRECH) = 190.228
- K19 ≈ 811.078 (calculando PMT con 10.7% EA, 118 m, saldo 58.056.655)
- **M7 esperado = (692.611 + 190.228) − 811.078 = +71.762**

Pero el pantallazo muestra **M7 = −101.760**. Esto implica que K19 en el momento de ese screenshot era ≈ 984.599, no 811.078.

**Hipótesis más probable:**
1. El estudio que miraste fue generado antes de un fix mío y tiene K19 calculado con otra tasa (p.ej. tasa sin dividir por 100), o
2. Tu Excel generado tiene una fórmula temporal que yo hubiera tocado sin querer.

**Para descartar:** cuando vuelvas, genera un estudio fresco de Cubillos con el código actual y mándame captura de las celdas C10, C12, D12, K19 y M7. Eso me dice exactamente qué está pasando.

El valor "real" que tú esperas (−649.920 = 692.612 − 1.342.532) sugiere que **lo que ves como "SIMULADOR 1.342.532" es una celda distinta a K19**. Quizá es la cuota de OPCIÓN #1 proyectada (la más corta) sin incluir FRECH, o una celda específica que no reconocí. Pregunta #13 del cuestionario.

---

## 6. CUESTIONARIO — Responde lo que sepas, en 30 segundos por pregunta

### A. INPUTS desde BD

**A1.** La cuota que está en BD col 21 (U), ¿es SIEMPRE la cuota **neta** que el cliente paga (ya con FRECH descontado), o a veces es la bruta? → __________

**A2.** Los 3 seguros (B10/B11/B12) en BD vienen del extracto directo. **Si un banco muestra "Seguro Desempleo" (no obligatorio) o "Otro Seguro Vivienda"** en su extracto, ¿dónde los pones?
- [ ] Los sumo al S. Vida
- [ ] Los sumo al S. Incendio
- [ ] Creo una cuarta columna
- [ ] Otro: _______

**A3.** El **Capital Adeudado** (col 31): ¿es el saldo a la fecha de corte del extracto, o el saldo al momento de perfilamiento? → __________

**A4.** La columna 34 (Actividad Económica) tiene valores tipo "INDEPENDIENTE", "EMPLEADO", etc. ¿Hay una lista cerrada de valores válidos? En la celda A32 veo "VIS DAVIVIENDA" usado en `D13 IF(B23=A32, 0.39, 0.29)`. ¿Qué significa esa comparación? → __________

### B. Cuota y sus componentes (lado izquierdo de validación)

**B1.** Definición operativa: la **"suma que debe dar la cuota"** es:
- (a) S.Vida + S.Incendio + S.Terremoto + Capital + Interés
- (b) Los anteriores + FRECH
- (c) Los anteriores − FRECH
- (d) Otra: _______

**B2.** Si la "SUMA CUOTA" (C12) sale negativa en más de $70.000:
- [ ] Es error de captura del extractor (datos mal tomados)
- [ ] El banco tiene otro concepto no listado (describirlo aquí: ____)
- [ ] Cuota incluye gasto administrativo
- [ ] Otro: _______

**B3.** Cuando un extracto muestra **"Otros Cargos"** o **"Gastos Administrativos"**, ¿los capturas? ¿Dónde van? → __________

**B4.** Para los **Leasing Habitacional (Davivienda BAJA $ 0% LEAS)**, la tasa cobrada es 10.95% pero la pactada es 19.29%. ¿Cuál se captura en BD col 24?
- [ ] La cobrada (lo que realmente se aplica)
- [ ] La pactada
- [ ] Depende del banco: _______

### C. DIF.SIMULA (lado derecho de validación)

**C1.** Confirma la fórmula que entiendo:
`DIF.SIMULA = (Cuota_Extracto + FRECH) − K19`
donde K19 es PMT(plazo_pendiente) con tasa cobrada + seguros.
- [ ] Sí, es exactamente eso
- [ ] Sí pero con un matiz: _______
- [ ] No, en realidad es: _______

**C2.** Tolerancia ±70.000. Cuando DIF.SIMULA está fuera, las causas que conoces son:
- [ ] Abono extra a capital reciente (cuota baja)
- [ ] FRECH mal cargado en BD
- [ ] Sistema de amortización alemán / UVR cantidad / Leasing con cuota baja inicial
- [ ] Tasa en BD diferente a la real
- [ ] Otros: _______

**C3.** Para los 4 clientes que salieron fuera de tolerancia en mi prueba (Cubillos, Peralta, Gomez, Lobaton), ¿puedes revisar sus extractos y decirme cuál es la causa real de cada uno? O al menos ¿tienes una regla manual tipo "si DIF.SIMULA > 200k, revisar"? → __________

### D. Simulador PMT y opciones

**D1.** Los plazos por defecto son `[13.5, 12, 11, 10, 9, 8.5]` años. Confirma mi interpretación:
- [ ] Son plazos FIJOS que se muestran al cliente como propuesta
- [ ] El consultor los puede cambiar manualmente en B16-B21
- [ ] Otro: _______

**D2.** Yo implementé **plazos dinámicos** (nunca mayores al pendiente, escalonado 1 año, mínimo 4). Ejemplo: si pendiente = 118 m (9.83 a), opciones = [9, 8, 7, 6, 5, 4].
- [ ] Me gusta esta regla, úsala siempre
- [ ] Prefiero otra escala (ej 1.5 año decreciente): _______
- [ ] Prefiero límite mínimo distinto (no 4 años): _______
- [ ] Solo aplicarla si pendiente < X años: _______

**D3.** La celda `D13 = IF(OR(B4=B33, B23=A32), 0.39, 0.29)` usa un ratio 39% o 29%. Confirma: **¿el 39% se aplica cuando el banco es "Banco de Bogotá" O la actividad es "VIS DAVIVIENDA"?** ¿Por qué esa regla? → __________

**D4.** En la fórmula `I15` de ESTUDIO (ingresos requeridos), se **EXCLUYEN** 3 bancos: `BANCOS!D5` (Bancolombia), `D6` (Caja Social), `D12` (La Hipotecaria). ¿Por qué estos 3 no tienen ingresos requeridos? → __________

### E. Honorarios

**E1.** `I22 = IF(I19<30.000.000, 1.800.000, I19*6%)`. Confirma:
- [ ] Siempre: $1.800.000 mínimo, o 6% del ahorro si este supera $30M
- [ ] Otro criterio: _______

**E2.** ¿Este mínimo de $1.800.000 debe incluir IVA o es antes de IVA? → __________

### F. FRECH

**F1.** `U8 = U7 + 15000`. U7 = DIF.SIMULA. Entonces U8 = DIF.SIMULA + 15.000. **¿Por qué se suman 15.000?** → __________

**F2.** `F21 = 84` (cuotas totales FRECH). ¿Esto es una ley fija (84 meses = 7 años) o varía por año? → __________

### G. Hoja ESTUDIO — Visualización

**G1.** El recuadro grande **"SIMULADOR $1.342.532"** (fondo negro) que ves en el estudio de Cubillos. ¿A qué celda corresponde?
- [ ] ACTUAL!K19 (cuota simulador con seguros, plazo pendiente)
- [ ] ESTUDIO!I9 (cuota opción #1 proyectada)
- [ ] Otra: _______ (abrir el .xlsx, clic en el número y mandar captura de la barra de fórmulas)

**G2.** En ESTUDIO hay 6 opciones en 2 filas (1-3 y 4-6). La OPCION #6 usa plazo más corto (8.5 años default). **¿El cliente típicamente elige la 1 (más plazo/cuota más baja) o la 6 (ahorro máximo)?** → __________

**G3.** El campo "PARTICIPACION ADICIONAL A CAPITAL" (I11, L11, O11) = cuota_nueva − cuota_actual. **¿Qué significa comercialmente?** → __________

### H. Pipeline de extractos (BD se siga llenando)

**H1.** Cuando extraemos un nuevo cliente del extracto, estos campos **faltan en el extracto y hay que tomarlos de CRM**:
- [ ] Cédula
- [ ] Consultor
- [ ] Ingresos
- [ ] Actividad Económica
- [ ] Otro: _______

**H2.** El CRM (`CRM.xlsx`) ¿es la fuente maestra de "leads" antes de que firmen? ¿BD es la fuente de "clientes activos con proceso"? → __________

**H3.** ¿Debería el pipeline **enriquecer** los datos del extracto con los del CRM automáticamente (joining por cédula o nombre)? → __________

### I. Cosas que YO necesito saber para no romper nada

**I1.** Las 6 hojas `PESOS (1)` a `PESOS (6)` son tablas de amortización de 360 filas. Cada una usa un plazo distinto (ACTUAL!B16 a B21). **¿Estas hojas están 100% auto-calculadas por fórmulas o alguna tiene datos hardcoded?** → __________

**I2.** La hoja `SIN` (oculta) aparece como versión "sin FRECH". **¿Se usa alguna vez o es legacy?** → __________

**I3.** Hay celdas que referencian **`[1]ACTUAL!...`** (externalLinks a otro Excel antiguo). Yo las limpié porque Excel estricto las rechazaba. ¿Estás OK con esa limpieza o quieres recuperar esas referencias? → __________

---

## 7. Cómo vamos a trabajar esto

1. **Responde el cuestionario** (A-I) por aquí o en el mismo .md. No te preocupes por responder todo perfecto: lo que no sepas lo dejamos como "pendiente de validar con un caso real".

2. Una vez responda, yo:
   - Actualizo mi código para que **respete al 100% la lógica del Excel original** (no solo los cálculos matemáticos)
   - Documento cada fórmula con sus reglas de negocio en un `README.md` técnico
   - Implemento el **clasificador de casos especiales** basado en tus respuestas (abono extra, FRECH mal cargado, sistema de amortización distinto)
   - Genero una prueba con los 10 clientes que muestre DIF.SIMULA real vs esperado con tus reglas

3. Cuando funcione al 100%, empaco todo como **skill de Cowork** para que cualquier miembro de tu equipo lo use desde el botón de skills.

---

**Pregunta 0 (meta):** ¿Este documento tiene el nivel de profundidad que esperabas, o quieres aún más detalle en alguna sección específica antes de responder?

---

*Análisis generado por Claude actuando como experto en matemática financiera + arquitecto de software*

# FÓRMULAS DEL MOTOR FINANCIERO — MejorAhora SAS

**Módulo:** `financial_engine.py` v1.1
**Fuente:** PESOS.xlsx (verificado celda por celda)
**Fecha:** 12 de Abril 2026

---

## 1. CONVERSIÓN DE TASAS

### EA → Tasa Mes Vencido (MV)
```
tasa_mv = (1 + tasa_ea)^(1/12) - 1
```
**Excel:** `ACTUAL|K14 = +(1+K16)^(0.0833333333333333)-1`

### MV → Tasa Nominal Mes Vencido (NMV)
```
tasa_nmv = tasa_mv × 12
```
**Excel:** `ACTUAL|K15 = +K14*12`

**Ejemplo (EA=10.95%):** MV = 0.008696720591 | NMV = 0.104360647093

---

## 2. CUOTA MENSUAL (PMT — Sistema Francés)

```
PMT = Capital × [r(1+r)^n] / [(1+r)^n - 1]

Donde:
  Capital = saldo_capital (B15, col 31)
  r = tasa_mv
  n = plazo en meses
```

**Excel:** `PESOS(1)|F19 = IF(ROUND(C18,0)=0, 0, PMT($D$8,$D$9,-$D$7))`

---

## 3. VALIDACIÓN DIF.SIMULA

Verifica coherencia entre cuota reportada y cuota calculada con los mismos parámetros del crédito actual.

```
cuota_validacion = PMT(tasa_mv, plazo_pendiente, saldo_capital) + seguro_total
DIF.SIMULA = (cuota_actual + frech_subsidio) - cuota_validacion
```

**Excel:**
- `ACTUAL|K19 = PMT(tasa_mv, plazo_actual, capital) + seguros`
- `ACTUAL|M7 = (K1 + H3) - K19`

**Tolerancia:** |DIF.SIMULA| ≤ $70,000

---

## 4. AJUSTE MENSUAL (U8)

Compensa la diferencia entre cuota real y calculada, más un buffer de $15,000.

```
U8 = DIF.SIMULA + 15,000
```

**Excel:**
- `ESTUDIO|U7 = ACTUAL!M7`
- `ESTUDIO|U8 = U7 + 15000`

---

## 5. CUOTA PRESENTADA EN ESTUDIO

La cuota que ve el cliente incluye PMT + seguros + ajuste, menos subsidio FRECH.

```
cuota_estudio = PMT_opcion + seguro_total - frech_subsidio + U8
```

**Excel:** `ESTUDIO|I9 = 'PESOS (1)'!F19 + H10 - B21 + U8`

Donde:
- H10 = seguro_total = seguro_vida + seguro_incendio + seguro_terremoto
- B21 = ACTUAL!B9 = frech_subsidio (generalmente 0)

---

## 6. TABLA DE AMORTIZACIÓN

Sistema francés con cuota constante. Se genera una tabla por opción (hojas PESOS 1-6).

```
Por cada período (mes 1 a plazo_meses):
  Intereses     = saldo_anterior × tasa_mv
  Abono Capital = cuota_PMT - intereses
  Saldo Nuevo   = saldo_anterior - abono_capital
  Seguro        = seg_vida + seg_incendio (constante)
  Cuota Total   = cuota_PMT + seguro
```

**Truncar cuando:** `ROUND(saldo, 0) = 0`
**Máximo:** 360 períodos (30 años)

**Excel:**
```
C19 = IF(C18-D19 < 0, 0, C18-D19)     # Saldo
D19 = F19 - E19                         # Abono capital
E19 = C18 × $D$8                        # Intereses
F19 = PMT($D$8, $D$9, -$D$7)           # Cuota (constante)
G19 = IF(ROUND(C18,0)=0, 0, $D$13+$D$14) # Seguro
H19 = G19 + F19                         # Cuota total
```

---

## 7. SITUACIÓN ACTUAL (Sin cambio)

```
total_pagos_actual = cuota_actual × plazo_pendiente + frech_subsidio × (plazo_pendiente - h21)
intereses_actual = total_pagos_actual - saldo_capital
```

**Excel:** `ESTUDIO|F12 = (F9*F8) + B21*(F8-H21)`

---

## 8. TOTAL PAGOS POR OPCIÓN

```
total_pagos_opcion = SUM(cuotas_PMT) + (seguro_total × plazo_meses) - U5 + (plazo_meses × U8)
```

Donde:
- U5 = frech_subsidio × h21 (generalmente 0)
- U8 = ajuste mensual

**Excel:** `ESTUDIO|I12 = SUM('PESOS (1)'!F19:F378) + (H10*I8) - U5 + (I8*U8)`

---

## 9. AHORRO DE INTERESES

```
intereses_opcion = total_pagos_opcion - saldo_capital
ahorro = intereses_actual - intereses_opcion
```

**Excel:**
- `ESTUDIO|I14 = I12 - I13` (I13 = saldo_capital)
- `ESTUDIO|I19 = F14 - I14`

---

## 10. HONORARIOS

```
SI ahorro < $30,000,000 → honorarios = $1,800,000 (mínimo)
SI ahorro ≥ $30,000,000 → honorarios = ahorro × 6%
```

**Excel:** `ESTUDIO|I22 = IF(I19<30000000, 1800000, I19*0.06)`

---

## 11. RATIO DE INGRESOS

```
SI banco = "BANCO DE BOGOTA" O actividad = "VIS DAVIVIENDA" → 0.39 (39%)
SINO → 0.29 (29%)
```

**Excel:** `ACTUAL|D13 = IF(OR(B4=B33, B23=A32), 0.39, 0.29)`

---

## 12. INGRESOS REQUERIDOS

```
SI banco ∈ [BANCOLOMBIA, CAJA SOCIAL, LA HIPOTECARIA] → 0 (no requiere)
SINO:
  numerador = cuota_estudio + frech_subsidio
  SI banco contiene "DAVIVIENDA" → numerador += 8.5 (ACTUAL B21)
  ingresos_requeridos = numerador / ratio
```

**Excel:**
```
ESTUDIO|I15 = IF(OR(banco=BANCOLOMBIA, CAJA SOCIAL, LA HIPOTECARIA),
                 0,
                 ((I9+ACTUAL!B9) + IF(FIND("DAVIVIENDA",B15), ACTUAL!B21, 0)) / ACTUAL!D13)
```

---

## 13. PORCENTAJE DE AHORRO

```
porcentaje = ahorro_opcion / intereses_situacion_actual
```

**Excel:** `ESTUDIO|K19 = (I19*1)/F14`

---

## 14. PLAZOS PREDETERMINADOS

| Opción | Años | Meses |
|--------|------|-------|
| 1 | 13.5 | 162 |
| 2 | 12.0 | 144 |
| 3 | 11.0 | 132 |
| 4 | 10.0 | 120 |
| 5 | 9.0 | 108 |
| 6 | 8.5 | 102 |

---

## 15. PARÁMETROS HARDCODEADOS

| Parámetro | Valor | Referencia |
|-----------|-------|-----------|
| Piso honorarios | $1,800,000 | ESTUDIO I22 |
| Porcentaje honorarios | 6% | ESTUDIO I22 |
| Threshold honorarios | $30,000,000 | ESTUDIO I22 |
| Ratio normal | 29% | ACTUAL D13 |
| Ratio especial | 39% | ACTUAL D13 |
| Ajuste fijo U8 | $15,000 | ESTUDIO U8 |
| DIF.SIMULA tolerancia | $70,000 | Validación |
| Max períodos | 360 | PESOS hojas |
| SMMLV | $1,300,000 | BANCOS H6 |
| Cantidad VIS | 135 | BANCOS I6 |

---

## 16. FLUJO DE CÁLCULO (Orden)

```
1. Datos cliente (BD.xlsx / HubSpot)
2. Convertir tasa: EA → MV
3. Validar: DIF.SIMULA con plazo actual
4. Calcular: U8 = DIF.SIMULA + 15,000
5. Situación actual: F12, F14
6. Para cada opción (6x):
   a. PMT con plazo opción
   b. Cuota estudio = PMT + seguro - FRECH + U8
   c. Tabla amortización (hasta 360 períodos)
   d. Total pagos = Σcuotas + seguro×plazo - U5 + plazo×U8
   e. Intereses = total_pagos - capital
   f. Ahorro = intereses_actual - intereses_opción
   g. Honorarios (6% o mínimo)
   h. Ingresos requeridos
7. Retornar JSON con 6 opciones
```

---

*Documento generado automáticamente a partir de PESOS.xlsx | MejorAhora SAS*

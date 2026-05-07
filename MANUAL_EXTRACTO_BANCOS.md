# MANUAL DE EXTRACCIÓN POR ENTIDAD BANCARIA

Este documento contiene los tips técnicos para la extracción precisa de datos de cada banco, según las indicaciones del usuario y la hoja "TIPO DE EXTRACTOS".

## REGLAS GENERALES
- **Orden del Nombre**: Siempre `NOMBRES APELLIDOS` (ej. `JOSE PEREZ`).
- **Sin Tildes**: Nunca usar tildes en el nombre del cliente ni del banco.
- **Números de Crédito**: Capturar completo, incluyendo guiones si existen (ej. `xxxxx-x`).
- **Tasas**: Convertir a decimal (ej. `12,50%` -> `0,1250`).

---

## DAVIVIENDA
- **Sistema de Amortización**: Si aparece el signo `$` en esta fila, el sistema es **UVR**.
- **Cuota Mensual (Mora)**: Si el extracto indica mora, usar el valor de la casilla `Valor Cuota Mes`.
- **Seguros**: Hoja 2. Si el desglose superior está en $0 o hay mora, usar el total de la casilla `+ Seguros:` (sección "Nuevo Saldo").
- **Capital Adeudado**: Ver casilla `Saldo a la Fecha de Corte:`.

## BANCOLOMBIA
- **Capital Adeudado**: Ver casilla `Saldo a la fecha en que se generó el extracto`.
- **Frech**: "Valor subsidio Gobierno".

## FNA (FONDO NACIONAL DEL AHORRO) - DOS FORMAS
### Forma 1: Extracto Estándar
- **Amortización**: `Uvr` si la sección "Saldo capital antes de ese pago" tiene valores en la casilla UVR.
- **Plazos**: "Cuotas o cánones totales" (Inicial) y "pendientes".
- **Abonos**: "Abono a capital financiado" y "Abono a interés".

### Forma 2: Estado de Cuenta
- **Plazo Inicial**: Calcular diferencia de años entre `FECHA APERTURA` y `VENCIMIENTO FINAL`.
- **Plazo Pendiente**: Diferencia de años entre la fecha actual y `VENCIMIENTO FINAL`.
- **Abonos**: Buscar en la TABLA de la segunda hoja (columna PESO) los valores de CAPITAL e INTERÉS CORRIENTE del mes actual.

## BANCO DE BOGOTÁ
- **Lógica de Fallback**: Si la columna `DETALLE VALOR A PAGAR` está vacía o en $0, tomar los datos de la columna `DETALLE PAGO ANTERIOR`.
- **Tipo de Crédito**: Si dice "(Extracto Crédito de Vivienda)", es `Hipotecario`.

## CAJA SOCIAL
- **Lógica de Fallback**: Si el cuadro `DETALLE DE PAGO` está vacío, tomar los datos de la columna `DETALLE CUOTA PERIODO ANTERIOR`.
- **Frech**: Buscar "Descuento Intereses DTCO".

## AV VILLAS
- **Prioridad**: Los datos de la SEGUNDA HOJA tienen prioridad absoluta sobre los de la primera.

## SCOTIABANK / COLPATRIA
- **Mapeo**: Siempre escribir `COLPATRIA`.

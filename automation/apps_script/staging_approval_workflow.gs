// MejorAhora - GENERADOS -> REGISTROS approval workflow
// v3.1 (2026-05-14) - Pestana renombrada STAGING -> GENERADOS (Jose feedback)
// v3.0 (2026-04-21) - Opcion A: ACTUALIZA fila existente en REGISTROS (no duplica)
//
// Sheet: BASE PARA ESTUDIOS OK (1_9FUAo8cSrLDWAkJlNoy29Cmyh9ojXwnW6zbvhGsESA)
// Instalado por: Jose (pegado directo en Extensiones > Apps Script del Sheet)
//
// CAMBIO CLAVE VS v2.0:
// v2.0 (bug): registros.appendRow(rowData) — agregaba fila NUEVA al final.
//             Cliente quedaba DUPLICADO: original con "Pendiente" + nueva con "Realizado".
// v3.0 (fix): busca fila existente por Numero de Credito (col E), actualiza ESTADO=Realizado.
//             Si no encuentra match, alerta y cancela (no duplica).
//
// Comportamiento:
// - onOpen agrega menu "MejorAhora" con item "Aprobar fila seleccionada -> REGISTROS"
// - aprobarFila() es MANUAL: el analista 1 hace clic en el menu sobre la fila en GENERADOS
// - Busca en REGISTROS la fila con mismo Numero de Credito (match exacto, tolerante a espacios)
// - Si encuentra: actualiza SU ESTADO=Realizado + borra fila de GENERADOS
// - Si NO encuentra: alerta al usuario y cancela (no crea duplicado)
// - NO es trigger automatico por onEdit. Requiere accion explicita del usuario.

// Indices de columna en GENERADOS/REGISTROS (1-based, formato Google Sheets).
// Coherente con MASTER_RULES §3.5 (42 cols) + listar_pendientes_hoy.py.
// TODO 2026-05-12: cuando se sume otro banco con esquema distinto, parametrizar.
// TODO 2026-05-12: copiar nota_crm (col L) de GENERADOS a REGISTROS al aprobar?
// Hoy se pierde — solo se actualiza ESTADO. Si el analista 1 necesita la nota persistente,
// considerar agregar `registros.getRange(matchRow, 12).setValue(notaCrm)` antes
// de borrar la fila de GENERADOS. Confirmar con Jose si aplica al workflow real.
const NUM_COLS = 42;        // Columnas A-AP
const COL_NOMBRE = 1;       // A = NOMBRE CLIENTE (1-based en Sheets)
const COL_CREDITO = 5;      // E = Numero de Credito
const COL_ESTADO = 7;       // G = ESTADO
const COL_NOTA_CRM = 12;    // L = Nota PARA CRM (pipeline escribe aqui — §3.8)

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('MejorAhora')
    .addItem('Aprobar fila seleccionada -> REGISTROS', 'aprobarFila')
    .addToUi();
}

/**
 * Normaliza un numero de credito para match:
 * trim + remove espacios internos + lowercase.
 * Conserva guiones y digitos tal cual.
 */
function normCredito(v) {
  if (v === null || v === undefined) return '';
  return String(v).trim().replace(/\s+/g, '').toLowerCase();
}

function aprobarFila() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActive();
  const staging = ss.getSheetByName('GENERADOS');
  const registros = ss.getSheetByName('REGISTROS');
  const active = ss.getActiveSheet();

  if (active.getName() !== 'GENERADOS') {
    ui.alert('Debes estar en GENERADOS para aprobar filas.');
    return;
  }

  const stgRow = staging.getActiveCell().getRow();
  if (stgRow < 2) {
    ui.alert('Selecciona una fila de datos (no la cabecera).');
    return;
  }

  const rowData = staging.getRange(stgRow, 1, 1, NUM_COLS).getValues()[0];
  const nombre = String(rowData[COL_NOMBRE - 1] || '').trim();
  const credito = String(rowData[COL_CREDITO - 1] || '').trim();

  if (!nombre) {
    ui.alert('La fila seleccionada esta vacia (sin NOMBRE CLIENTE).');
    return;
  }
  if (!credito) {
    ui.alert('La fila seleccionada no tiene Numero de Credito (col E).\n' +
             'No se puede localizar el registro en REGISTROS para actualizar.\n' +
             'Revisa la fila antes de aprobar.');
    return;
  }

  // Buscar fila del cliente en REGISTROS por Numero de Credito
  const creditoNorm = normCredito(credito);
  const regLastRow = registros.getLastRow();
  if (regLastRow < 2) {
    ui.alert('REGISTROS esta vacio — no hay donde actualizar.');
    return;
  }
  const colCredValues = registros.getRange(2, COL_CREDITO, regLastRow - 1, 1).getValues();

  let matchRow = -1;
  for (let i = 0; i < colCredValues.length; i++) {
    if (normCredito(colCredValues[i][0]) === creditoNorm) {
      matchRow = i + 2;  // +2 porque getRange empieza en fila 2 (1-based)
      break;
    }
  }

  if (matchRow === -1) {
    ui.alert(
      'No encontrado en REGISTROS\n\n' +
      'Cliente: ' + nombre + '\n' +
      'Numero de Credito: ' + credito + '\n\n' +
      'No se encontro ninguna fila con este Numero de Credito en REGISTROS.\n' +
      'Accion cancelada para evitar duplicados.\n\n' +
      'Revisa: (1) el numero de credito en GENERADOS, (2) si el cliente fue eliminado de REGISTROS.'
    );
    return;
  }

  // Confirmacion con info completa
  const estadoActual = registros.getRange(matchRow, COL_ESTADO).getValue();
  const confirm = ui.alert(
    'Aprobar y actualizar en REGISTROS',
    'Cliente: ' + nombre +
    '\nNumero de Credito: ' + credito +
    '\nFila GENERADOS: ' + stgRow +
    '\nFila REGISTROS: ' + matchRow +
    '\nESTADO actual en REGISTROS: "' + estadoActual + '"' +
    '\n\nSe ACTUALIZARA ESTADO="Realizado" en REGISTROS fila ' + matchRow +
    '\ny se BORRARA la fila ' + stgRow + ' de GENERADOS.' +
    '\n\n¿Continuar?',
    ui.ButtonSet.YES_NO
  );
  if (confirm !== ui.Button.YES) return;

  // Actualizar ESTADO en REGISTROS (NO appendRow — actualiza la fila existente)
  registros.getRange(matchRow, COL_ESTADO).setValue('Realizado');

  // Borrar fila de GENERADOS (Opcion B)
  staging.deleteRow(stgRow);

  ui.alert(
    'OK\n\n' +
    'Cliente: ' + nombre + '\n' +
    'Numero de Credito: ' + credito + '\n' +
    'REGISTROS fila ' + matchRow + ' actualizada a ESTADO="Realizado"\n' +
    'GENERADOS fila ' + stgRow + ' borrada'
  );
}

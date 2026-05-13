"""
proponedor_plazos.py
======================
Genera propuestas de 6 plazos para el estudio.

PRIORIDAD (Jose 2026-04-17, Regla 9.4):
  1. Manual override               -> manual
  2. Default                       -> por_saltos_100k
  3. Fallback (datos insuficientes)-> escalonado desde plazo pendiente

REGLA 9.4 - por_saltos_100k (ver ESTADO_PROYECTO.md §9.4):
- 6 opciones con saltos de abono ~$100k entre si (tolerancia $85k-$115k)
- Preferencia ANOS ENTEROS (10, 8, 6, 5). Medios anos (10.5, 6.5, 4.5)
  solo cuando los enteros no alcanzan el objetivo $100k.
- Cuando hay abono objetivo [min, max]: serie cubre min-100, min, medio, max,
  max+100, max+200. Cuando NO hay abono: [100k, 200k, 300k, 400k, 500k, 600k].
- Ajuste Opcion 1 "anti-plana": si el target base $100k no ahorra al menos
  ~1 ano vs plazo pendiente, desplazar toda la serie +$100k e iterar.
- Regla legal Ley 546 Colombia: plazo_total_credito >= 5 anos. Si el cliente
  ya pago >= 5 anos, sin restriccion. Si no, opcion mas corta >= 5 - pagado.
- Factibilidad: ingresos_req <= ingresos_cliente * 1.10. Se etiqueta pero
  NUNCA se rechazan opciones (siempre retorna 6).

Los metodos viejos (_proponer_por_ingresos, _proponer_por_abono) se
conservan solo como referencia historica.
"""

from typing import Optional
from dataclasses import dataclass

from reglas_negocio import (
    PLAZOS_DEFAULT,
    PLAZO_MINIMO_ANOS,
    PLAZO_PASO_DEFAULT,
    BANCOS_SIN_INGRESOS_REQUERIDOS,
)
# Constantes centralizadas (single source of truth — MASTER_RULES §8.15).
# Antes hardcoded como literals; deduplicado 2026-05-07 y 2026-05-12.
from config_reglas import (
    DIFF_OPCIONES_DEFAULT,
    DIFF_OPCIONES_PLAZO_CHICO,
    PLAZO_CHICO_MESES,
    # Ratios Mode B (ingresos requeridos) — antes 0.39/0.29 hardcoded
    RATIO_VIS,
    RATIO_NO_VIS,
    TOPE_INGRESOS_FACTOR,
    # §3c piso abono tiered — antes 100k/200k/300M hardcoded
    PISO_ABONO_SALDO_BAJO,
    PISO_ABONO_SALDO_ALTO,
    SALDO_THRESHOLD_TIER,
    # Regla 9.4 — paso de saltos en serie
    SALTO_ABONO_SERIE,
)


@dataclass
class PropuestaPlazos:
    plazos_anos: list          # Lista de 6 floats (anos)
    metodo: str                # "manual", "por_saltos_100k", "escalonado"
    notas: list                # Observaciones para el analista


def _pmt(tasa_mv: float, n: int, capital: float) -> float:
    if capital <= 0 or n <= 0:
        return 0.0
    if tasa_mv <= 0:
        return capital / n
    f = (1 + tasa_mv) ** n
    return capital * tasa_mv * f / (f - 1)


def _ea_a_mv(ea: float) -> float:
    return (1 + ea) ** (1.0 / 12.0) - 1


def _ingresos_requeridos(cuota_total: float, es_vis: bool) -> float:
    ratio = RATIO_VIS if es_vis else RATIO_NO_VIS
    return cuota_total / ratio


def proponer_plazos(
    *,
    plazo_pendiente_meses: int,
    tasa_ea: float,
    saldo: float,
    seguros_totales: float = 0,
    ingresos_cliente: float = 0,
    banco: str = "",
    es_vis: bool = False,
    abono_objetivo_min: float = 0,
    abono_objetivo_max: float = 0,
    plazos_manuales: Optional[list] = None,
    plazo_pagado_meses: int = 0,
) -> PropuestaPlazos:
    """
    Genera 6 plazos propuestos segun las reglas de negocio.

    Args:
        plazo_pendiente_meses: meses restantes del credito
        tasa_ea: tasa efectiva anual (decimal, ej 0.107)
        saldo: saldo capital
        seguros_totales: suma de seguros mensuales
        ingresos_cliente: ingresos demostrables (si se conocen)
        banco: nombre del banco (para saber si requiere certificar)
        es_vis: True si el credito es VIS (ratio 39%)
        abono_objetivo_min/max: rango de abono extra objetivo del cliente
        plazos_manuales: si el analista ya decidio 6 plazos, se usan estos

    Returns:
        PropuestaPlazos con plazos, metodo y notas
    """
    plazo_pend_anos_check = plazo_pendiente_meses / 12.0

    resultado = _proponer_plazos_impl(
        plazo_pendiente_meses=plazo_pendiente_meses,
        tasa_ea=tasa_ea,
        saldo=saldo,
        seguros_totales=seguros_totales,
        ingresos_cliente=ingresos_cliente,
        banco=banco,
        es_vis=es_vis,
        abono_objetivo_min=abono_objetivo_min,
        abono_objetivo_max=abono_objetivo_max,
        plazos_manuales=plazos_manuales,
        plazo_pagado_meses=plazo_pagado_meses,
    )

    # FIX R-DVV-18 (2026-05-05): Guardia absoluta — NUNCA retornar una opcion
    # que sea >= plazo pendiente. Cualquier plazo igual o mayor al plazo actual
    # EXTIENDE el credito, violando la regla fundamental de negocio y la Ley 546.
    # Esta guardia cubre todos los metodos (Mode A, B, E, manual, escalonado).
    antes = len(resultado.plazos_anos)
    validas = [p for p in resultado.plazos_anos if p < plazo_pend_anos_check]
    if len(validas) < antes:
        descartadas = antes - len(validas)
        resultado.notas.insert(0,
            "ADVERTENCIA R-DVV-18: {} opcion(es) descartada(s) por superar "
            "o igualar plazo pendiente ({:.2f} anos). Opciones invalidas "
            "habrian extendido el credito.".format(descartadas, plazo_pend_anos_check))
        resultado.plazos_anos = validas if validas else resultado.plazos_anos

    return resultado


def _proponer_plazos_impl(
    *,
    plazo_pendiente_meses: int,
    tasa_ea: float,
    saldo: float,
    seguros_totales: float = 0,
    ingresos_cliente: float = 0,
    banco: str = "",
    es_vis: bool = False,
    abono_objetivo_min: float = 0,
    abono_objetivo_max: float = 0,
    plazos_manuales: Optional[list] = None,
    plazo_pagado_meses: int = 0,
) -> PropuestaPlazos:
    """Implementacion interna. Llamar siempre via proponer_plazos() que aplica
    la guardia R-DVV-18 sobre el resultado."""

    # Caso 0: Plazos manuales del analista
    if plazos_manuales and len(plazos_manuales) >= 1:
        plazos = list(plazos_manuales)
        while len(plazos) < 6:
            plazos.append(plazos[-1])
        plazos = plazos[:6]
        return PropuestaPlazos(
            plazos_anos=plazos,
            metodo="manual",
            notas=["Plazos definidos manualmente por el analista."],
        )

    plazo_pend_anos = plazo_pendiente_meses / 12.0
    plazo_pagado_anos = plazo_pagado_meses / 12.0 if plazo_pagado_meses > 0 else 0.0

    # Prioridad (Regla 9.4, 2026-04-17):
    #   1. Manual (arriba)
    #   2. Regimen E (caso especial: saldo bajo + alta capacidad de pago)
    #   3. por_saltos_100k (default, cubre con y sin abono objetivo)
    #   4. escalonado (fallback si saltos_100k no logra 6 opciones validas)

    # Caso Regimen E (Jose 2026-04-17): caso especial validado con Sandy Garcia.
    # Cuando el cliente ya pago >=5 años (Ley 546 sin restricción de minimo) Y
    # tiene capacidad de pago suficiente para las 6 opciones cortas, la serie
    # [5, 4, 3, 2, 1.5, 1] mantiene orden descendente estricto y genera saltos
    # comercialmente utiles. Si al menos 1 opcion no es factible, se cae al
    # algoritmo normal (por_saltos_100k).
    plazos_e = _regimen_e_si_aplica(
        plazo_pend_anos=plazo_pend_anos,
        plazo_pagado_anos=plazo_pagado_anos,
        tasa_ea=tasa_ea,
        saldo=saldo,
        seguros=seguros_totales,
        ingresos_cliente=ingresos_cliente,
        es_vis=es_vis,
    )
    if plazos_e is not None:
        return PropuestaPlazos(
            plazos_anos=plazos_e,
            metodo="regimen_E",
            notas=[
                "[Regimen E] Caso especial detectado: plazo pagado >=5 años, "
                "ingresos cubren las 6 opciones cortas.",
                "Serie: [5, 4, 3, 2, 1.5, 1] — orden descendente estricto.",
                "Plazo pagado: {:.2f} años | Ingresos cliente: ${:,.0f}".format(
                    plazo_pagado_anos, ingresos_cliente),
            ],
        )

    # Caso Mode B - mixto_viable (Jose 2026-04-18, Dayanna):
    # Cuando hay ingresos conocidos y plazo minimo factible calculable,
    # garantizar que al menos 3/6 opciones sean factibles (primeras 3),
    # mientras las ultimas 3 honran el abono efectivo pedido por el cliente.
    # Condicion: plazo_min_factible en rango razonable vs plazo pendiente.
    if ingresos_cliente > 0:
        plazo_min_factible_anos = _plazo_min_factible(
            saldo=saldo,
            tasa_ea=tasa_ea,
            seguros=seguros_totales,
            ingresos_cliente=ingresos_cliente,
            es_vis=es_vis,
            tope_factor=TOPE_INGRESOS_FACTOR,
        )
        if plazo_min_factible_anos is not None:
            holgura = plazo_pend_anos - plazo_min_factible_anos
            # Mode B aplica cuando la holgura es positiva pero no abismal.
            # holgura > 10 anos -> Mode A (saltos_100k) funciona solo.
            # holgura en (-0.5, 10] anos -> Mode B da mejor mix factible+agresivo.
            # holgura <= -0.5 -> Mode C (concentrado) - pendiente; fallback A.
            if -0.5 < holgura <= 10.0:
                try:
                    plazos_b, notas_b = _proponer_mixto_viable(
                        plazo_min_factible=plazo_min_factible_anos,
                        plazo_pend_anos=plazo_pend_anos,
                        tasa_ea=tasa_ea,
                        saldo=saldo,
                        seguros=seguros_totales,
                        abono_min=abono_objetivo_min,
                        abono_max=abono_objetivo_max,
                        ingresos_cliente=ingresos_cliente,
                        es_vis=es_vis,
                        plazo_pagado_anos=plazo_pagado_anos,
                    )
                    return PropuestaPlazos(
                        plazos_anos=plazos_b,
                        metodo="mixto_viable",
                        notas=notas_b,
                    )
                except Exception as e:
                    # Si Mode B falla, caer a Mode A
                    pass

    try:
        plazos, notas = _proponer_por_saltos_100k(
            plazo_pend_anos=plazo_pend_anos,
            tasa_ea=tasa_ea,
            saldo=saldo,
            seguros=seguros_totales,
            abono_min=abono_objetivo_min,
            abono_max=abono_objetivo_max,
            ingresos_cliente=ingresos_cliente,
            es_vis=es_vis,
            plazo_pagado_anos=plazo_pagado_anos,
        )
        return PropuestaPlazos(
            plazos_anos=plazos,
            metodo="por_saltos_100k",
            notas=notas,
        )
    except Exception as e:
        plazos = _proponer_escalonado(plazo_pend_anos)
        return PropuestaPlazos(
            plazos_anos=plazos,
            metodo="escalonado",
            notas=[f"Fallback escalonado (por_saltos_100k fallo: {e})"],
        )


# ============================================================
# ESTRATEGIAS INTERNAS
# ============================================================

def _plazo_min_factible(
    saldo: float,
    tasa_ea: float,
    seguros: float,
    ingresos_cliente: float,
    es_vis: bool,
    tope_factor: float = TOPE_INGRESOS_FACTOR,
) -> Optional[float]:
    """Menor plazo (en anos, granularidad mes) cuya cuota cumpla
    cuota + seguros <= ingresos * ratio * tope_factor.

    Ratio: RATIO_VIS (VIS) / RATIO_NO_VIS (NO VIS) (colchon vs 40%/30% banco).
    tope_factor TOPE_INGRESOS_FACTOR = 10% extra permitido (ingresos reales vs
    certificados). Las 3 constantes viven en config_reglas.py.

    Devuelve anos (float) del primer mes donde la cuota es factible.
    Devuelve None si ningun plazo 1-30 anos cumple (caso extremo).
    """
    if ingresos_cliente <= 0 or saldo <= 0:
        return None
    tasa_mv = _ea_a_mv(tasa_ea)
    ratio = RATIO_VIS if es_vis else RATIO_NO_VIS
    cuota_max = ingresos_cliente * ratio * tope_factor
    if cuota_max <= seguros:
        return None  # ni siquiera los seguros caben en la capacidad
    # Buscar mes mas pequeno (plazo mas corto) cuya PMT+seg <= cuota_max.
    # Iterar desde 12 meses hasta 360 meses; devolver el PRIMER plazo que cumple.
    # "Primer plazo que cumple" = plazo corto donde la cuota aun es manejable.
    # En realidad queremos el MENOR plazo cuya cuota cabe en la capacidad,
    # que equivale al plazo donde PMT(meses, saldo) + seg <= cuota_max por 1a vez
    # al iterar de menor a mayor (meses creciendo, cuota decreciendo monotona).
    for meses in range(12, 361):
        pmt_val = _pmt(tasa_mv, meses, saldo) + seguros
        if pmt_val <= cuota_max:
            return meses / 12.0
    return None


def _regimen_e_si_aplica(
    plazo_pend_anos: float,
    plazo_pagado_anos: float,
    tasa_ea: float,
    saldo: float,
    seguros: float,
    ingresos_cliente: float,
    es_vis: bool,
) -> Optional[list]:
    """Detecta el caso especial Regimen E (Jose 2026-04-17).

    Condiciones (todas obligatorias):
      1. plazo_pagado_anos >= 5.0 (Ley 546 permite plazos < 4 años).
      2. ingresos_cliente > 0 (necesario para validar factibilidad).
      3. plazo_pend_anos >= 5.0 (la opc1 de 5 años debe ser reduccion real).
      4. Las 6 opciones [5, 4, 3, 2, 1.5, 1] son factibles:
         ingresos_req <= ingresos_cliente * 1.10 para cada una.

    Si todas se cumplen, retorna [5.0, 4.0, 3.0, 2.0, 1.5, 1.0].
    Si falla cualquiera, retorna None (delega al algoritmo normal).
    """
    if plazo_pagado_anos < 5.0:
        return None
    if ingresos_cliente <= 0:
        return None
    if plazo_pend_anos < 5.0:
        return None

    serie = [5.0, 4.0, 3.0, 2.0, 1.5, 1.0]
    tasa_mv = _ea_a_mv(tasa_ea)
    tope_ingresos = ingresos_cliente * TOPE_INGRESOS_FACTOR

    for a in serie:
        meses = int(round(a * 12))
        cuota = _pmt(tasa_mv, meses, saldo) + seguros
        ing_req = _ingresos_requeridos(cuota, es_vis)
        if ing_req > tope_ingresos:
            return None  # al menos 1 opcion no factible -> no aplica Regimen E

    return serie


def _proponer_por_saltos_100k(
    plazo_pend_anos: float,
    tasa_ea: float,
    saldo: float,
    seguros: float,
    abono_min: float,
    abono_max: float,
    ingresos_cliente: float,
    es_vis: bool,
    plazo_pagado_anos: float,
) -> tuple:
    """Regla 9.4 — proponedor de 6 plazos con saltos de abono ~$100k.

    Ver docstring del modulo para el detalle de la logica.
    """
    import math

    tasa_mv = _ea_a_mv(tasa_ea)
    cuota_actual = _pmt(tasa_mv, int(round(plazo_pend_anos * 12)), saldo) + seguros

    # Regla §3c (Jose 2026-04-23 + retro 2026-04-24): abono minimo OPC 1 tiered.
    # Constantes en config_reglas.py: PISO_ABONO_SALDO_BAJO / _ALTO / SALDO_THRESHOLD_TIER.
    #   saldo < $300M  -> piso $100k (subido desde $80k tras retro Sandra)
    #   saldo >= $300M -> piso $200k (creditos grandes admiten abonos mas altos)
    piso_abono = PISO_ABONO_SALDO_BAJO if saldo < SALDO_THRESHOLD_TIER else PISO_ABONO_SALDO_ALTO

    # 1) Rango legal de años (Ley 546 — corregido 2026-04-24 Jose)
    #    Regla: credito_total (pagado + restante) >= 5 anos.
    #    Si cliente ya pago >= 5 anos: cualquier plazo restante valido.
    #    Si pago < 5 anos: minimo restante = 5 - pagado.
    if plazo_pagado_anos >= 5.0:
        anio_min_legal = float(PLAZO_MINIMO_ANOS)  # 0.5 (granularidad practica)
    else:
        anio_min_legal = max(5.0 - plazo_pagado_anos, float(PLAZO_MINIMO_ANOS))

    # Techo = año mayor estricto < plazo pendiente (al menos 1 año de ahorro).
    # FIX 2026-05-05 (R-DVV-18): el techo NUNCA puede superar plazo_pend_anos.
    # Bug anterior: max(anio_max, ceil(anio_min_legal)) elevaba el techo por
    # encima del plazo pendiente cuando anio_min_legal > plazo_pend_anos,
    # generando opciones que EXTIENDEN el plazo (ej. Alexandra Bernal: 29 cuotas
    # pendientes -> opciones de 5+ anos). NUNCA extender plazo del cliente.
    anio_max = math.floor(plazo_pend_anos)
    if anio_max >= plazo_pend_anos:
        anio_max -= 1
    # anio_max NO puede superar plazo_pend_anos bajo ninguna circunstancia.
    # Si anio_min_legal >= plazo_pend_anos el crédito no es viable (sin opciones
    # legales de reducción) — el caller debe haberlo detectado antes (R-DVV-18).
    anio_max = min(anio_max, math.floor(plazo_pend_anos) - (1 if math.floor(plazo_pend_anos) >= plazo_pend_anos else 0))
    anio_max = max(anio_max, math.ceil(anio_min_legal)) if anio_min_legal < plazo_pend_anos else anio_max

    # 2) Construir listas de años candidatos (enteros primero, medios después)
    def _anios_entre(lo, hi, paso):
        out = []
        a = hi
        # Redondear hi hacia abajo al múltiplo del paso
        while a >= lo - 1e-9:
            out.append(round(a, 1))
            a -= paso
        return out

    anios_enteros = _anios_entre(math.ceil(anio_min_legal), anio_max, 1.0)
    anios_medios = _anios_entre(anio_min_legal + 0.5, anio_max - 0.5, 1.0)
    # Solo medios reales (terminan en .5)
    anios_medios = [a for a in anios_medios if abs(a - round(a)) > 0.1]

    def abono_de(anos):
        meses = int(round(anos * 12))
        return _pmt(tasa_mv, meses, saldo) + seguros - cuota_actual

    # 3) Generar serie de targets de abono
    # Paso = SALTO_ABONO_SERIE (config_reglas, default $100k). La serie por
    # defecto sin abono objetivo es [1x, 2x, 3x, 4x, 5x, 6x] del paso.
    _S = SALTO_ABONO_SERIE

    def _targets(shift=0.0):
        if abono_min > 0 or abono_max > 0:
            amin = abono_min if abono_min > 0 else abono_max
            amax = abono_max if abono_max > 0 else abono_min
            if abs(amax - amin) < 1:
                # abono fijo -> centrar
                base = [amin - 2 * _S, amin - _S, amin,
                        amin + _S, amin + 2 * _S, amin + 3 * _S]
            else:
                medio = (amin + amax) / 2.0
                base = [amin - _S, amin, medio, amax,
                        amax + _S, amax + 2 * _S]
        else:
            base = [_S, 2 * _S, 3 * _S, 4 * _S, 5 * _S, 6 * _S]
        return [max(0.0, t + shift) for t in base]

    # 4) Para cada target, elegir año con preferencia por enteros.
    #    Cuando NO hay abono objetivo, los targets de Opc2..6 se anclan de
    #    manera INCREMENTAL sobre el abono real de la opción anterior
    #    (abono_prev + $100k) para preservar el salto $100k real.
    def _elegir_anos_para_targets(targets_base, hay_abono_obj):
        usados = set()
        elegidos = []
        abonos_elegidos = []
        for i, tb in enumerate(targets_base):
            if i == 0:
                # Opc1: cuando hay abono_obj, anclar en el abono_obj real
                # (no en tb=amin-200k) para preservar salto $100k con Opc2.
                # Sin abono_obj, usar tb original (Jose 2026-04-17 BUG C fix2).
                if hay_abono_obj:
                    _amin = abono_min if abono_min > 0 else abono_max
                    target = max(tb, _amin)
                else:
                    target = tb
            else:
                # Incremental SIEMPRE (Jose 2026-04-17 + retro 2026-04-24):
                # default DIFF_OPCIONES_DEFAULT entre opciones. Si plazo_pend
                # < PLAZO_CHICO_MESES (5 anos = 60m) permite bajar a
                # DIFF_OPCIONES_PLAZO_CHICO cuando es necesario para que
                # quepan las 6 opciones en el rango disponible.
                # Constantes en config_reglas.py (§3d MASTER_RULES).
                paso = DIFF_OPCIONES_DEFAULT
                if plazo_pend_anos < (PLAZO_CHICO_MESES / 12.0):
                    paso = DIFF_OPCIONES_PLAZO_CHICO
                target = abonos_elegidos[-1] + paso

            mejor_ent, mejor_ent_dist = None, float("inf")
            mejor_med, mejor_med_dist = None, float("inf")

            for a in anios_enteros:
                if a in usados:
                    continue
                d = abs(abono_de(a) - target)
                if d < mejor_ent_dist:
                    mejor_ent, mejor_ent_dist = a, d

            for a in anios_medios:
                if a in usados:
                    continue
                d = abs(abono_de(a) - target)
                if d < mejor_med_dist:
                    mejor_med, mejor_med_dist = a, d

            # Preferencia entero: si entero está a menos de $40k del target,
            # ganar año entero. Si no, usar el que esté más cerca.
            if mejor_ent is not None and mejor_ent_dist <= 40_000:
                elegido = mejor_ent
            elif mejor_ent is None and mejor_med is None:
                elegido = anio_min_legal
            elif mejor_ent is None:
                elegido = mejor_med
            elif mejor_med is None:
                elegido = mejor_ent
            elif mejor_med_dist < mejor_ent_dist * 0.6:
                elegido = mejor_med
            else:
                elegido = mejor_ent

            elegidos.append(elegido)
            abonos_elegidos.append(abono_de(elegido))
            usados.add(elegido)
        return elegidos

    # 5) Ajuste Opcion 1 "anti-plana": si no hay abono objetivo y Opc1 no ahorra
    #    al menos ~1 año vs plazo pendiente, desplazar toda la serie +$100k.
    hay_abono_obj = (abono_min > 0 or abono_max > 0)
    shift = 0.0
    for _ in range(5):  # max 5 iteraciones (desplaza hasta +$500k)
        targets = _targets(shift)
        elegidos = _elegir_anos_para_targets(targets, hay_abono_obj)
        opciones_ord = sorted(set(elegidos), reverse=True)
        # Si hay duplicados por saturación, rellenar con siguientes años disponibles
        while len(opciones_ord) < 6:
            faltan = 6 - len(opciones_ord)
            resto = [a for a in (anios_enteros + anios_medios)
                     if a not in opciones_ord]
            for a in resto[:faltan]:
                opciones_ord.append(a)
            opciones_ord = sorted(set(opciones_ord), reverse=True)
            if not resto:
                break
        opciones_ord = opciones_ord[:6]

        # Regla 9.4 (Jose 2026-04-17 + §3c 2026-04-23): abono real >= piso tiered
        opciones_ord = [a for a in opciones_ord if abono_de(a) >= piso_abono]
        # Completar hasta 6 con anos adicionales que cumplan el umbral
        if len(opciones_ord) < 6:
            resto = [a for a in (anios_enteros + anios_medios)
                     if a not in opciones_ord and abono_de(a) >= piso_abono]
            resto_ord = sorted(resto, reverse=True)
            for a in resto_ord:
                if len(opciones_ord) >= 6:
                    break
                opciones_ord.append(a)
            opciones_ord = sorted(set(opciones_ord), reverse=True)[:6]

        if hay_abono_obj:
            break
        # Verificar Opc1 ahorre 0.5 ano Y abono real >= piso tiered
        if (opciones_ord
                and opciones_ord[0] <= plazo_pend_anos - 0.5
                and abono_de(opciones_ord[0]) >= piso_abono):
            break
        shift += SALTO_ABONO_SERIE  # la siguiente iteracion sube un escalon la serie

    # 6) Notas diagnosticas
    notas = []
    if hay_abono_obj:
        notas.append(
            "Regla 9.4 con abono objetivo [{:,.0f} - {:,.0f}]".format(
                abono_min, abono_max))
    else:
        if shift > 0:
            notas.append(
                "Regla 9.4 ajuste Opc1 anti-plana: serie desplazada +${:,.0f}"
                .format(shift))
        else:
            notas.append("Regla 9.4 sin abono objetivo (serie base $100k-$600k)")

    notas.append("Año minimo legal (Ley 546): {:.1f} (plazo pagado: {:.2f} años)"
                 .format(anio_min_legal, plazo_pagado_anos))

    if ingresos_cliente > 0:
        factibles = 0
        for a in opciones_ord:
            meses = int(round(a * 12))
            cuota_a = _pmt(tasa_mv, meses, saldo) + seguros
            ing_req = _ingresos_requeridos(cuota_a, es_vis)
            if ing_req <= ingresos_cliente * TOPE_INGRESOS_FACTOR:
                factibles += 1
        notas.append(
            "Factibles (ingresos x 1.10): {}/6  |  Ingresos cliente: ${:,.0f}"
            .format(factibles, ingresos_cliente))

    # Detalle de cada opción (abono, cuota, ingresos_req)
    for i, a in enumerate(opciones_ord, 1):
        meses = int(round(a * 12))
        cuota_a = _pmt(tasa_mv, meses, saldo) + seguros
        ab = cuota_a - cuota_actual
        ing_req = _ingresos_requeridos(cuota_a, es_vis)
        tag = ""
        if ingresos_cliente > 0 and ing_req > ingresos_cliente * TOPE_INGRESOS_FACTOR:
            tag = " [agresiva]"
        notas.append(
            "  Opc{} {:>4.1f} años | cuota ${:,.0f} | abono ${:,.0f} | req ${:,.0f}{}"
            .format(i, a, cuota_a, ab, ing_req, tag))

    return opciones_ord, notas


def _proponer_mixto_viable(
    plazo_min_factible: float,
    plazo_pend_anos: float,
    tasa_ea: float,
    saldo: float,
    seguros: float,
    abono_min: float,
    abono_max: float,
    ingresos_cliente: float,
    es_vis: bool,
    plazo_pagado_anos: float,
) -> tuple:
    """Mode B (Jose 2026-04-18, Dayanna): 6 plazos orquestados.

    Filosofia: el cliente pidio abono X, pero su capacidad real no lo soporta.
    En vez de forzar 6 opciones agresivas, garantizamos al menos 3 factibles
    para que el consultor tenga con que cerrar el negocio.

    Opc 1-3 (factibles, plazo > plazo_min_factible, holgura 15-5%):
      - Opc 1: ceil(plazo_min) + 2 anos (holgura amplia, cuota comoda)
      - Opc 2: ceil(plazo_min) + 1 ano
      - Opc 3: ceil(plazo_min) (borderline)
      - Cap superior al techo (plazo_pend - 1 ano).

    Opc 4-6 (agresivas, plazo < plazo_min_factible):
      - Si hay abono_objetivo: buscar anos cuyo abono_de se aproxime
        progresivamente al abono pedido por el cliente. Ultima opcion
        honra lo mas cerca posible al abono efectivo solicitado.
      - Sin abono_objetivo: pasos de ~2 anos bajando desde plazo_min.

    Ley 546: plazo minimo >= 5 anos si no pagados 5. El minimo legal se aplica
    como piso a TODAS las opciones.
    """
    import math

    tasa_mv = _ea_a_mv(tasa_ea)
    cuota_actual = _pmt(tasa_mv, int(round(plazo_pend_anos * 12)), saldo) + seguros

    # Ley 546: total del credito (pagado + restante) debe ser >= 5 anos.
    # Corregido 2026-04-24 (Jose): si ya pago >= 5 anos puede ir a cualquier
    # plazo restante. PLAZO_MINIMO_ANOS=0.5 es solo granularidad operativa.
    # Si no, lo que falta para completar 5 anos, con piso minimo 1.0 ano
    # (para permitir opciones agresivas cortas cuando plazo_pagado >= 4).
    if plazo_pagado_anos >= 5.0:
        anio_min_legal = float(PLAZO_MINIMO_ANOS)
    else:
        anio_min_legal = max(5.0 - plazo_pagado_anos, 1.0)

    # Techo: al menos 1 ano de ahorro vs plazo actual
    techo = math.floor(plazo_pend_anos)
    if techo >= plazo_pend_anos:
        techo -= 1
    # FIX 2026-05-05 (R-DVV-18 Modo B): NO elevar techo sobre plazo_pend_anos.
    # El max(techo, ceil(anio_min_legal)) elevaba el techo por encima del plazo
    # pendiente cuando anio_min_legal > plazo_pend_anos, generando opciones que
    # EXTIENDEN el plazo. Igual que el fix aplicado en _proponer_por_saltos_100k.
    if anio_min_legal < plazo_pend_anos:
        techo = max(techo, math.ceil(anio_min_legal))
    # else: no hay opciones legales < plazo_pend -> el caller detecta NO_VIABLE

    # Base = primer ano entero cuyo plazo cumple factibilidad con holgura
    # ceil(plazo_min_factible) es el entero inmediatamente mayor o igual
    base_int = int(math.ceil(plazo_min_factible))
    if base_int > techo:
        base_int = techo

    # Opc 1, 2, 3: plazos factibles (3 anos de rango)
    opc1 = min(base_int + 2, techo)
    opc2 = min(base_int + 1, techo)
    opc3 = min(base_int, techo)
    # Deduplicar manteniendo orden descendente
    factibles_bruto = [opc1, opc2, opc3]
    factibles_dedup = []
    for v in factibles_bruto:
        if v not in factibles_dedup:
            factibles_dedup.append(v)
    # Si faltan factibles (techo chico), complementar bajando a medios
    while len(factibles_dedup) < 3 and len(factibles_dedup) > 0:
        siguiente = max(factibles_dedup) - 0.5
        if siguiente in factibles_dedup or siguiente < base_int - 1:
            break
        factibles_dedup.append(siguiente)
    factibles_dedup = sorted(set(factibles_dedup), reverse=True)[:3]

    # Opc 4, 5, 6: agresivas (plazos < plazo_min_factible)
    # Granularidad 0.5 anios, piso = anio_min_legal (sin floor artificial 3.0)
    agresivas = []
    piso_agresivas = float(anio_min_legal)
    if base_int > anio_min_legal:
        tope_agresivas = float(base_int) - 0.5
        if tope_agresivas < piso_agresivas:
            tope_agresivas = piso_agresivas
    else:
        tope_agresivas = float(anio_min_legal)

    # Candidatos con granularidad 0.5 entre tope y piso
    candidatos = []
    a = tope_agresivas
    while a >= piso_agresivas - 0.01:
        candidatos.append(round(float(a), 2))
        a = a - 0.5
    candidatos = sorted(set(candidatos), reverse=True)

    hay_abono_obj = (abono_min > 0 or abono_max > 0)
    if hay_abono_obj and tope_agresivas > piso_agresivas and len(candidatos) > 0:
        # Estrategia de abono progresivo: Opc 4 abono suave, Opc 6 abono pedido
        amax = abono_max if abono_max > 0 else abono_min
        targets_abono = [amax * 0.5, amax * 0.75, amax]  # Opc 4, 5, 6
        for t in targets_abono:
            mejor, mejor_d = None, float("inf")
            for cand in candidatos:
                if cand in agresivas:
                    continue
                meses = int(round(cand * 12))
                ab = _pmt(tasa_mv, meses, saldo) + seguros - cuota_actual
                d = abs(ab - t)
                if d < mejor_d:
                    mejor, mejor_d = cand, d
            if mejor is not None:
                agresivas.append(mejor)
    else:
        # Sin abono objetivo: pasos progresivos de 1 anio
        for delta in [1, 2, 3]:
            v = max(float(base_int) - float(delta), piso_agresivas)
            if v not in agresivas:
                agresivas.append(round(float(v), 2))

    # Deduplicar agresivas
    agresivas_dedup = []
    for v in agresivas:
        if v not in agresivas_dedup:
            agresivas_dedup.append(v)

    # Rellenar con candidatos restantes si faltan agresivas
    for cand in candidatos:
        if len(agresivas_dedup) >= 3:
            break
        if cand not in agresivas_dedup:
            agresivas_dedup.append(cand)
    agresivas_dedup = sorted(set(agresivas_dedup), reverse=True)[:3]

    # Ensamblar: 6 opciones, ordenadas descendente, unicas
    todas = factibles_dedup + agresivas_dedup
    todas_unicas = []
    for v in todas:
        if v not in todas_unicas:
            todas_unicas.append(v)
    todas_unicas = sorted(todas_unicas, reverse=True)

    # Si aun faltan, rellenar con medios anios entre techo y piso_agresivas
    if len(todas_unicas) < 6:
        extras = []
        a2 = float(techo)
        while a2 >= piso_agresivas - 0.01:
            vv = round(float(a2), 2)
            if vv not in todas_unicas:
                extras.append(vv)
            a2 -= 0.5
        for v in extras:
            if len(todas_unicas) >= 6:
                break
            todas_unicas.append(v)
        todas_unicas = sorted(set(todas_unicas), reverse=True)

    opciones = [float(x) for x in todas_unicas[:6]]
    # Asegurar 6 opciones (padding con piso si falta)
    while len(opciones) < 6:
        opciones.append(float(piso_agresivas))
    opciones = sorted(set(opciones), reverse=True)
    # Si la dedup redujo, volver a rellenar
    while len(opciones) < 6:
        opciones.append(float(piso_agresivas))

    # §3c (2026-04-27): piso abono tiered en Modo B.
    # MODO A ya lo aplica (linea ~460). MODO B no lo tenia -> BUG.
    # Si el abono de una opcion < piso, reemplazar con plazos mas cortos
    # que si cumplan. Solo actua si al menos 3 opciones quedan (caso extremo:
    # ingresos muy bajos, no forzar piso infactible).
    piso_abono_b = PISO_ABONO_SALDO_BAJO if saldo < SALDO_THRESHOLD_TIER else PISO_ABONO_SALDO_ALTO
    def _abono_b(anos_):
        return _pmt(tasa_mv, int(round(anos_ * 12)), saldo) + seguros - cuota_actual

    opciones_con_piso = [a for a in opciones if _abono_b(a) >= piso_abono_b]
    if len(opciones_con_piso) >= 3:
        # Hay suficientes. Rellenar hasta 6 con plazos mas cortos que cumplan.
        extras_cands = []
        a_cand = float(techo)
        while a_cand >= float(anio_min_legal) - 0.01 and len(extras_cands) < 20:
            if a_cand not in opciones_con_piso and _abono_b(a_cand) >= piso_abono_b:
                extras_cands.append(round(a_cand, 2))
            a_cand -= 0.5
        for ec in sorted(extras_cands, reverse=True):
            if len(opciones_con_piso) >= 6:
                break
            opciones_con_piso.append(ec)
        opciones = sorted(set(opciones_con_piso), reverse=True)[:6]
        while len(opciones) < 6:
            opciones.append(opciones[-1])
    # Si < 3 pasan el piso (cliente muy limitado), conservar opciones originales
    # (el consultor manejara la conversacion de capacidad).

    # Notas diagnosticas
    notas = []
    ratio_real = RATIO_VIS if es_vis else RATIO_NO_VIS
    ratio_pct = round(ratio_real * 100)
    cuota_max_factible = ingresos_cliente * ratio_real * TOPE_INGRESOS_FACTOR
    notas.append(
        "[Modo B: mixto_viable] 3 factibles + 3 agresivas (viabilidad primero).")
    notas.append(
        "Plazo min factible: {:.2f} anos | Cuota max factible: ${:,.0f} "
        "(ratio {}%, tope x{:.2f})".format(
            plazo_min_factible, cuota_max_factible, ratio_pct, TOPE_INGRESOS_FACTOR))
    if hay_abono_obj:
        notas.append(
            "Abono cliente [${:,.0f} - ${:,.0f}] honrado en opc 4-6 (agresivas)".format(
                abono_min, abono_max))
    notas.append(
        "Ano minimo legal (Ley 546): {:.1f} (plazo pagado: {:.2f} anos)".format(
            anio_min_legal, plazo_pagado_anos))

    # Contar factibles reales
    factibles_count = 0
    for a in opciones:
        meses = int(round(a * 12))
        cuota_a = _pmt(tasa_mv, meses, saldo) + seguros
        ing_req = _ingresos_requeridos(cuota_a, es_vis)
        if ing_req <= ingresos_cliente * 1.10:
            factibles_count += 1
    notas.append(
        "Factibles (ingresos x 1.10): {}/6  |  Ingresos cliente: ${:,.0f}".format(
            factibles_count, ingresos_cliente))

    # Detalle por opcion
    for i, a in enumerate(opciones, 1):
        meses = int(round(a * 12))
        cuota_a = _pmt(tasa_mv, meses, saldo) + seguros
        ab = cuota_a - cuota_actual
        ing_req = _ingresos_requeridos(cuota_a, es_vis)
        tag = ""
        if ing_req > ingresos_cliente * TOPE_INGRESOS_FACTOR:
            tag = " [agresiva]"
        notas.append(
            "  Opc{} {:>4.1f} anos | cuota ${:,.0f} | abono ${:,.0f} | req ${:,.0f}{}"
            .format(i, a, cuota_a, ab, ing_req, tag))

    return opciones, notas


def _proponer_escalonado(plazo_pend_anos: float) -> list:
    """Genera 6 plazos escalonados desde plazo_pend hacia abajo.
    Paso default 2 anos, o 1 ano si el plazo es corto, minimo 4."""
    import math
    techo = math.floor(plazo_pend_anos)
    if techo == plazo_pend_anos:
        techo -= 1
    techo = max(techo, int(PLAZO_MINIMO_ANOS))

    # Elegir paso: si techo > 16, paso 2. Si no, paso 1.
    paso = 2 if techo >= 16 else 1
    plazos = []
    actual = float(techo)
    for _ in range(6):
        plazos.append(max(actual, PLAZO_MINIMO_ANOS))
        actual -= paso
        if actual < PLAZO_MINIMO_ANOS:
            actual = PLAZO_MINIMO_ANOS
    return plazos


def _proponer_por_ingresos(
    plazo_pend_anos: float,
    tasa_ea: float,
    saldo: float,
    seguros: float,
    ingresos: float,
    es_vis: bool,
) -> tuple:
    """3-4 opciones con cuota tal que ingresos_req <= ingresos cliente,
    luego 2 opciones con mayor ahorro (cuota un poco mas alta).

    NOTA (2026-04-17): este metodo es legado; ver docstring del modulo.
    """
    tasa_mv = _ea_a_mv(tasa_ea)
    ratio = RATIO_VIS if es_vis else RATIO_NO_VIS
    # Cuota maxima que cumple ratio con ingresos del cliente
    cuota_max_segun_ingresos = ingresos * ratio

    # Encontrar el menor plazo (en anos) cuya PMT + seguros <= cuota_max
    # Probar plazos desde plazo_pend-1 hacia abajo en pasos de 0.5 anos
    import math
    techo = math.floor(plazo_pend_anos)
    if techo == plazo_pend_anos:
        techo -= 1
    techo = max(techo, int(PLAZO_MINIMO_ANOS))

    plazo_optimo = None
    for anos in [float(x) for x in range(techo, int(PLAZO_MINIMO_ANOS) - 1, -1)]:
        meses = int(anos * 12)
        pmt_val = _pmt(tasa_mv, meses, saldo)
        if pmt_val + seguros <= cuota_max_segun_ingresos:
            plazo_optimo = anos
            break

    notas = []
    if plazo_optimo is None:
        notas.append("ATENCION: no hay plazo que permita cuota <= {:.0f} (ingresos * {:.0f}%).".format(
            cuota_max_segun_ingresos, ratio * 100))
        notas.append("Cliente debe certificar mas ingresos o aceptar cuota por encima del ratio.")
        # Usar escalonado como fallback
        return _proponer_escalonado(plazo_pend_anos), notas

    # Construir 6 opciones unicas, sin duplicados, ordenadas descendente.
    # Hasta 4 "suaves" (plazos >= plazo_optimo, cumplen ingresos)
    # Hasta 2 "agresivas" (plazos < plazo_optimo, para clientes que certifiquen mas)
    opciones_set = set()
    opciones = []

    # Suaves: desde plazo_optimo hacia techo
    p = plazo_optimo
    while p <= techo and len(opciones) < 4:
        if p not in opciones_set:
            opciones.append(float(p))
            opciones_set.add(p)
        p += 1

    # Agresivas: debajo de plazo_optimo
    p = plazo_optimo - 1
    while p >= PLAZO_MINIMO_ANOS and len(opciones) < 6:
        if p not in opciones_set:
            opciones.append(float(p))
            opciones_set.add(p)
        p -= 1

    # Si aun faltan (plazos muy restringidos), rellenar con paso 0.5
    if len(opciones) < 6:
        # Rellenar entre plazo_optimo y techo con 0.5
        pp = float(plazo_optimo) + 0.5
        while pp <= techo and len(opciones) < 6:
            if pp not in opciones_set:
                opciones.append(pp)
                opciones_set.add(pp)
            pp += 0.5
        # O con PLAZO_MINIMO
        while len(opciones) < 6:
            opciones.append(PLAZO_MINIMO_ANOS)

    # Ordenar descendente (plazo mas largo primero = cuota mas baja)
    opciones = sorted(opciones[:6], reverse=True)

    notas.append("Ingresos cliente: {:,.0f} | Ratio {:.0f}% | Cuota max aceptada: {:,.0f}".format(
        ingresos, ratio * 100, cuota_max_segun_ingresos))
    notas.append("Plazo optimo (primer plazo que cumple): {} anos".format(plazo_optimo))
    notas.append("4 opciones suaves + 2 agresivas (por si el cliente certifica mas).")
    return opciones, notas


def _proponer_por_abono(
    plazo_pend_anos: float,
    tasa_ea: float,
    saldo: float,
    seguros: float,
    abono_min: float,
    abono_max: float,
) -> tuple:
    """3 primeras opciones con abono en rango [min, max], 2 de mayor ahorro."""
    tasa_mv = _ea_a_mv(tasa_ea)
    import math
    techo = math.floor(plazo_pend_anos)
    if techo == plazo_pend_anos:
        techo -= 1
    techo = max(techo, int(PLAZO_MINIMO_ANOS))

    # Estimar plazo donde la cuota nueva - cuota actual este en rango
    # Aproximacion: ir bajando plazo hasta que incremento entre en rango
    cuota_actual_estim = _pmt(tasa_mv, int(plazo_pend_anos * 12), saldo) + seguros

    opciones_rango = []
    opciones_agresivas = []

    for anos in range(techo, int(PLAZO_MINIMO_ANOS) - 1, -1):
        meses = anos * 12
        pmt_val = _pmt(tasa_mv, meses, saldo) + seguros
        incremento = pmt_val - cuota_actual_estim
        if abono_min <= incremento <= abono_max:
            opciones_rango.append(float(anos))
        elif incremento > abono_max:
            opciones_agresivas.append(float(anos))

    # Tomar 3 en rango, 2 agresivas
    plazos = opciones_rango[:3] + opciones_agresivas[:2]
    while len(plazos) < 6:
        plazos.append(PLAZO_MINIMO_ANOS)
    plazos = plazos[:6]
    plazos = sorted(plazos, reverse=True)


    notas = [
        "Abono objetivo del cliente: {:,.0f} - {:,.0f}".format(abono_min, abono_max),
        "3 opciones dentro del rango + 2 agresivas (mayor ahorro).",
    ]
    return plazos, notas

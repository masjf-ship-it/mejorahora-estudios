"""Tests pytest para R-DVV-06 — duplicación de cuota Davivienda.

Espejo de TESTS D, E, N de `test_fase2.py`.

R-DVV-06 detecta cuando un cliente paga 2+ cuotas en un mes (mora) via 3
gatillos OR (G1, G2, G3). El refinamiento R-DVV-10 (caso Karen Tatiana)
exige `seguro_vida_aplicado > 0` para G2 — sin eso, G2 era false positive.
"""
from __future__ import annotations

from pipeline_davivienda import construir_datos


# ---- TEST N migrated — G2 NO dispara cuando seguro_vida=0 -------------
def test_rdvv06_g2_no_dispara_con_seguro_vida_cero():
    """Caso Karen Tatiana: Vision no extrajo seguro_vida (=0). Sin el guard
    de R-DVV-10, G2 disparaba erróneamente porque diff seguros aplicados vs
    +Seguros inferior > $10k. El fix exige `seg_vida_aplicado > 0` para G2.
    """
    pdf = {
        "credito": "571616690012705-4",
        "nombre": "KAREN TATIANA CAPERA AVILA",
        "cuota_mensual": 905_010,
        "plazo_inicial": 84,
        "cuotas_pendientes": 65,
        "tasa_cobrada": 0.1095,
        "frech_cobertura_pag1": 0,
        "seguro_vida": 0,             # Vision falló (real era $11,960)
        "seguro_incendio": 26_436,    # Vision sí extrajo
        "seguro_terremoto": 0,
        "total_aplicado": 905_010,    # NO duplicado
        "abonos_capital": 599_073,
        "intereses_corrientes": 254_034,
        "saldo_capital": 55_246_529,
        "seguros_inferior_total": 46_392,  # Diff con aplicados $26,436 > $10k → G2 antes false-positive
    }
    datos, notas = construir_datos(pdf, {}, {"nombre": "KAREN T"}, reg={})
    assert notas == [], (
        f"G2 NO debe disparar con seg_vida=0 (false positive guarded por R-DVV-10). "
        f"got notas: {notas}"
    )
    assert datos.seguro_vida == 0, "seguro_vida intacto en 0 (M1 R-DVV-10 lo bloqueará)"
    assert datos.seguro_incendio == 26_436, "seguro_incendio intacto"


# ---- G1 dispara: total_aplicado ≈ 2× cuota_mensual --------------------
def test_rdvv06_g1_dispara_total_aplicado_doble():
    """G1: total_aplicado ≈ 2× cuota_mensual (tolerancia ±5%).
    Cliente pagó dos meses juntos en un periodo (mora).
    """
    pdf = {
        "credito": "570000111-1",
        "nombre": "G1 CASE",
        "cuota_mensual": 1_000_000,
        "plazo_inicial": 240,
        "cuotas_pendientes": 200,
        "tasa_cobrada": 0.12,
        "frech_cobertura_pag1": 0,
        "seguro_vida": 30_000,
        "seguro_incendio": 50_000,
        "seguro_terremoto": 0,
        "total_aplicado": 2_000_000,   # ≈ 2× cuota → G1 dispara
        "abonos_capital": 200_000,
        "intereses_corrientes": 1_700_000,
        "saldo_capital": 100_000_000,
        "seguros_inferior_total": 80_000,
    }
    datos, notas = construir_datos(pdf, {}, {"nombre": "G1"}, reg={})
    # Tras R-DVV-06 disparo, debe haber al menos 1 nota_crm sobre la duplicación
    assert any("R-DVV-06" in n or "duplica" in n.lower() for n in notas), (
        f"G1 debio disparar R-DVV-06 con total_aplicado=2x. notas={notas}"
    )


# ---- E (control): cuota normal NO dispara R-DVV-06 --------------------
def test_rdvv06_no_dispara_cuota_normal():
    """Fernando canónico: cuota normal sin duplicación. R-DVV-06 NO dispara."""
    pdf = {
        "credito": "570238110001018-4",
        "nombre": "FERNANDO RODRIGO GALLO MARTINEZ",
        "cuota_mensual": 229_000,
        "plazo_inicial": 240,
        "cuotas_pendientes": 137,
        "tasa_cobrada": 0.12,
        "frech_cobertura_pag1": 0,
        "seguro_vida": 29_383,
        "seguro_incendio": 52_976,
        "seguro_terremoto": 12_758,
        "total_aplicado": 229_000,   # match cuota → G1 no dispara
        "abonos_capital": 35_608,
        "intereses_corrientes": 99_275,
        "saldo_capital": 12_985_250,
        "seguros_inferior_total": 95_117,
    }
    datos, notas = construir_datos(pdf, {}, {"nombre": "FERNANDO"}, reg={})
    assert not any("R-DVV-06" in n for n in notas), (
        f"caso normal NO debe disparar R-DVV-06. notas={notas}"
    )


# ---- TEST D migrated — override de seguros con +Seguros inferior -----
def test_rdvv06_override_seguros_con_seguros_inferior():
    """Caso Leidy canónico (leasing 600 con duplicación G1):
    - total_aplicado=$2,690,288 ≈ 2× cuota=$1,343,000 → G1 dispara
    - seguros_inferior_total=$111,315 disponible
    - Override: seguro_vida = $111,315; incendio y terremoto = 0
      (consolidado en vida — MOM R-DVV-06 'override seguros').
    """
    pdf = {
        "credito": "600707600145510-4",
        "nombre": "LEIDY YESENIA MENESES OBANDO",
        "cuota_mensual": 1_343_000,
        "plazo_inicial": 95,
        "cuotas_pendientes": 64,
        "tasa_cobrada": 0.105,
        "frech_cobertura_pag1": 0,
        "seguro_vida": 222_630,        # APLICADOS duplicados
        "seguro_incendio": 0,
        "seguro_terremoto": 0,
        "total_aplicado": 2_690_288,   # ≈ 2× cuota → G1
        "abonos_capital": 1_467_222,
        "intereses_corrientes": 1_031_750,
        "saldo_capital": 61_743_274,
        "seguros_inferior_total": 111_315,  # Real del mes (no duplicado)
    }
    staging_row = {"nombre": "LEIDY YESENIA MENESES OBANDO", "credito": "600707600145510-4"}
    datos, notas = construir_datos(pdf, {}, staging_row, reg={})

    # Override: vida = +Seguros inferior, otros en 0
    assert datos.seguro_vida == 111_315, (
        f"override seguro_vida esperado $111,315, got ${datos.seguro_vida:,.0f}"
    )
    assert datos.seguro_incendio == 0
    assert datos.seguro_terremoto == 0
    # Nota CRM mencionando duplicación
    assert len(notas) >= 1, "debe emitir nota CRM con duplicación detectada"
    assert any("Duplicacion" in n for n in notas), (
        f"nota debe mencionar 'Duplicacion'. got: {notas}"
    )


# ---- Override seguros sin +Seguros inferior (fallback /2) -------------
def test_rdvv06_override_seguros_sin_inferior_usa_mitad():
    """Cuando R-DVV-06 dispara pero seguros_inferior_total=0:
    fallback es seguros_aplicados / 2 (caso Yeimy Jissel canónico).
    """
    pdf = {
        "credito": "570040770103677-3",
        "nombre": "YEIMY JISSEL",
        "cuota_mensual": 500_000,
        "plazo_inicial": 240,
        "cuotas_pendientes": 200,
        "tasa_cobrada": 0.12,
        "frech_cobertura_pag1": 0,
        "seguro_vida": 60_000,         # APLICADOS duplicados (real $30k)
        "seguro_incendio": 40_000,     # APLICADOS duplicados (real $20k)
        "seguro_terremoto": 0,
        "total_aplicado": 1_000_000,   # 2× cuota → G1
        "abonos_capital": 100_000,
        "intereses_corrientes": 800_000,
        "saldo_capital": 50_000_000,
        "seguros_inferior_total": 0,   # NO disponible — fallback /2
    }
    datos, notas = construir_datos(pdf, {}, {"nombre": "YEIMY"}, reg={})
    # Fallback: vida = (60+40)/2 = 50_000, otros en 0
    expected_vida = (60_000 + 40_000) / 2
    assert datos.seguro_vida == expected_vida, (
        f"fallback vida esperado ${expected_vida:,.0f}, got ${datos.seguro_vida:,.0f}"
    )
    assert datos.seguro_incendio == 0
    assert datos.seguro_terremoto == 0

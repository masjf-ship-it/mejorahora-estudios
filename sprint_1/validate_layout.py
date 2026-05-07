"""Validador Task #26: verifica atributos de auto-layout en un XLSX generado.

Uso:
    python sprint_1/validate_layout.py "output/ESTUDIO FERNANDO RODRIGO GALLO MARTINEZ-21.04.26.xlsx" > diag_layout.txt 2>&1

Comprueba:
- workbook.xml <workbookView> tiene activeTab apuntando a ACTUAL
- workbook.xml <workbookView> tiene xWindow/yWindow/windowWidth/windowHeight
  (preset mitad derecha 1920x1080: xWindow=14400, windowWidth=14400)
- En el sheetN.xml de ACTUAL: tabSelected="1", zoomScale="145", zoomScaleNormal="145"
- En cualquier OTRA hoja: NO hay tabSelected (evita seleccion multiple)
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path


def _read(z: zipfile.ZipFile, name: str) -> str:
    return z.read(name).decode("utf-8")


def _map_sheet_name_to_file(wb_xml: str, rels_xml: str) -> dict[str, str]:
    """Retorna {nombre_hoja_upper: 'xl/worksheets/sheetN.xml'}."""
    name_to_rid: dict[str, str] = {}
    for m in re.finditer(r"<sheet\b[^>]*?>", wb_xml):
        tag = m.group(0)
        nm = re.search(r'\bname="([^"]*)"', tag)
        rm = re.search(r'(?:r:id|r:Id|relationshipId)="([^"]*)"', tag)
        if nm and rm:
            name_to_rid[nm.group(1).strip().upper()] = rm.group(1)

    rid_to_tgt: dict[str, str] = {}
    for m in re.finditer(r"<Relationship\b[^>]*?>", rels_xml):
        a = m.group(0)
        idm = re.search(r'\bId="([^"]*)"', a)
        tm = re.search(r'\bTarget="([^"]*)"', a)
        if idm and tm:
            t = tm.group(1).lstrip("/")
            if not t.startswith("xl/"):
                t = "xl/" + t
            rid_to_tgt[idm.group(1)] = t

    return {n: rid_to_tgt[r] for n, r in name_to_rid.items() if r in rid_to_tgt}


def _sheet_order(wb_xml: str) -> list[str]:
    """Orden 0-based de hojas en <sheets>."""
    out = []
    for m in re.finditer(r"<sheet\b[^>]*?>", wb_xml):
        nm = re.search(r'\bname="([^"]*)"', m.group(0))
        out.append((nm.group(1).strip().upper() if nm else ""))
    return out


def validate(xlsx_path: Path) -> int:
    if not xlsx_path.exists():
        print(f"[ERR] No existe: {xlsx_path}")
        return 2

    errors = 0
    with zipfile.ZipFile(xlsx_path, "r") as z:
        wb_xml = _read(z, "xl/workbook.xml")
        rels_xml = _read(z, "xl/_rels/workbook.xml.rels")
        sheet_map = _map_sheet_name_to_file(wb_xml, rels_xml)
        order = _sheet_order(wb_xml)

        print(f"== {xlsx_path.name} ==")
        print(f"Hojas en orden: {order}")

        # 1) workbookView
        wv_match = re.search(r"<workbookView\b[^>]*?/?>", wb_xml)
        if not wv_match:
            print("[FAIL] No hay <workbookView>")
            return 2
        wv = wv_match.group(0)
        print(f"\n<workbookView> tag completo:\n  {wv}\n")

        # 2) activeTab → debe ser el idx de ACTUAL
        at = re.search(r'\bactiveTab="(\d+)"', wv)
        if not at:
            print("[FAIL] workbookView sin activeTab")
            errors += 1
        else:
            at_idx = int(at.group(1))
            actual_idx = order.index("ACTUAL") if "ACTUAL" in order else -1
            if at_idx == actual_idx:
                print(f"[PASS] activeTab={at_idx} apunta a ACTUAL (idx {actual_idx})")
            else:
                print(f"[FAIL] activeTab={at_idx}, pero ACTUAL esta en idx {actual_idx}")
                errors += 1

        # 3) window geometry
        expected = {"xWindow": 14400, "yWindow": 0,
                    "windowWidth": 14400, "windowHeight": 15600}
        for k, v in expected.items():
            m = re.search(r'\b' + k + r'="(-?\d+)"', wv)
            if not m:
                print(f"[FAIL] workbookView sin {k}")
                errors += 1
            elif int(m.group(1)) != v:
                print(f"[WARN] {k}={m.group(1)} (esperado {v})")
            else:
                print(f"[PASS] {k}={v}")

        # 4) sheetViews por hoja
        print("\n-- sheetView por hoja --")
        for name_upper, fn in sheet_map.items():
            try:
                sheet_xml = _read(z, fn)
            except KeyError:
                continue
            sv = re.search(r"<sheetView\b[^>]*?/?>", sheet_xml)
            if not sv:
                print(f"  {name_upper}: (sin sheetView)")
                continue
            tag = sv.group(0)
            tsel = re.search(r'\btabSelected="([^"]*)"', tag)
            zs = re.search(r'\bzoomScale="([^"]*)"', tag)
            zsn = re.search(r'\bzoomScaleNormal="([^"]*)"', tag)

            if name_upper == "ACTUAL":
                ok_ts = tsel and tsel.group(1) == "1"
                ok_zs = zs and zs.group(1) == "145"
                ok_zsn = zsn and zsn.group(1) == "145"
                status = "PASS" if (ok_ts and ok_zs and ok_zsn) else "FAIL"
                if status == "FAIL":
                    errors += 1
                print(f"  [ACTUAL] tabSelected={tsel.group(1) if tsel else '-'} "
                      f"zoomScale={zs.group(1) if zs else '-'} "
                      f"zoomScaleNormal={zsn.group(1) if zsn else '-'} -> {status}")
            else:
                # Otras hojas: NO deben tener tabSelected
                if tsel:
                    print(f"  [{name_upper}] tabSelected={tsel.group(1)} -> FAIL (debe estar ausente)")
                    errors += 1
                else:
                    print(f"  [{name_upper}] (sin tabSelected) -> PASS")

    print(f"\n== Resultado: {'PASS' if errors == 0 else 'FAIL'} ({errors} errores) ==")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validate_layout.py <xlsx>")
        sys.exit(2)
    sys.exit(validate(Path(sys.argv[1])))

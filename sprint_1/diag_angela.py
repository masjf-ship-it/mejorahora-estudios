# -*- coding: utf-8 -*-
"""Diag completo ANGELA — lista worksheets, busca en todas las que parezcan REGISTROS."""
import sys
sys.path.insert(0, ".")
from hubspot_client import HubSpotClient
import drive_client

NOMBRE = "ANGELA CONSTANZA DIAZ SONS"

print("=" * 70)
print(f"DIAG v3: {NOMBRE}")
print("=" * 70)

gc, drive = drive_client.get_clients()
hs = HubSpotClient.from_config()

sh = gc.open_by_key(drive_client.SHEET_ID_BD)

print(f"\nSpreadsheet: {sh.title}")
print("Worksheets disponibles:")
ws_list = sh.worksheets()
for ws in ws_list:
    print(f"  - '{ws.title}' (rows={ws.row_count}, cols={ws.col_count})")

# Buscar Angela en TODAS las hojas
print("\n" + "=" * 70)
for ws in ws_list:
    try:
        all_rows = ws.get_all_values()
    except Exception as e:
        print(f"\n[{ws.title}] ERROR leyendo: {e}")
        continue
    if not all_rows:
        continue
    header = all_rows[0]
    # Buscar Angela
    found = None
    for i, row in enumerate(all_rows[1:], start=2):
        rowd = dict(zip(header, row + [""] * (len(header) - len(row))))
        joined = " ".join(str(v).upper() for v in rowd.values())
        if "ANGELA" in joined and "DIAZ" in joined and "SONS" in joined:
            found = (i, rowd)
            break
    if found:
        print(f"\n--- HOJA '{ws.title}' ROW {found[0]} ---")
        for k, v in found[1].items():
            if v:
                print(f"  [{k}]: {v}")

# HubSpot con CC correcta (desde "Acceso")
print("\n" + "=" * 70)
print("HUBSPOT lookup con CC=52912371")
ALL_PROPS = [
    "firstname", "lastname", "email", "phone", "hubspot_owner_id",
    "numero_de_identificacion", "identificacion", "cedula", "numero_de_cedula",
    "banco", "banco_donde_tienes_la_hipoteca_o_leasing_habitacional",
    "ingresos", "ingreso", "ingresos_mensuales", "ingresos_demostrables",
    "abono", "abono_efectivo", "abono_extraordinario",
    "actividad_economica", "ocupacion", "profesion",
    "ciudad", "ciudad_de_residencia",
]
m = hs.match_contact_cascade(cedula="52912371", nombre=NOMBRE, properties=ALL_PROPS)
print(f"matched_by: {m.get('matched_by')}")
contact = m.get("contact") or {}
if contact:
    print(f"id: {contact.get('id')}")
    props = contact.get("properties") or {}
    print("Propiedades con valor:")
    for k, v in sorted(props.items()):
        if v:
            print(f"  {k}: {v}")
else:
    print("SIN MATCH")

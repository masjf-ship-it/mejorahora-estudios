"""
conftest.py — pytest discovery setup para sprint_1/tests/.

Coexiste con `sprint_1/test_fase2.py` (script lineal golden, 16 tests A-P).
La migracion completa a pytest es tarea futura (Ola 3 / B2 full); por ahora
los tests pytest validan piezas puras (helpers sin deps externas) que no
requieren mocking pesado de Sheets / HubSpot / Drive.

Comando para correrlos:
    pytest sprint_1/tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

# Asegurar que sprint_1/ esta en sys.path para imports tipo
# `from listar_pendientes_hoy import dedup_por_credito`
SPRINT1 = Path(__file__).resolve().parent.parent
if str(SPRINT1) not in sys.path:
    sys.path.insert(0, str(SPRINT1))

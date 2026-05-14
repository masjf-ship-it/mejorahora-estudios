# OLA 3 — Plan detallado de escalabilidad

**Versión:** 1.0 · 2026-05-07
**Rol:** Documento de planeación (NO es fuente de reglas). Activo cuando se ejecuten B1, B2-full o B3.
**Política docs:** este archivo vive bajo `_planning/`. No se versiona como regla; se descarta cuando todo lo planeado se ejecute o revoque.

---

## Resumen

Las piezas grandes de Ola 3 (B1 BancoStrategy, B2 pytest+CI completo, B3 Workspace SA) **no se ejecutaron en la sesión 2026-05-07** por razones técnicas y de seguridad documentadas abajo. Este archivo deja la guía paso a paso para cuando arranquen.

| Pieza | Bloqueador | Ejecutable hoy |
|---|---|---|
| B1 BancoStrategy refactor | No hay segundo banco listo para validar la abstracción | NO — esperar a Bancolombia |
| B2 pytest + CI completo | Sin remoto GitHub configurado, no hay CI real | PARCIAL — B2-light entregado (pytest discovery + tests/dedup), CI cuando haya remoto |
| B3 Workspace SA | Requiere IAM/billing (MASTER_RULES §17.9 prohíbe a Claude) | NO — Jose ejecuta, Claude documenta |
| **B11 unificar número-parsers** (descubierto 2026-05-12) | 5 funciones equivalentes con sutiles diferencias en `_limpiar_num` / `_peso_col` / `_f` / `to_float` / `_norm_num` | PARCIAL — testear comportamiento idéntico para casos canónicos primero, después refactor |

---

## B1 — Abstraer `BancoStrategy` antes de duplicar `pipeline_<banco>.py`

### Problema

`sprint_1/pipeline_davivienda.py` tiene 1187 líneas. Cuando arranque Bancolombia, copiar/pegar y modificar es la ruta de menor resistencia y la ruta peor: duplica bugs, divide la verdad, complica los siguientes 3 bancos.

### Diseño objetivo

Crear `sprint_1/pipeline_base.py` con:
- Clase `BancoStrategy` (abstract) que define el contrato:
  - `nombre_banco: str`
  - `prefijos_validos: tuple[str, ...]`
  - `extract_pdf(path) -> dict` (delegado a `extract_<banco>_pdf.py`)
  - `aplicar_reglas_banco(datos) -> datos` (R-DVV-07 para Davivienda; equivalente para otros)
  - `validar_m1(datos) -> tuple[ok, errores]`
- Clase `Pipeline` que orquesta los 17 pasos canónicos (MASTER_RULES §6) usando un `BancoStrategy`.

`pipeline_davivienda.py` queda como:
```python
from pipeline_base import Pipeline
from extract_davivienda_pdf import parse_davivienda_pdf
from validar_extraccion_davivienda import validar_datos_cliente

class DaviviendaStrategy(BancoStrategy):
    nombre_banco = "DAVIVIENDA"
    prefijos_validos = ("570", "571", "600")
    extract_pdf = staticmethod(parse_davivienda_pdf)
    validar_m1 = staticmethod(validar_datos_cliente)
    def aplicar_reglas_banco(self, datos):
        # R-DVV-07 proyección 6ª cuota
        ...

if __name__ == "__main__":
    Pipeline(DaviviendaStrategy()).main()
```

### Pasos validables (con red de seguridad)

1. **Pre-condición:** test_fase2.py 16/16 PASS antes de empezar.
2. **Snapshot manual:** `_backups/2026-XX-XX_pre_b1_refactor/` (MASTER_RULES §17.11).
3. Crear `pipeline_base.py` con `BancoStrategy` ABC + `Pipeline`.
4. Migrar `procesar_cliente`, `enriquecer_con_hubspot`, `enriquecer_con_registros`, `_filtrar_pendientes_davivienda` a métodos de `Pipeline`.
5. Crear `DaviviendaStrategy` que implementa lo banco-específico (R-DVV-07, prefijos, mapeos).
6. **Reducir** `pipeline_davivienda.py` a ~30 líneas (entry point que arma `Pipeline(DaviviendaStrategy())`).
7. Ejecutar `test_fase2.py` → 16/16 PASS o **rollback inmediato** desde snapshot.
8. Ejecutar pipeline en `--dry-run` con `--max 3` y comparar output JSON byte-a-byte con corrida pre-refactor.
9. Solo entonces commitear.
10. **Validación Bancolombia:** crear `BancolombiaStrategy` mínima y ejecutar `--dry-run --max 1`. Si Bancolombia compila pero falla en M1 con motivo banco-específico (no por falla del refactor), B1 está validado.

### Riesgo principal

`procesar_cliente` (~300 líneas) tiene side effects en STAGING + Drive + log JSON. Romper su orden o early-returns rompe producción. Mitigación: refactor línea por línea con tests entre cada cambio, no rewrite from scratch.

### Cuándo ejecutar B1

Disparador: cuando exista `extract_bancolombia_pdf.py` con al menos 1 caso canónico que parsee correctamente. Antes de eso, no hay forma de validar que la abstracción es la correcta.

---

## B2 — pytest + CI completo

### Estado actual (post B2-light, 2026-05-07)

- `sprint_1/test_fase2.py` (script lineal, 16 tests A–P) — **suite golden, no se toca**.
- `sprint_1/tests/` con `conftest.py` y `test_dedup.py` (9 tests pytest sobre `dedup_por_credito`) — **co-existe con el script lineal**.
- `requirements.txt` actualizado con dependencias reales.

### Pendiente (B2-full)

#### Paso 1 — Convertir el suite golden a pytest sin perder cobertura
Cada `# TEST X — descripción` del script lineal se convierte en `def test_x_<slug>():`. El bloque `_assert(cond, msg)` se reemplaza con `assert cond, msg`.

Recorrido sugerido:
- TEST A → `tests/test_dvv07.py::test_proyeccion_sexta_cuota_julieth`
- TEST B → `tests/test_dvv07.py::test_proyeccion_no_aplica_cuotas_ge_6`
- TEST F (es_vis) → `tests/test_es_vis.py`
- TESTS I–N (M1) → `tests/test_m1.py`
- TEST O (HubSpot genéricos) → `tests/test_hubspot_genericos.py`

Mantener `test_fase2.py` como wrapper que invoca `pytest -v sprint_1/tests/` durante la transición.

#### Paso 2 — CI (cuando exista remoto GitHub)
`.github/workflows/tests.yml`:
```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.10' }
      - run: pip install -r sprint_1/requirements.txt
      - run: pytest sprint_1/tests/ -v --cov=sprint_1 --cov-report=term
      - run: python -c "import sys; sys.path.insert(0,'maintenance'); from maintenance_60min import check_doc_code_drift; assert not check_doc_code_drift(), 'drift detected'"
```

#### Paso 3 — Pre-commit con pytest local
Agregar al hook `.githooks/pre-commit`: si hay `.py` staged en `sprint_1/`, correr `python -m pytest sprint_1/tests/ -q` y bloquear si falla.

### Cuándo ejecutar B2-full

Disparador: cuando se cree el remoto GitHub (o equivalente). El refactor pytest tiene sentido si CI lo va a correr automáticamente; sin CI, agregar más complejidad sin beneficio.

---

## B3 — Service Account de Workspace para Drive §4.2

### Problema actual

- `credentials/sheets_sa.json` (SA `claude-bd-sync@mejorahora-automations.iam.gserviceaccount.com`) **no puede subir a Drive §4.2** porque la carpeta destino es propiedad de Gmail personal (`reducciondecreditos2@gmail.com`) y los SA en Gmail personal hitean `storageQuotaExceeded 403`.
- Workaround actual: OAuth user (`credentials/oauth_token.json`). Token revocado por Google cada ~6 meses (proyecto en modo "Testing"). Mantenimiento manual cada vez (`drive_oauth_setup.py`).

### Diseño objetivo

Crear o usar un Workspace de Google (cualquier dominio que MejorAhora controle) con:
1. Una organización Workspace (no personal Gmail).
2. Una **carpeta compartida** equivalente a `1UVsQtyzQHEpfRlcjUrq8gBsXgEqABoym`, dentro del Workspace.
3. Un nuevo SA con domain-wide delegation o miembro de un "Shared Drive" del Workspace.
4. Migrar `DRIVE_FOLDER_ANALISTAS_RW` en `config_reglas.py` al nuevo folder ID.
5. Eliminar dependencia de OAuth user.

### Pasos (Jose ejecuta — Claude no toca IAM, §17.9)

1. Validar si MejorAhora tiene Google Workspace activo. Si no: comprar plan Business Starter (~$6/usuario/mes).
2. Crear Shared Drive dentro del Workspace, ej. "MejorAhora Analistas".
3. Mover (no copiar) los Excel históricos de §4.2 al Shared Drive — **importante**: cualquier link existente apuntando a §4.2 dejará de funcionar. Notificar al equipo de analistas + consultores antes.
4. En GCP Console → IAM → Service Accounts → crear `mejorahora-drive-uploader@<projectid>.iam.gserviceaccount.com`.
5. Otorgar al SA acceso al Shared Drive como Content Manager (panel Shared Drive → Manage members).
6. Descargar JSON de la nueva SA → `credentials/drive_uploader_sa.json`.
7. Editar `sprint_1/oauth_drive.py` o crear `sprint_1/sa_drive.py`: usar Service Account credentials en lugar de OAuth user.
8. Smoke test: `py pipeline_davivienda.py --nombre "FERNANDO" --dry-run` y verificar que el upload aparece en el Shared Drive.
9. Actualizar `MASTER_RULES §4.5` y CHANGELOG.

### Beneficio

Cero mantenimiento OAuth. Cero `invalid_grant` cada 6 meses. SA nunca expira.

### Costo

- ~$72/año por usuario Workspace (1 usuario es suficiente para esto).
- 1-2 horas de migración inicial.

### Riesgo

Romper links existentes a `1UVsQtyzQHEpfRlcjUrq8gBsXgEqABoym`. Mitigación: dejar §4.2 en READ-ONLY paralelo durante una semana mientras se migra; comunicar al equipo.

---

## Notas finales

- B1, B2-full y B3 son **independientes entre sí**. Pueden ejecutarse en cualquier orden.
- La prioridad recomendada: **B3 (más alto ROI: cero mantenimiento OAuth) → B1 (cuando arranque Bancolombia) → B2-full (cuando exista CI)**.
- Cualquiera de los tres es trabajo de >1h y debe ir en commits/PRs separados, con red de seguridad (snapshot pre-cambio + tests post-cambio).
- Cuando se ejecute, eliminar la sección correspondiente de este archivo. Cuando todas se ejecuten, archivar `_planning/OLA_3_PLAN.md` a `_archivo/` (MASTER_RULES §15.4).

---

## B11 — Unificar número-parsers (descubierto sesión nocturna 2026-05-12)

### Problema

Hay **5 funciones distintas** para parsear números monetarios colombianos en el codebase:

| Función | Archivo | Maneja |
|---|---|---|
| `_limpiar_num(s)` | `extract_davivienda_pdf.py:25` | Strings de regex captures con varios formatos |
| `_peso_col(raw)` | `extract_davivienda_pdf.py:231` (local en función) | Formato colombiano de miles con punto |
| `_f(v, default)` | `pipeline_davivienda.py:463` | Versión más completa: rangos "X a Y", todos los formatos |
| `to_float(val)` | `excel_populator.py:190` | Simple: limpia $, comas, % |
| `_norm_num(v)` | `vision_extractor.py:340` | Muy simple: comma→dot solamente |

**Riesgo**: cada función fue creada con casos reales (Fernando, Jorge, Yeimy, etc.). Sus diferencias sutiles ya están battle-tested para cada uso. **Centralizar sin tests dedicados podría reintroducir bugs viejos.**

### Plan paso a paso

1. **Crear `sprint_1/tests/test_parse_numero.py`** con TODOS los casos canónicos cubiertos por cada función:
   - Caso Fernando: `_f('$4.800.000')` → 4800000.0
   - Caso Jorge: `_f('$200,000')` → 200000.0
   - Caso Yeimy: `_peso_col('22.021')` → 22021.0
   - Rangos: `_f('$100.000 a $300.000')` → 200000.0 (promedio)
   - Tasas: `to_float('14,31%')` → 0.1431
   - Edge: vacíos, None, "N/A"

2. Cada test ejecuta la función ORIGINAL para registrar el comportamiento actual (snapshot test).

3. Crear `sprint_1/utils/parse_numero.py` con `parse_numero(val, *, allow_range=False)` que cubra TODOS los casos.

4. **Migrar UNA función a la vez**, validando que el snapshot test sigue pasando.

5. Después de las 5 migraciones, eliminar las funciones locales.

### Cuándo ejecutar B11

Disparador: tras 7 días de operación cloud sin nuevos casos edge que añadir. Si aparecen casos nuevos, primero documentarlos como tests.

---

## B12 — Persistencia de logs JSON cloud (descubierto 2026-05-12)

### Problema

El pipeline en cloud genera `_logs/pipeline_davivienda_<timestamp>.json` por cada
corrida, pero el filesystem del container Anthropic es **efímero** — el archivo
se pierde al terminar la routine. Resultado:

- La **Routine 5 Métricas Semanal** (lunes 9:00) corre en su propio container
  fresco y ve 0 archivos JSON → reporte siempre vacío
- No hay forma de verificar "5 días clean" desde cloud
- Pérdida de auditoría: no podemos ver retroactivamente qué pasó hace 3 días

### Síntoma

```
# Metricas semanales pipeline Davivienda — 2026-05-12 23:34
# Ventana: ultimos 7 dias  ·  archivos JSON analizados: 0
(sin datos en la ventana — pipeline no corrio o logs ausentes)
```

### Opciones de fix

| Opción | Pros | Contras |
|---|---|---|
| **A. Commit logs a git** después de cada pipeline run | Visible en GitHub, sincroniza automático entre cloud y local | Clutterea el repo (~1 commit por run = 60+/mes) |
| **B. Upload logs a Drive** (carpeta dedicada, sólo SA) | Limpio, no clutterea repo | Requiere agregar lógica en `pipeline_davivienda.py::main()`, manejar cuota Drive SA |
| **C. Upload logs a Google Sheets** (1 fila/run) | Queryable, dashboards posibles | Cambio de formato (JSON → row), requiere schema definido |
| **D. Routine 5 también corre el pipeline antes de las métricas** | No requiere infra extra | Pipeline corre 3x al día en vez de 2x, gasto innecesario de creditos |

### Plan paso a paso (opción B recomendada)

1. Crear carpeta Drive `_logs_pipeline_json/` con permisos SA-only (no compartida).
2. En `pipeline_davivienda.py::main()`, después de escribir el JSON local, subirlo
   a Drive usando el cliente SA (no OAuth — los logs no van a §4.2 cliente).
3. En `metricas_pipeline.py`, agregar lógica que:
   - Si `is_cloud_env()`: descarga últimos N días de la carpeta Drive
   - Si local: usa `_logs/` como hoy
4. Mantener escritura local también (zero downside).

### Cuándo ejecutar B12

Disparador: cuando llevemos 3+ semanas en cloud y la falta de métricas semanales
empiece a doler (no sabemos si vamos por el día 5 clean o no). Si Jose decide
deshabilitar Windows Tasks antes de tener B12, valida el "5 días clean"
manualmente mirando cada transcript de Routine en `claude.ai/code/routines`.

# ESTADO_PROYECTO — Roadmap & Dashboard MejorAhora Estudios

**Versión:** 2.2 · 2026-05-07
**Rol:** Dashboard de progreso. NO es fuente de reglas (ver `MASTER_RULES.md` y `MOM_<BANCO>.md`).

---

## 0. Reglas vigentes

> **REGLAS Y REFERENCIA:** este archivo NO contiene reglas. Solo estado.
> - Reglas generales: `MASTER_RULES.md` (v2.8)
> - Reglas Davivienda: `MOM_DAVIVIENDA.md` (v1.5)
> - Constantes código: `sprint_1/config_reglas.py`
> - Cheatsheet bancos: `MANUAL_EXTRACTO_BANCOS.md`
> - Memoria operativa Claude: `spaces/.../memory/MEMORY.md` + `CHANGELOG.md`

---

## 1. Estado por banco

| Banco | Estado | Pipeline | Tests | Notas |
|---|---|---|---|---|
| **DAVIVIENDA** | ✅ OPERATIVO | `pipeline_davivienda.py` | 16/16 PASS (A-P) | R-DVV-01..18 + §3a-3e activas. MOM_DAVIVIENDA.md vigente. |
| BANCOLOMBIA | 🟡 PENDIENTE | — | — | Próximo en cola. Construir `extract_bancolombia_pdf.py` + `MOM_BANCOLOMBIA.md` |
| CAJA SOCIAL | 🟡 PENDIENTE | — | — | Tras Bancolombia |
| FNA | ⚪ BACKLOG | — | — | — |
| BANCO DE BOGOTÁ | ⚪ BACKLOG | — | — | — |
| Resto | ⚪ BACKLOG | — | — | AV Villas, Colpatria, etc. |

---

## 2. Hitos completados (cronología 2026)

| Fecha | Hito |
|---|---|
| 2026-04-16 | Cuestionario reglas de negocio inicial. bank_rules/DAVIVIENDA.md v1.0 |
| 2026-04-17 | Reglas 9.2/9.3/9.4 validadas con Martha. Auto-aplicación 9.3 + 9.4 |
| 2026-04-18 | Mode B mixto_viable activo |
| 2026-04-20 | GCP Service Account activa, BD canónica única confirmada |
| 2026-04-21 | Pipeline Davivienda E2E operativo. STAGING patron activo. Mantenimiento 60min |
| 2026-04-22 | Migración Vertex AI Gemini 2.5 Pro |
| 2026-04-23 | Sprint Fix Bloque (Fases 0-4): bug `_f` colombiano, R-DVV-06+G3, R-DVV-07, R-DVV-09 leasing, M1+M2 validadores, STEP 7 memoria |
| 2026-04-24 | Sprint Retro: 7 fixes (R-DVV-10/11/12 + §3c/3d/3e) + MOM creado + MASTER_RULES v2.0 + MOM_DAVIVIENDA v1.0 + arquitectura limpia |

---

## 3. Próximos hitos (roadmap)

### Corto plazo (esta semana)
- [ ] Procesar volumen Davivienda diario sin intervención (scheduled task 08:30)
- [ ] Validar sin errores 5+ días consecutivos antes de avanzar a Bancolombia

### Mediano plazo (próximas 2 semanas)
- [ ] Construir `extract_bancolombia_pdf.py`
- [ ] Crear `MOM_BANCOLOMBIA.md`
- [ ] Migrar pipeline a `pipeline_bancolombia.py` separado
- [ ] Test golden suite para Bancolombia
- [ ] Crear `pipeline_3bancos.py` como meta-orquestador (SOLO cuando ≥2 bancos OK)

### Largo plazo
- [ ] Caja Social
- [ ] FNA
- [ ] Banco de Bogotá
- [ ] Skill personalizado MejorAhora `/procesar-estudio` (invocable manual)
- [ ] PDF generation del estudio para entrega al cliente (post-Excel)

---

## 4. Métricas operativas

### Última corrida (2026-04-24)
- 9 pendientes Davivienda procesados
- 8 Excel generados (5 hipotecarios + 3 leasing 600 procesados como hipotecario)
- 1 Gilma reintentada exitosa tras 429 Vertex
- Notas CRM en columna L: 4 clientes con R-DVV-06 disparada

### Histórico
- Estudios manuales pre-automatización: ~30/día (1h c/u)
- Meta automatización: 50-100/día (≤15min c/u)
- Estado actual: ~10/día con red de seguridad (M1+M2+12 reglas)

---

## 5. Casos canónicos (referencia)

Ver `MOM_DAVIVIENDA.md §6` para tabla completa de casos validados.

---

## 6. Archivos del proyecto (mapa)

### Documentación
- `MASTER_RULES.md` — reglas generales (todos los bancos)
- `MOM_DAVIVIENDA.md` — reglas específicas Davivienda
- `ESTADO_PROYECTO.md` — este archivo (dashboard)
- `MANUAL_EXTRACTO_BANCOS.md` — cheatsheet rápido por banco
- `tips_de_banco.xlsx` — **referencia para construcción de extractores de bancos NUEVOS**. Contiene tips visuales de cómo leer cada banco. Consultar al construir `extract_<banco>_pdf.py` y `MOM_<BANCO>.md` para no empezar desde cero.

### Código operativo
- `sprint_1/pipeline_davivienda.py` — orquestador E2E
- `sprint_1/extract_davivienda_pdf.py` — parser pdfplumber
- `sprint_1/vision_extractor.py` — fallback Vertex AI Gemini
- `sprint_1/hubspot_client.py` — HubSpot CRM
- `sprint_1/proponedor_plazos.py` — Mode A + Mode B
- `sprint_1/excel_populator.py` — inyecta datos en PESOS.xlsx
- `sprint_1/validar_extraccion_davivienda.py` — M1
- `sprint_1/validar_excel_generado.py` — M2
- `sprint_1/test_fase2.py` — 16 tests golden
- `sprint_1/config_reglas.py` — constantes centralizadas
- `sprint_1/listar_pendientes_hoy.py` — publicador STAGING
- `maintenance/maintenance_60min.py` — mantenimiento horario + STEP 7

### Carpetas
- `_backups/` — snapshots históricos (168 retención = 7 días, FIFO)
- `_archivo/` — archivos sueltos archivados por mantenimiento
- `_archivo_analisis/` — scripts viejos pre-arquitectura actual
- `_logs/` — logs y reportes de anomalías
- `bank_rules/` — vacío post-consolidación 2026-04-24 (DAVIVIENDA.md absorbido en MOM_DAVIVIENDA)
- `credentials/` — JSON service account (no commitear)

---

## 7. Decisiones estratégicas vigentes

Las decisiones operativas viven en MASTER_RULES.md y MOM_<BANCO>.md. Aquí solo se mencionan las **estratégicas** (qué construir, en qué orden, con qué prioridad):

- **Banco por banco** (no paralelo). Validar al 100% antes de avanzar.
- **Davivienda primero** (mayor volumen + mayor cantidad de extractos disponibles).
- **Cero errores antes de escalar** (16 tests golden + M1 + M2 + STEP 7 antes de procesar volumen).
- **Política docs limpia** (MASTER_RULES §17.3): cuando una regla se revoca se BORRA del doc canónico; la traza histórica vive EXCLUSIVAMENTE en `CHANGELOG.md`. No se acumulan marcadores `[REVOCADA]` en MASTER_RULES/MOM.
- **Cualquier cambio de regla** requiere patrón formal "Actualización de Constitución Operativa" (ver `MASTER_RULES §19`).

---

**FIN ESTADO_PROYECTO v2.2**
**Próxima revisión:** cuando se sume Bancolombia o se completen 5+ días consecutivos sin errores.

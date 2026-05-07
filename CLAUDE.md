# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Doc hierarchy — read these before acting

This project lives by its docs. The order of authority is strict and enforced:

1. **`MOM_<BANCO>.md`** (currently only `MOM_DAVIVIENDA.md`) — bank-specific rules. **Wins over MASTER_RULES on contradiction.**
2. **`MASTER_RULES.md`** — general rules across all banks. The canonical source for stack, IDs, flow, validators, anti-patterns.
3. **`sprint_1/config_reglas.py`** — single source of truth for numeric constants (tolerances, prefixes, thresholds). If a rule has a number, it lives here.
4. **`ESTADO_PROYECTO.md`** — dashboard / roadmap. **Not a source of rules.**
5. **`CHANGELOG.md`** — historical trace of revoked/changed rules.
6. **`MANUAL_EXTRACTO_BANCOS.md`** — quick cheatsheet per bank for new extractor builds.

When a user request conflicts with what you find in code, MASTER_RULES/MOM wins. When MASTER_RULES and a MOM disagree, the MOM wins.

### Rule-update protocol (MASTER_RULES §19) — non-negotiable

Any new rule or change must:

1. Be written into `MASTER_RULES.md` (general) or `MOM_<BANCO>.md` (bank-specific) — **not just chat**.
2. **Delete** the old contradicting rule from the canonical doc (no `[REVOCADA]` markers in MASTER_RULES/MOM — those go in CHANGELOG).
3. Be logged in `CHANGELOG.md` with timestamp + reason (old → new).
4. Bump the doc version (header field).
5. Reconcile `sprint_1/config_reglas.py` if a constant changed.
6. Reconcile `sprint_1/test_fase2.py` if asserts change.

Skipping any step creates drift. Drift is the enemy.

## Common commands

All commands assume CWD = repo root unless noted. Many scripts use relative paths from `sprint_1/` (e.g. `../credentials/sheets_sa.json`), so `cd sprint_1` before running them.

### Daily pipeline (production flow)

```cmd
run_pipeline.bat
```

Runs PASO 1 (publish pending REGISTROS → STAGING) then PASO 2 (process STAGING). Logs to `_logs\scheduled_YYYYMMDD.txt`. Scheduled twice daily (08:30 / 20:30) under `MejorAhora\Pipeline Davivienda AM/PM`.

### Manual steps (debugging)

```cmd
cd sprint_1
py listar_pendientes_hoy.py --banco davivienda                 # PASO 1 — required first, otherwise pipeline says "sin pendientes"
py pipeline_davivienda.py > diag_pipeline.txt 2>&1             # PASO 2 — all pending
py pipeline_davivienda.py --nombre "FERNANDO" --force          # single client, re-process even if "Excel generado"
py pipeline_davivienda.py --credito 570238110001018-4 --dry-run
py pipeline_davivienda.py --max 3
```

### Tests (golden suite)

```cmd
py sprint_1\test_fase2.py > diag_fase2.txt 2>&1
```

**Must be 15/15 PASS (tests A–O)** before merging any change to extractor/proponedor/pipeline. There is no pytest harness; the script asserts inline and exits non-zero on failure.

### OAuth re-auth (when pipeline fails with `invalid_grant`)

```cmd
cd sprint_1
py diag_oauth.py > diag_oauth.txt 2>&1     # diagnose first
py drive_oauth_setup.py                    # opens browser, re-auth as reducciondecreditos2@gmail.com
```

The OAuth refresh token (`credentials/oauth_token.json`) gets revoked by Google when the project is in "Testing" mode and the token is unused for ~6 months. Service account (`credentials/sheets_sa.json`) cannot upload to Drive folder §4.2 because it hits `storageQuotaExceeded` on personal Gmail — that's why uploads use OAuth user.

### Maintenance (hourly)

```cmd
python maintenance\maintenance_60min.py --dry-run    # safe preview
python maintenance\maintenance_60min.py              # apply (backup + cleanup + STEP 7 memory audit)
```

Registered as `MejorAhora\Mantenimiento 60min` (HOURLY). See `maintenance/README.md`.

### Output convention (MASTER_RULES §18)

**Always redirect script output to a file. Never ask Jose for console screenshots.**

```cmd
py <script>.py > diag_<contexto>.txt 2>&1
```

Scheduled logs land in `_logs/scheduled_YYYYMMDD.txt`. Diagnostic captures live at the repo root as `<contexto>_diag.txt`.

## High-level architecture

The system is a single-pipeline-per-bank PDF-to-Excel automation. Today only **Davivienda** is operative; Bancolombia / Caja Social / FNA / Banco de Bogotá are in backlog. Each bank gets its own pipeline + MOM + extractor — no shared "generic" pipeline until ≥2 banks are live (then `pipeline_3bancos.py` becomes a meta-orchestrator).

### Three-layer data hierarchy (MASTER_RULES §7) — strict

| Layer       | Fields                                                          | Source of truth                                  |
|-------------|-----------------------------------------------------------------|--------------------------------------------------|
| Financial   | crédito, saldo, cuota, tasa, plazo, seguros, FRECH, intereses   | **PDF extract** (pdfplumber → Vertex Gemini fallback) |
| Client      | nombre, consultor, ingresos, abono, banco, email, actividad     | **HubSpot** (fallback REGISTROS via R-DVV-12)    |
| Operational | ESTADO, fecha solicitud, referenciador                          | **REGISTROS** (NEVER for financial data)         |

Crossing layers (e.g. taking financial numbers from REGISTROS) is a bug.

### Pipeline E2E flow per client (MASTER_RULES §6)

`sprint_1/pipeline_davivienda.py` orchestrates per row of STAGING:

1. **Pre-pass:** detect HubSpot generic signatures (≥3 clients with same consultor+actividad+ingresos → R-DVV-12, those clients fall back to REGISTROS).
2. Find client folder in Drive §4.1 → download PDF to tmp.
3. HubSpot cascade: CC → email → name. Multi-token name search in `firstname` (R-DVV-17C). CC like `"N/A"` is treated as missing (R-DVV-14, R-DVV-17A).
4. If PDF protected: `decrypt("")` first, then CC candidates (STAGING + HubSpot).
5. `extract_davivienda_pdf` (pdfplumber) → if critical fields empty → `vision_extractor` (Vertex AI Gemini 2.5 Pro).
6. REGISTROS lookup (cached once per run).
7. `construir_datos`: cascade HubSpot > REGISTROS > STAGING > default.
8. **M1 validate** (`validar_extraccion_davivienda.py::validar_datos_cliente`) → FAIL → REVISION_MANUAL, abort. Tolerance ±$70k warn / ±$500k error. `seguro_vida=0 AND seguro_incendio>0` → ERROR (R-DVV-10).
9. Bank-specific pre-9.3 rules (R-DVV-07: project to 6th paid quota for Davivienda/DaviBank when `cuotas_pagadas < 6`).
10. **R-DVV-18 pre-check Ley 546:** if `plazo_pagado + plazo_pendiente < 5 años` → REVISION_MANUAL `NO_VIABLE_LEY_546`, abort.
11. **Rule 9.3** (auto): if `|SUMA CUOTA| > $70k` → replace `capital_mensual` and `interes_mensual` with simulator values. Never touch seguros.
12. Recompute DIF.SIMULA. If `> $70k` (R-DVV-11) → REVISION_MANUAL.
13. **Rule 9.4** (`proponedor_plazos.py`): cascade `manual` → `regimen_E` → `mixto_viable` (Mode B) → `por_saltos_100k` (Mode A) → `escalonado`. **Wrapper filter (R-DVV-18) drops any option `>= plazo_pendiente`**, no exceptions.
14. `excel_populator.crear_estudio()` writes `output/ESTUDIO <NOMBRE>-DD.MM.AA.xlsx` (template = `PESOS.xlsx`, root). `ocultar_hoja_bd()` hides the BD sheet.
15. **M2 validate** (`validar_excel_generado.py`): naming, sheet ACTUAL+activeTab, B2/B5/B10–B15 vs `DatosClienteExcel`, B16:B21 plazos descending. Errors → "ALERTA M2" note in CRM, **does not block upload**.
16. Upload to Drive §4.2 via OAuth user.
17. Update STAGING: `estado="Excel generado"`, link, nota_crm in column L.

### Numeric tolerance is universal

`±$70.000 COP` is the single tolerance for: extractor cross-check, Rule 9.3 SUMA CUOTA, R-DVV-11 DIF.SIMULA, M1 sum-vs-cuota, BD-vs-PDF saldo. Centralized as `TOLERANCIA_*` in `config_reglas.py`. Change one value → changes the whole system.

### Constants live in `config_reglas.py` only

If a rule has a number (tolerance, prefix, threshold, ratio), it must come from `config_reglas.py`. Hardcoded literals in pipeline / proponedor / validators are bugs by definition.

### STAGING is the only pipeline destination

The pipeline writes only to the STAGING tab (Sheet `1_9FUAo8cSrLDWAkJlNoy29Cmyh9ojXwnW6zbvhGsESA`, "BASE PARA ESTUDIOS OK"). REGISTROS is human-managed. Always **append by column name**, never `clear()`, never positional index. The blacklisted Sheet IDs in MASTER_RULES §3.4 must never be used.

### Drive folder discipline

- §4.1 (extracts source, ID `17hN5TDiQ3Ozop-xT6g4OYAyQrZkZT0os`): **READ-ONLY** — never write, never rename, never delete.
- §4.2 (analyst folder, ID `1UVsQtyzQHEpfRlcjUrq8gBsXgEqABoym`): the only write target. Excel studies go here. Upload via OAuth user.
- §4.3 (per-client folders): Excel studies are MejorAhora intellectual property — **never** upload them to client folders.

## Stack snapshot

| Concern               | Value                                                       |
|-----------------------|-------------------------------------------------------------|
| Runtime               | Python 3.10+ (mostly stdlib; pdfplumber, openpyxl, google-* required) |
| GCP Project           | `mejorahora-automations`                                    |
| Service Account       | `claude-bd-sync@mejorahora-automations.iam.gserviceaccount.com` (`credentials/sheets_sa.json`) |
| Vision model          | Vertex AI `gemini-2.5-pro` (do **not** downgrade to flash without Jose's authorization) |
| HubSpot Private App   | `Control Notas MejoraHora` (portal `21065449`); token in `sprint_1/config.ini [HUBSPOT]` |
| HubSpot custom props  | `valor_de_ingresos` (NOT `ingresos`), `abono_efectivo` (NOT `abono`), `cedula` |
| Excel template        | `PESOS.xlsx` (repo root)                                    |
| Test harness          | Plain Python script (`test_fase2.py`), no pytest discovery  |

## Anti-patterns (MASTER_RULES §20) — enforced

- **§20.4** Never write to Drive §4.1.
- **§20.3** Never put Excel studies in client folders.
- **§20.5 / 20.6** Never invent numbers, never recompute the cuota from the extract — `Valor Cuota Mes` is literal truth (§8.10).
- **§20.10** Never process UVR — pesos only.
- **§20.11** One Excel per client, ever. If Jose adjusts manually, do not re-process.
- **§20.12 / R-DVV-18** Never propose a plazo `>= plazo_pendiente`. Never extend the term.
- **§20.1** Never use a blacklisted Sheet ID (§3.4).
- **§11.6** Never commit `config.ini` (contains HubSpot token) or anything in `credentials/`.
- **§17.10** Vertex stays on `gemini-2.5-pro` unless Jose authorizes a downgrade.
- "N/A" / "NA" / "N.A." is **not** an identifier — treat as empty for HubSpot/REGISTROS lookups (R-DVV-14, R-DVV-17A).

## Backups & file hygiene (MASTER_RULES §17.11)

- Hourly auto-snapshots: `_backups/<timestamp>/`, FIFO retention 336 (~14 days), managed by `maintenance_60min.py`.
- Manual pre-change snapshots: `_backups/YYYY-MM-DD_<motivo>/`. Auto-deleted after 30 days idle.
- **Never create backup folders outside `_backups/`** — they become orphans without retention.
- Permanent snapshots: `credentials/snapshot_permanente_<motivo>.zip` and document in CHANGELOG.

## Naming (MASTER_RULES §12)

- Excel studies: `ESTUDIO <NOMBRE MAYÚSCULAS SIN TILDES>-DD.MM.AA.xlsx` (hyphen, not underscore).
- Names in Sheets: UPPERCASE, no diacritics.
- N° crédito: **string** preserving leading zeros. Excel truncates beyond 15 digits — IDs longer than that must stay as text.
- Tasa: `0,00` (comma decimal). Money: `$` + `.` thousands separator (Colombian).

## Working with Jose (MASTER_RULES §22)

Claude operates as strategic partner, not passive executor. Surface risks, propose alternatives, and disagree directly with brief, concrete counter-proposals when an instruction looks technically wrong — even if Jose insists. If Jose overrides, execute and leave a written trace of the risk (chat or CHANGELOG). Jose's working language is Spanish; documents are in Spanish; preserve that in any new doc.

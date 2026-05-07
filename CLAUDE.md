# CLAUDE.md

This file orients Claude Code in this repository. It is intentionally short — it points to canonical sources rather than duplicating them. If a rule appears here AND in `MASTER_RULES.md`, MASTER_RULES wins.

## Doc hierarchy — read before acting

Strict order of authority:

1. **`MOM_<BANCO>.md`** (today: `MOM_DAVIVIENDA.md`) — bank-specific rules. **Wins over MASTER_RULES on contradiction.**
2. **`MASTER_RULES.md`** — general rules across all banks. Canonical source for stack, IDs, flow, validators, anti-patterns.
3. **`sprint_1/config_reglas.py`** — single source of truth for numeric constants (tolerances, prefixes, thresholds). If a rule has a number, it lives here.
4. **`ESTADO_PROYECTO.md`** — dashboard / roadmap. **Not a source of rules.**
5. **`CHANGELOG.md`** — historical trace of revoked/changed rules.
6. **`MANUAL_EXTRACTO_BANCOS.md`** — quick cheatsheet per bank for new extractor builds.

When user instruction conflicts with code, MASTER_RULES/MOM wins. When MASTER_RULES and a MOM disagree, the MOM wins.

### Rule-update protocol (MASTER_RULES §19) — non-negotiable

Any new rule or change must:
1. Land in `MASTER_RULES.md` (general) or `MOM_<BANCO>.md` (bank-specific).
2. **Delete** the old contradicting rule from the canonical doc (no `[REVOCADA]` markers — those go in CHANGELOG).
3. Be logged in `CHANGELOG.md` with timestamp + reason (old → new).
4. Bump the doc version (header field).
5. Reconcile `sprint_1/config_reglas.py` if a constant changed.
6. Reconcile `sprint_1/test_fase2.py` if asserts change.

Skipping any step creates drift. Drift is the enemy. The pre-commit hook (MASTER_RULES §17.12) catches the worst forms.

## Common commands

All commands assume CWD = repo root unless noted. Many scripts use relative paths from `sprint_1/` (e.g. `../credentials/sheets_sa.json`), so `cd sprint_1` before running them.

### Daily pipeline (production)

```cmd
run_pipeline.bat
```

Runs PASO 1 (publish pending REGISTROS → STAGING) then PASO 2 (process STAGING). Logs to `_logs\scheduled_YYYYMMDD.txt`. Scheduled twice daily (08:30 / 20:30) under `MejorAhora\Pipeline Davivienda AM/PM`.

### Manual / debugging

```cmd
cd sprint_1
py listar_pendientes_hoy.py --banco davivienda                 # PASO 1 — required first
py pipeline_davivienda.py > diag_pipeline.txt 2>&1             # PASO 2 — all pending
py pipeline_davivienda.py --nombre "FERNANDO" --force          # single client, re-process
py pipeline_davivienda.py --credito 570238110001018-4 --dry-run
py pipeline_davivienda.py --max 3
```

### Tests (golden suite)

```cmd
py sprint_1\test_fase2.py > diag_fase2.txt 2>&1
```

**16/16 PASS (tests A–P)** required before merging changes to extractor / proponedor / pipeline. Plain Python script, no pytest harness.

### Weekly metrics (B5)

```cmd
py sprint_1\metricas_pipeline.py --dias 7 --out _logs\metricas_semanal.txt
```

Aggregates `_logs/pipeline_davivienda_*.json` into success rate, failure categories, "5 days clean" criterion (ESTADO §3) — supports the call to escalate from Davivienda to Bancolombia.

### OAuth re-auth (when pipeline fails with `invalid_grant`)

```cmd
cd sprint_1
py diag_oauth.py > diag_oauth.txt 2>&1     # diagnose first
py drive_oauth_setup.py                    # browser flow as reducciondecreditos2@gmail.com
```

OAuth refresh token (`credentials/oauth_token.json`) gets revoked by Google when the project is in "Testing" mode and the token is unused for ~6 months. Service account (`credentials/sheets_sa.json`) cannot upload to Drive folder §4.2 because Gmail personal hits `storageQuotaExceeded` — that's why uploads use OAuth user.

### Maintenance (hourly)

```cmd
python maintenance\maintenance_60min.py --dry-run    # safe preview
python maintenance\maintenance_60min.py              # apply
```

Runs as `MejorAhora\Mantenimiento 60min` (HOURLY). Steps include backup, drift checker (STEP 8), memory audit (STEP 7). See `maintenance/README.md`.

### Pre-commit hook activation (one-time per clone)

```cmd
maintenance\install_hooks.cmd
```

Sets `core.hooksPath=.githooks`. The hook (MASTER_RULES §17.12) blocks: secrets staged, blacklist Sheet IDs, Python syntax errors, drift detected by STEP 8.

### Output convention (MASTER_RULES §18)

**Always redirect script output to a file. Never ask Jose for console screenshots.**

```cmd
py <script>.py > diag_<contexto>.txt 2>&1
```

Scheduled logs: `_logs/scheduled_YYYYMMDD.txt`. Diagnostic captures: `<contexto>_diag.txt` at repo root.

## High-level architecture (pointer)

Single-pipeline-per-bank PDF-to-Excel automation. Today only **Davivienda** is operative; Bancolombia / Caja Social / FNA / Banco de Bogotá are in backlog. See `MASTER_RULES.md` §6 for the canonical 17-step E2E flow per client, §7 for the 3-layer data hierarchy (Financial=PDF / Client=HubSpot / Operational=REGISTROS), §8 for universal adjustment rules (9.2/9.3/9.4 + §3a-3e + §8.15 universal tolerance ±$70k + §8.16 R-DVV-18 plazo guard).

## Stack quick-reference

Full stack table is `MASTER_RULES.md` §2. Critical pointers:
- Vision model: Vertex AI `gemini-2.5-pro` (do **not** downgrade without Jose's authorization — §17.10)
- HubSpot custom props: `valor_de_ingresos`, `abono_efectivo`, `cedula` (NOT `ingresos`/`abono`/generic — §5.7-5.8)
- Excel template: `PESOS.xlsx` (root), integrity-checked via `PESOS_TEMPLATE_SHA256` (B6)
- Python 3.10+, mostly stdlib + pdfplumber, openpyxl, google-* (see `sprint_1/requirements.txt`)

## Anti-patterns — top 5 (full list: MASTER_RULES §20)

- **§20.4** Never write to Drive §4.1 (extractos source — READ-ONLY).
- **§20.3** Never put Excel studies in client folders. Only §4.2.
- **§20.6 / §8.10** Never recompute the cuota. `Valor Cuota Mes` from the extract is literal truth.
- **§20.11** One Excel per client, ever. If Jose adjusts manually, do not re-process.
- **§20.12 / R-DVV-18** Never propose a plazo `>= plazo_pendiente`. Never extend the term.

## Backups & file hygiene (pointer)

- Hourly auto-snapshots: `_backups/<timestamp>/`, FIFO retention 168 (~7 days). `RETENTION_N` in `maintenance_60min.py` is the source of truth (MASTER_RULES §17.11).
- Manual pre-change snapshots: `_backups/YYYY-MM-DD_<motivo>/`. Auto-deleted after 30 days idle.
- Permanent snapshots: `credentials/snapshot_permanente_<motivo>.zip` + CHANGELOG entry.
- **Never** create backup folders outside `_backups/` (orphans without retention).

## Working with Jose (MASTER_RULES §23)

Claude operates as strategic partner. Surface risks, propose alternatives, and disagree directly with brief, concrete counter-proposals when an instruction looks technically wrong — even if Jose insists. If Jose overrides, execute and leave a written trace of the risk (chat or CHANGELOG). Jose's working language is Spanish; documents are in Spanish; preserve that in any new doc.

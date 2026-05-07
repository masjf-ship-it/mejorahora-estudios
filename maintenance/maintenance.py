# -*- coding: utf-8 -*-
"""
maintenance.py — Ciclo de mantenimiento MejorAhora Estudios.

Cadencia: cada 12 horas (07:00 y 19:00) via Windows Task Scheduler
(MejorAhora\\Mantenimiento AM + MejorAhora\\Mantenimiento PM).

Historico: este script corria cada 60 min (de ahi su nombre original
maintenance_60min.py) cuando MejorAhora operaba en Cowork Desktop, donde
el agente "olvidaba" cosas entre sesiones; backups frecuentes + auditoria
de memoria operativa (STEP 7) eran un workaround. En Claude Code la
memoria son archivos versionados (CLAUDE.md + MASTER_RULES.md +
CHANGELOG.md) y el drift checker (STEP 8) + pre-commit hook validan
integridad estructural. Cadencia reducida a 12h y STEP 7 eliminado el
2026-05-07.

Operaciones (MASTER_RULES.md §15):
  1. Backup   — copia lista blanca a _backups/<ts>/
  2. Diff     — verifica consistencia entre docs canonicos
  3. Reporte  — _logs/anomalies_<ts>.txt si hay hallazgos
  4. Limpieza — mueve archivos sueltos en raiz NO whitelisted a _archivo/YYYY-MM/
  5. Log      — append a _logs/mant.log
  STEP 8 (2026-05-07) — drift checker docs <-> codigo (no autopoda)

Uso:
  python maintenance.py                # --apply (default)
  python maintenance.py --dry-run      # reporta sin mover/borrar
  python maintenance.py --quick        # solo log heartbeat, no backup

Codigos de salida:
  0 — OK (con o sin anomalias, que quedan en reporte)
  1 — Error critico (no se pudo escribir log)
"""
from __future__ import annotations

import argparse
import configparser
import datetime as dt
import fnmatch
import os
import shutil
import sys
from pathlib import Path

# -----------------------------------------------------------------------------
# Configuracion
# -----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent  # ESTUDIOS CLAUDE/
BACKUPS_DIR = PROJECT_ROOT / "_backups"
ARCHIVO_DIR = PROJECT_ROOT / "_archivo"
LOGS_DIR = PROJECT_ROOT / "_logs"
WHITELIST_PATH = HERE / "whitelist.txt"

# Retencion: 30 snapshots = ~15 dias a 2 corridas/dia (07:00, 19:00).
# MASTER_RULES §17.11 — esta constante es la FUENTE DE VERDAD.
# Cambio 2026-05-07: 168 (cadencia horaria) -> 30 (cadencia 12h, STEP 7 eliminado).
RETENTION_N = 30

# Backup — lista de patrones (relativos a PROJECT_ROOT) a snapshotear.
# Limpieza 2026-05-07: removidos archivos consolidados (SOURCE_OF_TRUTH, PROMPT_DEFINITIVO,
# CRM.xlsx, BD.xlsx, tips_de_banco.csv, bank_rules/) y config.ini (token leak risk —
# si necesitas backup de config, usa snapshot manual cifrado en credentials/).
BACKUP_TARGETS = [
    "MASTER_RULES.md",
    "MOM_DAVIVIENDA.md",
    "ESTADO_PROYECTO.md",
    "MANUAL_EXTRACTO_BANCOS.md",
    "CLAUDE.md",
    "CHANGELOG.md",
    "PESOS.xlsx",
    "tips_de_banco.xlsx",
    "run_pipeline.bat",
    "sprint_1/*.py",
    "sprint_1/docs/*.md",
    "automation/apps_script/*.gs",
    "maintenance/*.py",
    "maintenance/*.bat",
    "maintenance/*.cmd",
    "maintenance/whitelist.txt",
    "maintenance/README.md",
]

# Rutas que se verifican existan (para el diff / anomalias)
REQUIRED_PATHS = [
    PROJECT_ROOT / "MASTER_RULES.md",
    PROJECT_ROOT / "MOM_DAVIVIENDA.md",
    PROJECT_ROOT / "CHANGELOG.md",
    PROJECT_ROOT / "sprint_1" / "config.ini",
    PROJECT_ROOT / "sprint_1" / "hubspot_client.py",
    PROJECT_ROOT / "sprint_1" / "config_reglas.py",
]

# Patrones que NUNCA deben aparecer en codigo/docs (lista negra BD, etc.)
FORBIDDEN_PATTERNS = [
    ("1UbQ_Ghb0dmeCWAmEJNdFGkBsbK6PNWr6T48Pi-nTdd8", "BD lista negra §3.4"),
    ("1fsop9wgv1HvRxREnYQGopR7d3TSUhlIFU4bm6QQ0ykM", "BD lista negra §3.4"),
]

# Extensiones que SI escaneamos en busqueda de forbidden patterns
SCAN_EXTENSIONS = {".py", ".md", ".ini", ".bat", ".cmd", ".txt", ".gs", ".json"}

# Carpetas que se ignoran en el scan forbidden (para no alertar sobre backups)
IGNORE_SCAN_DIRS = {"_backups", "_archivo", "_archivo_analisis", "_logs", ".git"}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def now_ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d_%H%M")


def now_iso() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dirs() -> None:
    for d in (BACKUPS_DIR, ARCHIVO_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_whitelist() -> list[str]:
    if not WHITELIST_PATH.exists():
        return []
    out = []
    for line in WHITELIST_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def is_whitelisted(name: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def log_line(msg: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with (LOGS_DIR / "mant.log").open("a", encoding="utf-8") as fh:
        fh.write(f"[{now_iso()}] {msg}\n")


# -----------------------------------------------------------------------------
# Paso 1 — Backup
# -----------------------------------------------------------------------------
def do_backup(dry_run: bool) -> tuple[int, Path]:
    """Copia archivos del BACKUP_TARGETS a _backups/<ts>/. Retorna (copiados, path)."""
    ts = now_ts()
    dest_root = BACKUPS_DIR / ts
    copied = 0
    if dry_run:
        return 0, dest_root

    dest_root.mkdir(parents=True, exist_ok=True)
    manifest_lines = [f"# Backup manifest — {now_iso()}", ""]

    for pattern in BACKUP_TARGETS:
        pat_path = PROJECT_ROOT / pattern
        # Si el patron tiene glob, expandir
        if any(c in pattern for c in "*?[]"):
            parent = pat_path.parent
            if not parent.exists():
                continue
            matches = list(parent.glob(pat_path.name))
        else:
            matches = [pat_path] if pat_path.exists() else []

        for src in matches:
            if not src.is_file():
                continue
            rel = src.relative_to(PROJECT_ROOT)
            dst = dest_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
                copied += 1
                manifest_lines.append(str(rel).replace("\\", "/"))
            except Exception as exc:
                manifest_lines.append(f"# ERROR copying {rel}: {exc}")

    (dest_root / "MANIFEST.txt").write_text(
        "\n".join(manifest_lines), encoding="utf-8"
    )
    return copied, dest_root


def rotate_backups(keep_n: int, dry_run: bool) -> int:
    if not BACKUPS_DIR.exists():
        return 0
    subdirs = sorted(
        [p for p in BACKUPS_DIR.iterdir() if p.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    old = subdirs[keep_n:]
    if dry_run:
        return len(old)
    removed = 0
    for d in old:
        try:
            shutil.rmtree(d)
            removed += 1
        except Exception:
            pass
    return removed


# Retencion logs pipeline JSON: 30 dias = 30 corridas/dia * 30 = 900 max razonable.
# Diferente de RETENTION_N (snapshots backup horarios). 2026-05-07: pre-fix se
# acumulaban sin limite (51 archivos en 30 dias).
RETENTION_PIPELINE_LOGS_DAYS = 30


def rotate_pipeline_logs(keep_days: int, dry_run: bool) -> int:
    """Borra `_logs/pipeline_davivienda_*.json` mas antiguos que keep_days.

    El nombre incluye fecha YYYYMMDD, asi que la rotacion es por fecha del
    log (no mtime), lo que es mas preciso si los archivos se copian/mueven.
    """
    import re as _re
    if not LOGS_DIR.exists():
        return 0
    pat = _re.compile(r"^pipeline_davivienda_(\d{8})_\d{6}\.json$")
    cutoff = dt.date.today() - dt.timedelta(days=keep_days)
    candidatos = []
    for p in LOGS_DIR.iterdir():
        m = pat.match(p.name)
        if not m:
            continue
        try:
            fecha = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        if fecha < cutoff:
            candidatos.append(p)
    if dry_run:
        return len(candidatos)
    removed = 0
    for p in candidatos:
        try:
            p.unlink()
            removed += 1
        except Exception:
            pass
    return removed


# -----------------------------------------------------------------------------
# Paso 2 y 3 — Diff + Reporte
# -----------------------------------------------------------------------------
def scan_forbidden_patterns() -> list[tuple[Path, str, str]]:
    """Busca IDs de lista negra en archivos activos. Retorna [(path, pattern, reason)]."""
    findings = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Filtrar directorios que se ignoran
        dirs[:] = [d for d in dirs if d not in IGNORE_SCAN_DIRS]
        for fn in files:
            ext = Path(fn).suffix.lower()
            if ext not in SCAN_EXTENSIONS:
                continue
            fp = Path(root) / fn
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pattern, reason in FORBIDDEN_PATTERNS:
                if pattern in text:
                    findings.append((fp, pattern, reason))
    return findings


def check_required_paths() -> list[Path]:
    missing = []
    for p in REQUIRED_PATHS:
        if not p.exists():
            missing.append(p)
    return missing


def check_hubspot_token() -> str | None:
    """Retorna None si OK, o string con el problema."""
    cfg_path = PROJECT_ROOT / "sprint_1" / "config.ini"
    if not cfg_path.exists():
        return "sprint_1/config.ini no existe"
    cfg = configparser.ConfigParser()
    try:
        cfg.read(cfg_path, encoding="utf-8")
    except Exception as e:
        return f"config.ini ilegible: {e}"
    if "HUBSPOT" not in cfg:
        return "config.ini sin seccion [HUBSPOT]"
    token = cfg["HUBSPOT"].get("token", "").strip()
    if not token:
        return "[HUBSPOT] token vacio"
    if not token.startswith("pat-"):
        return "[HUBSPOT] token con formato invalido (no empieza con 'pat-')"
    return None


def write_anomaly_report(findings: dict, ts: str) -> Path | None:
    has_issues = any(v for k, v in findings.items() if k != "memory") or (
        findings.get("memory") and findings["memory"].get("has_issues")
    ) or bool(findings.get("drift"))
    if not has_issues:
        return None
    path = LOGS_DIR / f"anomalies_{ts}.txt"
    lines = [
        f"# Anomalias — {now_iso()}",
        f"# Generado por maintenance.py",
        "",
    ]
    if findings.get("missing"):
        lines.append("## Archivos requeridos ausentes (MASTER_RULES §2, §18)")
        for p in findings["missing"]:
            lines.append(f"  - MISSING: {p}")
        lines.append("")
    if findings.get("hubspot"):
        lines.append("## HubSpot (MASTER_RULES §5)")
        lines.append(f"  - {findings['hubspot']}")
        lines.append("")
    if findings.get("forbidden"):
        lines.append("## Lista negra presente (MASTER_RULES §3.4 / §19.1)")
        for fp, pat, reason in findings["forbidden"]:
            rel = fp.relative_to(PROJECT_ROOT)
            lines.append(f"  - {rel}  ← {pat}  [{reason}]")
        lines.append("")
    if findings.get("drift"):
        lines.append("## Drift docs ↔ codigo (STEP 8, 2026-05-07)")
        for d in findings["drift"]:
            lines.append(f"  - {d}")
        lines.append("  ACCION: alinear el doc o el codigo y registrar en CHANGELOG.")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# -----------------------------------------------------------------------------
# Paso 4 — Limpieza raiz
# -----------------------------------------------------------------------------
# (definida abajo en clean_root() — antes esta seccion contenia STEP 7
#  "Memoria operativa del agente" — eliminado 2026-05-07. Ver header docstring.)


# -----------------------------------------------------------------------------
# Paso 8 — Drift checker (2026-05-07)
# Detecta inconsistencias estructurales entre docs canonicos y codigo:
#   - Header version != Footer version del mismo doc
#   - PESOS.xlsx hash != PESOS_TEMPLATE_SHA256
#   - RETENTION_N en codigo != menciones explicitas en MASTER_RULES
#   - Referencias a archivos canonicos inexistentes desde docs
#   - ESTADO_PROYECTO version stale respecto a MASTER_RULES/MOM
# -----------------------------------------------------------------------------
def check_doc_code_drift() -> list[str]:
    """Retorna lista de mensajes de drift. Vacia = sin problemas."""
    issues: list[str] = []

    def _read(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return ""

    import re as _re

    # 1) Header vs footer en MASTER_RULES.md
    mr_path = PROJECT_ROOT / "MASTER_RULES.md"
    mr_text = _read(mr_path)
    if mr_text:
        m_head = _re.search(r"\*\*Versi[oó]n:\*\*\s*([\d.]+)", mr_text)
        m_foot = _re.search(r"FIN MASTER_RULES v([\d.]+)", mr_text)
        if m_head and m_foot and m_head.group(1) != m_foot.group(1):
            issues.append(
                f"MASTER_RULES.md: header v{m_head.group(1)} != footer v{m_foot.group(1)}"
            )

    # 2) Header vs footer en ESTADO_PROYECTO.md
    es_path = PROJECT_ROOT / "ESTADO_PROYECTO.md"
    es_text = _read(es_path)
    if es_text:
        m_head = _re.search(r"\*\*Versi[oó]n:\*\*\s*([\d.]+)", es_text)
        m_foot = _re.search(r"FIN ESTADO_PROYECTO v([\d.]+)", es_text)
        if m_head and m_foot and m_head.group(1) != m_foot.group(1):
            issues.append(
                f"ESTADO_PROYECTO.md: header v{m_head.group(1)} != footer v{m_foot.group(1)}"
            )

    # 3) ESTADO §0 cita MASTER_RULES/MOM con version stale
    if es_text and mr_text:
        m_es_master = _re.search(r"MASTER_RULES\.md`?\s*\(v([\d.]+)\)", es_text)
        m_real = _re.search(r"\*\*Versi[oó]n:\*\*\s*([\d.]+)", mr_text)
        if m_es_master and m_real and m_es_master.group(1) != m_real.group(1):
            issues.append(
                f"ESTADO_PROYECTO §0 cita MASTER_RULES v{m_es_master.group(1)} "
                f"pero el archivo es v{m_real.group(1)}"
            )
    mom_path = PROJECT_ROOT / "MOM_DAVIVIENDA.md"
    mom_text = _read(mom_path)
    if es_text and mom_text:
        m_es_mom = _re.search(r"MOM_DAVIVIENDA\.md`?\s*\(v([\d.]+)\)", es_text)
        m_real_mom = _re.search(r"\*\*Versi[oó]n:\*\*\s*([\d.]+)", mom_text)
        if m_es_mom and m_real_mom and m_es_mom.group(1) != m_real_mom.group(1):
            issues.append(
                f"ESTADO_PROYECTO §0 cita MOM_DAVIVIENDA v{m_es_mom.group(1)} "
                f"pero el archivo es v{m_real_mom.group(1)}"
            )

    # 4) PESOS.xlsx hash vs config_reglas.PESOS_TEMPLATE_SHA256
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "sprint_1"))
        from config_reglas import verify_pesos_template  # type: ignore
        ok, msg = verify_pesos_template(PROJECT_ROOT)
        if not ok:
            issues.append(f"PESOS.xlsx: {msg}")
    except Exception as exc:
        issues.append(f"No se pudo verificar PESOS.xlsx hash: {exc}")

    # 5) RETENTION_N (este script) consistente con MASTER_RULES §17.11
    if mr_text:
        # Busca el numero de snapshots citado en §17.11
        m_ret = _re.search(r"Retenci[oó]n:\s*\*?\*?(\d+)\s*snapshots", mr_text)
        if m_ret:
            doc_n = int(m_ret.group(1))
            if doc_n != RETENTION_N:
                issues.append(
                    f"Retencion drift: codigo RETENTION_N={RETENTION_N} != "
                    f"MASTER_RULES §17.11 cita {doc_n}"
                )

    # 6) Referencias a archivos canonicos inexistentes desde MASTER_RULES
    if mr_text:
        for ref in _re.findall(r"`([A-Z][A-Z0-9_]+\.md)`", mr_text):
            ref_path = PROJECT_ROOT / ref
            if not ref_path.exists():
                # Excepciones: archivos genericos referenciados como pattern
                if ref.startswith("MOM_") and ref != "MOM_DAVIVIENDA.md":
                    continue  # MOM_<BANCO>.md futuros
                issues.append(
                    f"MASTER_RULES referencia `{ref}` que no existe en raiz"
                )

    return issues


def clean_root(patterns: list[str], dry_run: bool) -> list[tuple[Path, Path]]:
    """Mueve archivos sueltos en raiz NO whitelisted a _archivo/YYYY-MM/.
    Retorna lista [(src, dst)] de lo que se movio (o se moveria en dry-run)."""
    moved = []
    month = dt.datetime.now().strftime("%Y-%m")
    dest_root = ARCHIVO_DIR / month
    for entry in PROJECT_ROOT.iterdir():
        if entry.is_dir():
            continue  # §18.7 — nunca mover carpetas
        name = entry.name
        if is_whitelisted(name, patterns):
            continue
        dst = dest_root / name
        if not dry_run:
            dest_root.mkdir(parents=True, exist_ok=True)
            # Si dst existe, agregar sufijo timestamp
            if dst.exists():
                stem, suffix = os.path.splitext(name)
                dst = dest_root / f"{stem}_{now_ts()}{suffix}"
            try:
                shutil.move(str(entry), str(dst))
            except Exception as exc:
                log_line(f"ERROR moving {entry}: {exc}")
                continue
        moved.append((entry, dst))
    return moved


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Mantenimiento 12h MejorAhora (AM/PM)")
    ap.add_argument("--dry-run", action="store_true", help="No mueve ni borra nada")
    ap.add_argument("--quick", action="store_true", help="Solo heartbeat log")
    ap.add_argument("--no-clean", action="store_true", help="Skip paso 4 limpieza")
    args = ap.parse_args()

    dry_run = bool(args.dry_run)
    mode = "DRY-RUN" if dry_run else "APPLY"

    try:
        ensure_dirs()
    except Exception as exc:
        print(f"ERROR ensuring dirs: {exc}", file=sys.stderr)
        return 1

    if args.quick:
        log_line(f"HEARTBEAT mode={mode}")
        print(f"[{now_iso()}] heartbeat {mode}")
        return 0

    ts = now_ts()
    summary = {"ts": ts, "mode": mode}

    # Paso 1 — Backup
    copied, dest = do_backup(dry_run)
    summary["backup_copied"] = copied
    summary["backup_path"] = str(dest.relative_to(PROJECT_ROOT)) if not dry_run else "(dry)"

    # Rotacion
    rotated = rotate_backups(RETENTION_N, dry_run)
    summary["backup_rotated"] = rotated

    # Rotacion logs pipeline (2026-05-07): _logs/pipeline_davivienda_*.json
    # crecian sin limite (51 archivos en 30 dias pre-rotation).
    rotated_logs = rotate_pipeline_logs(RETENTION_PIPELINE_LOGS_DAYS, dry_run)
    summary["pipeline_logs_rotated"] = rotated_logs

    # Paso 2 — Diff
    # STEP 7 "memoria operativa" eliminado 2026-05-07 (era workaround Cowork).
    findings = {
        "missing": check_required_paths(),
        "hubspot": check_hubspot_token(),
        "forbidden": scan_forbidden_patterns(),
        "drift": check_doc_code_drift(),  # STEP 8 (2026-05-07)
    }
    summary["anom_missing"] = len(findings["missing"])
    summary["anom_hubspot"] = 1 if findings["hubspot"] else 0
    summary["anom_forbidden"] = len(findings["forbidden"])
    summary["anom_drift"] = len(findings["drift"])

    # Paso 3 — Reporte
    rpt = write_anomaly_report(findings, ts)
    summary["report"] = str(rpt.relative_to(PROJECT_ROOT)) if rpt else "none"

    # Paso 4 — Limpieza
    if not args.no_clean:
        whitelist = load_whitelist()
        moved = clean_root(whitelist, dry_run)
        summary["moved"] = len(moved)
        for src, dst in moved:
            prefix = "WOULD MOVE" if dry_run else "MOVED"
            log_line(
                f"{prefix} {src.relative_to(PROJECT_ROOT)} -> "
                f"{dst.relative_to(PROJECT_ROOT)}"
            )
    else:
        summary["moved"] = 0

    # Paso 5 — Log summary
    log_line(
        f"CYCLE mode={summary['mode']} backup={summary['backup_copied']}/"
        f"rotated={summary['backup_rotated']} pipeline_logs_rotated={summary['pipeline_logs_rotated']} "
        f"anom_missing={summary['anom_missing']} anom_hubspot={summary['anom_hubspot']} "
        f"anom_forbidden={summary['anom_forbidden']} anom_drift={summary['anom_drift']} "
        f"moved={summary['moved']} report={summary['report']}"
    )

    # stdout para humano
    print(f"== mantenimiento 12h [{mode}] ==")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

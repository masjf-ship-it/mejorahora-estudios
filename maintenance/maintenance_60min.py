# -*- coding: utf-8 -*-
"""
maintenance_60min.py — Ciclo de mantenimiento horario MejorAhora Estudios.

Ejecuta cada 60 min (via Windows Task Scheduler) y al inicio/cierre de sesion.

Operaciones (ver MASTER_RULES.md §18):
  1. Backup   — copia lista blanca a _backups/<ts>/
  2. Diff     — verifica consistencia entre docs canonicos
  3. Reporte  — _logs/anomalies_<ts>.txt si hay hallazgos
  4. Limpieza — mueve archivos sueltos en raiz NO whitelisted a _archivo/YYYY-MM/
  5. Log      — append a _logs/mant.log

Uso:
  python maintenance_60min.py              # --apply (default)
  python maintenance_60min.py --dry-run    # reporta sin mover/borrar
  python maintenance_60min.py --quick      # solo log heartbeat, no backup

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

# Retencion: 1 semana a 1 corrida/hora = 24*7 (Jose 2026-04-25 política limpia)
# Reducido desde 336 (~2 semanas) tras revocar política acumulativa.
RETENTION_N = 168

# Backup — lista de patrones (relativos a PROJECT_ROOT) a snapshotear
BACKUP_TARGETS = [
    "MASTER_RULES.md",
    "SOURCE_OF_TRUTH.md",
    "ESTADO_PROYECTO.md",
    "MANUAL_EXTRACTO_BANCOS.md",
    "PROMPT_DEFINITIVO_AGENTE.md",
    "PESOS.xlsx",
    "CRM.xlsx",
    "BD.xlsx",
    "tips_de_banco.csv",
    "run_pipeline.bat",
    "sprint_1/*.py",
    "sprint_1/config.ini",  # cuidado: contiene token — ver §17
    "sprint_1/bank_rules/*.md",
    "automation/apps_script/*.gs",
    "bank_rules/*.md",
    "maintenance/*.py",
    "maintenance/*.bat",
    "maintenance/*.cmd",
    "maintenance/whitelist.txt",
    "maintenance/README.md",
]

# Rutas que se verifican existan (para el diff / anomalias)
REQUIRED_PATHS = [
    PROJECT_ROOT / "MASTER_RULES.md",
    PROJECT_ROOT / "SOURCE_OF_TRUTH.md",
    PROJECT_ROOT / "sprint_1" / "config.ini",
    PROJECT_ROOT / "sprint_1" / "hubspot_client.py",
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
    )
    if not has_issues:
        return None
    path = LOGS_DIR / f"anomalies_{ts}.txt"
    lines = [
        f"# Anomalias — {now_iso()}",
        f"# Generado por maintenance_60min.py",
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
    mem = findings.get("memory") or {}
    if mem.get("has_issues"):
        lines.append("## Memoria operativa del agente (STEP 7, 2026-04-23)")
        lines.append(f"  - path: {mem.get('path', '(no encontrada)')}")
        lines.append(f"  - pointers en MEMORY.md: {mem.get('pointers', 0)}")
        if mem.get("broken"):
            lines.append("  - POINTERS ROTOS (archivo no existe):")
            for b in mem["broken"]:
                lines.append(f"      * {b}")
        if mem.get("orphans"):
            lines.append("  - ARCHIVOS HUERFANOS (.md sin pointer en MEMORY.md):")
            for o in mem["orphans"]:
                lines.append(f"      * {o}")
        if mem.get("stale_project"):
            lines.append("  - PROJECT MEMORIES STALE (>90 dias sin modificar):")
            for name, fecha in mem["stale_project"]:
                lines.append(f"      * {name}  (ult. mod {fecha})")
        if mem.get("changelog_stale"):
            lines.append(f"  - CHANGELOG.md sin entradas nuevas (ult. mod {mem.get('changelog_last')})")
        lines.append("  NOTA: reporte solamente. Respeta politica 'nada se borra'"
                     " (feedback_memoria_acumulativa_total).")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# -----------------------------------------------------------------------------
# Paso 7 — Memoria operativa del agente (2026-04-23)
# -----------------------------------------------------------------------------
def find_memory_dir() -> Path | None:
    """Localiza el directorio de memoria del agente Claude.

    Precedencia:
      1. env MEJORAHORA_MEMORY_DIR
      2. archivo `maintenance/memory_dir.txt` (una linea con la ruta)
      3. busqueda recursiva en %APPDATA%\\Claude\\local-agent-mode-sessions
    Retorna None si no se encuentra.
    """
    # 1) env var override
    override = os.environ.get("MEJORAHORA_MEMORY_DIR", "").strip()
    if override:
        p = Path(override)
        if (p / "MEMORY.md").exists():
            return p
    # 2) archivo config persistente
    cfg_file = HERE / "memory_dir.txt"
    if cfg_file.exists():
        try:
            raw = cfg_file.read_text(encoding="utf-8-sig")  # -sig tolera BOM
            # Tomar primera linea no vacia, por si hay comentarios/blank lines
            for line in raw.splitlines():
                ruta = line.strip().strip('"').strip("'")
                if not ruta or ruta.startswith("#"):
                    continue
                p = Path(ruta)
                if (p / "MEMORY.md").exists():
                    return p
                break
        except Exception:
            pass
    # 3) busqueda automatica en multiples ubicaciones
    #    Claude Desktop (MSI) usa APPDATA\Claude
    #    Claude for Windows Store sandboxa en
    #      LOCALAPPDATA\Packages\Claude_*\LocalCache\Roaming\Claude
    candidates = []
    for env_var in ("APPDATA", "LOCALAPPDATA"):
        base = os.environ.get(env_var, "")
        if not base:
            continue
        for subdir in ("Claude", "AnthropicClaude", "Anthropic"):
            p = Path(base) / subdir
            if p.exists():
                candidates.append(p)
    # Windows Store sandbox
    localapp = os.environ.get("LOCALAPPDATA", "")
    if localapp:
        packages = Path(localapp) / "Packages"
        if packages.exists():
            for pkg in packages.glob("Claude_*"):
                candidates.append(pkg)
    for base_path in candidates:
        try:
            for mem_file in base_path.rglob("MEMORY.md"):
                return mem_file.parent
        except Exception:
            continue
    return None


def check_memory_health() -> dict:
    """Audita la memoria del agente. Solo reporta — no borra nada.

    Respeta feedback_memoria_acumulativa_total.md (nada se borra).
    """
    import re as _re
    out = {
        "available": False,
        "path": None,
        "pointers": 0,
        "broken": [],
        "orphans": [],
        "stale_project": [],
        "changelog_last": None,
        "changelog_stale": False,
        "has_issues": False,
    }
    memdir = find_memory_dir()
    if memdir is None:
        return out
    out["available"] = True
    out["path"] = str(memdir)

    mpath = memdir / "MEMORY.md"
    try:
        lines = mpath.read_text(encoding="utf-8").splitlines()
    except Exception:
        return out

    # Extraer referencias tipo [Title](file.md)
    pointer_re = _re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)')
    referenced = set()
    for line in lines:
        m = pointer_re.search(line)
        if m:
            out["pointers"] += 1
            target = m.group(2).strip()
            referenced.add(target)
            target_path = memdir / target
            if not target_path.exists():
                out["broken"].append(target)

    # Huerfanos: .md presentes sin pointer
    reserved = {"MEMORY.md"}
    for mdfile in memdir.glob("*.md"):
        if mdfile.name in reserved:
            continue
        if mdfile.name not in referenced:
            out["orphans"].append(mdfile.name)

    # Stale project memories: project_*.md sin modificar >90 dias
    umbral = dt.datetime.now() - dt.timedelta(days=90)
    for mdfile in memdir.glob("project_*.md"):
        try:
            mtime = dt.datetime.fromtimestamp(mdfile.stat().st_mtime)
            if mtime < umbral:
                out["stale_project"].append((mdfile.name, mtime.strftime("%Y-%m-%d")))
        except Exception:
            continue

    # CHANGELOG.md: alertar si no hay actividad >7 dias
    clog = memdir / "CHANGELOG.md"
    if clog.exists():
        try:
            mtime = dt.datetime.fromtimestamp(clog.stat().st_mtime)
            out["changelog_last"] = mtime.strftime("%Y-%m-%d %H:%M")
            if mtime < dt.datetime.now() - dt.timedelta(days=7):
                out["changelog_stale"] = True
        except Exception:
            pass

    out["has_issues"] = bool(
        out["broken"] or out["orphans"] or out["stale_project"] or out["changelog_stale"]
    )
    return out


# -----------------------------------------------------------------------------
# Paso 4 — Limpieza raiz
# -----------------------------------------------------------------------------
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
    ap = argparse.ArgumentParser(description="Mantenimiento 60min MejorAhora")
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

    # Paso 2 — Diff
    findings = {
        "missing": check_required_paths(),
        "hubspot": check_hubspot_token(),
        "forbidden": scan_forbidden_patterns(),
        "memory": check_memory_health(),  # STEP 7 (2026-04-23)
    }
    summary["anom_missing"] = len(findings["missing"])
    summary["anom_hubspot"] = 1 if findings["hubspot"] else 0
    summary["anom_forbidden"] = len(findings["forbidden"])
    mem = findings["memory"]
    summary["mem_available"] = mem["available"]
    summary["mem_pointers"] = mem["pointers"]
    summary["mem_broken"] = len(mem["broken"])
    summary["mem_orphans"] = len(mem["orphans"])
    summary["mem_stale"] = len(mem["stale_project"])

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
        f"rotated={summary['backup_rotated']} anom_missing={summary['anom_missing']} "
        f"anom_hubspot={summary['anom_hubspot']} "
        f"anom_forbidden={summary['anom_forbidden']} moved={summary['moved']} "
        f"mem_avail={summary['mem_available']} mem_ptrs={summary['mem_pointers']} "
        f"mem_broken={summary['mem_broken']} mem_orphans={summary['mem_orphans']} "
        f"mem_stale={summary['mem_stale']} report={summary['report']}"
    )

    # stdout para humano
    print(f"== mantenimiento 60min [{mode}] ==")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

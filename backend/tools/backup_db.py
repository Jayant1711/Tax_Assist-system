# Summer internship project
"""Tax Assist backup tooling (Sprint 3 Wave F — docs/backup-recovery.md).

Pure-stdlib helpers backing the two artifacts the production stack owns:

1. the SQLite store (``TAX_DB_PATH`` — users, auth sessions, app
   sessions), and
2. the append-only JSONL streams under ``logs/`` (the global audit
   stream ``logs/audit/session_audit.jsonl``, the per-session blackbox
   streams ``logs/blackbox/<sid>.jsonl``, and the app log
   ``logs/app/app.jsonl`` — all share the audit_logger rotation
   mechanics).

Runbook (summary — the authoritative version is docs/backup-recovery.md):

- HOT BACKUP (preferred, app keeps running; one-worker + WAL gives a
  consistent snapshot)::

      cd backend
      python tools/backup_db.py --out-dir /backups

  ``backup_database`` uses the sqlite3 online backup API (the ``.backup``
  command's library form; ``VACUUM INTO`` would work too but the backup
  API also copies the WAL-consistent state without a full rewrite). The
  copy is written to a temp file, verified with ``PRAGMA
  integrity_check``, then atomically renamed to a timestamped ``.bak``.

- STREAM COPIES: never copy only the active JSONL file — rotation
  maintains generations ``.N ... .2 .1`` plus the active stream, and
  concatenating them in that order replays every line in write order.
  ``copy_jsonl_streams`` copies each stream family in exactly that
  order, and ``scan_jsonl_integrity`` line-scans a copy to count corrupt
  lines before you trust it.

- RETENTION INTERPLAY: ``TAX_AUDIT_RETENTION_DAYS`` (and the app-log
  twin ``TAX_APP_LOG_RETENTION_DAYS``) sweep only ROTATED generations of
  the LIVE streams — the active file is never deleted by the app. Old
  backups are untouched by any of these settings: the backup directory
  IS the long-term archive, apply your own retention there.

- RECOVERY (full runbook in docs/backup-recovery.md): stop the backend
  -> restore the DB file (and delete any stale ``-wal``/``-shm`` of the
  dead database) + the log streams -> start -> verify ``GET /health``
  reports ok -> line-scan the restored streams
  (``scan_jsonl_integrity``) -> append an incident record to the audit
  stream.

CLI::

    python tools/backup_db.py --out-dir /backups [--db-path PATH]
                              [--log-dir PATH] [--skip-db] [--skip-streams]

Prints one JSON summary line on success; exits non-zero on failure.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Make the backend package modules importable no matter the caller's cwd
# (script lives in backend/tools/).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_DB_PATH = "data/taxassist.db"
DEFAULT_LOG_DIR = "logs"

# JSONL stream families under the log dir, as <relative dir>, <glob>.
STREAM_FAMILIES = (("audit", "session_audit.jsonl*"), ("blackbox", "*.jsonl"), ("app", "app.jsonl*"))


# ---------------------------------------------------------------------------
# SQLite backup (online .backup API; VACUUM INTO noted in the docstring)
# ---------------------------------------------------------------------------


def _timestamp() -> str:
    """UTC timestamp for backup file names (sortable, filesystem-safe).

    Microsecond precision: two backups of the same source within the same
    second must never collide (the atomic rename would otherwise silently
    overwrite the first one).
    """
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def backup_database(db_path: str, output_dir: str) -> str:
    """Consistent online backup of *db_path* into *output_dir*.

    Opens the source with the sqlite3 online backup API (page-consistent
    snapshot; safe against a single concurrent writer under WAL) and
    streams it into ``<stem>.<UTC timestamp>.bak`` inside *output_dir*.
    The copy is created as ``.bak.tmp`` first, verified with ``PRAGMA
    integrity_check``, then atomically renamed — a failed run never
    leaves a plausible-looking corrupt ``.bak`` behind (the ``.tmp`` is
    removed on ANY failure).

    Returns the final backup path. Raises FileNotFoundError when the
    source does not exist, RuntimeError on an integrity-check failure,
    and sqlite3.Error for unreadable/corrupt sources.
    """
    src_path = Path(db_path)
    if not src_path.is_file():
        raise FileNotFoundError(f"database not found: {db_path}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / f"{src_path.stem}.{_timestamp()}.bak"
    tmp_path = out_dir / (final_path.name + ".tmp")

    try:
        source = sqlite3.connect(str(src_path))
        try:
            destination = sqlite3.connect(str(tmp_path))
            try:
                source.backup(destination)
                # Trust, then verify: an integrity failure aborts the rename.
                row = destination.execute("PRAGMA integrity_check").fetchone()
                result = row[0] if row else "missing"
                if result != "ok":
                    raise RuntimeError(
                        f"backup failed integrity_check: {result} ({tmp_path})"
                    )
            finally:
                destination.close()
        finally:
            source.close()
        os.replace(tmp_path, final_path)
    except BaseException:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:  # pragma: no cover — best-effort cleanup
            pass
        raise
    return str(final_path)


# ---------------------------------------------------------------------------
# JSONL stream copies (rotation-aware ordering)
# ---------------------------------------------------------------------------


def _generation_number(path: Path, stream_name: str) -> Optional[int]:
    """Rotation generation N for ``<stream>.N``, or None for other files."""
    suffix = path.name[len(stream_name) + 1:]
    if not suffix.isdigit() or not path.name.startswith(stream_name + "."):
        return None
    return int(suffix)


def discover_stream_files(stream_path: str) -> List[Path]:
    """All files of one rotated stream family, in WRITE order.

    Rotation (audit_logger.AuditLogger._rotate_if_needed) shifts the
    active file to ``.1`` and older generations up, so concatenating
    ``.max ... .2 .1`` then the ACTIVE file replays every line in write
    order. Gaps are legal (a deferred rotation skips a slot); unknown
    sibling files are ignored. A missing stream/directory copies nothing.
    """
    stream = Path(stream_path)
    parent = stream.parent
    if not parent.is_dir():
        return []
    generations: List[Path] = []
    for candidate in parent.iterdir():
        if candidate.name == stream.name or not candidate.is_file():
            continue
        if _generation_number(candidate, stream.name) is not None:
            generations.append(candidate)
    generations.sort(key=lambda p: _generation_number(p, stream.name) or 0, reverse=True)
    ordered = generations + ([stream] if stream.exists() else [])
    return ordered


def copy_jsonl_stream(stream_path: str, output_dir: str) -> List[str]:
    """Copy one (possibly rotated) JSONL stream family in write order.

    Generation ``.N`` files keep their names; the active stream keeps its
    base name. Returns the copied paths in write order (oldest
    generation first, active stream last). A missing stream copies
    nothing (and returns []) — callers decide whether that is fatal.
    """
    ordered = discover_stream_files(stream_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    copied: List[str] = []
    for src in ordered:
        dest = out_dir / src.name
        shutil.copy2(src, dest)
        copied.append(str(dest))
    return copied


def copy_jsonl_streams(log_dir: str, output_dir: str) -> Dict[str, List[str]]:
    """Copy every JSONL stream family under *log_dir* into *output_dir*.

    Preserves the relative layout (audit/, blackbox/, app/) so a restored
    tree is byte-for-byte what the app expects. Glob matches that are
    rotation generations of a sibling stream (``<base>.<digits>``) are
    NOT separate families — each family is copied once, from its base
    stream, in full write order (generations first, active last).
    Per-session blackbox streams have no rotations (one file per session
    id; the sanitizer forbids dots) but share the same discipline.
    """
    log_root = Path(log_dir)
    manifest: Dict[str, List[str]] = {}
    for sub_dir, pattern in STREAM_FAMILIES:
        family_dir = log_root / sub_dir
        if not family_dir.is_dir():
            continue
        matches = sorted(family_dir.glob(pattern))
        names = {p.name for p in matches}
        bases = [
            p
            for p in matches
            if not any(
                other != p.name
                and p.name.startswith(other + ".")
                and p.name[len(other) + 1:].isdigit()
                for other in names
            )
        ]
        for base in bases:
            copied = copy_jsonl_stream(
                str(base), str(Path(output_dir) / sub_dir)
            )
            if copied:
                manifest.setdefault(f"{sub_dir}/{base.name}", []).extend(copied)
    return manifest


def scan_jsonl_integrity(path: str) -> Dict[str, int]:
    """Line-scan a JSONL stream: total, corrupt and well-formed counts.

    Read-only diagnostic used by the recovery runbook (a restored stream
    is trusted only after a scan reports its corrupt-line count). Same
    skip-with-count semantics as AuditLogger._scan_stream — the file is
    never modified.
    """
    total = 0
    corrupt = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            total += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                corrupt += 1
                continue
            if not isinstance(entry, dict):
                corrupt += 1
    return {"total_lines": total, "corrupt_lines": corrupt, "valid_lines": total - corrupt}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Back up the SQLite store and the JSONL log streams "
        "(docs/backup-recovery.md)."
    )
    parser.add_argument("--out-dir", required=True, help="backup output directory")
    parser.add_argument("--db-path", default=None, help="SQLite store path (default: TAX_DB_PATH or %s)" % DEFAULT_DB_PATH)
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR, help="log dir holding the JSONL streams (default: %(default)s)")
    parser.add_argument("--skip-db", action="store_true", help="skip the SQLite backup")
    parser.add_argument("--skip-streams", action="store_true", help="skip the JSONL stream copies")
    args = parser.parse_args(argv)

    if args.db_path:
        db_path = args.db_path
    else:
        try:
            import config  # backend module: keeps the CLI in sync with the app

            db_path = config.tax_db_path()
        except Exception:
            db_path = DEFAULT_DB_PATH

    summary: Dict[str, object] = {"timestamp": _timestamp()}
    try:
        if not args.skip_db:
            backup_file = backup_database(db_path, args.out_dir)
            summary["database_backup"] = backup_file
            size = os.path.getsize(backup_file)
            summary["database_backup_bytes"] = size
        if not args.skip_streams:
            summary["streams"] = copy_jsonl_streams(args.log_dir, args.out_dir)
    except (OSError, sqlite3.Error, RuntimeError, FileNotFoundError) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}))
        return 1

    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

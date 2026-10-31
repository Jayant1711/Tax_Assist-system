#!/usr/bin/env python3
"""Offline migration: legacy read-modify-write audit JSON -> append-only JSONL.

Sprint 2 Step F (ADR-009 / H6). This tool is committed but NOT run on the
real logs in this step; the local ``backend/logs/`` tree stays as-is until
an operator chooses to migrate.

RUNBOOK (offline, one-shot; never in the request path; stop the backend
first so nothing appends while the migration runs):

    cd backend
    python tests\\tools\\migrate_audit_to_jsonl.py --logs-dir logs --dry-run
    python tests\\tools\\migrate_audit_to_jsonl.py --logs-dir logs
    # verify the printed parity lines, then (optionally) archive the legacy
    # sources out of the way — the tool never deletes them:
    #   move logs\\session_audit.json logs\\archive\\
    #   move logs\\blackbox\\*.json logs\\archive\\
    # restart the backend; new turns append to the .jsonl streams.

Behavior
--------
- Global trail: ``logs/session_audit.json`` (a JSON array of entries) is
  rewritten as ``logs/audit/session_audit.jsonl`` — ONE line per entry,
  each line tagged ``"migrated": true``, original timestamps and content
  preserved verbatim (the legacy trail predates write-time PII
  minimization; minimizing here would rewrite history).
- Per-session blackbox: ``logs/blackbox/<sid>.json`` (``{"turns": [...]}``)
  becomes ``logs/blackbox/<sid>.jsonl`` — one line per turn, tagged
  ``"migrated": true``.
- Entry-count parity is verified before anything is published; the tool
  prints ``N -> M`` and exits non-zero (removing the partial output) on a
  mismatch.
- An existing ``.jsonl`` target is NEVER rewritten: append-only files are
  skipped with a message.
- A corrupt/unexpected source is archived WHOLE to
  ``logs/archive/<name>.corrupt-<timestamp>.json`` and the JSONL target
  starts fresh (not created here); the corrupt source is never modified.
- The tool is stdlib-only and reads nothing but the paths under --logs-dir.

Exit codes: 0 = nothing to do or all migrations verified; 1 = parity or
I/O failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

MIGRATED_FLAG = "migrated"
GLOBAL_SOURCE = os.path.join("session_audit.json")
GLOBAL_TARGET = os.path.join("audit", "session_audit.jsonl")
BLACKBOX_DIR = "blackbox"
ARCHIVE_DIR = os.path.join("archive")


def _read_json(path: str) -> Tuple[Optional[Any], Optional[str]]:
    """Load JSON, returning (data, None) or (None, error-description)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _archive_whole(source: str, logs_dir: str) -> str:
    """Copy the corrupt source file whole into logs/archive/ (never modified)."""
    archive_dir = os.path.join(logs_dir, ARCHIVE_DIR)
    os.makedirs(archive_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.basename(source)
    target = os.path.join(archive_dir, f"{base}.corrupt-{stamp}.json")
    with open(source, "rb") as src:
        payload = src.read()
    with open(target, "wb") as dst:
        dst.write(payload)
    return target


def _write_jsonl_atomic(target: str, lines: List[str]) -> None:
    """Write all lines to a temp file, then atomically put it in place.

    The tool creates the target exactly once (it never appends to or
    rewrites an existing stream — that discipline belongs to the logger).
    """
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".migrating"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for line in lines:
            fh.write(line + "\n")
    if os.path.exists(target):  # race guard: never rewrite a live stream
        os.remove(tmp)
        raise RuntimeError(f"target appeared during migration: {target}")
    os.replace(tmp, target)


def _migrate_global(logs_dir: str, dry_run: bool) -> int:
    source = os.path.join(logs_dir, GLOBAL_SOURCE)
    target = os.path.join(logs_dir, GLOBAL_TARGET)
    if not os.path.exists(source):
        print(f"session_audit: no legacy file at {source} — nothing to do")
        return 0
    if os.path.exists(target):
        print(f"session_audit: target {target} already exists — skipped (never rewritten)")
        return 0
    data, error = _read_json(source)
    if error or not isinstance(data, list):
        if dry_run:
            print(
                f"session_audit: corrupt source ({error or 'not a JSON array'}) — "
                "would archive whole to logs/archive/; JSONL starts fresh"
            )
            return 0
        archived = _archive_whole(source, logs_dir)
        print(
            f"session_audit: corrupt source ({error or 'not a JSON array'}) — "
            f"archived whole to {archived}; JSONL starts fresh"
        )
        return 0
    lines = [
        json.dumps({**entry, MIGRATED_FLAG: True}, ensure_ascii=False)
        if isinstance(entry, dict)
        else json.dumps({"legacy_entry": entry, MIGRATED_FLAG: True}, ensure_ascii=False)
        for entry in data
    ]
    print(f"session_audit: {len(data)} -> {len(lines)} entries" + (" (dry run)" if dry_run else ""))
    if dry_run:
        return 0
    if len(lines) != len(data):
        print("session_audit: parity check FAILED — no output written")
        return 1
    _write_jsonl_atomic(target, lines)
    print(f"session_audit: wrote {target} (parity OK)")
    return 0


def _migrate_blackbox_file(source: str, logs_dir: str, dry_run: bool) -> int:
    target = source[: -len(".json")] + ".jsonl"
    if os.path.exists(target):
        print(f"blackbox {os.path.basename(source)}: target already exists — skipped")
        return 0
    data, error = _read_json(source)
    if error or not isinstance(data, dict) or not isinstance(data.get("turns"), list):
        if dry_run:
            print(
                f"blackbox {os.path.basename(source)}: corrupt source "
                f"({error or 'no turns[]'}) — would archive whole to logs/archive/"
            )
            return 0
        archived = _archive_whole(source, logs_dir)
        print(
            f"blackbox {os.path.basename(source)}: corrupt source "
            f"({error or 'no turns[]'}) — archived whole to {archived}"
        )
        return 0
    turns = data["turns"]
    lines = [
        json.dumps({**turn, MIGRATED_FLAG: True}, ensure_ascii=False)
        if isinstance(turn, dict)
        else json.dumps({"legacy_turn": turn, MIGRATED_FLAG: True}, ensure_ascii=False)
        for turn in turns
    ]
    print(
        f"blackbox {os.path.basename(source)}: {len(turns)} -> {len(lines)} turns"
        + (" (dry run)" if dry_run else "")
    )
    if dry_run:
        return 0
    if len(lines) != len(turns):
        print(f"blackbox {os.path.basename(source)}: parity check FAILED — no output written")
        return 1
    _write_jsonl_atomic(target, lines)
    print(f"blackbox {os.path.basename(source)}: wrote {target} (parity OK)")
    return 0


def _migrate_blackbox(logs_dir: str, dry_run: bool) -> int:
    blackbox_dir = os.path.join(logs_dir, BLACKBOX_DIR)
    if not os.path.isdir(blackbox_dir):
        print(f"blackbox: no directory at {blackbox_dir} — nothing to do")
        return 0
    failures = 0
    for name in sorted(os.listdir(blackbox_dir)):
        if not name.endswith(".json"):
            continue
        failures += _migrate_blackbox_file(os.path.join(blackbox_dir, name), logs_dir, dry_run)
    if failures == 0:
        print("blackbox: all per-session files processed")
    return failures


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate legacy audit JSON to append-only JSONL (offline)."
    )
    parser.add_argument(
        "--logs-dir",
        default="logs",
        help="backend logs directory (default: logs; run from backend/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print counts without writing anything",
    )
    args = parser.parse_args(argv)

    if not os.path.isdir(args.logs_dir):
        print(f"logs directory not found: {args.logs_dir}")
        return 1
    print(f"migration target: {args.logs_dir}" + (" (dry run)" if args.dry_run else ""))
    rc = _migrate_global(args.logs_dir, args.dry_run)
    rc |= _migrate_blackbox(args.logs_dir, args.dry_run)
    if rc == 0:
        print("migration complete")
    else:
        print("migration FAILED (see messages above); nothing partial was published")
    return rc


if __name__ == "__main__":
    sys.exit(main())

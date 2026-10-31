"""Sprint 3 Wave F backup tool tests — backup_db.py contract.

Covers the docs/backup-recovery.md tool: online SQLite backup (verified
copy: integrity_check ok, content identical), rotation-aware JSONL
stream copies (generation order preserved, nothing lost), and the
integrity line-scan. Pure stdlib, tmp-path isolated, no app state.
"""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.backup_db import (  # noqa: E402
    backup_database,
    copy_jsonl_stream,
    copy_jsonl_streams,
    discover_stream_files,
    scan_jsonl_integrity,
)


def _make_source_db(path) -> None:
    con = sqlite3.connect(str(path))
    try:
        con.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT)")
        con.executemany(
            "INSERT INTO probe (value) VALUES (?)", [(f"row-{i}",) for i in range(25)]
        )
        con.commit()
    finally:
        con.close()


class TestSqliteBackup:
    def test_backup_is_a_verified_consistent_copy(self, tmp_path) -> None:
        source = tmp_path / "taxassist.db"
        _make_source_db(source)
        out_dir = tmp_path / "backups"

        backup_file = backup_database(str(source), str(out_dir))

        assert os.path.isfile(backup_file)
        assert backup_file.endswith(".bak")
        # Verified: the copy opens, answers integrity_check and holds the rows.
        con = sqlite3.connect(backup_file)
        try:
            assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            count = con.execute("SELECT COUNT(*) FROM probe").fetchone()[0]
        finally:
            con.close()
        assert count == 25

    def test_backup_names_are_timestamped_and_non_colliding(self, tmp_path) -> None:
        source = tmp_path / "taxassist.db"
        _make_source_db(source)
        first = backup_database(str(source), str(tmp_path))
        # No monkeypatching of the clock — the temp-file rename discipline
        # means a second run within the same second still cannot clobber
        # the first backup: distinct files, both valid.
        second = backup_database(str(source), str(tmp_path))
        assert first != second
        assert os.path.isfile(first) and os.path.isfile(second)

    def test_missing_source_raises_file_not_found(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            backup_database(str(tmp_path / "nope.db"), str(tmp_path / "out"))

    def test_corrupt_source_does_not_produce_a_plausible_bak(self, tmp_path) -> None:
        bad = tmp_path / "corrupt.db"
        bad.write_bytes(b"this is not a sqlite database" * 100)
        # A non-sqlite file fails at the backup read (sqlite3.DatabaseError);
        # a truncated-but-headered file would fail the integrity check
        # (RuntimeError). Either way nothing plausible may survive.
        with pytest.raises((RuntimeError, sqlite3.DatabaseError, sqlite3.Error)):
            backup_database(str(bad), str(tmp_path / "out"))
        out_dir = tmp_path / "out"
        assert out_dir.is_dir()
        assert list(out_dir.iterdir()) == [], "failed run must clean up (no .tmp litter)"


class TestStreamCopies:
    def _write_stream(self, root, name, generations, active_lines):
        audit_dir = root / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        # Generations written newest-arrival LAST in file order (.N oldest).
        for n, lines in sorted(generations.items()):
            (audit_dir / f"{name}.{n}").write_text(
                "".join(json.dumps({"gen": n, "i": i}) + "\n" for i, line in enumerate(lines)),
                encoding="utf-8",
            )
        (audit_dir / name).write_text(
            "".join(json.dumps({"gen": "active", "i": i}) + "\n" for i in range(active_lines)),
            encoding="utf-8",
        )

    def test_discovery_orders_oldest_generation_to_active(self, tmp_path) -> None:
        self._write_stream(tmp_path, "session_audit.jsonl", {1: ["a"], 3: ["b"], 5: ["c"]}, 2)
        ordered = discover_stream_files(str(tmp_path / "audit" / "session_audit.jsonl"))
        names = [os.path.basename(p) for p in ordered]
        # Write order: .5 (oldest) ... .1, then the ACTIVE stream. Gaps are
        # legal (deferred rotations) and skipped slots are simply absent.
        assert names == [
            "session_audit.jsonl.5",
            "session_audit.jsonl.3",
            "session_audit.jsonl.1",
            "session_audit.jsonl",
        ]

    def test_copy_replays_every_line_in_write_order(self, tmp_path) -> None:
        log_dir = tmp_path / "logs"
        self._write_stream(log_dir, "session_audit.jsonl", {1: ["a"], 2: ["b"]}, 3)
        out_dir = tmp_path / "backup"

        copied = copy_jsonl_stream(str(log_dir / "audit" / "session_audit.jsonl"), str(out_dir))

        assert [os.path.basename(p) for p in copied] == [
            "session_audit.jsonl.2",
            "session_audit.jsonl.1",
            "session_audit.jsonl",
        ]
        replay = []
        for path in copied:
            with open(path, "r", encoding="utf-8") as fh:
                replay.extend(json.loads(line)["gen"] for line in fh if line.strip())
        # .2 (oldest) first, then .1, then the active stream — exactly the
        # order concatenating them replays write order.
        assert replay == [2, 1, "active", "active", "active"]

    def test_missing_stream_copies_nothing(self, tmp_path) -> None:
        assert copy_jsonl_stream(str(tmp_path / "audit" / "ghost.jsonl"), str(tmp_path / "out")) == []

    def test_copy_jsonl_streams_covers_audit_blackbox_and_app(self, tmp_path) -> None:
        log_dir = tmp_path / "logs"
        self._write_stream(log_dir, "session_audit.jsonl", {1: ["a"]}, 1)
        blackbox = log_dir / "blackbox"
        blackbox.mkdir(parents=True)
        (blackbox / "abc12345.jsonl").write_text(
            json.dumps({"turn": 1}) + "\n", encoding="utf-8"
        )
        app_dir = log_dir / "app"
        app_dir.mkdir(parents=True)
        (app_dir / "app.jsonl").write_text(
            json.dumps({"message": "hi"}) + "\n", encoding="utf-8"
        )

        manifest = copy_jsonl_streams(str(log_dir), str(tmp_path / "backup"))

        assert set(manifest) == {
            "audit/session_audit.jsonl",
            "blackbox/abc12345.jsonl",
            "app/app.jsonl",
        }
        backup_root = tmp_path / "backup"
        assert (backup_root / "blackbox" / "abc12345.jsonl").is_file()
        assert (backup_root / "app" / "app.jsonl").is_file()
        assert (backup_root / "audit" / "session_audit.jsonl.1").is_file()


class TestIntegrityScan:
    def test_counts_corrupt_and_valid_lines_without_modifying(self, tmp_path) -> None:
        stream = tmp_path / "stream.jsonl"
        stream.write_text(
            json.dumps({"ok": 1}) + "\n"
            + "not json at all\n"
            + json.dumps({"ok": 2}) + "\n"
            + "\n"  # blank lines are not counted
            + "[1, 2, 3]\n",  # valid JSON, not an object -> corrupt
            encoding="utf-8",
        )
        before = stream.read_bytes()

        report = scan_jsonl_integrity(str(stream))

        assert report == {"total_lines": 4, "corrupt_lines": 2, "valid_lines": 2}
        assert stream.read_bytes() == before  # read-only scan

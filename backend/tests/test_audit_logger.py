"""Sprint 2 Step F — append-only JSONL audit infrastructure (test spec).

Every test runs against a temporary log_dir; the real backend/logs tree is
never touched (the /history tests monkeypatch main.audit onto a tmp dir).

Covers (design doc Step F + ADR-009/H6):
- concurrent appends: 16 threads x 25 writes -> exactly 400 whole,
  valid, distinct JSON lines (one os.write per line under a lock);
- corrupt-line recovery: existing bytes stay byte-identical, the reader
  skips malformed lines with a counted warning;
- read immutability: read_entries never modifies the file (hash check);
- never-truncate: a corrupt active stream only ever grows;
- rotation: TAX_AUDIT_MAX_BYTES generations, concatenation = zero loss,
  TAX_AUDIT_MAX_FILES cap drops only the oldest;
- retention: expired rotated generations swept, active never deleted,
  invalid env ints fall back to documented defaults;
- serialization failure: minimal redacted record, caller unaffected;
- PII minimization at write + TAX_AUDIT_STORE_TEXT opt-in (512 cap);
- safe_session_id path safety for hostile ids;
- /history: gate 404 default, sid filter, pagination (limit<=200,
  offset), corrupt_lines_skipped surfaced, legacy session_audit.json
  read-only fallback, never serves blackbox content.
"""
import hashlib
import json
import os
import re
import threading
import time

import pytest

from audit_logger import AuditLogger

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# "untrusted_" + 16 lowercase hex digest chars + .jsonl — path-safe by
# construction (no separators, no traversal sequences).
_UNTRUSTED_SID_RE = re.compile(r"^untrusted_[0-9a-f]{16}$")


def _make_logger(tmp_path, **kwargs) -> AuditLogger:
    return AuditLogger(log_dir=str(tmp_path), **kwargs)


def _stream_path(tmp_path) -> str:
    return os.path.join(str(tmp_path), "audit", "session_audit.jsonl")


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _seed_lines(path: str, *lines: str) -> bytes:
    """Write raw bytes to the stream as if a previous process had left them."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = "".join(line + "\n" for line in lines).encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(payload)
    return payload


def _good_seed_line(sid: str) -> str:
    return json.dumps(
        {"timestamp": "2026-01-01T00:00:00", "session_id": sid, "event": "seed"}
    )


# ---------------------------------------------------------------------------
# Concurrent append integrity
# ---------------------------------------------------------------------------


class TestConcurrentAppends:
    def test_16_threads_x_25_calls_yield_400_whole_lines(self, tmp_path) -> None:
        log = _make_logger(tmp_path)
        stream = _stream_path(tmp_path)
        failures = []

        def worker(t: int) -> None:
            try:
                for c in range(25):
                    log.log_interaction(
                        f"sid_t{t:02d}c{c:03d}",
                        "x" * (t * 25 + c + 1),  # unique char length per call
                        f"resp {t}-{c}",
                        {"salary": t * 1000 + c},
                    )
            except Exception as exc:  # recorded, never raised into the thread
                failures.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(16)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert failures == []
        raw = _read_bytes(stream)
        assert raw.endswith(b"\n")  # newline-terminated stream
        lines = raw.decode("utf-8").splitlines()
        assert len(lines) == 400
        parsed = [json.loads(line) for line in lines]  # every line whole JSON
        assert len(set(lines)) == 400                  # no interleaved/duplicate lines
        assert len({e["session_id"] for e in parsed}) == 400


# ---------------------------------------------------------------------------
# Corrupt-line recovery / read immutability / never-truncate
# ---------------------------------------------------------------------------


class TestAppendOnlyIntegrity:
    def test_corrupt_line_recovery_without_wipe(self, tmp_path) -> None:
        log = _make_logger(tmp_path)
        stream = _stream_path(tmp_path)
        before = _seed_lines(
            stream, _good_seed_line("sid_seed_a"), "{corrupt", _good_seed_line("sid_seed_b")
        )

        log.log_interaction("sid_after", "hello", "world", {"salary": 1})

        after = _read_bytes(stream)
        # Existing bytes byte-identical — the append never rewrote anything.
        assert after[: len(before)] == before
        entries, corrupt, has_more = log.read_entries()
        assert corrupt == 1
        assert has_more is False
        assert [e["session_id"] for e in entries] == [
            "sid_seed_a",
            "sid_seed_b",
            "sid_after",
        ]

    def test_read_entries_never_modifies_the_file(self, tmp_path) -> None:
        log = _make_logger(tmp_path)
        stream = _stream_path(tmp_path)
        _seed_lines(stream, _good_seed_line("sid_a"), "not json at all", _good_seed_line("sid_b"))
        before = hashlib.sha256(_read_bytes(stream)).hexdigest()

        for _ in range(3):
            entries, corrupt, _ = log.read_entries()
        entries, corrupt, _ = log.read_entries(limit=1)

        assert hashlib.sha256(_read_bytes(stream)).hexdigest() == before
        assert corrupt == 1
        assert len(entries) == 1

    def test_never_truncates_on_corrupt_active_stream(self, tmp_path) -> None:
        log = _make_logger(tmp_path)
        stream = _stream_path(tmp_path)
        # No trailing newline: a naive rewriter would lose everything; the
        # append-only writer must preserve these bytes exactly and keep going.
        before = _seed_lines(stream, "GARBAGE NOT JSON")[:-1]  # strip the \n

        for i in range(3):
            log.log_interaction(f"sid_grow_{i}", f"in {i}", f"out {i}", {"salary": i})

        after = _read_bytes(stream)
        assert after[: len(before)] == before          # corrupt prefix untouched
        assert len(after) > len(before)                # file only grew
        entries, corrupt, _ = log.read_entries()
        assert corrupt == 1
        assert [e["session_id"] for e in entries] == [
            "sid_grow_0",
            "sid_grow_1",
            "sid_grow_2",
        ]


# ---------------------------------------------------------------------------
# Rotation and retention
# ---------------------------------------------------------------------------


class TestRotation:
    def test_rotation_generations_zero_loss_in_order(self, tmp_path) -> None:
        log = _make_logger(tmp_path, max_bytes=400, max_files=12)
        total = 12
        for i in range(total):
            log.log_interaction("sid_rot", f"in {i}", f"out {i}", {"salary": i})

        audit_dir = os.path.join(str(tmp_path), "audit")
        base = os.path.join(audit_dir, "session_audit.jsonl")
        gens = [
            p
            for p in os.listdir(audit_dir)
            if re.fullmatch(r"session_audit\.jsonl\.\d+", p)
        ]
        assert gens, "rotation produced no archived generations"

        # Oldest generation first: .N ... .1, then the active stream.
        parts = sorted(
            (os.path.join(audit_dir, g) for g in gens),
            key=lambda p: int(p.rsplit(".", 1)[1]),
            reverse=True,
        )
        if os.path.exists(base):
            parts.append(base)
        lines = []
        for p in parts:
            with open(p, "r", encoding="utf-8") as fh:
                lines.extend(line for line in fh.read().splitlines() if line)

        assert len(lines) == total  # zero loss
        seq = [json.loads(line) for line in lines]
        assert [e["internal_state"]["salary"] for e in seq] == list(range(total))

    def test_max_files_cap_drops_only_the_oldest(self, tmp_path) -> None:
        log = _make_logger(tmp_path, max_bytes=400, max_files=2)
        total = 10
        for i in range(total):
            log.log_interaction("sid_cap", f"in {i}", f"out {i}", {"salary": i})

        audit_dir = os.path.join(str(tmp_path), "audit")
        names = set(os.listdir(audit_dir))
        assert names <= {
            "session_audit.jsonl",
            "session_audit.jsonl.1",
            "session_audit.jsonl.2",
        }
        parts = [
            os.path.join(audit_dir, n)
            for n in ("session_audit.jsonl.2", "session_audit.jsonl.1", "session_audit.jsonl")
            if n in names
        ]
        lines = []
        for p in parts:
            with open(p, "r", encoding="utf-8") as fh:
                lines.extend(line for line in fh.read().splitlines() if line)
        seq = [json.loads(line)["internal_state"]["salary"] for line in lines]
        # Survivors are a contiguous, ordered suffix of the written entries —
        # only whole oldest generations were dropped, nothing else was lost.
        start = seq[0]
        assert seq == list(range(start, total))
        assert start > 0  # the cap actually dropped generations


class TestRetention:
    def test_expired_rotated_generations_swept_active_survives(self, tmp_path) -> None:
        log = _make_logger(tmp_path, retention_days=30, max_files=5)
        log.log_interaction("sid_ret", "in", "out", {"salary": 1})  # active exists

        audit_dir = os.path.join(str(tmp_path), "audit")
        expired = os.path.join(audit_dir, "session_audit.jsonl.3")
        in_window = os.path.join(audit_dir, "session_audit.jsonl.2")
        for path, age_days in ((expired, 40), (in_window, 10)):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_good_seed_line("sid_gen") + "\n")
            past = time.time() - age_days * 86400
            os.utime(path, (past, past))

        # A fresh construction runs the retention sweep (as app start does).
        _make_logger(tmp_path, retention_days=30, max_files=5)

        assert not os.path.exists(expired)
        assert os.path.exists(in_window)
        active = os.path.join(audit_dir, "session_audit.jsonl")
        assert os.path.exists(active)  # the ACTIVE file is never deleted
        entries, _, _ = _make_logger(tmp_path, retention_days=30, max_files=5).read_entries()
        assert [e["session_id"] for e in entries] == ["sid_ret"]

    @pytest.mark.parametrize(
        ("env", "value", "attr", "default"),
        [
            ("TAX_AUDIT_MAX_BYTES", "not-an-int", "max_bytes", 10_000_000),
            ("TAX_AUDIT_MAX_BYTES", "-5", "max_bytes", 10_000_000),
            ("TAX_AUDIT_MAX_FILES", "abc", "max_files", 5),
            ("TAX_AUDIT_MAX_FILES", "0", "max_files", 5),
            ("TAX_AUDIT_RETENTION_DAYS", "thirty", "retention_days", 30),
            ("TAX_AUDIT_RETENTION_DAYS", "-1", "retention_days", 30),
        ],
    )
    def test_invalid_env_falls_back_to_documented_defaults(
        self, tmp_path, monkeypatch, env, value, attr, default
    ) -> None:
        monkeypatch.setenv(env, value)
        log = _make_logger(tmp_path)
        assert getattr(log, attr) == default


# ---------------------------------------------------------------------------
# Serialization failure and PII minimization
# ---------------------------------------------------------------------------


class TestSerializationFailure:
    def test_unserializable_field_writes_minimal_record(self, tmp_path) -> None:
        log = _make_logger(tmp_path)
        # object() cannot be JSON-serialized: the audit line must still land,
        # redacted, and the caller must be unaffected.
        log.log_interaction(
            "sid_boom", "in", "out", {"salary": 1, "unserializable": object()}
        )

        entries, corrupt, _ = log.read_entries()
        assert corrupt == 0
        assert len(entries) == 1
        record = entries[0]
        assert record["event"] == "serialization_failure"
        assert record["session_id"] == "sid_boom"
        assert set(record) == {"timestamp", "session_id", "event"}

    def test_stream_recovers_after_serialization_failure(self, tmp_path) -> None:
        log = _make_logger(tmp_path)
        log.log_interaction("sid_bad", "in", "out", {"bad": object()})
        log.log_interaction("sid_good", "in", "out", {"salary": 5})

        entries, corrupt, _ = log.read_entries()
        assert corrupt == 0
        assert [e["session_id"] for e in entries] == ["sid_bad", "sid_good"]
        assert entries[0]["event"] == "serialization_failure"
        assert entries[1]["event"] != "serialization_failure"


class TestPiiMinimization:
    def test_raw_text_dropped_correlation_hash_kept(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("TAX_AUDIT_STORE_TEXT", raising=False)
        log = _make_logger(tmp_path)
        text = "my salary is 50 lakhs and I keep cash at home"
        response = "Thanks! Now, what about your other income sources?"
        log.log_interaction(
            "sid_pii",
            text,
            response,
            {
                "salary": 5_000_000,
                "phase": "PROFILING",
                "history": [{"role": "user", "text": text}],
                "_last_val": 42,
                "_prev_salary": 7,
                "_last_question": "what is your salary?",
                "memory": {"k": "v"},
            },
            extracted=["SALARY: 5,000,000"],
            plan="Ask income details",
        )

        stream = _stream_path(tmp_path)
        raw = _read_bytes(stream)
        assert text.encode("utf-8") not in raw
        assert response.encode("utf-8") not in raw
        assert b"what is your salary?" not in raw

        (entry,) = log.read_entries()[0]
        assert entry["event"] == "chat_turn"
        assert entry["user_input"]["stored"] is False
        assert entry["user_input"]["sha256_16"] == hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()[:16]
        assert entry["user_input"]["char_length"] == len(text)
        assert entry["ai_response"]["char_length"] == len(response)
        assert entry["extracted"] == ["SALARY: 5,000,000"]
        assert entry["plan"] == "Ask income details"
        assert entry["internal_state"]["salary"] == 5_000_000
        assert entry["internal_state"]["phase"] == "PROFILING"
        for dropped in ("history", "_last_val", "_prev_salary", "_last_question", "memory"):
            assert dropped not in entry["internal_state"]

    def test_store_text_env_opt_in_truncates_to_512(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TAX_AUDIT_STORE_TEXT", "1")
        log = _make_logger(tmp_path)
        long_text = "word " * 200 + "END-MARKER"  # 1000+ chars
        log.log_interaction("sid_text", long_text, "ok", {"salary": 1})

        (entry,) = log.read_entries()[0]
        assert entry["user_input"]["stored"] is True
        assert entry["user_input"]["text"] == long_text[:512]
        assert entry["user_input"]["char_length"] == len(long_text)
        assert entry["user_input"]["sha256_16"] == hashlib.sha256(
            long_text.encode("utf-8")
        ).hexdigest()[:16]

    def test_tax_summary_compact_totals_kept(self, tmp_path) -> None:
        log = _make_logger(tmp_path)
        tax_results = {
            "tax_year": "2025-26",
            "assessment_year": "2026-27",
            "fy_label": "FY 2025-26 (AY 2026-27)",
            "recommendation": "Old regime is better",
            "savings": 1234.5,
            "efficiency_score": 72.1,
            "old_regime": {"total_tax": 100.0, "taxable_income": 900.0, "risk_level": "Low"},
        }
        log.log_interaction("sid_tax", "in", "out", {"salary": 1}, tax_results=tax_results)

        (entry,) = log.read_entries()[0]
        tax = entry["tax_calculation"]
        assert tax["tax_year"] == "2025-26"
        assert tax["assessment_year"] == "2026-27"
        assert tax["fy_label"] == "FY 2025-26 (AY 2026-27)"
        assert tax["old_regime"]["total_tax"] == 100.0
        assert tax["old_regime"]["taxable_income"] == 900.0
        assert tax["savings"] == 1234.5


# ---------------------------------------------------------------------------
# Path safety (adapted from test_session_security.py)
# ---------------------------------------------------------------------------


class TestAuditPathSafety:
    def test_hostile_session_id_stays_inside_log_dir(self, tmp_path) -> None:
        log = _make_logger(tmp_path)
        log.log_interaction("../evil", "hi", "hello", {"salary": 1})

        entries, _, _ = log.read_entries()
        assert len(entries) == 1
        sid = entries[0]["session_id"]
        assert _UNTRUSTED_SID_RE.match(sid), sid
        # Nothing written anywhere except the audit stream inside log_dir.
        assert os.listdir(str(tmp_path)) == ["audit"]
        assert os.listdir(os.path.join(str(tmp_path), "audit")) == [
            "session_audit.jsonl"
        ]

    def test_hostile_id_maps_stably_across_turns(self, tmp_path) -> None:
        log = _make_logger(tmp_path)
        log.log_interaction("../evil", "a", "b", {})
        log.log_interaction("../evil", "c", "d", {})
        entries, _, _ = log.read_entries()
        assert [e["session_id"] for e in entries] == [entries[0]["session_id"]] * 2
        assert _UNTRUSTED_SID_RE.match(entries[0]["session_id"])


# ---------------------------------------------------------------------------
# /history endpoint
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    previous_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    try:
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as test_client:
            yield test_client
    finally:
        os.chdir(previous_cwd)


@pytest.fixture
def fake_audit(tmp_path, monkeypatch):
    """Point main.audit at a tmp-dir logger so no real log file is touched."""
    import main as main_module

    logger = _make_logger(tmp_path)
    monkeypatch.setattr(main_module, "audit", logger)
    return logger


class TestHistoryEndpoint:
    def test_gate_stays_404_by_default(self, client, monkeypatch) -> None:
        monkeypatch.delenv("TAX_ENABLE_HISTORY", raising=False)
        response = client.get("/history/sid_hist1")
        assert response.status_code == 404

    def test_enabled_serves_jsonl_entries_filtered_by_sid(
        self, client, fake_audit, monkeypatch
    ) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "1")
        for i in range(3):
            fake_audit.log_interaction("sid_hist1", f"in {i}", f"out {i}", {"salary": i})
        fake_audit.log_interaction("sid_other", "other in", "other out", {})

        response = client.get("/history/sid_hist1")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"entries", "corrupt_lines_skipped", "has_more"}
        assert body["corrupt_lines_skipped"] == 0
        assert body["has_more"] is False
        assert [e["session_id"] for e in body["entries"]] == ["sid_hist1"] * 3
        # Same schema fields the frontend knows; free text minimized.
        entry = body["entries"][0]
        assert entry["user_input"]["char_length"] == len("in 0")
        assert entry["user_input"]["stored"] is False
        assert entry["internal_state"]["salary"] == 0

    def test_enabled_filters_hostile_sid_to_sanitized_name(
        self, client, fake_audit, monkeypatch
    ) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "1")
        fake_audit.log_interaction("../evil", "hi", "hello", {})
        entries, _, _ = fake_audit.read_entries()
        sanitized = entries[0]["session_id"]

        response = client.get(f"/history/{sanitized}")
        assert response.status_code == 200
        assert len(response.json()["entries"]) == 1

    def test_pagination_limit_offset_and_has_more(
        self, client, fake_audit, monkeypatch
    ) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "1")
        for i in range(5):
            fake_audit.log_interaction("sid_page", f"in {i}", f"out {i}", {"salary": i})

        page1 = client.get("/history/sid_page", params={"limit": 2, "offset": 0}).json()
        assert len(page1["entries"]) == 2
        assert page1["has_more"] is True
        assert [e["internal_state"]["salary"] for e in page1["entries"]] == [0, 1]

        page3 = client.get("/history/sid_page", params={"limit": 2, "offset": 4}).json()
        assert len(page3["entries"]) == 1
        assert page3["has_more"] is False
        assert page3["entries"][0]["internal_state"]["salary"] == 4

    @pytest.mark.parametrize(
        "params", [{"limit": 0}, {"limit": 201}, {"limit": "abc"}, {"offset": -1}]
    )
    def test_pagination_bounds_are_hard_422s(self, client, fake_audit, monkeypatch, params) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "1")
        response = client.get("/history/sid_page", params=params)
        assert response.status_code == 422

    def test_corrupt_lines_skipped_surfaced(self, client, fake_audit, monkeypatch) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "1")
        with open(fake_audit.log_file, "a", encoding="utf-8") as fh:
            fh.write("{broken line\n")
        fake_audit.log_interaction("sid_corrupt", "in", "out", {"salary": 1})
        fake_audit.log_interaction("sid_corrupt", "in2", "out2", {"salary": 2})

        response = client.get("/history/sid_corrupt")
        assert response.status_code == 200
        body = response.json()
        assert body["corrupt_lines_skipped"] == 1
        assert len(body["entries"]) == 2

    def test_legacy_session_audit_json_fallback_read_only(
        self, client, fake_audit, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "1")
        legacy_path = os.path.join(str(tmp_path), "session_audit.json")
        legacy_entries = [
            {
                "timestamp": "2026-04-23T00:25:00",
                "session_id": "sid_legacy",
                "user_input": "raw legacy text",
                "ai_response": "legacy reply",
                "internal_state": {"salary": 100},
                "tax_calculation": "Pending",
            },
            {"timestamp": "2026-04-23T00:26:00", "session_id": "sid_other_legacy"},
        ]
        with open(legacy_path, "w", encoding="utf-8") as fh:
            json.dump(legacy_entries, fh)
        before = _read_bytes(legacy_path)

        response = client.get("/history/sid_legacy")
        assert response.status_code == 200
        body = response.json()
        assert body["entries"] == [legacy_entries[0]]
        assert body["corrupt_lines_skipped"] == 0
        assert body["has_more"] is False
        # Read-only: the legacy file was not rewritten or migrated in place.
        assert _read_bytes(legacy_path) == before
        assert not os.path.exists(_stream_path(tmp_path))

    def test_never_serves_blackbox_content(self, client, fake_audit, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "1")
        fake_audit.log_interaction("sid_bb", "global in", "global out", {"salary": 3})
        blackbox_dir = os.path.join(str(tmp_path), "blackbox")
        os.makedirs(blackbox_dir, exist_ok=True)
        with open(
            os.path.join(blackbox_dir, "sid_bb.jsonl"), "w", encoding="utf-8"
        ) as fh:
            fh.write(
                json.dumps({"session_id": "sid_bb", "secret": "BLACKBOX_ONLY_MARKER"})
                + "\n"
            )

        response = client.get("/history/sid_bb")
        assert response.status_code == 200
        assert b"BLACKBOX_ONLY_MARKER" not in response.content
        assert len(response.json()["entries"]) == 1

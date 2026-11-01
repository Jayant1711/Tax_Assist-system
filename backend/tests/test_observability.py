"""Sprint 3 Wave H observability tests (design §7) — red first.

Covers the Wave H contract end to end:

1. **Request-ID middleware** — ``X-Request-ID`` present on responses
   (including hardening short-circuits) and UNIQUE per request; an
   inbound ``X-Request-ID`` is never echoed (ids are always server
   uuid4s).
2. **JSON log shape** — a captured record parses to exactly the design
   field set (timestamp/level/logger/message + request fields via the
   contextvars filter), and non-request records omit the request fields.
3. **Secret hygiene** — after a full register→login→chat flow, the app
   log must contain NO password, NO session token (cookie value), and NO
   user message text — only the structured record plus the access line.
4. **App-log rotation** — a tiny ``TAX_APP_LOG_MAX_BYTES`` fires the
   audit-module rotation; no line is lost; invalid env values fall back
   to the documented defaults (same pattern as TAX_AUDIT_*).
5. **Engine-failure path** — a crashing engine still returns 200 with
   ``tax_report: null`` AND logs a structured ERROR record carrying the
   request id and the sha256[:16] session-id hash (never the raw id).
"""
import hashlib
import json
import logging
import os
import re
import uuid

import pytest

import observability

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UA = {"User-Agent": "test-wave-h-agent/1.0"}
MARKER_PASSWORD = "zebra-unicorn-passphrase-123"  # policy-legal, unique
MARKER_MESSAGE = "zebra unicorn marker: my income is 12 lakhs salary"


@pytest.fixture()
def app_log_file(tmp_path):
    """Re-anchor the app log into tmp; restore the backend anchor after.

    Yields the tmp app.jsonl path. setup_logging REPLACES the installed
    handlers (idempotent), so this never duplicates lines; the finalizer
    re-anchors the handler at the backend logs dir (absolute path, stable
    regardless of the authed_client fixture's cwd juggling).
    """
    log_dir = str(tmp_path / "logs")
    observability.setup_logging("dev", log_dir=log_dir)
    yield os.path.join(log_dir, "app", "app.jsonl")
    observability.setup_logging("dev", log_dir=os.path.join(BACKEND_DIR, "logs"))


def _read_entries(path):
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@pytest.fixture()
def _clean_request_context():
    """Reset every request-context var around a test (no leakage)."""
    for var in (
        observability.request_id_var,
        observability.user_id_var,
        observability.request_path_var,
        observability.request_status_var,
        observability.request_duration_var,
    ):
        var.set(None)
    yield
    for var in (
        observability.request_id_var,
        observability.user_id_var,
        observability.request_path_var,
        observability.request_status_var,
        observability.request_duration_var,
    ):
        var.set(None)


class TestRequestIdMiddleware:
    def test_header_present_and_unique_per_request(self, authed_client) -> None:
        ids = set()
        for _ in range(3):
            response = authed_client.get("/health")
            assert response.status_code in (200, 503)
            request_id = response.headers.get("x-request-id")
            assert request_id, "every response must carry X-Request-ID"
            assert re.fullmatch(r"[0-9a-f]{32}", request_id)  # uuid4().hex
            ids.add(request_id)
        assert len(ids) == 3, "request ids must be unique per request"

    def test_inbound_request_id_is_not_trusted(self, authed_client) -> None:
        response = authed_client.get(
            "/health", headers={"X-Request-ID": "attacker-chosen-id"}
        )
        request_id = response.headers["x-request-id"]
        assert request_id != "attacker-chosen-id"
        assert re.fullmatch(r"[0-9a-f]{32}", request_id)

    def test_short_circuit_responses_carry_the_header(self, authed_client) -> None:
        # Origin-check 403 (state-changing route, disallowed Origin) is a
        # middleware short-circuit — the request-ID middleware is
        # outermost, so the header must still be on it.
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session_id": "whatever"},
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 403
        assert response.headers.get("x-request-id")


class TestJsonLogShape:
    @pytest.mark.usefixtures("_clean_request_context")
    def test_design_field_set_on_a_request_record(self) -> None:
        captured = []

        class Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        probe = logging.getLogger("observability.test.shape")
        capture = Capture()
        probe.addHandler(capture)
        try:
            observability.set_request_context("rid-1234", "/chat")
            observability.set_request_result(200, 12.345)
            token = observability.user_id_var.set("user-42")
            try:
                probe.info("hello %s", "world")
            finally:
                observability.user_id_var.reset(token)
        finally:
            probe.removeHandler(capture)

        entry = observability.JsonFormatter().to_entry(captured[0])
        # The design §7 field set — all present on a request record.
        assert entry["message"] == "hello world"
        assert entry["level"] == "INFO"
        assert entry["logger"] == "observability.test.shape"
        assert entry["request_id"] == "rid-1234"
        assert entry["user_id"] == "user-42"
        assert entry["path"] == "/chat"
        assert entry["status"] == 200
        assert entry["duration_ms"] == 12.35  # rounded, 2dp
        assert "T" in entry["timestamp"]  # ISO-8601
        # One compact JSON line round-trips.
        assert json.loads(json.dumps(entry)) == entry

    @pytest.mark.usefixtures("_clean_request_context")
    def test_non_request_records_omit_request_fields(self) -> None:
        captured = []

        class Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        probe = logging.getLogger("observability.test.shape.offrequest")
        capture = Capture()
        probe.addHandler(capture)
        try:
            probe.warning("outside any request")
        finally:
            probe.removeHandler(capture)

        entry = observability.JsonFormatter().to_entry(captured[0])
        for field in ("request_id", "user_id", "path", "status", "duration_ms"):
            assert field not in entry

    def test_dev_console_is_human_readable_and_prod_is_json(self) -> None:
        dev = observability.build_console_handler("dev")
        prod = observability.build_console_handler("prod")
        assert not isinstance(dev.formatter, observability.JsonFormatter)
        assert isinstance(prod.formatter, observability.JsonFormatter)


class TestSecretHygiene:
    def test_no_tokens_passwords_or_message_bodies_in_app_log(
        self, authed_client, app_log_file
    ) -> None:
        client = authed_client
        client.headers.update(UA)

        # Register + login with a DISTINCTIVE password; capture the token
        # exactly as it travels (Set-Cookie) — these three strings are the
        # secrets the log stream must never contain.
        email = "wave-h-{}@example.com".format(uuid.uuid4().hex[:12])
        register = client.post(
            "/auth/register", json={"email": email, "password": MARKER_PASSWORD}
        )
        assert register.status_code == 201
        login = client.post(
            "/auth/login", json={"email": email, "password": MARKER_PASSWORD}
        )
        assert login.status_code == 200
        set_cookie = login.headers["set-cookie"]
        token = set_cookie.split(";", 1)[0].split("=", 1)[1]
        assert token  # positive control: we actually captured a token

        # One chat turn carrying a marker message (the user's free text).
        bootstrap = client.post("/sessions")
        assert bootstrap.status_code == 200
        session_id = bootstrap.json()["session_id"]
        chat = client.post(
            "/chat",
            json={"message": MARKER_MESSAGE, "session_id": session_id},
        )
        assert chat.status_code == 200
        request_id = chat.headers["x-request-id"]

        entries = _read_entries(app_log_file)
        raw_stream = open(app_log_file, "r", encoding="utf-8").read()

        # 1. None of the secrets appear anywhere in the log output.
        assert MARKER_PASSWORD not in raw_stream
        assert token not in raw_stream
        # The distinctive marker words never travel together (the message
        # body is never logged; single common words like "salary" may).
        for line in raw_stream.splitlines():
            assert not ("zebra" in line and "unicorn" in line)

        # 2. The structured access record exists and correlates.
        access = [e for e in entries if e.get("logger") == "observability.access"]
        chat_access = [e for e in access if e.get("path") == "/chat"]
        assert chat_access, "expected an access record for the chat turn"
        assert chat_access[-1]["status"] == 200
        assert chat_access[-1]["request_id"] == request_id
        assert isinstance(chat_access[-1]["duration_ms"], (int, float))

        # 3. The chat-turn lines carry the request id (correlation), and
        #    the authenticated user id from the request context.
        owner_id = register.json()["user_id"]
        correlated = [e for e in entries if e.get("request_id") == request_id]
        assert correlated
        assert any(e.get("user_id") == owner_id for e in correlated)


class TestAppLogRotation:
    def test_tiny_env_cap_fires_rotation_and_loses_nothing(
        self, tmp_path, monkeypatch
    ) -> None:
        # Cap 1024 bytes with ~240-byte records: the 5th write pushes the
        # active stream over the cap -> one rotation -> .1 holds 5 lines,
        # the active file holds the 6th. (A cap SMALLER than one line
        # would rotate on every write — a valid but degenerate regime.)
        monkeypatch.setenv("TAX_APP_LOG_MAX_BYTES", "1024")
        handler = observability.build_app_log_handler(str(tmp_path))
        assert handler.max_bytes == 1024  # env honored (validated parser)

        probe = logging.getLogger("observability.test.rotation")
        probe.addHandler(handler)
        previous_propagate = probe.propagate
        probe.propagate = False
        try:
            for i in range(6):
                probe.info("y" * 150 + str(i))  # each record ~240 bytes
        finally:
            probe.removeHandler(handler)
            probe.propagate = previous_propagate

        active = os.path.join(tmp_path, "app", "app.jsonl")
        generation_1 = active + ".1"
        assert os.path.exists(generation_1), "rotation must have fired"

        total = sum(
            len([line for line in open(p, encoding="utf-8") if line.strip()])
            for p in (active, generation_1)
        )
        assert total == 6, "rotation must preserve every line"

    def test_invalid_env_falls_back_to_documented_defaults(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setenv("TAX_APP_LOG_MAX_BYTES", "bogus")
        monkeypatch.setenv("TAX_APP_LOG_MAX_FILES", "0")
        monkeypatch.setenv("TAX_APP_LOG_RETENTION_DAYS", "-3")
        handler = observability.build_app_log_handler(str(tmp_path))
        assert handler.max_bytes == handler.DEFAULT_MAX_BYTES
        assert handler.max_files == handler.DEFAULT_MAX_FILES
        assert handler.retention_days == handler.DEFAULT_RETENTION_DAYS


class TestEngineFailurePath:
    def test_engine_failure_keeps_graceful_null_and_logs_structured_error(
        self, authed_client, app_log_file, monkeypatch
    ) -> None:
        import main as main_module

        bootstrap = authed_client.post("/sessions")
        assert bootstrap.status_code == 200
        session_id = bootstrap.json()["session_id"]

        def _boom(*args, **kwargs):
            raise RuntimeError("boom engine down")

        monkeypatch.setattr(main_module.engine, "calculate_tax_advanced", _boom)

        response = authed_client.post(
            "/chat",
            json={"message": "I earn 12 lakhs salary", "session_id": session_id},
        )
        # Graceful degradation is UNCHANGED: 200 + null report.
        assert response.status_code == 200
        assert response.json()["tax_report"] is None
        request_id = response.headers["x-request-id"]

        entries = _read_entries(app_log_file)
        failures = [
            e
            for e in entries
            if e.get("level") == "ERROR" and "tax engine failure" in e.get("message", "")
        ]
        assert failures, "expected a structured engine-failure record"
        entry = failures[-1]
        # Correlated with the request that failed...
        assert entry["request_id"] == request_id
        assert entry["error"].startswith("RuntimeError")
        assert "boom engine down" in entry["error"]
        assert entry["logger"] == "main"
        # ...identifies the session by HASH only (never the raw id)...
        expected_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
        assert expected_hash in entry["message"]
        assert session_id not in json.dumps(entry)
        # ...and carries a traceback for ERROR-level records.
        assert "traceback" in entry


class TestSetupLoggingIdempotency:
    def test_repeated_setup_never_duplicates_handlers(self, tmp_path) -> None:
        observability.setup_logging("dev", log_dir=str(tmp_path / "one"))
        observability.setup_logging("dev", log_dir=str(tmp_path / "two"))
        root = logging.getLogger()
        app_handlers = [
            h for h in root.handlers if isinstance(h, observability.JsonlAppLogHandler)
        ]
        assert len(app_handlers) == 1
        # The surviving handler is anchored at the LATEST log_dir.
        assert app_handlers[0].path == os.path.abspath(
            os.path.join(str(tmp_path / "two"), "app", "app.jsonl")
        )
        # Restore the backend anchor for the rest of the session.
        observability.setup_logging("dev", log_dir=os.path.join(BACKEND_DIR, "logs"))

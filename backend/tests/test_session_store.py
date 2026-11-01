"""Server-side app_sessions + the session_id wire contract (Sprint 3 Wave D).

Tests FIRST (red), per docs/sprint3-design.md §2 (ADR-013) and the Wave D
build-order step D. Red at fe888cd (no app_sessions store, no /sessions,
/chat still takes a client-supplied session dict, /history gates off);
green after the Wave D implementation.

Contract pinned here:

- POST /sessions   -> 200 {session_id, session: projection}; server-issued
  uuid4-hex id; bootstrap state {id, phase: "PROFILING", history: []};
  authed by default, anonymous ONLY under TAX_ENABLE_ANON_DEMO=1 with a
  user_id NULL row.
- POST /chat       -> body {message, session_id}; the state lives
  server-side (income books into the store and round-trips via the id
  alone); the response `session` is the read-only projection (internal
  keys dropped, frontend keys kept); foreign/unknown id -> 404; anonymous
  -> 401 (demo off); an old-style session-dict body -> 422.
- POST /calculate  -> body {session_id, tax_year?}; full report shape
  (old_regime/new_regime/... + fy fields) computed from the server-side
  state; an explicit tax_year overrides the state pin.
- GET /sessions | GET /sessions/{id} | DELETE /sessions/{id}: owner-checked
  CRUD (foreign/unknown -> 404, delete -> 204).
- GET /history/{sid}: auth + ownership (foreign/unknown -> 404, anonymous
  -> 401); TAX_ENABLE_HISTORY now defaults ON (Sprint-1 interim C5 gate
  superseded by auth + ownership; the env stays as a kill-switch).
- State validation stays enforced: the wire can no longer inject a session
  payload at all, and a (test-seeded) stored state that fails the
  Sprint-1+2 validator is refused at the load boundary — server-side only.
- Audit additive field: chat-turn audit + blackbox records carry user_id
  (absent for anonymous demo turns; the stream is otherwise unchanged).
"""
import json
import os
import re
import types

import pytest

from tests.conftest import BACKEND_DIR, make_session, register_and_login

_UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")

# Internal keys the projection must never leak (ADR-013: state minus the
# audit scrub set — history/_last_*/memory).
_INTERNAL_KEYS = ("history", "_last_question", "_last_val", "_prev_salary", "memory")


@pytest.fixture()
def wave_d_env(monkeypatch, tmp_path):
    """Isolated SQLite store + isolated JSONL audit stream + dev posture.

    Mirrors test_auth.auth_env (Wave C): TAX_DB_PATH points into tmp_path
    and db.init_db() re-points the store BEFORE any client exists;
    main.audit is swapped for a tmp-rooted AuditLogger so audit/blackbox
    assertions read exactly what the endpoints wrote; rate limits are
    raised so request-heavy tests never trip the production buckets.
    """
    monkeypatch.setenv("TAX_DB_PATH", str(tmp_path / "wave-d.db"))
    monkeypatch.setenv("TAX_RATE_LIMIT_AUTH_PER_MIN", "1000")
    monkeypatch.setenv("TAX_RATE_LIMIT_CHAT_PER_MIN", "1000")
    monkeypatch.setenv("TAX_RATE_LIMIT_CALC_PER_MIN", "1000")
    monkeypatch.setenv("TAX_RATE_LIMIT_GLOBAL_PER_MIN", "1000")
    monkeypatch.delenv("TAX_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("TAX_ENABLE_ANON_DEMO", raising=False)
    monkeypatch.delenv("TAX_ENABLE_HISTORY", raising=False)
    previous_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)  # main resolves its relative logs dirs against cwd
    try:
        import db as db_module
        import main as main_module
        from audit_logger import AuditLogger

        db_module.init_db()
        audit = AuditLogger(str(tmp_path / "logs"))
        monkeypatch.setattr(main_module, "audit", audit)
        yield types.SimpleNamespace(tmp_path=tmp_path, audit=audit, db=db_module)
    finally:
        os.chdir(previous_cwd)


@pytest.fixture()
def client(wave_d_env):
    from fastapi.testclient import TestClient

    from main import create_app

    with TestClient(create_app("dev")) as test_client:
        yield test_client


@pytest.fixture()
def authed_client(client):
    """Module-local override of the shared conftest fixture.

    Registration MUST happen after wave_d_env re-pointed the store (the
    auth_sessions row has to live in the same db the requests read), so
    this module logs in on the env-aware `client` instead of the conftest
    client, which anchors the store to the default TAX_DB_PATH.
    """
    register_and_login(client)
    return client


@pytest.fixture()
def blackbox_dir():
    """The blackbox directory the module-level SessionLab writes into
    (relative "logs/blackbox" resolved against backend/ while cwd is
    pinned by wave_d_env)."""
    return os.path.join(BACKEND_DIR, "logs", "blackbox")


# ---------------------------------------------------------------------------
# Bootstrap (POST /sessions)
# ---------------------------------------------------------------------------


class TestSessionBootstrap:
    def test_bootstrap_returns_server_uuid_and_projection(self, authed_client) -> None:
        response = authed_client.post("/sessions")
        assert response.status_code == 200
        body = response.json()
        assert _UUID_HEX_RE.match(body["session_id"]), body["session_id"]
        # The projection of the bootstrap state: identity + phase, and the
        # empty history list is internal (never projected).
        assert body["session"]["id"] == body["session_id"]
        assert body["session"]["phase"] == "PROFILING"
        assert "history" not in body["session"]

    def test_get_session_returns_owned_projection(self, authed_client) -> None:
        sid = make_session(authed_client)
        response = authed_client.get(f"/sessions/{sid}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == sid
        assert body["phase"] == "PROFILING"

    def test_sessions_list_is_owned_and_shows_timestamps(self, authed_client) -> None:
        sid_a = make_session(authed_client)
        sid_b = make_session(authed_client)
        response = authed_client.get("/sessions")
        assert response.status_code == 200
        rows = {row["id"]: row for row in response.json()}
        assert sid_a in rows and sid_b in rows
        for row in (rows[sid_a], rows[sid_b]):
            assert row["created_at"]
            assert row["updated_at"]

    def test_delete_session_is_owner_checked_204(self, authed_client) -> None:
        sid = make_session(authed_client)
        assert authed_client.delete(f"/sessions/{sid}").status_code == 204
        assert authed_client.get(f"/sessions/{sid}").status_code == 404
        # Idempotency is NOT promised for a deleted id: it is unknown now.
        assert authed_client.delete(f"/sessions/{sid}").status_code == 404

    def test_foreign_session_crud_is_404(self, authed_client) -> None:
        sid = make_session(authed_client)
        # Second user on the same client: the cookie jar now authenticates
        # user B, for whom user A's session id is exactly "unknown".
        register_and_login(authed_client)
        assert authed_client.get(f"/sessions/{sid}").status_code == 404
        assert authed_client.delete(f"/sessions/{sid}").status_code == 404
        assert authed_client.post(
            "/chat", json={"message": "hi", "session_id": sid}
        ).status_code == 404
        assert authed_client.post(
            "/calculate", json={"session_id": sid}
        ).status_code == 404


# ---------------------------------------------------------------------------
# Chat: server-side state round-trip + projection
# ---------------------------------------------------------------------------


class TestChatServerSideState:
    def test_chat_books_income_server_side(self, authed_client) -> None:
        sid = make_session(authed_client)
        response = authed_client.post(
            "/chat",
            json={
                "message": "I am a software engineer earning 18 LPA",
                "session_id": sid,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["session_id"] == sid
        assert body["extracted"]  # non-empty extraction list
        assert body["session"]["salary"] == 1_800_000  # 18 LPA round-trips
        assert body["tax_report"] is not None  # real-time computation gate
        # Server-side round trip: the id alone reconstructs the state.
        stored = authed_client.get(f"/sessions/{sid}").json()
        assert stored["salary"] == 1_800_000

    def test_projection_excludes_internal_keys(self, authed_client) -> None:
        sid = make_session(authed_client)
        response = authed_client.post(
            "/chat", json={"message": "my salary is 500000", "session_id": sid}
        )
        assert response.status_code == 200
        projection = response.json()["session"]
        for key in _INTERNAL_KEYS:
            assert key not in projection, key
        # The keys the frontend reads survive the projection.
        assert projection["id"] == sid
        assert projection["phase"] in {"PROFILING", "INCOME", "EXPENDITURE", "FINAL"}
        assert projection["salary"] == 500_000

    def test_unknown_session_id_is_404(self, authed_client) -> None:
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": "0" * 32}
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Calculate: {session_id, tax_year?}
# ---------------------------------------------------------------------------


class TestCalculateFromServerState:
    def test_calculate_returns_full_report_with_fy_fields(self, authed_client) -> None:
        sid = make_session(authed_client)
        income = authed_client.post(
            "/chat",
            json={"message": "my salary is 1800000", "session_id": sid},
        )
        assert income.status_code == 200
        response = authed_client.post("/calculate", json={"session_id": sid})
        assert response.status_code == 200
        body = response.json()
        for key in ("old_regime", "new_regime", "recommendation"):
            assert key in body
        # ADR-008 identity fields: unpinned -> registry default (Step A3).
        assert body["tax_year"] == "2025-26"
        assert body["assessment_year"] == "2026-27"
        assert body["fy_label"] == "FY 2025-26 (AY 2026-27)"

    def test_tax_year_override_wins_over_state(self, authed_client) -> None:
        sid = make_session(authed_client)
        income = authed_client.post(
            "/chat",
            json={"message": "my salary is 1800000", "session_id": sid},
        )
        assert income.status_code == 200
        pinned = authed_client.post(
            "/calculate", json={"session_id": sid, "tax_year": "fy_2024_25"}
        )
        assert pinned.status_code == 200
        body = pinned.json()
        assert body["tax_year"] == "2024-25"
        assert body["fy_label"] == "FY 2024-25 (AY 2025-26)"

    def test_unknown_session_id_is_404(self, authed_client) -> None:
        assert authed_client.post(
            "/calculate", json={"session_id": "0" * 32}
        ).status_code == 404


# ---------------------------------------------------------------------------
# Auth surfaces: 401 (demo off) / demo flag / ownership
# ---------------------------------------------------------------------------


class TestAuthSurfaces:
    def test_anonymous_requests_are_401_with_demo_off(self, client) -> None:
        # Deny-by-default (ADR-012): /chat, /calculate and /sessions all
        # require the cookie; the demo opt-in is unset in this fixture.
        assert client.post(
            "/chat", json={"message": "hi", "session_id": "0" * 32}
        ).status_code == 401
        assert client.post(
            "/calculate", json={"session_id": "0" * 32}
        ).status_code == 401
        assert client.post("/sessions").status_code == 401
        assert client.get("/sessions").status_code == 401

    def test_demo_flag_permits_anonymous_null_user_sessions(
        self, client, wave_d_env, monkeypatch
    ) -> None:
        monkeypatch.setenv("TAX_ENABLE_ANON_DEMO", "1")
        bootstrap = client.post("/sessions")
        assert bootstrap.status_code == 200
        sid = bootstrap.json()["session_id"]

        # The store row is a user_id NULL session (design §1: demo rows).
        row = wave_d_env.db.query_one(
            "SELECT user_id FROM app_sessions WHERE id = ?", (sid,)
        )
        assert row is not None
        assert row["user_id"] is None

        chat = client.post("/chat", json={"message": "hi", "session_id": sid})
        assert chat.status_code == 200
        calculate = client.post("/calculate", json={"session_id": sid})
        assert calculate.status_code == 200

    def test_demo_flag_never_unlocks_history(
        self, client, wave_d_env, monkeypatch
    ) -> None:
        monkeypatch.setenv("TAX_ENABLE_ANON_DEMO", "1")
        sid = client.post("/sessions").json()["session_id"]
        assert client.post(
            "/chat", json={"message": "hi", "session_id": sid}
        ).status_code == 200
        # Anonymous history stays 401 even with the demo flag on.
        assert client.get(f"/history/{sid}").status_code == 401


# ---------------------------------------------------------------------------
# Breaking contract: old-style bodies -> 422
# ---------------------------------------------------------------------------


class TestLegacyContract422:
    def test_old_style_chat_body_is_422(self, authed_client) -> None:
        sid = make_session(authed_client)
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session": {"id": sid, "salary": 9_999}},
        )
        assert response.status_code == 422
        assert "server-side" in response.text
        # Defense against mixed bodies too: a client that half-migrates.
        mixed = authed_client.post(
            "/chat",
            json={"message": "hi", "session_id": sid, "session": {"id": sid}},
        )
        assert mixed.status_code == 422

    def test_old_style_calculate_body_is_422(self, authed_client) -> None:
        response = authed_client.post(
            "/calculate", json={"id": "sid_x", "salary": 1_800_000, "80c": 150_000}
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# State validation stays enforced (server-side write path only)
# ---------------------------------------------------------------------------


class TestStateValidationEnforced:
    def test_wire_cannot_inject_hostile_session_payload(self, authed_client) -> None:
        # The pre-Wave-D attack (client-authored state) is structurally
        # closed: the session dict is not part of the request contract and
        # the legacy key is rejected before any handler logic runs.
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session": {"id": "sid_ok", "salary": "abc"}},
        )
        assert response.status_code == 422

    def test_forged_stored_state_is_refused_at_the_load_boundary(
        self, authed_client, wave_d_env
    ) -> None:
        """Defense-in-depth (H5/N1): a state that fails the Sprint-1+2
        validator can only exist via a direct store write (tests/ops), and
        BOTH consumers refuse it with a 422 instead of computing on it."""
        sid = make_session(authed_client)
        wave_d_env.db.save_state(sid, {"id": sid, "salary": "abc"})
        chat = authed_client.post(
            "/chat", json={"message": "hi", "session_id": sid}
        )
        assert chat.status_code == 422
        calculate = authed_client.post("/calculate", json={"session_id": sid})
        assert calculate.status_code == 422


# ---------------------------------------------------------------------------
# /history: ownership + default flip
# ---------------------------------------------------------------------------


class TestHistoryOwnership:
    def test_owned_history_serves_entries_by_default(
        self, authed_client, wave_d_env
    ) -> None:
        # No TAX_ENABLE_HISTORY involved: the Sprint-1 interim gate default
        # flips to ON in Wave D (C5 closed by auth + ownership instead).
        sid = make_session(authed_client)
        turn = authed_client.post(
            "/chat", json={"message": "my salary is 500000", "session_id": sid}
        )
        assert turn.status_code == 200
        response = authed_client.get(f"/history/{sid}")
        assert response.status_code == 200
        body = response.json()
        assert body["corrupt_lines_skipped"] == 0
        assert [e["session_id"] for e in body["entries"]] == [sid]

    def test_foreign_history_is_404(self, authed_client, wave_d_env) -> None:
        sid = make_session(authed_client)
        turn = authed_client.post("/chat", json={"message": "hi", "session_id": sid})
        assert turn.status_code == 200
        register_and_login(authed_client)  # now user B
        assert authed_client.get(f"/history/{sid}").status_code == 404

    def test_anonymous_history_is_401(self, client, wave_d_env) -> None:
        assert client.get(f"/history/{'0' * 32}").status_code == 401

    def test_kill_switch_still_disables_history(self, authed_client, monkeypatch) -> None:
        sid = make_session(authed_client)
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "0")
        response = authed_client.get(f"/history/{sid}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}


# ---------------------------------------------------------------------------
# Audit additive field: user_id (stream otherwise unchanged)
# ---------------------------------------------------------------------------


class TestAuditUserIdAdditive:
    def test_authed_turn_records_user_id(
        self, authed_client, wave_d_env, blackbox_dir
    ) -> None:
        sid = make_session(authed_client)
        turn = authed_client.post(
            "/chat", json={"message": "hi", "session_id": sid}
        )
        assert turn.status_code == 200
        entries = wave_d_env.audit.read_entries()[0]
        entry = next(e for e in entries if e["event"] == "chat_turn")
        assert entry["user_id"]
        # Blackbox record carries the same additive field.
        with open(os.path.join(blackbox_dir, f"{sid}.jsonl"), encoding="utf-8") as fh:
            blackbox_entry = json.loads(fh.readline())
        assert blackbox_entry["user_id"] == entry["user_id"]

    def test_demo_turn_omits_user_id(
        self, client, wave_d_env, monkeypatch, blackbox_dir
    ) -> None:
        monkeypatch.setenv("TAX_ENABLE_ANON_DEMO", "1")
        sid = client.post("/sessions").json()["session_id"]
        turn = client.post("/chat", json={"message": "hi", "session_id": sid})
        assert turn.status_code == 200
        (entry,) = wave_d_env.audit.read_entries()[0]
        assert "user_id" not in entry  # additive: present only when known
        with open(os.path.join(blackbox_dir, f"{sid}.jsonl"), encoding="utf-8") as fh:
            blackbox_entry = json.loads(fh.readline())
        assert "user_id" not in blackbox_entry

    def test_auth_events_still_sanitized(self, client, wave_d_env) -> None:
        # Wave C contract unchanged: the user_id field joins the existing
        # sanitized auth records (no raw email/token appears with it).
        register_and_login(client)
        entries = wave_d_env.audit.read_entries()[0]
        register_entry = next(e for e in entries if e["event"] == "auth_register")
        assert register_entry["user_id"]
        assert "email_sha256_16" in register_entry  # correlation hash, never raw
        assert "@example.com" not in json.dumps(entries)
        assert "password" not in json.dumps(entries)

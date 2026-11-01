"""Auth-core tests (Sprint 3 Wave C) — red first.

Contract under test (design §1 ADR-012, §2 ADR-013):

- POST /auth/register  -> 201 {user_id, email}; 409 duplicate; 422 policy
  (password length 12..1024, email format).
- POST /auth/login     -> 200 {user_id, email} + Set-Cookie (HttpOnly,
  SameSite=Lax, Path=/, Secure per TAX_COOKIE_SECURE, __Host- prefix when
  Secure, Max-Age = sliding TTL); uniform 401 "Invalid email or password"
  for unknown email AND wrong password (scrypt runs on both paths —
  timing equalization); 423 generic lockout response once the account is
  locked (5 failures -> 15 min), only ever shown to a CORRECT password.
- POST /auth/logout    -> 204 + cookie clear + row revoke (idempotent).
- GET  /auth/me        -> 200 {user_id, email, expires_at} or 401
  {"detail": "Authentication required"} (never hints why).
- GET  /auth/sessions  -> own active sessions (token-hash prefix id,
  created, last_used, expires, current).
- DELETE /auth/sessions/{id} -> 204, owner-checked (foreign -> 404).
- UA mismatch invalidates the session row.
- db.py migrations are idempotent (init twice; schema exactly per design).
- Auth events land in the JSONL audit stream as new event types,
  sanitized: no raw email, no tokens, no passwords — sha256[:16]
  correlation hashes only.
"""
import hashlib
import os
import sqlite3
import threading
import time
import types
from http.cookies import SimpleCookie

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A fixed UA for every request in this module: sessions are UA-hash bound
# at issue, so requests must present the SAME UA or the row is invalidated
# (that behavior itself is tested in TestUaBinding).
UA = {"User-Agent": "test-auth-agent/1.0"}

PASSWORD = "correct horse battery staple"  # 28 chars, policy-legal
DEV_COOKIE = "ta_session"


def _register(client, email, password=PASSWORD):
    return client.post(
        "/auth/register", json={"email": email, "password": password}, headers=UA
    )


def _login(client, email, password=PASSWORD, ua=None):
    return client.post(
        "/auth/login", json={"email": email, "password": password}, headers=ua or UA
    )


def _me(client, ua=None, cookies=None):
    if cookies is None:
        return client.get("/auth/me", headers=ua or UA)
    # Swap the client's cookie jar for the explicitly provided one (per-
    # request cookies= is deprecated by httpx and its behavior ambiguous).
    import httpx

    saved = client.cookies
    jar = httpx.Cookies()
    for name, value in cookies.items():
        jar.set(name, value)
    client.cookies = jar
    try:
        return client.get("/auth/me", headers=ua or UA)
    finally:
        client.cookies = saved


def _set_cookie_token(response, name=DEV_COOKIE):
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    assert name in cookie, response.headers.get("set-cookie")
    return cookie[name].value


@pytest.fixture()
def auth_env(monkeypatch, tmp_path):
    """Isolated SQLite db + isolated JSONL audit stream + dev posture.

    - TAX_DB_PATH points into tmp_path and db.init_db() re-points the
      store BEFORE any client exists.
    - main.audit is swapped for an AuditLogger rooted in tmp_path so the
      auth-event assertions read exactly what the endpoints wrote.
    - Rate limits are raised so request-heavy tests do not trip the
      10/min production /auth bucket (that bucket has its own test).
    """
    monkeypatch.setenv("TAX_DB_PATH", str(tmp_path / "auth-test.db"))
    monkeypatch.setenv("TAX_RATE_LIMIT_AUTH_PER_MIN", "1000")
    monkeypatch.setenv("TAX_RATE_LIMIT_GLOBAL_PER_MIN", "1000")
    monkeypatch.delenv("TAX_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("TAX_SESSION_TTL_MINUTES", raising=False)
    monkeypatch.delenv("TAX_SESSION_ABS_TTL_HOURS", raising=False)
    import db as db_module
    import main as main_module
    from audit_logger import AuditLogger

    db_module.init_db()
    audit = AuditLogger(str(tmp_path / "logs"))
    monkeypatch.setattr(main_module, "audit", audit)
    return types.SimpleNamespace(tmp_path=tmp_path, audit=audit, db=db_module)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from main import create_app

    with TestClient(create_app("dev")) as test_client:
        yield test_client


def _stream_text(auth_env) -> str:
    with open(auth_env.audit.log_file, "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_happy_path_201(self, auth_env, client) -> None:
        response = _register(client, "alice@example.com")
        assert response.status_code == 201
        body = response.json()
        assert set(body) == {"user_id", "email"}
        assert body["email"] == "alice@example.com"
        assert isinstance(body["user_id"], str) and body["user_id"]

    def test_register_duplicate_is_409(self, auth_env, client) -> None:
        assert _register(client, "dup@example.com").status_code == 201
        response = _register(client, "dup@example.com")
        assert response.status_code == 409
        assert "detail" in response.json()

    def test_register_duplicate_case_insensitive_is_409(
        self, auth_env, client
    ) -> None:
        assert _register(client, "casey@Example.com").status_code == 201
        assert _register(client, "CASEY@example.COM").status_code == 409

    def test_register_password_too_short_is_422(self, auth_env, client) -> None:
        response = _register(client, "short@example.com", password="x" * 11)
        assert response.status_code == 422

    def test_register_password_too_long_is_422(self, auth_env, client) -> None:
        response = _register(client, "long@example.com", password="x" * 1025)
        assert response.status_code == 422

    def test_register_password_boundaries_pass(self, auth_env, client) -> None:
        assert _register(client, "min@example.com", password="x" * 12).status_code == 201
        assert (
            _register(client, "max@example.com", password="x" * 1024).status_code
            == 201
        )

    @pytest.mark.parametrize(
        "email", ["not-an-email", "missing-at.example.com", "a@", "@b.com", ""]
    )
    def test_register_invalid_email_is_422(self, auth_env, client, email) -> None:
        response = _register(client, email)
        assert response.status_code == 422

    def test_register_never_echoes_password_material(
        self, auth_env, client
    ) -> None:
        response = _register(client, "nopass@example.com")
        assert PASSWORD not in response.text


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success_sets_hardened_cookie(self, auth_env, client) -> None:
        assert _register(client, "cookie@example.com").status_code == 201
        response = _login(client, "cookie@example.com")
        assert response.status_code == 200
        assert set(response.json()) == {"user_id", "email"}

        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        morsel = cookie[DEV_COOKIE]
        assert morsel["httponly"] is True
        assert morsel["samesite"].lower() == "lax"
        assert morsel["path"] == "/"
        assert not morsel["secure"]  # dev posture: no Secure flag
        from config import session_ttl_minutes

        assert morsel["max-age"] == str(session_ttl_minutes() * 60)

    def test_login_cookie_is_host_prefixed_when_secure(
        self, auth_env, client, monkeypatch
    ) -> None:
        monkeypatch.setenv("TAX_COOKIE_SECURE", "1")
        assert _register(client, "secure@example.com").status_code == 201
        response = _login(client, "secure@example.com")
        assert response.status_code == 200
        header = response.headers["set-cookie"]
        assert "__Host-ta_session=" in header
        assert "Secure" in header
        assert "HttpOnly" in header
        assert "SameSite=lax" in header

    def test_wrong_password_is_uniform_401(self, auth_env, client) -> None:
        assert _register(client, "wrongpw@example.com").status_code == 201
        response = _login(client, "wrongpw@example.com", password="not-the-password")
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid email or password"}

    def test_unknown_email_is_uniform_401(self, auth_env, client) -> None:
        response = _login(client, "ghost@nowhere.test")
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid email or password"}

    def test_timing_smoke_both_failure_paths_run_scrypt(
        self, auth_env, client
    ) -> None:
        # Both failure paths must cost a real scrypt (~50-100 ms) so an
        # attacker cannot distinguish known from unknown emails by timing.
        assert _register(client, "timing@example.com").status_code == 201
        start = time.perf_counter()
        wrong = _login(client, "timing@example.com", password="wrong-password-1")
        wrong_elapsed = time.perf_counter() - start
        start = time.perf_counter()
        unknown = _login(client, "ghost@nowhere.test")
        unknown_elapsed = time.perf_counter() - start
        assert wrong.status_code == unknown.status_code == 401
        assert wrong_elapsed > 0.05, wrong_elapsed
        assert unknown_elapsed > 0.05, unknown_elapsed

    def test_login_is_case_insensitive_on_email(self, auth_env, client) -> None:
        assert _register(client, "MiXeD@Example.com").status_code == 201
        response = _login(client, "mixed@example.com")
        assert response.status_code == 200

    def test_lockout_after_five_failures(self, auth_env, client) -> None:
        assert _register(client, "lockout@example.com").status_code == 201
        for _ in range(5):
            response = _login(client, "lockout@example.com", password="bad-password-1")
            assert response.status_code == 401
            assert response.json() == {"detail": "Invalid email or password"}
        # Locked now: even the CORRECT password gets the generic lockout
        # response — never a session.
        locked = _login(client, "lockout@example.com")
        assert locked.status_code == 423
        assert locked.json() == {"detail": "Account temporarily locked"}
        # A wrong password while locked stays the uniform 401 (no oracle).
        assert (
            _login(client, "lockout@example.com", password="bad-password-2").status_code
            == 401
        )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_revokes_session(self, auth_env, client) -> None:
        assert _register(client, "bye@example.com").status_code == 201
        assert _login(client, "bye@example.com").status_code == 200
        assert _me(client).status_code == 200
        response = client.post("/auth/logout", headers=UA)
        assert response.status_code == 204
        assert _me(client).status_code == 401

    def test_logout_is_idempotent(self, auth_env, client) -> None:
        assert _register(client, "idem@example.com").status_code == 201
        assert _login(client, "idem@example.com").status_code == 200
        assert client.post("/auth/logout", headers=UA).status_code == 204
        # Second logout (revoked/no session) is still a clean 204.
        assert client.post("/auth/logout", headers=UA).status_code == 204

    def test_logout_without_any_session_is_204(self, auth_env, client) -> None:
        assert client.post("/auth/logout", headers=UA).status_code == 204

    def test_logout_clears_the_cookie(self, auth_env, client) -> None:
        assert _register(client, "clear@example.com").status_code == 201
        assert _login(client, "clear@example.com").status_code == 200
        response = client.post("/auth/logout", headers=UA)
        assert "set-cookie" in response.headers
        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        morsel = cookie[DEV_COOKIE]
        assert morsel.value == ""
        assert morsel["max-age"] == "0" or "expired" in morsel["expires"]


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


class TestMe:
    def test_me_happy_path(self, auth_env, client) -> None:
        assert _register(client, "me@example.com").status_code == 201
        assert _login(client, "me@example.com").status_code == 200
        response = _me(client)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"user_id", "email", "expires_at"}
        assert body["email"] == "me@example.com"
        assert isinstance(body["expires_at"], str) and "T" in body["expires_at"]

    def test_me_touches_and_slides_the_session(self, auth_env, client) -> None:
        assert _register(client, "slide@example.com").status_code == 201
        assert _login(client, "slide@example.com").status_code == 200
        before = _me(client).json()["expires_at"]
        time.sleep(0.02)
        after = _me(client).json()["expires_at"]
        assert after > before  # sliding TTL re-anchored on each use

    def test_me_without_cookie_is_401(self, auth_env, client) -> None:
        response = client.get("/auth/me", headers=UA)
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required"}

    def test_me_with_garbage_cookie_is_401(self, auth_env, client) -> None:
        response = _me(client, cookies={DEV_COOKIE: "not-a-real-token"})
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required"}


# ---------------------------------------------------------------------------
# Session list + per-session revoke
# ---------------------------------------------------------------------------


class TestSessions:
    def test_list_shows_own_active_sessions(self, auth_env, client) -> None:
        assert _register(client, "list@example.com").status_code == 201
        token_a = _set_cookie_token(_login(client, "list@example.com"))
        token_b = _set_cookie_token(_login(client, "list@example.com"))
        assert token_a != token_b

        response = client.get("/auth/sessions", headers=UA)
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 2
        for row in rows:
            assert set(row) == {"id", "created_at", "last_used_at", "expires_at", "current"}
        ids = {row["id"] for row in rows}
        assert len(ids) == 2
        current_flags = [row["current"] for row in rows]
        assert current_flags.count(True) == 1  # the newest login

    def test_revoke_single_session_by_owner(self, auth_env, client) -> None:
        assert _register(client, "revoke@example.com").status_code == 201
        token_a = _set_cookie_token(_login(client, "revoke@example.com"))
        _login(client, "revoke@example.com")  # newest = jar/current

        rows = client.get("/auth/sessions", headers=UA).json()
        target = next(row["id"] for row in rows if not row["current"])
        response = client.delete(f"/auth/sessions/{target}", headers=UA)
        assert response.status_code == 204

        # The revoked session's cookie is dead; the current one still works.
        assert _me(client, cookies={DEV_COOKIE: token_a}).status_code == 401
        assert _me(client).status_code == 200
        remaining = client.get("/auth/sessions", headers=UA).json()
        assert len(remaining) == 1
        assert remaining[0]["id"] != target

    def test_revoke_is_owner_checked(self, auth_env, client) -> None:
        # User A owns the target row; user B must get a 404, not a revoke.
        assert _register(client, "owner@example.com").status_code == 201
        assert _login(client, "owner@example.com").status_code == 200
        rows = client.get("/auth/sessions", headers=UA).json()
        foreign_id = rows[0]["id"]

        from fastapi.testclient import TestClient

        from main import create_app

        with TestClient(create_app("dev")) as other:
            assert _register(other, "attacker@example.com").status_code == 201
            assert _login(other, "attacker@example.com").status_code == 200
            response = other.delete(f"/auth/sessions/{foreign_id}", headers=UA)
            assert response.status_code == 404
        # A's session is untouched.
        assert _me(client).status_code == 200

    def test_revoke_unknown_row_id_is_404(self, auth_env, client) -> None:
        assert _register(client, "unknown-row@example.com").status_code == 201
        assert _login(client, "unknown-row@example.com").status_code == 200
        response = client.delete(
            "/auth/sessions/000000000000", headers=UA
        )
        assert response.status_code == 404

    def test_revoke_malformed_row_id_is_404(self, auth_env, client) -> None:
        assert _register(client, "malformed@example.com").status_code == 201
        assert _login(client, "malformed@example.com").status_code == 200
        # Malformed ids never match a row (404); the HTTP client may also
        # refuse invalid percent-encoding outright (400) — both are fine.
        assert client.delete("/auth/sessions/%ZZ", headers=UA).status_code in (
            400, 404,
        )
        assert client.delete("/auth/sessions/short", headers=UA).status_code == 404


# ---------------------------------------------------------------------------
# UA binding
# ---------------------------------------------------------------------------


class TestUaBinding:
    def test_ua_mismatch_invalidates_the_session(self, auth_env, client) -> None:
        assert _register(client, "uabind@example.com").status_code == 201
        assert _login(client, "uabind@example.com").status_code == 200
        assert _me(client).status_code == 200
        # A different UA is rejected...
        stolen = client.get(
            "/auth/me", headers={"User-Agent": "stolen-session-bot/9"}
        )
        assert stolen.status_code == 401
        # ...and the mismatch INVALIDATES the row: even the original UA
        # can no longer use it.
        assert _me(client).status_code == 401


# ---------------------------------------------------------------------------
# db.py migrations
# ---------------------------------------------------------------------------


class TestMigrations:
    def test_init_twice_is_idempotent(self, auth_env) -> None:
        db = auth_env.db
        path_one = db.init_db()
        path_two = db.init_db()
        assert path_one == path_two
        con = sqlite3.connect(path_two)
        try:
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert {"users", "auth_sessions", "schema_migrations"} <= tables
            rows = con.execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            ).fetchall()
            # Wave D adaptation (mechanical — design §2): the app_sessions
            # migration joins the registry; idempotency itself is unchanged
            # (init twice, no duplicate rows).
            assert rows == [(1, "users_auth_sessions"), (2, "app_sessions")]
        finally:
            con.close()

    def test_schema_matches_design(self, auth_env) -> None:
        db = auth_env.db
        path = db.init_db()
        con = sqlite3.connect(path)
        try:
            users_cols = {
                row[1]
                for row in con.execute("PRAGMA table_info(users)")
            }
            assert users_cols == {
                "id", "email", "password_hash", "auth_provider",
                "oauth_subject", "is_active", "failed_logins",
                "locked_until", "created_at",
            }
            session_cols = {
                row[1]
                for row in con.execute("PRAGMA table_info(auth_sessions)")
            }
            assert session_cols == {
                "token_hash", "user_id", "created_at", "last_used_at",
                "expires_at", "absolute_expires_at", "revoked_at",
                "ua_hash", "ip_hash",
            }
        finally:
            con.close()

    def test_init_creates_missing_directory(self, auth_env, monkeypatch, tmp_path) -> None:
        db = auth_env.db
        nested = tmp_path / "fresh" / "nested" / "taxassist.db"
        monkeypatch.setenv("TAX_DB_PATH", str(nested))
        path = db.init_db()
        assert nested.exists()
        assert os.path.abspath(path) == os.path.abspath(str(nested))

    def test_foreign_keys_and_wal_enabled(self, auth_env) -> None:
        db = auth_env.db
        path = db.init_db()
        con = db.get_connection()
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000

    def test_connections_are_thread_local(self, auth_env) -> None:
        db = auth_env.db
        db.init_db()
        results = {}

        def worker() -> None:
            con = db.get_connection()
            results["probe"] = con.execute("SELECT 1").fetchone()[0] == 1
            results["isolation"] = db.get_connection() is con

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=10)
        assert results["probe"] is True
        assert results["isolation"] is True


# ---------------------------------------------------------------------------
# Auth events -> JSONL audit stream (sanitized)
# ---------------------------------------------------------------------------


class TestAuthAuditEvents:
    def test_lifecycle_events_reach_the_stream(self, auth_env, client) -> None:
        assert _register(client, "audit@example.com").status_code == 201
        assert _login(client, "audit@example.com").status_code == 200
        client.post("/auth/logout", headers=UA)

        text = _stream_text(auth_env)
        assert '"event":"auth_register"' in text.replace(", ", ",")
        assert '"event":"auth_login_success"' in text
        assert '"event":"auth_logout"' in text

    def test_lockout_event_reaches_the_stream(self, auth_env, client) -> None:
        assert _register(client, "audit-lock@example.com").status_code == 201
        for _ in range(5):
            assert (
                _login(client, "audit-lock@example.com", password="bad-password-1")
                .status_code
                == 401
            )
        text = _stream_text(auth_env)
        assert '"event":"auth_lockout"' in text

    def test_failure_event_reaches_the_stream(self, auth_env, client) -> None:
        assert _register(client, "audit-fail@example.com").status_code == 201
        assert (
            _login(client, "audit-fail@example.com", password="bad-password-1").status_code
            == 401
        )
        text = _stream_text(auth_env)
        assert '"event":"auth_login_failure"' in text

    def test_stream_is_sanitized(self, auth_env, client) -> None:
        email = "sensitive@example.com"
        assert _register(client, email).status_code == 201
        login_response = _login(client, email)
        assert login_response.status_code == 200
        token = _set_cookie_token(login_response)
        client.post("/auth/logout", headers=UA)

        text = _stream_text(auth_env)
        # No raw email, no token, no password anywhere in the stream.
        assert email not in text
        assert "sensitive@" not in text
        assert token not in text
        assert PASSWORD not in text
        # Correlation hash of the (normalized) email IS present.
        expected_hash = hashlib.sha256(email.lower().encode("utf-8")).hexdigest()[:16]
        assert expected_hash in text

    def test_revoke_event_reaches_the_stream(self, auth_env, client) -> None:
        assert _register(client, "audit-revoke@example.com").status_code == 201
        assert _login(client, "audit-revoke@example.com").status_code == 200
        rows = client.get("/auth/sessions", headers=UA).json()
        client.delete(f"/auth/sessions/{rows[0]['id']}", headers=UA)
        text = _stream_text(auth_env)
        assert '"event":"auth_session_revoke"' in text


# ---------------------------------------------------------------------------
# CSRF origin posture (scope item: /auth/* validates Origin like the rest)
# ---------------------------------------------------------------------------


class TestAuthOriginCheck:
    def test_foreign_origin_on_register_is_403(self, auth_env, client) -> None:
        response = client.post(
            "/auth/register",
            json={"email": "origin@example.com", "password": PASSWORD},
            headers={**UA, "Origin": "https://evil.example"},
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Origin not allowed"}

    def test_foreign_origin_on_login_is_403(self, auth_env, client) -> None:
        response = client.post(
            "/auth/login",
            json={"email": "origin@example.com", "password": PASSWORD},
            headers={**UA, "Origin": "https://evil.example"},
        )
        assert response.status_code == 403

    def test_allowlisted_origin_on_login_passes(self, auth_env, client) -> None:
        # Dev allowlist default (config.cors_origins): localhost:3000.
        assert _register(client, "origin-ok@example.com").status_code == 201
        response = client.post(
            "/auth/login",
            json={"email": "origin-ok@example.com", "password": PASSWORD},
            headers={**UA, "Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200

    def test_absent_origin_on_login_passes(self, auth_env, client) -> None:
        # Non-browser / same-origin clients send no Origin — permitted this
        # wave (cookies are not yet consumed by protected routes; Wave D).
        assert _register(client, "origin-absent@example.com").status_code == 201
        assert _login(client, "origin-absent@example.com").status_code == 200


# ---------------------------------------------------------------------------
# Rate limiting (auth bucket wired through the Wave B middleware)
# ---------------------------------------------------------------------------


class TestAuthRateLimiting:
    def test_auth_bucket_applies_to_auth_routes(self, auth_env, client, monkeypatch) -> None:
        monkeypatch.setenv("TAX_RATE_LIMIT_AUTH_PER_MIN", "2")
        codes = [
            _login(client, "ghost@nowhere.test").status_code for _ in range(3)
        ]
        assert codes == [401, 401, 429]
        limited = client.post(
            "/auth/login",
            json={"email": "ghost@nowhere.test", "password": PASSWORD},
            headers=UA,
        )
        assert limited.status_code == 429
        body = limited.json()
        assert body["detail"] == "Rate limit exceeded"
        assert limited.headers.get("Retry-After") == str(body["retry_after_seconds"])

"""Hardening-edge tests (Sprint 3 Step B) — red first.

Covers the middleware stack added in create_app, in the documented
request order: body-cap -> security-headers -> origin-check -> rate-limit
-> CORS. Each short-circuit response (413/403/429) must also carry the
full security-header set — the headers control applies to every response
the app emits, not only to ones that reach a route.

Scope guards for this wave (no contract change): CORS itself stays the
Sprint-1 wildcard (allowlist + credentials land with the auth wave), and
rate-limit keys are client IPs (user-id keys land with auth).
"""
import os
import time

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The exact security-header set from the Sprint 3 design (§4). Values are
# compared exactly — a weakened policy must fail here.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def assert_security_headers(response) -> None:
    for name, value in SECURITY_HEADERS.items():
        actual = response.headers.get(name)
        assert actual == value, f"header {name}: expected {value!r}, got {actual!r}"


@pytest.fixture()
def client():
    """Fresh app per test (own rate-limiter state, dev docs)."""
    previous_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    try:
        from fastapi.testclient import TestClient

        from main import create_app

        with TestClient(create_app("dev")) as test_client:
            yield test_client
    finally:
        os.chdir(previous_cwd)


def _chat_payload(sid: str = "sid_hard1") -> dict:
    return {"message": "hi", "session": {"id": sid}}


class TestBodyCap:
    def test_oversized_body_is_413(self, client) -> None:
        # Content-Length (~1.1 MB) exceeds the documented 1 MB default.
        response = client.post(
            "/chat",
            json={"message": "x" * 1_100_000, "session": {"id": "sid_cap1"}},
        )
        assert response.status_code == 413
        assert response.json() == {"detail": "Request body too large"}

    def test_oversized_body_response_carries_security_headers(self, client) -> None:
        response = client.post(
            "/chat",
            json={"message": "x" * 1_100_000, "session": {"id": "sid_cap1"}},
        )
        assert response.status_code == 413
        assert_security_headers(response)

    def test_body_under_cap_passes(self, client) -> None:
        # A padded-but-legal session (~50 KB, under the 100 KB session cap)
        # sails through the body-cap middleware untouched.
        response = client.post(
            "/chat",
            json={
                "message": "hi",
                "session": {"id": "sid_cap2", "pad": "x" * 50_000},
            },
        )
        assert response.status_code == 200


class TestSecurityHeaders:
    def test_headers_on_health(self, client) -> None:
        response = client.get("/health")
        assert response.status_code in (200, 503)
        assert_security_headers(response)

    def test_headers_on_404(self, client) -> None:
        assert_security_headers(client.get("/definitely-not-a-route"))

    def test_headers_on_chat(self, client) -> None:
        response = client.post("/chat", json=_chat_payload())
        assert response.status_code == 200
        assert_security_headers(response)


class TestOriginCheck:
    def test_foreign_origin_on_chat_is_403(self, client) -> None:
        response = client.post(
            "/chat", json=_chat_payload(), headers={"Origin": "https://evil.example"}
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Origin not allowed"}

    def test_foreign_origin_response_carries_security_headers(self, client) -> None:
        response = client.post(
            "/chat", json=_chat_payload(), headers={"Origin": "https://evil.example"}
        )
        assert response.status_code == 403
        assert_security_headers(response)

    def test_foreign_origin_on_calculate_is_403(self, client) -> None:
        response = client.post(
            "/calculate",
            json={"salary": 100000},
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 403

    def test_allowlisted_origin_passes(self, client) -> None:
        # Dev default allowlist (config.cors_origins) is localhost:3000.
        response = client.post(
            "/chat",
            json=_chat_payload(),
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200

    def test_absent_origin_passes(self, client) -> None:
        # Same-origin / non-browser clients send no Origin — permitted THIS
        # wave; cookie hardening arrives with the auth wave.
        response = client.post("/chat", json=_chat_payload())
        assert response.status_code == 200

    def test_get_requests_are_never_origin_checked(self, client) -> None:
        response = client.get(
            "/health", headers={"Origin": "https://evil.example"}
        )
        assert response.status_code in (200, 503)


class TestRateLimiting:
    def test_limiter_allows_up_to_limit_then_denies(self) -> None:
        from rate_limit import RateLimiter

        limiter = RateLimiter()
        for _ in range(3):
            allowed, retry_after = limiter.check("key", 3, 60.0)
            assert allowed is True
            assert retry_after == 0
        allowed, retry_after = limiter.check("key", 3, 60.0)
        assert allowed is False
        assert retry_after >= 1

    def test_limiter_window_expiry_restores_budget(self) -> None:
        from rate_limit import RateLimiter

        limiter = RateLimiter()
        assert limiter.check("k", 1, 0.05)[0] is True
        assert limiter.check("k", 1, 0.05)[0] is False
        time.sleep(0.08)  # window (50 ms) elapses
        assert limiter.check("k", 1, 0.05)[0] is True

    def test_limiter_keys_are_independent(self) -> None:
        from rate_limit import RateLimiter

        limiter = RateLimiter()
        assert limiter.check("a", 1, 60.0)[0] is True
        assert limiter.check("b", 1, 60.0)[0] is True
        assert limiter.check("a", 1, 60.0)[0] is False

    def test_limiter_lru_cap_evicts_oldest_key(self) -> None:
        from rate_limit import RateLimiter

        limiter = RateLimiter(max_keys=2)
        limiter.check("a", 10, 60.0)
        limiter.check("b", 10, 60.0)
        limiter.check("c", 10, 60.0)  # evicts "a" (least recently used)
        assert limiter.check("a", 10, 60.0)[0] is True  # re-created cleanly

    def test_limiter_reset_clears_state(self) -> None:
        from rate_limit import RateLimiter

        limiter = RateLimiter()
        assert limiter.check("k", 1, 60.0)[0] is True
        assert limiter.check("k", 1, 60.0)[0] is False
        limiter.reset()
        assert limiter.check("k", 1, 60.0)[0] is True

    def test_integration_429_with_retry_after_header(self, client, monkeypatch) -> None:
        # Small limits via env (read at request time); the fresh app in the
        # fixture has its own limiter so no other test's traffic leaks in.
        monkeypatch.setenv("TAX_RATE_LIMIT_CHAT_PER_MIN", "1")
        monkeypatch.setenv("TAX_RATE_LIMIT_GLOBAL_PER_MIN", "1000")
        # 422 bodies still consume budget (the limiter runs before routing).
        first = client.post("/chat", json={"message": "hi", "session": {"id": "bad!!"}})
        assert first.status_code == 422
        second = client.post("/chat", json={"message": "hi", "session": {"id": "bad!!"}})
        assert second.status_code == 429
        body = second.json()
        assert body["detail"] == "Rate limit exceeded"
        assert isinstance(body["retry_after_seconds"], int)
        assert body["retry_after_seconds"] >= 1
        assert second.headers.get("Retry-After") == str(body["retry_after_seconds"])
        assert_security_headers(second)

    def test_integration_global_bucket_is_shared(self, client, monkeypatch) -> None:
        # One /chat then one /calculate: distinct class buckets, shared
        # global bucket — a global limit of 1 stops the second request.
        monkeypatch.setenv("TAX_RATE_LIMIT_GLOBAL_PER_MIN", "1")
        monkeypatch.setenv("TAX_RATE_LIMIT_CHAT_PER_MIN", "1000")
        monkeypatch.setenv("TAX_RATE_LIMIT_CALC_PER_MIN", "1000")
        first = client.post("/chat", json={"message": "hi", "session": {"id": "bad!!"}})
        assert first.status_code == 422
        second = client.post("/calculate", json={"salary": "abc"})
        assert second.status_code == 429

    def test_health_is_rate_limit_exempt(self, client, monkeypatch) -> None:
        monkeypatch.setenv("TAX_RATE_LIMIT_GLOBAL_PER_MIN", "1")
        for _ in range(3):
            response = client.get("/health")
            assert response.status_code in (200, 503)


class TestDocsGating:
    def test_prod_disables_docs(self) -> None:
        from fastapi.testclient import TestClient

        from main import create_app

        previous_cwd = os.getcwd()
        os.chdir(BACKEND_DIR)
        try:
            with TestClient(create_app("prod")) as prod_client:
                assert prod_client.get("/docs").status_code == 404
                assert prod_client.get("/redoc").status_code == 404
                assert prod_client.get("/openapi.json").status_code == 404
        finally:
            os.chdir(previous_cwd)

    def test_dev_keeps_docs_enabled(self) -> None:
        from fastapi.testclient import TestClient

        from main import create_app

        previous_cwd = os.getcwd()
        os.chdir(BACKEND_DIR)
        try:
            with TestClient(create_app("dev")) as dev_client:
                assert dev_client.get("/docs").status_code == 200
        finally:
            os.chdir(previous_cwd)

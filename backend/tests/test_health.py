"""GET /health tests (Sprint 3 Step B) — red first.

Contract (design §3): 200 {"status":"ok","checks":{"db":"ok","audit":
"ok"},"app_env","version"}; a failing check degrades the whole response
to 503 while naming the failing check; ?verbose=1 adds uptime + registry
keys ONLY in dev; the endpoint is public (no auth) and rate-limit
exempt. The db check must NEVER create the database file/directory — a
not-yet-provisioned database is exactly the degradation /health exists
to report.
"""
import os
import sqlite3

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def client():
    previous_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    try:
        from fastapi.testclient import TestClient

        from main import create_app

        with TestClient(create_app("dev")) as test_client:
            yield test_client
    finally:
        os.chdir(previous_cwd)


def _make_db(tmp_path):
    db = tmp_path / "taxassist.db"
    con = sqlite3.connect(str(db))
    try:
        con.execute("CREATE TABLE probe (x INTEGER)")
        con.commit()
    finally:
        con.close()
    return db


def _set_healthy_db(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TAX_DB_PATH", str(_make_db(tmp_path)))


class TestHealthOkShape:
    def test_ok_shape_and_contract_keys(self, client, monkeypatch, tmp_path) -> None:
        _set_healthy_db(monkeypatch, tmp_path)
        response = client.get("/health")  # no credentials — public endpoint
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"] == {"db": "ok", "audit": "ok"}
        assert body["app_env"] == "dev"
        assert body["version"] == "0.3.0"

    def test_no_auth_required(self, client, monkeypatch, tmp_path) -> None:
        _set_healthy_db(monkeypatch, tmp_path)
        # Explicitly no auth machinery exists yet; the endpoint must answer
        # a bare request (the auth wave will keep /health public).
        response = client.get("/health", headers={"Authorization": ""})
        assert response.status_code == 200

    def test_db_check_never_creates_the_database(
        self, client, monkeypatch, tmp_path
    ) -> None:
        # A fresh deployment reports degraded — /health must not conjure
        # the db file into existence as a side effect of probing it.
        missing = tmp_path / "fresh" / "taxassist.db"
        monkeypatch.setenv("TAX_DB_PATH", str(missing))
        response = client.get("/health")
        assert response.status_code == 503
        assert not missing.exists()


class TestHealthDegraded:
    def test_degraded_when_db_path_cannot_be_opened(
        self, client, monkeypatch, tmp_path
    ) -> None:
        # Parent directory does not exist -> the db cannot be opened.
        monkeypatch.setenv("TAX_DB_PATH", str(tmp_path / "missing" / "taxassist.db"))
        response = client.get("/health")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["checks"]["db"] != "ok"
        assert body["checks"]["audit"] == "ok"  # failing check is named precisely

    def test_degraded_when_db_file_is_not_a_database(
        self, client, monkeypatch, tmp_path
    ) -> None:
        db = tmp_path / "corrupt.db"
        db.write_bytes(b"this is not a sqlite database")
        monkeypatch.setenv("TAX_DB_PATH", str(db))
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["checks"]["db"] != "ok"

    def test_degraded_when_audit_dir_missing(
        self, client, monkeypatch, tmp_path
    ) -> None:
        import main as main_module

        _set_healthy_db(monkeypatch, tmp_path)
        monkeypatch.setattr(
            main_module.audit, "audit_dir", str(tmp_path / "no" / "such" / "dir")
        )
        response = client.get("/health")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["checks"]["audit"] != "ok"
        assert body["checks"]["db"] == "ok"


class TestVerboseGating:
    def test_verbose_adds_uptime_and_registry_in_dev(
        self, client, monkeypatch, tmp_path
    ) -> None:
        _set_healthy_db(monkeypatch, tmp_path)
        body = client.get("/health", params={"verbose": "1"}).json()
        assert "uptime_seconds" in body
        assert isinstance(body["uptime_seconds"], (int, float))
        assert isinstance(body.get("registry"), list)
        assert "fy_2025_26" in body["registry"]

    def test_no_verbose_keys_without_query_param(
        self, client, monkeypatch, tmp_path
    ) -> None:
        _set_healthy_db(monkeypatch, tmp_path)
        body = client.get("/health").json()
        assert "uptime_seconds" not in body
        assert "registry" not in body

    def test_verbose_keys_absent_in_prod(self, monkeypatch, tmp_path) -> None:
        from fastapi.testclient import TestClient

        from main import create_app

        _set_healthy_db(monkeypatch, tmp_path)
        previous_cwd = os.getcwd()
        os.chdir(BACKEND_DIR)
        try:
            with TestClient(create_app("prod")) as prod_client:
                response = prod_client.get("/health", params={"verbose": "1"})
                assert response.status_code == 200
                body = response.json()
                assert "uptime_seconds" not in body
                assert "registry" not in body
                assert body["app_env"] == "prod"
        finally:
            os.chdir(previous_cwd)


class TestHealthPublicAndExempt:
    def test_health_exempt_from_rate_limiting(self, client, monkeypatch) -> None:
        # A 1-request/min global budget would stop any limited route; /health
        # must keep answering (explicitly exempt per design §4).
        monkeypatch.setenv("TAX_RATE_LIMIT_GLOBAL_PER_MIN", "1")
        for _ in range(3):
            response = client.get("/health")
            assert response.status_code in (200, 503)

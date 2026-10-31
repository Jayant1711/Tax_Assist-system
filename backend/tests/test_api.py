"""FastAPI happy-path tests (first API coverage — ISSUE #16).

Covers /chat and /calculate happy paths only; validation-error paths
(422s) and /history behavior arrive in a later issue. The app resolves
its relative "logs" directory against the process cwd, so the module-
scoped client fixture chdirs into backend/ for the duration of these
tests and restores the previous cwd afterwards.
"""
import os

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def test_chat_happy_path_session_round_trip(client) -> None:
    response = client.post(
        "/chat",
        json={
            "message": "I am a software engineer earning 18 LPA",
            "session": {"id": "sid_apitest1", "phase": "PROFILING"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["extracted"]  # non-empty extraction list
    session = body["session"]
    assert session.get("salary") == 1_800_000  # 18 LPA round-trips in the session
    assert body["tax_report"] is not None      # real-time computation gate


def test_calculate_happy_path(client) -> None:
    response = client.post(
        "/calculate",
        json={"id": "sid_apitest1", "salary": 1_800_000, "80c": 150_000},
    )
    assert response.status_code == 200
    body = response.json()
    assert "old_regime" in body
    assert "new_regime" in body
    assert "recommendation" in body
    # Sprint 2 (ADR-008): results report the resolved rule-set identity.
    assert body["tax_year"] == "2024-25"
    assert body["assessment_year"] == "2025-26"
    assert body["fy_label"] == "FY 2024-25 (AY 2025-26)"

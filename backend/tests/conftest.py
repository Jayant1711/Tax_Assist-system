"""Shared Sprint 3 Wave D fixtures — the mechanical-adaptation toolkit.

The ADR-013 contract swap (docs/sprint3-design.md §2) makes /chat,
/calculate and /history owned, server-side-session endpoints:

- every wire-level test needs a REGISTERED + LOGGED-IN TestClient (the
  opaque session cookie persists in the client's cookie jar), and
- session ids are SERVER-ISSUED (uuid4 hex from POST /sessions) — the
  client-supplied session dict is gone from the wire.

This module is the documented adaptation fixture set (design §10):
``register_and_login`` / ``make_session`` plain helpers plus the
``authed_client`` / ``session_id`` function-scoped fixtures built on the
module-level app. Every adaptation comment in the adapted test files
points here.
"""
import os
import uuid

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A fixed User-Agent for every request made through these helpers: auth
# session rows are UA-hash bound at issue time (ADR-012), so requests must
# present the SAME UA as the login that issued the cookie. The helper sets
# it as the client's DEFAULT header so every later request matches.
UA = {"User-Agent": "test-wave-d-agent/1.0"}
PASSWORD = "correct horse battery staple"  # 28 chars — policy-legal


def register_and_login(client, email=None):
    """Register a fresh account and log this client in (cookie retained).

    Returns the email (unique per call, so repeats on one client model a
    second user — the ownership tests rely on that).
    """
    email = email or "wave-d-{}@example.com".format(uuid.uuid4().hex[:12])
    # Set the UA default BEFORE the first request so register, login and
    # every subsequent request present one consistent UA hash.
    client.headers.update(UA)
    response = client.post(
        "/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    response = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return email


def make_session(client) -> str:
    """Bootstrap one server-side session; returns its server-issued id."""
    response = client.post("/sessions")
    assert response.status_code == 200, response.text
    session_id = response.json()["session_id"]
    assert isinstance(session_id, str) and session_id
    return session_id


def _open_client():
    """TestClient on the module-level app, with the store re-anchored.

    Re-runs db.init_db() against the CURRENT TAX_DB_PATH: earlier modules
    in the suite re-point the store at (deleted) per-test tmp paths, so
    every client re-anchors before issuing requests (idempotent, cheap).
    """
    import db as db_module
    from fastapi.testclient import TestClient

    from main import app

    db_module.init_db()
    return TestClient(app)


@pytest.fixture()
def authed_client():
    """A registered + logged-in TestClient (Wave D protected surface).

    chdirs into backend/ for the duration (main resolves its relative
    logs directories against the process cwd) and restores afterwards.
    """
    previous_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    try:
        client = _open_client()
        with client as test_client:
            register_and_login(test_client)
            yield test_client
    finally:
        os.chdir(previous_cwd)


@pytest.fixture()
def session_id(authed_client):
    """One server-issued app-session id owned by authed_client's user."""
    return make_session(authed_client)

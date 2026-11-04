# tests/test_recommendation_events.py — Sprint 5 Wave 1 (P2 / ADR-017)
"""Acceptance-capture contract tests: the recommendation_events table,
shown-event recording from the closing turn, and the action endpoint
(auth + ownership + validation)."""
import uuid

import pytest

from tests.conftest import (  # noqa: E402
    BACKEND_DIR, _open_client, make_session, register_and_login,
)


# ---------------------------------------------------------------------------
# migration (db-level)
# ---------------------------------------------------------------------------

def test_migration_applies() -> None:
    import db

    conn = db.get_connection()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "recommendation_events" in tables


# ---------------------------------------------------------------------------
# closing-turn capture (the shown events land in the table)
# ---------------------------------------------------------------------------

@pytest.fixture()
def closed_session():
    """Drive one discovery to the closing turn.

    Returns (client, sid, user_id, events) — the client stays logged in
    for the action endpoints; events are read via the db helper with the
    real user id (fetched from users by the registered email).
    """
    import os

    import db as db_mod
    from fastapi.testclient import TestClient

    from main import app

    previous_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    client = None
    try:
        db_mod.init_db()
        client = TestClient(app)
        email = register_and_login(client)
        sid = make_session(client)
        for msg in ["I am a software engineer earning 24 lakhs",
                    "1.5 lakhs in PPF", "25k health insurance", "no",
                    "no", "no", "no", "no", "no"]:
            r = client.post("/chat", json={"message": msg,
                                           "session_id": sid})
            assert r.status_code == 200
        user_id = db_mod.get_connection().execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()[0]
        events = db_mod.list_recommendation_events(sid, user_id)
        return client, sid, user_id, events
    finally:
        os.chdir(previous_cwd)


class TestClosingTurnCapture:
    def test_shown_events_recorded(self, closed_session) -> None:
        client, sid, user_id, events = closed_session
        # the closing turn ranked and showed material recommendations
        assert len(events) >= 1
        assert all(ev["savings_engine"] >= 0 for ev in events)
        assert all(ev["action"] in (None, "accepted", "rejected",
                                    "ignored") for ev in events)

    def test_events_scoped_to_session(self, closed_session) -> None:
        client, sid, user_id, events = closed_session
        assert all(ev["session_id"] == sid for ev in events)


# ---------------------------------------------------------------------------
# action endpoint (auth + ownership + validation)
# ---------------------------------------------------------------------------

class TestActionEndpoint:
    def test_action_requires_auth(self) -> None:
        from fastapi.testclient import TestClient

        from main import app

        import os

        previous = os.getcwd()
        os.chdir(BACKEND_DIR)
        try:
            fresh = TestClient(app)  # no login
            r = fresh.post(
                "/sessions/sess_x/recommendations/ev_1/action",
                json={"action": "accepted"})
            assert r.status_code in (401, 403)
        finally:
            os.chdir(previous)

    def test_action_updates_event(self, closed_session) -> None:
        client, sid, user_id, events = closed_session
        event_id = events[0]["id"]
        r = client.post(
            f"/sessions/{sid}/recommendations/{event_id}/action",
            json={"action": "accepted"})
        assert r.status_code == 200
        assert r.json()["action"] == "accepted"

    def test_action_validates_value(self, closed_session) -> None:
        client, sid, user_id, events = closed_session
        r = client.post(
            f"/sessions/{sid}/recommendations/{events[0]['id']}/action",
            json={"action": "bogus"})
        assert r.status_code == 422

    def test_unknown_event_404(self, authed_client, session_id) -> None:
        r = authed_client.post(
            f"/sessions/{session_id}/recommendations/{uuid.uuid4().hex}/action",
            json={"action": "accepted"})
        assert r.status_code == 404

    def test_foreign_session_404(self, authed_client) -> None:
        r = authed_client.post(
            "/sessions/not-mine/recommendations/whatever/action",
            json={"action": "accepted"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# list endpoint
# ---------------------------------------------------------------------------

class TestListEndpoint:
    def test_list_shows_events_newest_first(self, closed_session) -> None:
        client, sid, user_id, events = closed_session
        r = client.get(f"/sessions/{sid}/recommendations")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) >= 1
        assert rows[0]["created_at"] >= rows[-1]["created_at"]

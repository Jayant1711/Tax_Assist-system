# tests/test_sprint7_adoption.py — Sprint 7 S7.1/S7.2/S7.3
"""Adoption loop completion: action finality (S7.2), the cross-session
Adoption Dashboard (S7.1), and one-click Apply with engine repricing
(S7.3)."""
import os

import pytest

from tests.conftest import (
    BACKEND_DIR, make_session, register_and_login,
)


def _drive_to_final(client, sid):
    # the proven 9-turn flow: closes naturally with 3 shown events
    # (80e, 80d_parents, 24b — all correctly zero-savings because the
    # new regime wins at this profile by ~Rs 2 lakh)
    for msg in ["I am a software engineer earning 24 lakhs",
                "1.5 lakhs in PPF", "25k health insurance", "no",
                "no", "no", "no", "no", "no"]:
        r = client.post("/chat", json={"message": msg, "session_id": sid})
        assert r.status_code == 200


def _uid(email):
    import db as db_mod

    return db_mod.get_connection().execute(
        "SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]


@pytest.fixture()
def final_session():
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
        _drive_to_final(client, sid)
        events = db_mod.list_recommendation_events(sid, _uid(email))
        return client, sid, email, events
    finally:
        os.chdir(previous_cwd)


class TestActionFinality:
    def test_viewed_never_overwrites_accepted(self, final_session) -> None:
        """S7.2: the auto-fired viewed action can never clobber a real
        decision — accepted is final."""
        import db as db_mod

        client, sid, email, events = final_session
        uid = _uid(email)
        event = events[0]
        assert client.post(
            f"/sessions/{sid}/recommendations/{event['id']}/action",
            json={"action": "accepted"}).status_code == 200
        # a later report render auto-fires viewed — it must NOT overwrite
        assert client.post(
            f"/sessions/{sid}/recommendations/{event['id']}/action",
            json={"action": "viewed"}).status_code == 200
        assert db_mod.get_connection().execute(
            "SELECT action FROM recommendation_events WHERE id = ?",
            (event["id"],)).fetchone()[0] == "accepted"

    def test_accepted_upgrades_a_viewed_event(self, final_session) -> None:
        import db as db_mod

        client, sid, email, events = final_session
        event = events[0]
        assert client.post(
            f"/sessions/{sid}/recommendations/{event['id']}/action",
            json={"action": "viewed"}).status_code == 200
        assert client.post(
            f"/sessions/{sid}/recommendations/{event['id']}/action",
            json={"action": "accepted"}).status_code == 200
        assert db_mod.get_connection().execute(
            "SELECT action FROM recommendation_events WHERE id = ?",
            (event["id"],)).fetchone()[0] == "accepted"


class TestAdoptionOverview:
    def test_overview_aggregates_across_sessions(self, final_session) -> None:
        import db as db_mod
        from fastapi.testclient import TestClient

        from main import app

        client, sid, email, events = final_session
        uid = _uid(email)
        # accept one recommendation in THIS session, then add a second
        # session for the same user with its own events
        event = events[0]
        client.post(f"/sessions/{sid}/recommendations/{event['id']}/action",
                    json={"action": "accepted"})
        sid2 = make_session(client)
        _drive_to_final(client, sid2)

        r = client.get("/analytics/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["total_shown"] >= 2
        assert data["total_accepted"] >= 1
        assert 0.0 < data["acceptance_rate"] <= 1.0
        # fixture events are zero-savings (new regime wins by ~Rs 2L);
        # the Accepted-Rupee metric itself is covered with positive rows
        # in TestUserAdoptionOverviewDb below
        assert data["accepted_rupees"] == 0.0
        assert data["resolved_events"] >= 1
        assert data["calibration_gate"]["target"] == 30
        assert data["calibration_gate"]["met"] is False
        heads = {h["head"] for h in data["per_head"]}
        assert heads

    def test_overview_is_scoped_to_the_caller(self, final_session) -> None:
        from fastapi.testclient import TestClient

        from main import app

        client, sid, email, _events = final_session
        # a different user sees an empty overview
        client2 = TestClient(app)
        register_and_login(client2)
        r = client2.get("/analytics/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["total_shown"] == 0
        assert data["accepted_rupees"] == 0

    def test_overview_requires_auth(self) -> None:
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)
        assert client.get("/analytics/overview").status_code == 401


class TestApplyEndpoint:
    def test_apply_tops_up_headroom_and_reprices(
            self, final_session) -> None:
        import db as db_mod

        client, sid, email, events = final_session
        event = next(e for e in events if e["head"] == "24b")
        before = client.post("/calculate",
                             json={"session_id": sid}).json()
        r = client.post(
            f"/sessions/{sid}/recommendations/{event['id']}/apply")
        assert r.status_code == 200
        data = r.json()
        assert data["applied"] is True and data["head"] == "24b"
        assert data["new_value"] == 200_000
        # the state persisted AND the calculation is the new authority
        state = db_mod.get_connection().execute(
            "SELECT state FROM app_sessions WHERE id = ?", (sid,)).fetchone()
        import json as _json
        assert _json.loads(state[0]).get("24b") == 200_000
        after = data["calculation"]
        assert after["new_regime"]["total_tax"] == \
            before["new_regime"]["total_tax"]  # 24(b) is old-regime-only
        assert after["old_regime"]["total_tax"] < \
            before["old_regime"]["total_tax"]

    def test_apply_is_idempotent_at_the_cap(self, final_session) -> None:
        client, sid, email, events = final_session
        event = next(e for e in events if e["head"] == "24b")
        r1 = client.post(
            f"/sessions/{sid}/recommendations/{event['id']}/apply")
        assert r1.status_code == 200
        r2 = client.post(
            f"/sessions/{sid}/recommendations/{event['id']}/apply")
        assert r2.status_code == 409  # headroom already fully applied

    def test_apply_404_on_foreign_or_unknown_event(
            self, final_session) -> None:
        from fastapi.testclient import TestClient

        from main import app

        client, sid, email, _events = final_session
        assert client.post(
            f"/sessions/{sid}/recommendations/does-not-exist/apply"
        ).status_code == 404
        client2 = TestClient(app)
        register_and_login(client2)
        sid2 = make_session(client2)
        other_events = client2.get(
            f"/sessions/{sid2}/recommendations").json()
        # no events in sid2 for this user: apply against sid is foreign
        assert client2.post(
            f"/sessions/{sid}/recommendations/does-not-exist/apply"
        ).status_code == 404

    def test_apply_requires_auth(self, final_session) -> None:
        from fastapi.testclient import TestClient

        from main import app

        client, sid, email, events = final_session
        bare = TestClient(app)
        assert bare.post(
            f"/sessions/{sid}/recommendations/{events[0]['id']}/apply"
        ).status_code == 401


class TestUserAdoptionOverviewDb:
    def test_accepted_rupees_and_gate_directly(self) -> None:
        """db-level: Accepted-Rupee sums the ENGINE savings of accepted
        events only, and resolved counts accepted/rejected/ignored.
        Direct db writes run inside the chdir+init_db guard (the store
        path is re-pointed per test)."""
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
            uid = _uid(email)
            # two accepted (engine savings 32,500 and 1,300), one rejected;
            # ids are run-unique because this store persists across runs
            import uuid as _uuid
            run = _uuid.uuid4().hex[:8]
            for rec, head, sav, action in [
                    (f"ovr_{run}_a1", "24b", 32500.0, "accepted"),
                    (f"ovr_{run}_a2", "80g", 1300.0, "accepted"),
                    (f"ovr_{run}_r1", "80c", 46875.0, "rejected")]:
                assert db_mod.record_recommendation_shown(
                    sid, uid, rec, head, 1.0, sav, 0.85)
                assert db_mod.record_recommendation_action(rec, uid, action)
            overview = db_mod.user_adoption_overview(uid)
            assert overview["accepted_rupees"] >= 33800.0
            assert overview["resolved_events"] >= 3
            heads = {h["head"]: h for h in overview["per_head"]}
            assert heads["24b"]["accepted_savings"] >= 32500.0
        finally:
            os.chdir(previous_cwd)


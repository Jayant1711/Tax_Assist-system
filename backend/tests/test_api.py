"""FastAPI happy-path tests (first API coverage — ISSUE #16).

Covers /chat and /calculate happy paths; validation-error paths (422s)
live in test_validation.py, /history behavior in its own class there.

Wave D adaptation (mechanical, documented — design §10): the ADR-013
contract swap moved session state server-side, so /chat takes
{message, session_id}, /calculate takes {session_id}, and both require
an authenticated user (ADR-012) via the shared authed_client fixture
(tests/conftest.py); the session id is SERVER-ISSUED (POST /sessions).
Assertion kinds are unchanged: income still round-trips into the
response session (now the read-only projection), the real-time gate
still fires, and /calculate still reports the full shape + ADR-008
identity fields.
"""
from tests.conftest import make_session


def test_chat_happy_path_session_round_trip(authed_client) -> None:
    # Was: {"message", "session": {"id": "sid_apitest1", ...}} with a
    # client-chosen id. Wave D: bootstrap a server-uuid session and carry
    # ONLY the id on the wire.
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
    assert body["extracted"]  # non-empty extraction list
    assert body["session_id"] == sid           # server-issued id echoes back
    session = body["session"]                  # read-only projection (ADR-013)
    assert session.get("salary") == 1_800_000  # 18 LPA round-trips in the session
    assert body["tax_report"] is not None      # real-time computation gate


def test_calculate_happy_path(authed_client) -> None:
    # Was: the full engine payload {id, salary, 80c} on the wire. Wave D:
    # the same numbers are booked through the conversation (server-side
    # state), then /calculate computes from that state via the id alone.
    sid = make_session(authed_client)
    chat = authed_client.post(
        "/chat",
        json={"message": "my salary is 1800000", "session_id": sid},
    )
    assert chat.status_code == 200
    response = authed_client.post("/calculate", json={"session_id": sid})
    assert response.status_code == 200
    body = response.json()
    assert "old_regime" in body
    assert "new_regime" in body
    assert "recommendation" in body
    # Sprint 2 (ADR-008): results report the resolved rule-set identity.
    # Step A3 flipped the registry default — an unpinned call now resolves
    # FY 2025-26 (the matrix file pins both years explicitly).
    assert body["tax_year"] == "2025-26"
    assert body["assessment_year"] == "2026-27"
    assert body["fy_label"] == "FY 2025-26 (AY 2026-27)"

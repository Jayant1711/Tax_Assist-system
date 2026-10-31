"""Request validation + global exception handler tests (ISSUE #2 — H5/N1).

Wave D adaptation (mechanical, documented — design §10 / ADR-013): the
client no longer supplies session state, so the payload-validation rows
moved to the SERVER-STATE boundaries. Concretely, per row:

- /chat + /calculate request bodies shrank to {message, session_id} /
  {session_id, tax_year?}; an old-style body is a 422 (the dedicated
  contract rows live in test_session_store.py; here old-style bodies
  appear only where the original test POSTed one, and the 422 it asserts
  now comes from the contract guard instead of the payload validator).
- rows about client-supplied STATE are re-homed on the server-state load
  boundary: the state is seeded through the store (tests are trusted
  writers — the only way an invalid state can exist), and BOTH /chat and
  /calculate refuse it with the same 422 via _validate_session_payload
  (main._load_owned_state). The validator rows themselves are UNCHANGED
  and are additionally pinned unit-level in
  TestSessionPayloadValidatorRows below.
- /calculate's old ge/le model rows died with the client payload; where a
  row can no longer exist on any wire path (negative income can never be
  written — NLP clamps to 0..1e11) the test pins that write-path
  guarantee instead. No assertion is weakened beyond this documented
  contract change.

The global Exception handler must still return a sanitized 500 with no
stack details, and the 422 body must describe errors without echoing
attacker input — both unchanged.
"""
import json
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


@pytest.fixture(scope="module")
def lenient_client():
    """TestClient that lets the app's global Exception handler respond.

    Starlette's ServerErrorMiddleware re-raises after the handler runs, so
    the exception would otherwise surface inside the test client itself.
    """
    previous_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    try:
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        os.chdir(previous_cwd)


def _seed_state(authed_client, session_id: str, state) -> None:
    """Seed a server-side state (trusted test write into app_sessions).

    Tests bypass the request surface ON PURPOSE: pre-Wave-D these states
    arrived on the wire; Wave D stores are written by the server only, so
    the tests exercise the load boundary by writing directly. The id key
    is forced to the row id so the validator's id row holds.
    """
    import db

    assert isinstance(state, dict)
    seeded = {"id": session_id, **state}
    db.execute(
        "UPDATE app_sessions SET state = ? WHERE id = ?",
        (json.dumps(seeded, default=str), session_id),
    )


class TestCalculateEndpointValidation:
    def test_rejects_non_numeric_salary(self, authed_client, session_id) -> None:
        # Was: body {"salary": "abc"} -> 422 at the CalculateRequest row.
        # Wave D: the same row guards the server-state load boundary.
        _seed_state(authed_client, session_id, {"salary": "abc"})
        response = authed_client.post("/calculate", json={"session_id": session_id})
        assert response.status_code == 422

    def test_rejects_non_dict_capital_gain_entry(self, authed_client, session_id) -> None:
        _seed_state(authed_client, session_id, {"capital_gains": ["oops"]})
        response = authed_client.post("/calculate", json={"session_id": session_id})
        assert response.status_code == 422

    def test_rejects_formatted_amount_string(self, authed_client, session_id) -> None:
        # Indian-style digit grouping is not machine-coercible → 422 (the
        # string-amount row of the state validator; nothing coerces on the
        # server-side path).
        _seed_state(
            authed_client,
            session_id,
            {"capital_gains": [{"type": "equity_ltcg", "amount": "2,00,000"}]},
        )
        response = authed_client.post("/calculate", json={"session_id": session_id})
        assert response.status_code == 422

    def test_plain_numeric_string_amount_no_longer_exists(self, authed_client, session_id) -> None:
        # Was: pydantic v2 lax mode coerced "200000" → 200000.0 on the
        # client payload (documented). Wave D: the payload is gone — string
        # amounts are REJECTED at the state load boundary (row above) and
        # the numeric value computes identically, which is what this
        # adapted row pins (cg income 200000 lands in taxable_income).
        _seed_state(
            authed_client,
            session_id,
            {"capital_gains": [{"type": "equity_ltcg", "amount": 200000}]},
        )
        response = authed_client.post("/calculate", json={"session_id": session_id})
        assert response.status_code == 200
        body = response.json()
        assert body["old_regime"]["taxable_income"] == 200000.0

    def test_negative_salary_can_never_reach_a_report(self, authed_client, session_id) -> None:
        # Was: body {"salary": -5} -> 422 at the CalculateRequest ge=0 row.
        # Wave D: the write path cannot produce one — NLP clamps every
        # written amount into 0..1e11 — so the adapted row pins that no
        # negative salary can exist in the projected state after a turn
        # (the numeric row itself is unchanged; /chat already applied it
        # pre-Wave-D).
        response = authed_client.post(
            "/chat",
            json={"message": "my salary is -500000", "session_id": session_id},
        )
        assert response.status_code == 200
        salary = response.json()["session"].get("salary")
        assert salary is None or salary >= 0

    def test_rejects_out_of_range_age(self, authed_client, session_id) -> None:
        # The 0..120 age row now guards the server-state load boundary.
        _seed_state(authed_client, session_id, {"age": 999})
        response = authed_client.post("/calculate", json={"session_id": session_id})
        assert response.status_code == 422

    def test_ignores_junk_extra_keys(self, authed_client, session_id) -> None:
        # The shrunk request model keeps extra="ignore": old-contract junk
        # keys ride along without affecting the computation.
        response = authed_client.post(
            "/calculate",
            json={
                "session_id": session_id,
                "phase": "FINAL",
                "history": [1, 2, 3],
            },
        )
        assert response.status_code == 200
        body = response.json()
        for key in ("old_regime", "new_regime", "recommendation", "savings", "efficiency_score"):
            assert key in body

    def test_frontend_payload_shape_and_numbers_unchanged(self, authed_client, session_id) -> None:
        # Sprint 2 (ADR-008): pinned to fy_2024_25 (both here and in the
        # reference below) so the numeric-parity check survives the Step A3
        # default flip to fy_2025_26. Wave D: the old wire payload is now
        # the SEEDED server state; the endpoint must compute exactly what
        # the engine computes on it (guards the engine-default handling,
        # e.g. the registry professional-tax default for salaried users).
        payload = {
            "salary": 1800000,
            "80c": 150000,
            "profile": "Salaried",
        }
        _seed_state(authed_client, session_id, payload)
        response = authed_client.post(
            "/calculate",
            json={"session_id": session_id, "tax_year": "fy_2024_25"},
        )
        assert response.status_code == 200
        body = response.json()
        for key in ("old_regime", "new_regime", "recommendation", "savings", "efficiency_score"):
            assert key in body
        # Numeric parity: the endpoint must compute exactly what the engine
        # computes on the raw payload.
        from main import engine

        reference = engine.calculate_tax_advanced(
            dict(payload), tax_year="fy_2024_25"
        )
        assert body["old_regime"]["total_tax"] == reference["old_regime"].total_tax
        assert body["new_regime"]["total_tax"] == reference["new_regime"].total_tax
        assert body["recommendation"] == reference["recommendation"]
        assert body["savings"] == reference["savings"]
        assert body["efficiency_score"] == reference["efficiency_score"]


class TestChatEndpointValidation:
    def test_rejects_non_numeric_income_in_session(self, authed_client, session_id) -> None:
        _seed_state(authed_client, session_id, {"salary": "abc"})
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": session_id}
        )
        assert response.status_code == 422

    def test_rejects_bad_capital_gain_amount_in_session(self, authed_client, session_id) -> None:
        _seed_state(
            authed_client, session_id, {"capital_gains": [{"amount": "x"}]}
        )
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": session_id}
        )
        assert response.status_code == 422

    def test_rejects_oversized_message(self, authed_client, session_id) -> None:
        response = authed_client.post(
            "/chat", json={"message": "x" * 5000, "session_id": session_id}
        )
        assert response.status_code == 422

    def test_rejects_oversized_session_state(self, authed_client, session_id) -> None:
        # Was: a 150KB pad inside the client session dict -> 422. Wave D:
        # the 100KB cap guards the STORED state at the load boundary; the
        # test seeds the oversized state directly (save_state would refuse
        # it — that store-side cap is pinned in test_session_store.py).
        import db

        oversized = {"id": session_id, "pad": "x" * 150_000}
        db.execute(
            "UPDATE app_sessions SET state = ? WHERE id = ?",
            (json.dumps(oversized), session_id),
        )
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": session_id}
        )
        assert response.status_code == 422

    def test_valid_session_still_ok(self, authed_client, session_id) -> None:
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": session_id}
        )
        assert response.status_code == 200


class TestGlobalExceptionHandler:
    def test_unhandled_exception_returns_sanitized_500(self, lenient_client) -> None:
        from fastapi.routing import APIRoute

        from main import app

        async def probe() -> None:
            raise RuntimeError("boom-secret-stack-details")

        route = APIRoute("/_boom_probe", probe, methods=["POST"])
        app.router.routes.append(route)
        try:
            response = lenient_client.post("/_boom_probe", json={})
            assert response.status_code == 500
            assert response.json() == {"detail": "Internal server error"}
            assert "boom-secret-stack-details" not in response.text
            assert "RuntimeError" not in response.text
        finally:
            app.router.routes.remove(route)


class TestNonFiniteRejection:
    """Non-finite floats (inf/nan) must be clean 422s, never sanitized 500s
    and never persisted to the blackbox while the audit entry is skipped.

    Wave D: the client can no longer POST state, so the inf/nan rows are
    pinned on the server-state load boundary — the state is seeded with
    the non-finite value (json round-trips Infinity/NaN) and /chat must
    refuse it before NLP/engine see it. The old raw-body posts are kept
    for the two legacy /calculate bodies (they now 422 at the request
    model — session_id required — and use an AUTHED client because the
    auth dependency resolves before body validation).
    """

    def test_calculate_rejects_infinite_salary(self, authed_client) -> None:
        # Old-contract body: session_id is required now, so this is a 422
        # at the request model (the 1e309 inf never reaches the engine).
        response = authed_client.post("/calculate", content='{"salary": 1e309}',
                                      headers={"Content-Type": "application/json"})
        assert response.status_code == 422

    def test_calculate_rejects_infinite_capital_gain_amount(self, authed_client) -> None:
        response = authed_client.post(
            "/calculate",
            content='{"capital_gains": [{"type": "equity_ltcg", "amount": 1e309}]}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_chat_rejects_infinite_salary_in_stored_state(self, authed_client, session_id) -> None:
        _seed_state(authed_client, session_id, {"salary": float("inf")})
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": session_id}
        )
        assert response.status_code == 422

    def test_chat_rejects_nan_salary_in_stored_state(self, authed_client, session_id) -> None:
        _seed_state(authed_client, session_id, {"salary": float("nan")})
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": session_id}
        )
        assert response.status_code == 422

    def test_finite_boundary_still_valid(self, authed_client, session_id) -> None:
        # le=1e11 is inclusive and 1e11 is finite: the boundary values must
        # keep computing (regression guard), now via the server state.
        _seed_state(authed_client, session_id, {"salary": 1e11})
        assert authed_client.post(
            "/calculate", json={"session_id": session_id}
        ).status_code == 200
        _seed_state(
            authed_client,
            session_id,
            {"capital_gains": [{"type": "equity_ltcg", "amount": 1e11}]},
        )
        assert authed_client.post(
            "/calculate", json={"session_id": session_id}
        ).status_code == 200


class TestValidationErrorResponse:
    """The 422 body must describe the error, never echo the attacker input.

    Wave D: the /calculate and /chat rows use an AUTHED client — the auth
    dependency resolves before body validation, so an anonymous request
    would 401 before ever reaching the 422 under test.
    """

    def test_body_shape_and_no_input_echo(self, authed_client) -> None:
        response = authed_client.post("/calculate", json={"salary": "abc"})
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == "Validation error"
        assert body["errors"], "at least one error entry"
        entry = body["errors"][0]
        assert set(entry) == {"loc", "msg", "type"}
        assert all(isinstance(part, str) for part in entry["loc"])
        assert "abc" not in response.text

    def test_large_invalid_input_not_reflected(self, authed_client) -> None:
        # ~100KB session that fails for an unrelated reason: with the
        # default handler the 'input' echo made the body ~100KB. Wave D:
        # the trigger is now the legacy session-dict key (the contract
        # guard fires before anything reads the payload); the reflection
        # guard is unchanged.
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session": {"id": "../evil", "pad": "x" * 99_000}},
        )
        assert response.status_code == 422
        assert len(response.content) < 2000
        assert "xxxx" not in response.text

    def test_errors_capped_at_20(self, client) -> None:
        # Wave D adaptation: a single request can no longer carry 25
        # independently-invalid engine fields (the /calculate body shrank
        # to {session_id, tax_year}), so the 20-entry cap is pinned against
        # the app's RequestValidationError handler via the same probe-route
        # pattern TestGlobalExceptionHandler uses — cap logic and response
        # shape are unchanged.
        from fastapi.exceptions import RequestValidationError
        from fastapi.routing import APIRoute

        from main import app

        async def probe() -> None:
            raise RequestValidationError(
                [
                    {
                        "loc": ("body", f"field{i}"),
                        "msg": "bad",
                        "type": "value_error",
                        "input": "x",
                    }
                    for i in range(25)
                ]
            )

        route = APIRoute("/_validation_probe", probe, methods=["POST"])
        app.router.routes.append(route)
        try:
            response = client.post("/_validation_probe", json={})
            assert response.status_code == 422
            assert len(response.json()["errors"]) == 20
        finally:
            app.router.routes.remove(route)


class TestSessionPayloadValidatorRows:
    """The Sprint-1+2 session validator rows, pinned unit-level.

    Wave D adaptation of the former TestChatRequestSessionValidators: the
    rows used to be exercised through ChatRequest's `session` field (the
    client-supplied state); the field is gone, and the SAME rows now guard
    the server-side state — so each row is asserted against
    _validate_session_payload directly. Pydantic surfaced the ValueError
    as ValidationError before; the direct call raises ValueError (same
    rejection, one frame earlier). Every row and bound is unchanged.
    """

    @staticmethod
    def _validate(state):
        from main import _validate_session_payload

        _validate_session_payload(state)

    def test_oversized_session_rejected(self) -> None:
        with pytest.raises(ValueError):
            self._validate({"id": "sid_ok", "pad": "x" * 100_001})

    def test_moderate_session_accepted(self) -> None:
        self._validate({"id": "sid_ok", "pad": "x" * 50_000})  # no raise

    def test_null_and_missing_numeric_keys_accepted(self) -> None:
        self._validate({"salary": None, "business": 5_000})  # no raise

    def test_bool_income_rejected(self) -> None:
        with pytest.raises(ValueError):
            self._validate({"salary": True})

    @pytest.mark.parametrize("key", ["salary", "80c", "80u_80dd", "professional_tax"])
    def test_string_numeric_keys_rejected(self, key) -> None:
        with pytest.raises(ValueError):
            self._validate({key: "1800000"})

    def test_capital_gains_must_be_list_of_dicts_with_numeric_amount(self) -> None:
        with pytest.raises(ValueError):
            self._validate({"capital_gains": {"amount": 5}})
        with pytest.raises(ValueError):
            self._validate({"capital_gains": ["oops"]})
        with pytest.raises(ValueError):
            self._validate({"capital_gains": [{"amount": True}]})
        self._validate(
            {"capital_gains": [{"type": "equity_ltcg", "amount": 200000}]}
        )  # no raise

    def test_age_bounds(self) -> None:
        self._validate({"age": 120})  # no raise
        with pytest.raises(ValueError):
            self._validate({"age": 121})
        with pytest.raises(ValueError):
            self._validate({"age": -1})
        with pytest.raises(ValueError):
            self._validate({"age": "30"})
        with pytest.raises(ValueError):
            self._validate({"age": True})

    def test_session_id_validated(self) -> None:
        self._validate({"id": "sid_ok"})  # no raise
        with pytest.raises(ValueError):
            self._validate({"id": "../evil"})

    def test_non_finite_numerics_rejected(self) -> None:
        with pytest.raises(ValueError):
            self._validate({"id": "sid_fin1", "salary": float("inf")})
        with pytest.raises(ValueError):
            self._validate({"id": "sid_fin1", "salary": float("nan")})
        with pytest.raises(ValueError):
            self._validate(
                {"id": "sid_fin1", "capital_gains": [{"amount": float("inf")}]}
            )
        with pytest.raises(ValueError):
            self._validate({"id": "sid_fin1", "80c": float("-inf")})
        # ints are always finite — a normal int value still passes.
        self._validate({"id": "sid_fin1", "salary": 1_800_000})  # no raise


class TestCalculateRequestModel:
    """The shrunk Wave D model: {session_id, tax_year?} (ADR-013).

    Adaptation of the former alias round-trip rows: the engine-key aliases
    ("80c", "24b", ...) were the client payload's field names and died
    with it — the state carries those keys server-side and is validated
    by _validate_session_payload (pinned in TestSessionPayloadValidatorRows
    and TestCalculateEndpointValidation). What remains on the model is the
    id (required) and the ADR-008 pin (registry-checked), pinned here.
    """

    def test_session_id_required(self) -> None:
        from pydantic import ValidationError

        from main import CalculateRequest

        assert CalculateRequest(session_id="0" * 32).session_id == "0" * 32
        with pytest.raises(ValidationError):
            CalculateRequest()  # missing session_id

    def test_unknown_tax_year_rejected_at_model(self) -> None:
        from pydantic import ValidationError

        from main import CalculateRequest

        with pytest.raises(ValidationError):
            CalculateRequest(session_id="0" * 32, tax_year="fy_1999_00")

    def test_removed_80eea_rejected_at_model(self) -> None:
        # Sprint 2 Step D control, kept on the shrunk model: the removed
        # section is never silently swallowed by extra="ignore".
        from pydantic import ValidationError

        from main import CalculateRequest

        with pytest.raises(ValidationError):
            CalculateRequest(**{"session_id": "0" * 32, "80eea": 150_000})


class TestTaxYearValidation:
    """Sprint 2 (ADR-008): the optional tax-year pin must reject unknown
    registry keys with a clean 422 (no silent fallback) and round-trip a
    valid key into the response's rule-set identity fields. Wave D: the
    pin is a request OVERRIDE on /calculate and (as a state key) validated
    at the server-state boundary on /chat."""

    def test_calculate_rejects_unknown_tax_year(self, authed_client, session_id) -> None:
        response = authed_client.post(
            "/calculate",
            json={"session_id": session_id, "tax_year": "fy_1999_00"},
        )
        assert response.status_code == 422
        body = response.json()
        assert any("fy_2024_25" in err["msg"] for err in body["errors"])

    def test_calculate_accepts_registered_tax_year(self, authed_client, session_id) -> None:
        # The old body seeded salary 500000 inline; Wave D seeds the state.
        _seed_state(authed_client, session_id, {"salary": 500000})
        response = authed_client.post(
            "/calculate",
            json={"session_id": session_id, "tax_year": "fy_2024_25"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["tax_year"] == "2024-25"
        assert body["fy_label"] == "FY 2024-25 (AY 2025-26)"

    def test_calculate_without_tax_year_keeps_default(self, authed_client, session_id) -> None:
        # Step A3 flipped the registry default; an unpinned call resolves
        # FY 2025-26 (fy_2024_25 remains available via an explicit pin).
        _seed_state(authed_client, session_id, {"salary": 500000})
        response = authed_client.post(
            "/calculate", json={"session_id": session_id}
        )
        assert response.status_code == 200
        assert response.json()["tax_year"] == "2025-26"

    def test_chat_rejects_unknown_tax_year_in_state(self, authed_client, session_id) -> None:
        # Was: the client session dict carried the bad pin -> 422 at the
        # request model. Wave D: the pin is a state key, so the SAME
        # registry row guards it at the server-state load boundary.
        _seed_state(authed_client, session_id, {"tax_year": "fy_1999_00"})
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": session_id}
        )
        assert response.status_code == 422

    def test_chat_accepts_null_tax_year_in_state(self, authed_client, session_id) -> None:
        _seed_state(authed_client, session_id, {"tax_year": None})
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": session_id}
        )
        assert response.status_code == 200


class TestHistoryEndpointGate:
    """Wave D (design §2): /history requires auth + an OWNED app session,
    and the Sprint-1 interim C5 gate default flips to ON — C5 is closed by
    authentication + per-user ownership instead (foreign/unknown -> 404,
    anonymous -> 401). TAX_ENABLE_HISTORY survives as an explicit
    kill-switch: only 0/false/False disables, read at request time."""

    def test_anonymous_history_is_401(self, client, monkeypatch) -> None:
        monkeypatch.delenv("TAX_ENABLE_HISTORY", raising=False)
        response = client.get(f"/history/{'0' * 32}")
        assert response.status_code == 401

    def test_owned_history_enabled_by_default(self, authed_client, session_id) -> None:
        # No TAX_ENABLE_HISTORY involved: the documented default is ON.
        response = authed_client.get(f"/history/{session_id}")
        assert response.status_code == 200
        assert response.json() == {
            "entries": [],
            "corrupt_lines_skipped": 0,
            "has_more": False,
        }

    def test_foreign_history_is_404(self, authed_client, session_id) -> None:
        from tests.conftest import register_and_login

        register_and_login(authed_client)  # the cookie now authenticates user B
        response = authed_client.get(f"/history/{session_id}")
        assert response.status_code == 404

    def test_kill_switch_disables_for_owned_session(
        self, authed_client, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "0")
        response = authed_client.get(f"/history/{session_id}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}

    def test_switch_is_exact_other_values_stay_on(
        self, authed_client, session_id, monkeypatch
    ) -> None:
        # Documented flip (supersedes the Sprint-1 opt-in semantics): the
        # kill-switch is exact — any non-falsy value leaves history on.
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "yes")
        response = authed_client.get(f"/history/{session_id}")
        assert response.status_code == 200

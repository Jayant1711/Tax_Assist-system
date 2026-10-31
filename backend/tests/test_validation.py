"""Request validation + global exception handler tests (ISSUE #2 — H5/N1).

/calculate must 422 on non-numeric income, malformed capital gains and out-of
-range values, ignore junk extra keys, and keep the frontend payload contract
(shape AND numbers) identical to the pre-validation endpoint. /chat must 422
on string income keys, bad capital-gains amounts, oversized messages and
oversized sessions instead of 500-ing. The global Exception handler must
return a sanitized 500 with no stack details.
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


class TestCalculateEndpointValidation:
    def test_rejects_non_numeric_salary(self, client) -> None:
        response = client.post("/calculate", json={"salary": "abc"})
        assert response.status_code == 422

    def test_rejects_non_dict_capital_gain_entry(self, client) -> None:
        response = client.post("/calculate", json={"capital_gains": ["oops"]})
        assert response.status_code == 422

    def test_rejects_formatted_amount_string(self, client) -> None:
        # Indian-style digit grouping is not machine-coercible → 422.
        response = client.post(
            "/calculate",
            json={"capital_gains": [{"type": "equity_ltcg", "amount": "2,00,000"}]},
        )
        assert response.status_code == 422

    def test_coerces_plain_numeric_string_amount(self, client) -> None:
        # pydantic v2 lax mode coerces "200000" → 200000.0 (documented).
        response = client.post(
            "/calculate",
            json={"capital_gains": [{"type": "equity_ltcg", "amount": "200000"}]},
        )
        assert response.status_code == 200
        body = response.json()
        # The coerced amount reaches the engine: cg income 200000 lands in
        # taxable_income (no other income in the payload).
        assert body["old_regime"]["taxable_income"] == 200000.0

    def test_rejects_negative_salary(self, client) -> None:
        response = client.post("/calculate", json={"salary": -5})
        assert response.status_code == 422

    def test_rejects_out_of_range_age(self, client) -> None:
        response = client.post("/calculate", json={"age": 999})
        assert response.status_code == 422

    def test_ignores_junk_extra_keys(self, client) -> None:
        response = client.post(
            "/calculate",
            json={"phase": "FINAL", "history": [1, 2, 3]},
        )
        assert response.status_code == 200
        body = response.json()
        for key in ("old_regime", "new_regime", "recommendation", "savings", "efficiency_score"):
            assert key in body

    def test_frontend_payload_shape_and_numbers_unchanged(self, client) -> None:
        payload = {"id": "sid_x", "salary": 1800000, "80c": 150000, "profile": "Salaried"}
        response = client.post("/calculate", json=payload)
        assert response.status_code == 200
        body = response.json()
        for key in ("old_regime", "new_regime", "recommendation", "savings", "efficiency_score"):
            assert key in body
        # Numeric parity: the endpoint must compute exactly what the engine
        # computes on the raw payload (guards the engine-default handling,
        # e.g. the internal professional_tax default for salaried users).
        from main import engine

        reference = engine.calculate_tax_advanced(dict(payload))
        assert body["old_regime"]["total_tax"] == reference["old_regime"].total_tax
        assert body["new_regime"]["total_tax"] == reference["new_regime"].total_tax
        assert body["recommendation"] == reference["recommendation"]
        assert body["savings"] == reference["savings"]
        assert body["efficiency_score"] == reference["efficiency_score"]


class TestChatEndpointValidation:
    def test_rejects_non_numeric_income_in_session(self, client) -> None:
        response = client.post(
            "/chat",
            json={"message": "hi", "session": {"id": "sid_ok", "salary": "abc"}},
        )
        assert response.status_code == 422

    def test_rejects_bad_capital_gain_amount_in_session(self, client) -> None:
        response = client.post(
            "/chat",
            json={
                "message": "hi",
                "session": {"id": "sid_ok", "capital_gains": [{"amount": "x"}]},
            },
        )
        assert response.status_code == 422

    def test_rejects_oversized_message(self, client) -> None:
        response = client.post(
            "/chat",
            json={"message": "x" * 5000, "session": {"id": "sid_ok"}},
        )
        assert response.status_code == 422

    def test_rejects_oversized_session(self, client) -> None:
        response = client.post(
            "/chat",
            json={
                "message": "hi",
                "session": {"id": "sid_ok", "pad": "x" * 150_000},
            },
        )
        assert response.status_code == 422

    def test_valid_session_still_ok(self, client) -> None:
        response = client.post(
            "/chat",
            json={"message": "hi", "session": {"id": "sid_ok"}},
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

    httpx's json= encoder refuses non-finite floats client-side, so these
    tests post raw bodies — exactly how the values arrive in production:
    "1e309" is strict JSON that Python's server-side parser maps to inf,
    and Infinity/NaN literals are non-standard tokens json.loads accepts.
    """

    @staticmethod
    def _post_raw(client, url: str, payload: str):
        return client.post(url, content=payload, headers={"Content-Type": "application/json"})

    def test_calculate_rejects_infinite_salary(self, client) -> None:
        # 1e309 parses to float('inf'); was a sanitized 500 before the fix
        # (default 422 handler crashed serializing the echoed inf input).
        response = self._post_raw(client, "/calculate", '{"salary": 1e309}')
        assert response.status_code == 422

    def test_calculate_rejects_infinite_capital_gain_amount(self, client) -> None:
        response = self._post_raw(
            client,
            "/calculate",
            '{"capital_gains": [{"type": "equity_ltcg", "amount": 1e309}]}',
        )
        assert response.status_code == 422

    def test_chat_rejects_infinite_salary_in_session(self, client) -> None:
        response = self._post_raw(
            client,
            "/chat",
            '{"message": "hi", "session": {"id": "sid_fin1", "salary": Infinity}}',
        )
        assert response.status_code == 422

    def test_chat_rejects_nan_salary_in_session(self, client) -> None:
        response = self._post_raw(
            client,
            "/chat",
            '{"message": "hi", "session": {"id": "sid_fin1", "salary": NaN}}',
        )
        assert response.status_code == 422

    def test_finite_boundary_still_valid(self, client) -> None:
        # le=1e11 is inclusive and 1e11 is finite: numeric-string coercion
        # must keep working up to the cap (regression guard).
        assert client.post("/calculate", json={"salary": "1e11"}).status_code == 200
        assert client.post(
            "/calculate",
            json={"capital_gains": [{"type": "equity_ltcg", "amount": "1e11"}]},
        ).status_code == 200


class TestValidationErrorResponse:
    """The 422 body must describe the error, never echo the attacker input."""

    def test_body_shape_and_no_input_echo(self, client) -> None:
        response = client.post("/calculate", json={"salary": "abc"})
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == "Validation error"
        assert body["errors"], "at least one error entry"
        entry = body["errors"][0]
        assert set(entry) == {"loc", "msg", "type"}
        assert all(isinstance(part, str) for part in entry["loc"])
        assert "abc" not in response.text

    def test_large_invalid_input_not_reflected(self, client) -> None:
        # ~100KB session that fails for an unrelated reason (bad id): with
        # the default handler the 'input' echo made the body ~100KB.
        response = client.post(
            "/chat",
            json={"message": "hi", "session": {"id": "../evil", "pad": "x" * 99_000}},
        )
        assert response.status_code == 422
        assert len(response.content) < 2000
        assert "xxxx" not in response.text

    def test_errors_capped_at_20(self, client) -> None:
        response = client.post(
            "/calculate",
            json={"capital_gains": [{"amount": "not-a-number"}] * 25},
        )
        assert response.status_code == 422
        assert len(response.json()["errors"]) == 20


class TestChatRequestSessionValidators:
    def _request(self, session):
        from main import ChatRequest

        return ChatRequest(message="hi", session=session)

    def test_oversized_session_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._request({"id": "sid_ok", "pad": "x" * 100_001})

    def test_moderate_session_accepted(self) -> None:
        parsed = self._request({"id": "sid_ok", "pad": "x" * 50_000})
        assert parsed.session["pad"].startswith("xxx")

    def test_null_and_missing_numeric_keys_accepted(self) -> None:
        parsed = self._request({"salary": None, "business": 5_000})
        assert parsed.session["salary"] is None
        assert parsed.session["business"] == 5_000

    def test_bool_income_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._request({"salary": True})

    @pytest.mark.parametrize("key", ["salary", "80c", "80u_80dd", "professional_tax"])
    def test_string_numeric_keys_rejected(self, key) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._request({key: "1800000"})

    def test_capital_gains_must_be_list_of_dicts_with_numeric_amount(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._request({"capital_gains": {"amount": 5}})
        with pytest.raises(ValidationError):
            self._request({"capital_gains": ["oops"]})
        with pytest.raises(ValidationError):
            self._request({"capital_gains": [{"amount": True}]})
        parsed = self._request({"capital_gains": [{"type": "equity_ltcg", "amount": 200000}]})
        assert parsed.session["capital_gains"][0]["amount"] == 200000

    def test_age_bounds(self) -> None:
        from pydantic import ValidationError

        assert self._request({"age": 120}).session["age"] == 120
        with pytest.raises(ValidationError):
            self._request({"age": 121})
        with pytest.raises(ValidationError):
            self._request({"age": -1})
        with pytest.raises(ValidationError):
            self._request({"age": "30"})
        with pytest.raises(ValidationError):
            self._request({"age": True})

    def test_session_id_validated(self) -> None:
        from pydantic import ValidationError

        assert self._request({"id": "sid_ok"}).session["id"] == "sid_ok"
        with pytest.raises(ValidationError):
            self._request({"id": "../evil"})

    def test_non_finite_numerics_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._request({"id": "sid_fin1", "salary": float("inf")})
        with pytest.raises(ValidationError):
            self._request({"id": "sid_fin1", "salary": float("nan")})
        with pytest.raises(ValidationError):
            self._request({"id": "sid_fin1", "capital_gains": [{"amount": float("inf")}]})
        with pytest.raises(ValidationError):
            self._request({"id": "sid_fin1", "80c": float("-inf")})
        # ints are always finite — a normal int value still passes.
        assert self._request({"id": "sid_fin1", "salary": 1_800_000}).session["salary"] == 1_800_000


class TestCalculateRequestModel:
    def test_alias_round_trip(self) -> None:
        from main import CalculateRequest

        req = CalculateRequest(**{"salary": 10, "80c": 1500, "24b": 20000})
        dumped = req.model_dump(by_alias=True)
        assert dumped["80c"] == 1500.0
        assert dumped["24b"] == 20000.0
        assert "c80" not in dumped and "b24" not in dumped

    def test_populate_by_name(self) -> None:
        from main import CalculateRequest

        req = CalculateRequest(c80=1500)
        assert req.model_dump(by_alias=True)["80c"] == 1500.0

    def test_id_must_be_valid_session_id(self) -> None:
        from pydantic import ValidationError

        from main import CalculateRequest

        assert CalculateRequest(id="sid_ok").id == "sid_ok"
        with pytest.raises(ValidationError):
            CalculateRequest(id="../evil")


class TestHistoryEndpointGate:
    """C5 interim: /history is 404 unless TAX_ENABLE_HISTORY opts in."""

    def test_history_disabled_by_default(self, client, monkeypatch) -> None:
        monkeypatch.delenv("TAX_ENABLE_HISTORY", raising=False)
        response = client.get("/history/history_probe_1")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}

    def test_history_enabled_with_env(self, client, monkeypatch) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "1")
        # The endpoint filters by sid; an unknown sid yields [] whether or
        # not the log file exists in cwd.
        response = client.get("/history/history_probe_1")
        assert response.status_code == 200
        assert response.json() == []

    def test_history_enabled_with_true(self, client, monkeypatch) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "True")
        response = client.get("/history/history_probe_1")
        assert response.status_code == 200
        assert response.json() == []

    def test_history_stays_disabled_for_other_values(self, client, monkeypatch) -> None:
        monkeypatch.setenv("TAX_ENABLE_HISTORY", "yes")
        response = client.get("/history/history_probe_1")
        assert response.status_code == 404

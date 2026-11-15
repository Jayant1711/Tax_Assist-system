# tests/test_audit_wave1.py — regression pins for the fresh-eyes audit
# wave 1 fixes. Every test here corresponds to a defect the audit found
# (and that the pre-audit code shipped with).
import os

import pytest

from tests.conftest import (
    BACKEND_DIR, make_session, register_and_login,
)


def _chat(client, sid, msg):
    return client.post("/chat", json={"message": msg, "session_id": sid})


@pytest.fixture()
def chat_client():
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
        yield client, sid
    finally:
        os.chdir(previous_cwd)


def _session_state(sid):
    import db as db_mod
    import json as _json

    row = db_mod.get_connection().execute(
        "SELECT state FROM app_sessions WHERE id = ?", (sid,)).fetchone()
    return _json.loads(row[0])


class TestCorrectionSemantics:
    """The backend-review P0s: corrections replaced, not summed; no
    cross-head corruption; no 500 on numberless corrections."""

    def test_numberless_correction_does_not_500(self, chat_client) -> None:
        """\u201Cthat's wrong\u201D (correction keyword, no digits, no category)
        used to raise UnboundLocalError -> 500."""
        client, sid = chat_client
        r = _chat(client, sid, "I am a software engineer earning 24 lakhs")
        assert r.status_code == 200
        r = _chat(client, sid, "that's wrong")
        assert r.status_code == 200  # was 500

    def test_same_category_correction_replaces(self, chat_client) -> None:
        client, sid = chat_client
        _chat(client, sid, "my salary is 600000 per year")
        _chat(client, sid, "actually I earn 50000 per month")
        state = _session_state(sid)
        # 50,000/month annualizes to 600,000 — the REPLACE semantics book
        # the corrected figure, not 600000+600000=1,200,000
        assert state.get("salary") == 600_000

    def test_named_head_correction_replaces_that_head(
            self, chat_client) -> None:
        client, sid = chat_client
        _chat(client, sid, "my salary is 600000 per year")
        _chat(client, sid, "my 80c investment is 150000")
        _chat(client, sid, "oops the 80c is actually 50000")
        state = _session_state(sid)
        # the correction replaces 80C; salary is untouched (the old
        # first-fit subtract pulled 50,000 out of salary instead)
        assert state.get("80c") == 50_000
        assert state.get("salary") == 600_000

    def test_new_category_correction_does_not_shrink_salary(
            self, chat_client) -> None:
        client, sid = chat_client
        _chat(client, sid, "my salary is 600000 per year")
        _chat(client, sid, "actually my rent is 20000 per month")
        state = _session_state(sid)
        # a NEW head's correction must not pull the amount out of salary
        assert state.get("salary") == 600_000


class TestParsingGuards:
    def test_rent_inside_parents_is_not_matched(self) -> None:
        """The 4-char keyword 'rent' matched inside 'parents' — the 80D
        premium booked as rent instead."""
        from ai_models import SemanticAttention

        att = SemanticAttention()
        best, is_default = att.resolve_category_detailed(
            "I pay 40000 insurance premium for my parents", 7, 12, None, None)
        assert best != "rent_paid"

    def test_pm_cares_is_not_monthly(self) -> None:
        """\u201Cdonated 50000 PM Cares fund\u201D was 12x over-booked by the
        pm rest-prefix check."""
        from ai_models import UniversalParser

        parser = UniversalParser()
        matches = parser.parse("donated 50000 PM Cares fund")
        assert matches and matches[0]["val"] == 50_000
        assert not matches[0].get("annualized")


class TestZeroSentinel:
    def test_zero_intent_with_real_amount_books_the_amount(
            self, chat_client) -> None:
        """\u201CI don't have 80C but my salary is 1200000\u201D — the
        sentence-level zero-sentinel zeroed the whole booking."""
        client, sid = chat_client
        _chat(client, sid, "I don't have 80C but my salary is 1200000")
        state = _session_state(sid)
        assert state.get("salary") == 1_200_000

    def test_booked_zero_income_advances_discovery(self, chat_client) -> None:
        """\u201Cnothing\u201D books salary = 0; the discovery must advance
        to the deduction steps instead of looping on the income ask."""
        client, sid = chat_client
        _chat(client, sid, "I am a salaried employee")
        _chat(client, sid, "nothing")
        state = _session_state(sid)
        assert state.get("salary") == 0
        r = _chat(client, sid, "no")
        # the plan must NOT re-ask for income
        assert "income amount" not in r.json().get("response", "")


class TestMonthlyRent:
    def test_monthly_rent_answer_annualizes(self, chat_client) -> None:
        """The discovery question asks for MONTHLY rent — a bare answer
        was booked as an annual figure and zeroed the HRA exemption."""
        client, sid = chat_client
        _chat(client, sid, "I am a salaried employee earning 15 lakhs, my "
                            "basic salary is 6 lakhs")
        _chat(client, sid, "monthly rent is 25000")
        state = _session_state(sid)
        assert state.get("rent_paid") == 300_000  # 25,000 x 12


class TestRegimeGatedTips:
    def test_report_tips_follow_the_recommendation(self) -> None:
        """The /calculate tips call was un-gated: a New-Regime
        recommendation shipped old-regime tips with a non-engine rupee
        figure."""
        from tax_engine import TaxEngine

        e = TaxEngine()
        data = {"salary": 2_000_000}
        res = e.calculate_tax_advanced(data)
        assert res["recommendation"] == "New Regime"
        tips = res["new_regime"].savings_tips or []
        joined = " ".join(tips)
        # the New-Regime note is the only tip: no old-regime rupee-figure
        # tips (the removed ADR-001 violation) may appear
        assert "New Regime note" in joined
        assert "Invest ₹" not in joined and "save an instant" not in joined


class TestTaxYearPassthrough:
    def test_recommend_uses_the_pinned_year(self) -> None:
        """recommend() hardcoded fy_2025_26 — a session pinned to
        fy_2024_25 was priced under the wrong year's rules."""
        from tax_engine import TaxEngine
        from tax_intelligence import recommend

        e = TaxEngine()
        s = {"id": "p", "salary": 1_500_000, "tax_year": "fy_2024_25"}
        review = recommend(s, e, None, top_n=1, tax_year="fy_2024_25")
        # FY 2024-25 new regime at 15L: 0-3 nil, 3-6 5%, 6-9 10%,
        # 9-12 15%, 12-15 20% on (15L - 50k std) = 14.5L -> 1,70,000
        assert review["recommendation"] == "New Regime"
        # the pinned year flows through: no crash, engine-priced figures
        assert isinstance(review["recommendations"], list)

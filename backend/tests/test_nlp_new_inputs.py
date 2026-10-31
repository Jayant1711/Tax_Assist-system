"""Sprint 2 Step D2/G — NLP input collection (age guard, category collection,
write clamping, CG enum).

Tests FIRST (red), per AI_RULES.md. Spec: docs/sprint2-design.md
"Step D2/G" (2026-10-31).

What this step closes:
  - G / G-1: ages book as INCOME today ("I am 105 years old" -> salary=105;
    "my age is 150" -> other_income=150 — both verified live). A dedicated
    anchored extractor runs BEFORE clause parsing: cue words age/aged/
    "years old"/umar/umr plus the "I am <int>" copula; integers 0-120 book
    session["age"] (int, last explicit wins), out-of-range 121-999 and
    non-integers are swallowed with an advisory, and every consumed span is
    masked so the number NEVER reaches UniversalParser. Family-context
    numbers ("my father is 91") are swallowed — never the user's own age.
    "senior citizen" floors age at 60 with the assumption stated in the
    reply. "age" leaves the OVERWRITE_CATS list (extractor-only writes).
  - V-1: every NLP-written numeric is clamped to 0..1e11 AFTER monthly
    annualization at the assignment block (central helper), with the
    clamped-to-₹100-crore advisory.
  - V-2: CapitalGainItem.type is a 3-value Literal (422 otherwise) and
    /chat session capital_gains entries are type-checked (the "crypto"
    untaxed-income hole).
  - 80U/80DD + 80G category collection: keyword-honest heuristics; no
    keyword match -> ask-back reply, nothing booked. Percentage numbers in
    disability utterances never book as amounts.
"""
import os
from typing import Any, Dict, List

import pytest

from nlp_engine import NLPEngine

nlp = NLPEngine()

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AGE_RANGE_ADVISORY_FRAGMENT = "Age must be 0-120"
CLAMP_ADVISORY = "Amount exceeds the supported range — clamped to ₹100 crore"

INCOME_AND_DEDUCTION_KEYS = (
    "salary", "business", "rental", "other_income", "agriculture",
    "80c", "80d", "80d_parents", "nps", "24b", "80g", "80e", "80tta",
    "80ttb", "80gg", "80u_80dd", "80ddb", "80ddb_expenditure",
    "hra_received", "rent_paid", "capital_gains",
)


def run_chat(turns: List[str]) -> Dict[str, Any]:
    """Simulate a multi-turn chat; returns the final session."""
    sess: Dict[str, Any] = {"id": f"pytest_d2g_{id(turns)}"}
    for msg in turns:
        nlp.process_message(msg, sess)
    return sess


def _assert_no_money_keys(sess: Dict[str, Any]) -> None:
    for key in INCOME_AND_DEDUCTION_KEYS:
        assert key not in sess, f"{key} was booked: {sess.get(key)!r}"


def _numeric_session_values(obj: Any) -> List[float]:
    """Every numeric leaf in the session (strings excluded — the 80U/80DD
    category enum values like "40_79" are not bookings)."""
    found: List[float] = []
    if isinstance(obj, bool):
        return found
    if isinstance(obj, (int, float)):
        found.append(float(obj))
    elif isinstance(obj, dict):
        for value in obj.values():
            found.extend(_numeric_session_values(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_numeric_session_values(item))
    return found


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


# =========================================================================
# 1. Objective G — the anchored age extractor (+ G-1 regression)
# =========================================================================

class TestAgeExtractor:
    def test_i_am_67_books_age_only(self) -> None:
        sess = run_chat(["I am 67"])
        assert sess.get("age") == 67
        assert isinstance(sess.get("age"), int)  # written as int only
        _assert_no_money_keys(sess)

    def test_age_cue_books_72(self) -> None:
        sess = run_chat(["age 72"])
        assert sess.get("age") == 72
        _assert_no_money_keys(sess)

    def test_105_years_old_never_books_salary(self) -> None:
        """G-1 regression: "I am 105 years old" booked salary=105 before
        the extractor (verified live 2026-10-31)."""
        sess = run_chat(["I am 105 years old"])
        assert sess.get("age") == 105
        assert "salary" not in sess
        _assert_no_money_keys(sess)

    def test_150_is_swallowed_with_advisory(self) -> None:
        """G-1 regression: "my age is 150" booked other_income=150."""
        sess: Dict[str, Any] = {"id": "pytest_d2g_150"}
        result = nlp.process_message("my age is 150", sess)
        assert "age" not in sess
        assert "other_income" not in sess
        assert any(
            AGE_RANGE_ADVISORY_FRAGMENT in entry for entry in result["extracted"]
        )

    def test_6_years_old_books_age_only(self) -> None:
        sess = run_chat(["I am 6 years old"])
        assert sess.get("age") == 6
        _assert_no_money_keys(sess)

    def test_last_explicit_age_wins(self) -> None:
        sess = run_chat(["I am 67", "sorry I am 56"])
        assert sess.get("age") == 56

    def test_father_age_never_books_session_age(self) -> None:
        sess = run_chat(["my father is 91"])
        assert "age" not in sess
        _assert_no_money_keys(sess)

    def test_senior_citizen_defaults_to_60_with_stated_assumption(self) -> None:
        sess: Dict[str, Any] = {"id": "pytest_d2g_senior"}
        result = nlp.process_message("senior citizen", sess)
        assert sess.get("age") == 60
        # the reply states the assumption so it can be corrected
        assert "60" in result["response"]
        assert "assum" in result["response"].lower()

    def test_senior_citizen_does_not_lower_explicit_age(self) -> None:
        sess = run_chat(["I am 67", "I am a senior citizen"])
        assert sess.get("age") == 67

    def test_self_and_father_in_one_message(self) -> None:
        sess = run_chat(["I am 67, my father is 91"])
        assert sess.get("age") == 67
        _assert_no_money_keys(sess)

    def test_non_integer_age_rejected(self) -> None:
        sess: Dict[str, Any] = {"id": "pytest_d2g_float"}
        result = nlp.process_message("my age is 67.5", sess)
        assert "age" not in sess
        assert any(
            AGE_RANGE_ADVISORY_FRAGMENT in entry for entry in result["extracted"]
        )

    def test_age_extractor_leaves_income_flow_untouched(self) -> None:
        """Regression: the engineer/earning phrasing has no age cue —
        salary booking must be exactly as before."""
        sess = run_chat(["I am a software engineer earning 18 LPA"])
        assert sess.get("salary") == 1_800_000
        assert "age" not in sess

    def test_copula_money_suffix_never_truncates(self) -> None:
        """Regression: the greedy {1,3} digit run backtracked past the
        money guard — "I am 45k earner" extracted a truncated age 4 AND
        corrupted the salary to 5000 (the blanked digit left "5k")."""
        sess = run_chat(["I am 45k earner"])
        assert "age" not in sess
        assert sess.get("salary") == 45_000

    def test_age_cue_money_continuation_routes_to_money(self) -> None:
        sess = run_chat(["my age is 45 lakh"])
        assert "age" not in sess
        assert sess.get("other_income") == 4_500_000

    def test_age_booking_survives_chat_round_trip(self, client) -> None:
        """session["age"] is an int 0-120 — the main.py validator row
        must accept the extractor's write on the next /chat turn."""
        response = client.post(
            "/chat",
            json={"message": "I am 67", "session": {"id": "sid_d2g_age1"}},
        )
        assert response.status_code == 200
        assert response.json()["session"]["age"] == 67


# =========================================================================
# 2. V-1 — NLP write clamping (0..1e11, post-annualization)
# =========================================================================

class TestNlpWriteClamping:
    def test_salary_50000_crore_clamped_to_1e11(self) -> None:
        """G-1-adjacent hole: "my salary is 50000 crore" booked 5e11."""
        sess: Dict[str, Any] = {"id": "pytest_d2g_clamp1"}
        result = nlp.process_message("my salary is 50000 crore", sess)
        assert sess.get("salary") == 1e11
        assert any(CLAMP_ADVISORY in entry for entry in result["extracted"])

    def test_salary_20000_crore_clamped_to_1e11(self) -> None:
        sess = run_chat(["my salary is 20000 crore"])
        assert sess.get("salary") == 1e11

    def test_80c_below_cap_not_clamped(self) -> None:
        sess = run_chat(["I invest 5 crore in PPF"])
        assert sess.get("80c") == 5e7  # 5 crore < 1e11 — untouched

    def test_accumulated_writes_clamped(self) -> None:
        """The accumulate branch (deductions) clamps the SUM, not just the
        single value: 9e11 + 9e11 must not produce 1.8e12."""
        sess = run_chat([
            "80c investment of 90000 crore",
            "80c investment of 90000 crore",
        ])
        assert sess.get("80c") == 1e11

    def test_capital_gains_amount_clamped(self) -> None:
        sess = run_chat(["sold property for 20000 crore"])
        gains = sess.get("capital_gains")
        assert isinstance(gains, list) and gains
        assert gains[0]["amount"] == 1e11

    def test_monthly_annualized_then_clamped(self) -> None:
        """Clamp applies AFTER annualization: 20000 crore/month x12 must
        clamp to 1e11 (not clamp the 2.4e12 monthly figure first... the
        pre-annualization figure is 2e11, already over — either way the
        session must never hold more than 1e11)."""
        sess = run_chat(["my salary is 20000 crore monthly"])
        assert sess.get("salary") == 1e11

    def test_clamp_helper_unit_contract(self) -> None:
        clamp = NLPEngine._clamp_amount
        assert clamp(100.0) == (100.0, False)
        assert clamp(5e11) == (1e11, True)
        assert clamp(-5.0) == (0.0, False)      # negatives -> 0
        assert clamp(0.0) == (0.0, False)


# =========================================================================
# 3. V-2 — capital-gains type enum at both boundaries
# =========================================================================

CG_TYPES = ("equity_ltcg", "equity_stcg", "property_cg")


class TestCapitalGainsTypeEnum:
    @pytest.mark.parametrize("cg_type", ["crypto", "gold", ""])
    def test_calculate_rejects_unknown_cg_type(self, client, cg_type) -> None:
        response = client.post(
            "/calculate",
            json={"capital_gains": [{"type": cg_type, "amount": 100}]},
        )
        assert response.status_code == 422, cg_type

    def test_calculate_missing_cg_type_rejected(self, client) -> None:
        """The untaxed-income hole: an entry with no type books income and
        no tax at the engine — the boundary must reject it."""
        response = client.post(
            "/calculate", json={"capital_gains": [{"amount": 100}]}
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("cg_type", CG_TYPES)
    def test_calculate_accepts_all_three_types(self, client, cg_type) -> None:
        response = client.post(
            "/calculate",
            json={"capital_gains": [{"type": cg_type, "amount": 100}]},
        )
        assert response.status_code == 200, cg_type

    def test_chat_rejects_unknown_cg_type_in_session(self, client) -> None:
        response = client.post(
            "/chat",
            json={
                "message": "hi",
                "session": {
                    "id": "sid_d2g_cg1",
                    "capital_gains": [{"type": "crypto", "amount": 100}],
                },
            },
        )
        assert response.status_code == 422

    def test_chat_missing_cg_type_in_session_rejected(self, client) -> None:
        response = client.post(
            "/chat",
            json={
                "message": "hi",
                "session": {
                    "id": "sid_d2g_cg2",
                    "capital_gains": [{"amount": 100}],
                },
            },
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("cg_type", CG_TYPES)
    def test_chat_accepts_valid_cg_types_in_session(self, client, cg_type) -> None:
        response = client.post(
            "/chat",
            json={
                "message": "hi",
                "session": {
                    "id": "sid_d2g_cg3",
                    "capital_gains": [{"type": cg_type, "amount": 100}],
                },
            },
        )
        assert response.status_code == 200, cg_type

    def test_session_model_rejects_unknown_cg_type(self) -> None:
        from pydantic import ValidationError

        from main import ChatRequest

        with pytest.raises(ValidationError):
            ChatRequest(
                message="hi",
                session={
                    "id": "sid_d2g_cg4",
                    "capital_gains": [{"type": "crypto", "amount": 100}],
                },
            )

    def test_nlp_cg_type_inference_stays_in_enum(self) -> None:
        """Scope item 3 (verify): the engine's inference is restricted to
        the 3-value enum for every utterance family."""
        for text, expected in [
            ("sold shares for 5 lakhs", "equity_ltcg"),
            ("sold shares short term for 5 lakhs", "equity_stcg"),
            ("sold property for 5 lakhs", "property_cg"),
        ]:
            sess: Dict[str, Any] = {"id": "pytest_d2g_cgt"}
            nlp.process_message(text, sess)
            gains = sess.get("capital_gains")
            assert isinstance(gains, list) and gains, text
            assert gains[0]["type"] == expected, text


# =========================================================================
# 4. 80U/80DD disability category collection
# =========================================================================

class TestDisabilityCategoryCollection:
    def test_severe_disability_books_80_plus(self) -> None:
        sess = run_chat(["I have severe disability"])
        assert sess.get("80u_80dd_category") == "80_plus"

    def test_40_percent_disabled_books_40_79_and_no_amount(self) -> None:
        """Percentage guard: the 40 must never book anywhere (the digit
        pass drops <100 today, and the pre-parse mask keeps >=100 out)."""
        sess = run_chat(["I am 40 percent disabled"])
        assert sess.get("80u_80dd_category") == "40_79"
        assert 40.0 not in _numeric_session_values(sess)
        _assert_no_money_keys(sess)

    def test_80_percent_disability_books_80_plus_never_amount(self) -> None:
        sess = run_chat(["I have 80 percent disability"])
        assert sess.get("80u_80dd_category") == "80_plus"
        assert "80u_80dd" not in sess
        _assert_no_money_keys(sess)

    def test_100_percent_disability_books_80_plus_never_amount(self) -> None:
        """100 is >= the parser's <100 drop — without the percentage mask
        it would book as money."""
        sess = run_chat(["disability 100 percent"])
        assert sess.get("80u_80dd_category") == "80_plus"
        assert 100.0 not in _numeric_session_values(sess)
        _assert_no_money_keys(sess)

    def test_bare_80u_mention_asks_back_and_books_nothing(self) -> None:
        sess: Dict[str, Any] = {"id": "pytest_d2g_80u"}
        result = nlp.process_message("I have 80u", sess)
        assert "80u_80dd_category" not in sess
        assert "40-79%" in result["response"]  # the category ask-back

    def test_askback_answer_80_percent_books_80_plus(self) -> None:
        sess = run_chat(["I have 80u", "80 percent"])
        assert sess.get("80u_80dd_category") == "80_plus"

    def test_askback_answer_partial_books_40_79(self) -> None:
        sess = run_chat(["I have 80dd", "partial"])
        assert sess.get("80u_80dd_category") == "40_79"


# =========================================================================
# 5. 80G donation category collection
# =========================================================================

class TestDonationCategoryCollection:
    def test_pm_cares_books_80g_and_cat_100_no_limit(self) -> None:
        sess = run_chat(["donated 1 lakh to PM CARES"])
        assert sess.get("80g") == 100_000
        assert sess.get("80g_category") == "cat_100_no_limit"

    def test_ngo_books_cat_50_no_limit(self) -> None:
        sess = run_chat(["donated 1 lakh to an NGO"])
        assert sess.get("80g") == 100_000
        assert sess.get("80g_category") == "cat_50_no_limit"

    def test_national_defence_books_cat_100_no_limit(self) -> None:
        sess = run_chat(["donated 50000 to National Defence Fund"])
        assert sess.get("80g") == 50_000
        assert sess.get("80g_category") == "cat_100_no_limit"

    def test_charitable_trust_books_cat_50_no_limit(self) -> None:
        sess = run_chat(["donated 2 lakhs to a charitable trust"])
        assert sess.get("80g") == 200_000
        assert sess.get("80g_category") == "cat_50_no_limit"

    def test_government_donee_books_cat_100_qualifying_limit(self) -> None:
        sess = run_chat(["donated 1 lakh to government"])
        assert sess.get("80g_category") == "cat_100_qualifying_limit"

    def test_temple_books_cat_50_qualifying_limit(self) -> None:
        sess = run_chat(["donated 50000 to temple"])
        assert sess.get("80g_category") == "cat_50_qualifying_limit"

    def test_donation_without_category_books_amount_and_asks_back(self) -> None:
        """Existing flow keeps the amount booking; no category key is
        guessed (the engine applies its disclosed default) — the reply
        asks the donee category instead."""
        sess: Dict[str, Any] = {"id": "pytest_d2g_80g"}
        result = nlp.process_message("donated 5 lakhs", sess)
        assert sess.get("80g") == 500_000
        assert "80g_category" not in sess
        assert "donee category" in result["response"]

    def test_bare_80g_mention_asks_back_without_booking(self) -> None:
        sess: Dict[str, Any] = {"id": "pytest_d2g_80g2"}
        result = nlp.process_message("80g", sess)
        assert "80g" not in sess
        assert "80g_category" not in sess
        assert "donee category" in result["response"]


# =========================================================================
# 6. Validator rows (landed in Step D — spot-verify they still hold)
# =========================================================================

class TestValidatorRowsSpotCheck:
    """Step D landed the 80u_80dd_category (3-value), 80g_category
    (4-value) and 80ddb_expenditure (bounded numeric) session rows; this
    step adds nothing new on the validator side (NLP-side only) — these
    spot-checks pin that the rows still hold after the D2/G changes."""

    @pytest.mark.parametrize(
        "session",
        [
            {"id": "sid_d2g_v1", "80u_80dd_category": "severe"},
            {"id": "sid_d2g_v1", "80g_category": "cat_9"},
            {"id": "sid_d2g_v1", "80ddb_expenditure": -1},
            {"id": "sid_d2g_v1", "80ddb_expenditure": 1e11 + 1},
        ],
    )
    def test_rows_still_reject_bad_values(self, client, session) -> None:
        assert client.post("/chat", json={"message": "hi", "session": session}).status_code == 422

    @pytest.mark.parametrize(
        "session",
        [
            {"id": "sid_d2g_v2", "80u_80dd_category": "80_plus"},
            {"id": "sid_d2g_v2", "80g_category": "cat_50_no_limit"},
            {"id": "sid_d2g_v2", "80ddb_expenditure": 60_000},
        ],
    )
    def test_rows_still_accept_good_values(self, client, session) -> None:
        assert client.post("/chat", json={"message": "hi", "session": session}).status_code == 200

"""Sprint 2 Step B — HRA three-leg Rule 2A (Sec 10(13A)) + split rent/HRA inputs.

Tests FIRST (red), per AI_RULES.md. Spec: docs/sprint2-design.md "Step B" +
docs/tax-verification.md §8 (statutory method, unchanged) + expert rulings
(R-e pattern: assumptions are disclosed, never guessed).

Engine (Rule 2A least-of, FY 2025-26 old regime):
    exemption = least of
      (a) actual HRA received
      (b) rent paid - 10% of salary
      (c) salary x 50% (metro: Delhi/Mumbai/Kolkata/Chennai) or 40% (else)
    0 when salary <= 0, rent_paid <= 0 or hra_received <= 0.

Legacy compat (binding): the pre-existing session key ``hra`` maps to BOTH
legs, reproducing the legacy formula min(0.4*salary, hra, hra - 0.1*salary)
EXACTLY — proven by the parity cell at salary 18L for hra in {3L, 5L}.
The new keys ``hra_received``/``rent_paid`` are authoritative per leg when
present. 80GG guard switches to hra_received > 0 (a user who receives HRA
can never claim 80GG, even when the Rule 2A exemption computes to 0).

is_metro: bool strictly at both boundaries; None/absent assumes non-metro
and the engine discloses it with the verbatim advisory (never silent).
NLP: the legacy ``hra`` attention category is split into ``hra_received``
and ``rent_paid``; both accumulate (never overwrite), so one sentence books
both legs clause-locally; metro city names in rent/HRA context book
is_metro=True (heuristic documented in nlp_engine.py).

GT10 ruling cell (hand-computed, FY 2025-26): salary 18,00,000, HRA received
3,00,000, rent 4,00,000, metro -> exemption = min(3,00,000; 4,00,000 -
1,80,000; 9,00,000) = 2,20,000 -> old-regime taxable 18,00,000 - 50,000 std
- 2,20,000 = 15,30,000 -> slab 12,500 + 1,00,000 + 1,59,000 = 2,71,500
x1.04 cess = 2,82,360.00 (prof tax 0 explicit, no other deductions).
"""
import os
from typing import Any, Dict, List

import pytest

from ai_models import SemanticAttention, UniversalParser
from nlp_engine import NLPEngine
from tax_engine import TaxEngine
from tax_rules import get_rules

engine = TaxEngine()
nlp = NLPEngine()
parser = UniversalParser()
attention = SemanticAttention()

YEAR = "fy_2025_26"
RULES = get_rules(YEAR)

# Verbatim advisory (task spec + sprint2-design.md Step B item 3): the
# non-metro assumption must never be silent. Both registered years carry
# non_metro_pct 0.40, so the "40%" wording is registry-stable.
METRO_ADVISORY = "Metro status not provided — non-metro 40% assumption applied"


def _old_result(data: Dict[str, Any]):
    return engine.calculate_tax_advanced(dict(data), tax_year=YEAR)["old_regime"]


def _hra_exemption(data: Dict[str, Any]) -> float:
    """The booked Sec 10(13A) exemption (0.0 when no explanation entry)."""
    amounts = [
        exp.amount for exp in _old_result(data).explanations
        if exp.section == "10(13A)"
    ]
    assert len(amounts) <= 1
    return amounts[0] if amounts else 0.0


def _observations(data: Dict[str, Any]) -> List[str]:
    return _old_result(data).audit_observations


# =========================================================================
# 1. Engine — Rule 2A least-of matrix (direct helper, registry rules)
# =========================================================================

@pytest.mark.parametrize(
    "salary,hra_received,rent_paid,expected",
    [
        # metro: each of the three legs wins once
        (1_000_000, 100_000, 500_000, 100_000),   # leg (a) smallest
        (1_800_000, 300_000, 400_000, 220_000),   # leg (b) smallest (GT10)
        (1_000_000, 600_000, 900_000, 500_000),   # leg (c) smallest: 50%
    ],
    ids=["metro-leg-a", "metro-leg-b-GT10", "metro-leg-c-50pct"],
)
def test_calc_hra_metro_least_of_legs(salary, hra_received, rent_paid, expected) -> None:
    assert engine._calc_hra(RULES, salary, hra_received, rent_paid, True) == float(expected)


@pytest.mark.parametrize(
    "salary,hra_received,rent_paid,expected",
    [
        (1_000_000, 100_000, 500_000, 100_000),   # leg (a) smallest
        (1_000_000, 300_000, 250_000, 150_000),   # leg (b) smallest
        (1_000_000, 600_000, 900_000, 400_000),   # leg (c) smallest: 40%
    ],
    ids=["nonmetro-leg-a", "nonmetro-leg-b", "nonmetro-leg-c-40pct"],
)
def test_calc_hra_non_metro_least_of_legs(salary, hra_received, rent_paid, expected) -> None:
    assert engine._calc_hra(RULES, salary, hra_received, rent_paid, False) == float(expected)


def test_calc_hra_none_assumes_non_metro() -> None:
    """is_metro None (unknown) books the non-metro 40% leg."""
    assert engine._calc_hra(RULES, 1_000_000, 600_000, 900_000, None) == 400_000.0


@pytest.mark.parametrize(
    "salary,hra_received,rent_paid",
    [
        (0, 300_000, 400_000),        # salary <= 0
        (1_000_000, 300_000, 0),      # rent_paid <= 0
        (1_000_000, 0, 400_000),      # hra_received <= 0
        (1_000_000, 300_000, 50_000),  # rent < 10% of salary -> leg (b) negative
    ],
    ids=["salary-zero", "rent-zero", "hra-zero", "rent-below-10pct"],
)
def test_calc_hra_zero_guards(salary, hra_received, rent_paid) -> None:
    assert engine._calc_hra(RULES, salary, hra_received, rent_paid, True) == 0.0


# =========================================================================
# 2. Engine — end-to-end cells (fy_2025_26, old regime)
# =========================================================================

def test_gt10_ruling_cell_metro() -> None:
    """Ruling GT10: salary 18L, hra_received 3L, rent 4L, metro, prof tax 0.

    Exemption 2,20,000 (leg b) -> old total 2,82,360.00 (see module docstring
    for the full hand computation)."""
    data = {
        "salary": 1_800_000,
        "hra_received": 300_000,
        "rent_paid": 400_000,
        "is_metro": True,
        "professional_tax": 0,
    }
    old = _old_result(data)
    assert _hra_exemption(data) == 220_000.0
    assert old.taxable_income == 1_530_000.0
    assert old.total_tax == 282_360.00


def test_gt10_exemption_is_metro_insensitive() -> None:
    """GT10's binding leg is (b): the metro pct leg never governs, so the
    exemption is identical for True/False/None — isolating the advisory."""
    base = {"salary": 1_800_000, "hra_received": 300_000, "rent_paid": 400_000,
            "professional_tax": 0}
    assert _hra_exemption({**base, "is_metro": True}) == 220_000.0
    assert _hra_exemption({**base, "is_metro": False}) == 220_000.0
    assert _hra_exemption(base) == 220_000.0


def test_city_contrast_pair_delhi_vs_jaipur() -> None:
    """Identical-except-leg: the metro pct leg BINDS, so Delhi (50%) and
    Jaipur (40%) differ on the same figures."""
    base = {"salary": 1_000_000, "hra_received": 600_000, "rent_paid": 900_000,
            "professional_tax": 0}
    delhi = _hra_exemption({**base, "is_metro": True})
    jaipur = _hra_exemption({**base, "is_metro": False})
    assert delhi == 500_000.0   # 50% of salary
    assert jaipur == 400_000.0  # 40% of salary
    assert delhi - jaipur == 100_000.0


@pytest.mark.parametrize("rent", [0, None], ids=["rent-zero", "rent-absent"])
def test_rent_zero_or_absent_zero_with_advisory(rent) -> None:
    data = {"salary": 1_000_000, "hra_received": 300_000, "professional_tax": 0}
    if rent is not None:
        data["rent_paid"] = rent
    assert _hra_exemption(data) == 0.0
    assert METRO_ADVISORY in _observations(data)


def test_salary_zero_zero_with_advisory() -> None:
    data = {"hra_received": 300_000, "rent_paid": 400_000, "professional_tax": 0}
    old = _old_result(data)
    assert old.total_deductions == 0.0
    assert _hra_exemption(data) == 0.0
    assert METRO_ADVISORY in _observations(data)


def test_metro_advisory_absent_when_explicitly_answered() -> None:
    base = {"salary": 1_000_000, "hra_received": 600_000, "rent_paid": 900_000,
            "professional_tax": 0}
    assert METRO_ADVISORY not in _observations({**base, "is_metro": True})
    assert METRO_ADVISORY not in _observations({**base, "is_metro": False})
    # Unknown (absent) -> disclosed on BOTH regimes (shared observations).
    result = engine.calculate_tax_advanced(dict(base), tax_year=YEAR)
    assert METRO_ADVISORY in result["old_regime"].audit_observations
    assert METRO_ADVISORY in result["new_regime"].audit_observations


def test_rent_below_10pct_books_zero_no_exemption_entry() -> None:
    data = {"salary": 1_000_000, "hra_received": 300_000, "rent_paid": 50_000,
            "is_metro": True, "professional_tax": 0}
    assert _hra_exemption(data) == 0.0
    assert _old_result(data).total_deductions == 50_000.0  # std deduction only


def test_new_regime_ignores_all_three_hra_keys() -> None:
    """115BAC: hra_received/rent_paid/is_metro must not move the new regime."""
    loaded = {"salary": 1_800_000, "hra_received": 300_000, "rent_paid": 400_000,
              "is_metro": True, "professional_tax": 0}
    control = {"salary": 1_800_000, "professional_tax": 0}
    result = engine.calculate_tax_advanced(dict(loaded), tax_year=YEAR)
    reference = engine.calculate_tax_advanced(dict(control), tax_year=YEAR)
    assert result["new_regime"].total_tax == reference["new_regime"].total_tax
    assert result["new_regime"].total_tax == 150_800.0  # TI 17,25,000 x slabs


# =========================================================================
# 3. Engine — legacy-compat parity cell (binding)
# =========================================================================

@pytest.mark.parametrize("legacy_hra", [300_000, 500_000])
def test_legacy_hra_key_reproduces_legacy_formula(legacy_hra: int) -> None:
    """The session key ``hra`` (frontend-suggested, pre-existing) maps to BOTH
    hra_received and rent_paid, so the three-leg formula reproduces the
    legacy two-keyword formula min(0.4*salary, hra, hra - 0.1*salary) EXACTLY.
    At salary 18L: hra 3L -> 1,20,000; hra 5L -> 3,20,000."""
    salary = 1_800_000
    exemption = _hra_exemption(
        {"salary": salary, "hra": legacy_hra, "professional_tax": 0}
    )
    legacy = max(0.0, min(0.4 * salary, legacy_hra, legacy_hra - 0.1 * salary))
    assert exemption == legacy
    assert exemption == {300_000: 120_000.0, 500_000: 320_000.0}[legacy_hra]


def test_new_keys_authoritative_over_legacy_hra() -> None:
    salary = 1_000_000
    # hra_received overrides the legacy hra for its leg.
    got = _hra_exemption({"salary": salary, "hra": 300_000, "hra_received": 100_000,
                          "rent_paid": 500_000, "professional_tax": 0})
    assert got == 100_000.0
    # rent_paid overrides the legacy hra for the rent leg only: legs are
    # (a) 3,00,000 (legacy hra), (b) 2,50,000 - 1,00,000 = 1,50,000,
    # (c) 4,00,000 -> 1,50,000. Had the legacy hra filled BOTH legs,
    # leg (b) would be 2,00,000 — distinguishable.
    got = _hra_exemption({"salary": salary, "hra": 300_000, "rent_paid": 250_000,
                          "professional_tax": 0})
    assert got == 150_000.0
    # An explicit hra_received 0 is authoritative (present beats legacy).
    assert _hra_exemption({"salary": salary, "hra": 300_000, "hra_received": 0,
                           "rent_paid": 500_000, "professional_tax": 0}) == 0.0


# =========================================================================
# 4. Engine — 80GG guard switches to hra_received > 0
# =========================================================================

def test_80gg_blocked_when_hra_received_declared() -> None:
    """Deliberate behavior change (spec Step B item 1): the guard tests the
    HRA RECEIVED leg, not the computed exemption. Legacy: {"hra": 50_000} at
    salary 10L computed hra_ex = min(4,00,000; 50,000; -50,000) -> 0 and let
    80GG through; a user who receives HRA can never claim 80GG."""
    data = {"salary": 1_000_000, "80gg": 100_000, "hra": 50_000,
            "professional_tax": 0}
    assert _old_result(data).total_deductions == 50_000.0  # std deduction only
    assert engine._calc_80gg(100_000, 1_000_000, 50_000, RULES) == 0.0


def test_80gg_granted_on_rent_without_any_hra() -> None:
    # The legacy "80gg" session key IS the rent input for non-HRA claimants
    # (the engine subtracts 10% of income internally): 80GG = least of
    # 60,000 / 25% x 10,00,000 / 3,00,000 - 10% x 10,00,000 = 60,000.
    data = {"salary": 1_000_000, "80gg": 300_000, "professional_tax": 0}
    assert _old_result(data).total_deductions == 110_000.0  # 50,000 std + 60,000
    assert engine._calc_80gg(300_000, 1_000_000, 0, RULES) == 60_000.0


# =========================================================================
# 5. NLP — split attention categories, dual booking, metro detection
# =========================================================================

def run_chat(turns: List[str], session: Dict[str, Any] = None):
    sess: Dict[str, Any] = session if session is not None else {"id": "pytest_hra"}
    responses = []
    for msg in turns:
        result = nlp.process_message(msg, sess)
        responses.append(result["response"])
    return sess, responses


def test_dual_booking_in_one_sentence() -> None:
    """Clause-local resolution (Sprint 1) books BOTH legs from one sentence."""
    sess, _ = run_chat(["I receive 3L HRA and pay 2L rent"])
    assert sess.get("hra_received") == 300_000
    assert sess.get("rent_paid") == 200_000


def test_dual_booking_monthly_annualized_exactly_once() -> None:
    sess, _ = run_chat(["I pay 25k rent monthly and receive 15k HRA monthly"])
    assert sess.get("rent_paid") == 300_000      # 25k x 12, once
    assert sess.get("hra_received") == 180_000   # 15k x 12, once


def test_metro_city_books_is_metro_true() -> None:
    sess, _ = run_chat(["I live in Mumbai and pay 20k rent"])
    assert sess.get("is_metro") is True
    assert sess.get("rent_paid") == 20_000


def test_non_metro_city_stays_unbooked() -> None:
    """NLP never asserts a non-metro city: is_metro stays absent (falsy) and
    the engine's non-metro 40% assumption + advisory covers the session."""
    sess, _ = run_chat(["I live in Jaipur and pay 20k rent"])
    assert not sess.get("is_metro")
    assert sess.get("rent_paid") == 20_000


def test_metro_city_without_rent_context_ignored() -> None:
    """Documented heuristic: a metro city books is_metro only with rent/HRA
    context (or while the rent/HRA discovery question is open) — "I work in
    Mumbai" must not flip the HRA metro flag."""
    sess, _ = run_chat(["I work in Mumbai"])
    assert "is_metro" not in sess


def test_rent_accumulates_never_overwrites() -> None:
    """Both new keys accumulate like other deductions (NOT in OVERWRITE_CATS)."""
    sess, _ = run_chat(["I pay 10k rent and 5k rent"])
    assert sess.get("rent_paid") == 15_000
    sess, _ = run_chat(["I pay 10k rent", "I pay 5k rent"])
    assert sess.get("rent_paid") == 15_000


def test_hra_discovery_question_asks_all_three() -> None:
    sess, _ = run_chat(
        ["hello"],
        {"id": "pytest_hra_q", "salary": 1_800_000, "80c": 150_000,
         "80d": 25_000, "nps": 50_000},
    )
    reply = _
    assert reply, "a reply was generated"
    body = reply[0].lower()
    assert "rent" in body
    assert "hra" in body
    assert "metro" in body
    # The reply states the non-metro default (the response must disclose it).
    assert "40%" in body


def test_bare_no_walks_rent_then_hra_then_metro() -> None:
    """The combined question collects all three slots; three bare "no"s zero
    rent, zero HRA and book is_metro=False, completing the waterfall."""
    sess, responses = run_chat(
        ["hello", "no", "no", "no"],
        {"id": "pytest_hra_no", "salary": 1_800_000, "80c": 150_000,
         "80d": 25_000, "nps": 50_000},
    )
    assert sess.get("rent_paid") == 0
    assert sess.get("hra_received") == 0
    assert sess.get("is_metro") is False
    assert sess.get("phase") == "FINAL"


def test_bare_city_reply_to_hra_question_books_metro() -> None:
    """Answering the metro part with a bare city name (no rent keyword in the
    utterance) books is_metro via the open-question context."""
    sess, _ = run_chat(
        ["hello", "Mumbai"],
        {"id": "pytest_hra_city", "salary": 1_800_000, "80c": 150_000,
         "80d": 25_000, "nps": 50_000},
    )
    assert sess.get("is_metro") is True


def test_attention_split_resolutions() -> None:
    """A16-family: rent-paid utterances book rent_paid; HRA-received
    utterances book hra_received; rental income stays rental."""
    cases = [
        ("I pay rent of 20k per month", "rent_paid"),
        ("monthly rent paid 25k", "rent_paid"),
        ("my monthly rent is 30k", "rent_paid"),
        ("flat rent 18k", "rent_paid"),
        ("my hra is 15k monthly", "hra_received"),
        ("hra received from employer 20k", "hra_received"),
        ("house rent allowance of 3 lakhs", "hra_received"),
        ("rent received from tenant 15k", "rental"),
    ]
    for sentence, expected in cases:
        matches = parser.parse(sentence)
        vs, ve = (matches[0]["start"], matches[0]["end"]) if matches else (0, 0)
        assert attention.resolve_category(sentence, vs, ve) == expected, sentence


# =========================================================================
# 6. API validation rows (security table: bool-strict is_metro; numeric
#    0..1e11 non-finite-reject hra_received/rent_paid)
# =========================================================================

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


class TestCalculateRequestHraFields:
    def test_gt10_via_calculate_endpoint(self, client) -> None:
        response = client.post("/calculate", json={
            "salary": 1_800_000, "hra_received": 300_000, "rent_paid": 400_000,
            "is_metro": True, "professional_tax": 0,
        })
        assert response.status_code == 200
        assert response.json()["old_regime"]["total_tax"] == 282_360.0

    @pytest.mark.parametrize(
        "payload",
        [
            {"is_metro": "yes"},
            {"is_metro": 1},
            {"is_metro": "true"},
            {"hra_received": -5},
            {"hra_received": "abc"},
            {"rent_paid": 1e12},
            {"rent_paid": -1},
        ],
        ids=["metro-yes", "metro-1", "metro-true-str", "hra-negative",
             "hra-string", "rent-over-1e11", "rent-negative"],
    )
    def test_rejects_invalid_rows(self, client, payload) -> None:
        response = client.post("/calculate", json=payload)
        assert response.status_code == 422, payload

    def test_plain_numeric_string_hra_coerces_like_other_fields(self, client) -> None:
        # Documented pydantic lax-mode behavior for /calculate numeric
        # fields (mirrors capital_gains amount coercion in test_validation):
        # "300000" -> 300000.0. (String rejection is the SESSION rows'
        # job — covered in TestChatSessionHraRows.)
        response = client.post("/calculate", json={"hra_received": "300000"})
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "payload",
        [
            {"is_metro": True},
            {"is_metro": False},
            {"is_metro": None},
            {"hra_received": 0},
            {"rent_paid": 1e11},
            {"hra_received": 300_000, "rent_paid": 400_000},
        ],
        ids=["metro-true", "metro-false", "metro-null", "hra-zero",
             "rent-at-cap", "both-valid"],
    )
    def test_accepts_valid_rows(self, client, payload) -> None:
        response = client.post("/calculate", json=payload)
        assert response.status_code == 200, payload

    def test_rejects_infinite_hra_received(self, client) -> None:
        # Raw body: 1e309 parses to inf server-side (bounds reject it).
        response = client.post(
            "/calculate",
            content='{"salary": 1800000, "hra_received": 1e309}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestChatSessionHraRows:
    def _chat(self, client, session: Dict[str, Any]):
        return client.post("/chat", json={"message": "hi", "session": session})

    @pytest.mark.parametrize(
        "session",
        [
            {"id": "sid_hra_val1", "is_metro": "yes"},
            {"id": "sid_hra_val1", "is_metro": 1},
            {"id": "sid_hra_val1", "hra_received": -5},
            {"id": "sid_hra_val1", "rent_paid": 1e12},
            {"id": "sid_hra_val1", "hra_received": "abc"},
        ],
        ids=["metro-yes", "metro-1", "hra-negative", "rent-over-1e11",
             "hra-string"],
    )
    def test_rejects_invalid_session_rows(self, client, session) -> None:
        assert self._chat(client, session).status_code == 422, session

    @pytest.mark.parametrize(
        "session",
        [
            {"id": "sid_hra_ok1", "is_metro": True},
            {"id": "sid_hra_ok1", "is_metro": False},
            {"id": "sid_hra_ok1", "is_metro": None},
            {"id": "sid_hra_ok1", "hra_received": 0},
            {"id": "sid_hra_ok1", "rent_paid": 1e11},
        ],
        ids=["metro-true", "metro-false", "metro-null", "hra-zero",
             "rent-at-cap"],
    )
    def test_accepts_valid_session_rows(self, client, session) -> None:
        assert self._chat(client, session).status_code == 200, session

    def test_legacy_hra_key_keeps_numeric_row(self, client) -> None:
        assert self._chat(
            client, {"id": "sid_hra_ok1", "hra": 300_000}
        ).status_code == 200

    def test_metro_advisory_reaches_chat_response(self, client) -> None:
        """The response must state the non-metro assumption (the engine's
        audit observation rides inside the chat tax_report)."""
        response = client.post(
            "/chat",
            json={
                "message": "I get 3l hra and pay 4l rent yearly",
                "session": {"id": "sid_hra_adv1", "salary": 1_800_000},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["session"]["hra_received"] == 300_000
        assert body["session"]["rent_paid"] == 400_000
        assert body["tax_report"] is not None
        assert any(
            METRO_ADVISORY in obs
            for obs in body["tax_report"]["old_regime"]["audit_observations"]
        )

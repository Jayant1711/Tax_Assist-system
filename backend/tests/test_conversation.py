"""Block 4 port — multi-turn conversation flows (legacy checks C01-C10).

Source flows: backend/test_suite.py lines 143-249. Assertion upgrades per
ISSUE #16: C04 now asserts the full documented correction round-trip
(salary restored to 6,000,000 AND 80c set to 200,000). The tautological
C03b check of the legacy harness is NOT ported — see the C03 docstring
for the verified engine behavior behind that decision.
"""
from typing import Any, Dict, List, Tuple

from nlp_engine import NLPEngine
from tax_engine import TaxEngine

nlp = NLPEngine()
engine = TaxEngine()


def run_chat(turns: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Simulate a full multi-turn chat. Returns (final session, responses)."""
    sess: Dict[str, Any] = {"id": f"pytest_conv_{id(turns)}"}
    responses: List[str] = []
    for msg in turns:
        result = nlp.process_message(msg, sess)
        responses.append(result["response"])
    return sess, responses


def test_c01_salaried_with_80c_80d() -> None:
    sess, _ = run_chat([
        "I am a software engineer",
        "my CTC is 25 lakhs",
        "80c investments of 1.5 lakhs",
        "health insurance of 25k",
        "no",
        "no",
        "no",
        "/end",
    ])
    assert sess.get("profile") == "Salaried"
    assert abs(sess.get("salary", 0) - 2_500_000) < 1
    assert abs(sess.get("80c", 0) - 150_000) < 1
    assert abs(sess.get("80d", 0) - 25_000) < 1


def test_c02_business_owner_multi_income() -> None:
    sess, _ = run_chat([
        "I run a shop",
        "my business income is 40 lakhs",
        "I also have rental income of 10 lakhs",
        "80c of 1 lakh",
        "no",
        "/end",
    ])
    assert sess.get("profile") == "Business Owner"
    assert abs(sess.get("business", 0) - 4_000_000) < 1
    assert abs(sess.get("rental", 0) - 1_000_000) < 1


def test_c03_ppf_captured_via_80c() -> None:
    """Ports legacy C03a only. Legacy C03b was a tautology (_last_question
    is always set, so the `or` branch always held) and is deliberately not
    carried over. The real assertion it gestured at — the "yes 25k" turn
    context-carrying to 80d via the asked-category prior — does NOT hold in
    the current engine: the acknowledgement prefix ("Mapped — 80C: ...") is
    stored inside _last_question and _get_asked_cat matches "80c" keywords
    before "80d" ones, so the bare value lands in 80c (total 175,000) and
    80d stays None. Documented in the ISSUE #16 migration report instead of
    being pinned as a failing test.
    """
    sess, _ = run_chat([
        "I am a teacher earning 30 lakhs",
        "1.5 lakh in PPF",
        "yes 25k",  # intended as the 80D answer; currently mapped to 80C
    ])
    assert sess.get("80c", 0) > 0  # C03a: PPF amount captured


def test_c04_correction_round_trip() -> None:
    sess, _ = run_chat([
        "I am a pilot earning 60 lakhs",
        "2 lakhs",              # no context -> transiently lands on salary
        "no that was 80C",      # correction re-maps it and restores salary
    ])
    assert sess.get("profile") == "Salaried"
    assert sess.get("salary") == 6_000_000  # restored, not left at 200,000
    assert sess.get("80c") == 200_000       # the corrected 2L lands in 80C


def test_c05_multi_entity_sentence() -> None:
    sess, _ = run_chat([
        "I earn 50L from salary, 10L from rental, and I paid 1.5L in PPF",
    ])
    assert abs(sess.get("salary", 0) - 5_000_000) < 1
    assert abs(sess.get("rental", 0) - 1_000_000) < 1
    assert abs(sess.get("80c", 0) - 150_000) < 1


def test_c06_hinglish_profession() -> None:
    sess, _ = run_chat([
        "mera kaam farming hai",
        "meri income 20 lakh hai",
    ])
    assert sess.get("profile") is not None


def test_c07_word_form_numbers() -> None:
    sess, _ = run_chat([
        "I am a banker earning thirty five lakhs annually",
    ])
    assert sess.get("profile") == "Salaried"
    assert abs(sess.get("salary", 0) - 3_500_000) < 1


def test_c08_senior_citizen_profile() -> None:
    sess, _ = run_chat([
        "I am a retired government officer",
        "pension income of 8 lakhs",
        "FD interest of 3 lakhs",  # 80TTB routing not asserted (as in legacy)
    ])
    assert sess.get("profile") == "Salaried"


def test_c09_complex_ca_case() -> None:
    sess, _ = run_chat([
        "I am a CA running my own practice",
        "professional income 45 lakhs",
        "I also have 5 lakhs from shares sold",
        "I paid 1.5L in LIC and 50k in NPS",
        "health insurance for family 30k",
        "I donated 20k to PM fund",
        "/end",
    ])
    assert sess.get("profile") == "Business Owner"
    assert sess.get("business", 0) > 0
    assert sess.get("80c", 0) > 0


def test_c10_end_command() -> None:
    sess, _ = run_chat(["I earn 50L", "/end"])
    assert sess.get("phase") == "FINAL"


# ── ISSUE #3 (C3): monthly amounts must be annualized exactly once ──────

def test_per_month_annualized_once() -> None:
    """C3: "per month" is annualized by the parser itself (unit ×12); the
    engine must not repeat the ×12. Regression for salary == 11,520,000
    (×144)."""
    sess, _ = run_chat([
        "I am a software engineer",
        "my salary is 80,000 per month",
    ])
    assert sess.get("salary") == 960_000


def test_pm_annualized_once() -> None:
    """C3: "pm" is annualized by the parser's trailing-window check; the
    engine must not repeat the ×12."""
    sess, _ = run_chat([
        "I am a software engineer",
        "my salary is 45k pm",
    ])
    assert sess.get("salary") == 540_000


def test_monthly_keyword_annualized_once() -> None:
    """C3: "monthly" is not a parser unit — the engine performs (and must
    still perform) exactly one ×12 for it."""
    sess, _ = run_chat([
        "I am a software engineer",
        "i earn 8 lakhs monthly",
    ])
    assert sess.get("salary") == 9_600_000


# ── ISSUE #6 (C4a): default fall-through must not clobber income ────────

def test_default_fallthrough_does_not_clobber_income() -> None:
    """C4a: a profile-default fall-through (no category keyword scored
    above threshold) must never OVERWRITE an existing positive income.
    The amount is reported back with the UNRECOGNIZED badge so the user
    keeps control (regression for salary 4,500,000 → 200,000)."""
    sess: Dict[str, Any] = {"id": "pytest_conv_c4a"}
    nlp.process_message("I am a teacher earning 30 lakhs", sess)
    result = nlp.process_message("2 lakhs", sess)
    assert sess.get("salary") == 3_000_000
    assert any("UNRECOGNIZED AMOUNT" in e for e in result["extracted"])


def test_fresh_junk_amount_still_books() -> None:
    """C4a: a fresh session has no positive income to protect — the legacy
    booking behavior is unchanged (no profile -> other_income)."""
    sess, _ = run_chat(["2 lakhs"])
    assert sess.get("other_income") == 200_000


# ── ISSUE #7 (C4b): clause-bound negative keywords ──────────────────────

def test_clause_binding_splits_amounts() -> None:
    """C4b: "health" sits in 80c.neg, and the sentence-global penalty used
    to zero out the whole 80C category so 80D captured BOTH amounts
    (80d == 200,000, no 80c). Each value must book to the category of the
    clause it appears in."""
    sess, _ = run_chat([
        "I invested 1.5L in PPF and 50k in health insurance",
    ])
    assert sess.get("80c") == 150_000
    assert sess.get("80d") == 50_000


def test_both_clauses_same_category_accumulate() -> None:
    """C4b: two clauses resolving to the same category accumulate within
    the turn (unchanged legacy semantics)."""
    sess, _ = run_chat([
        "I have 1 lakh in PPF and 2 lakhs in ELSS",
    ])
    assert sess.get("80c") == 300_000


# ── ISSUE #8 (C4c): property-sale noun forms book to capital_gains ──────

def test_property_sale_noun_form_books_capital_gains() -> None:
    """C4c: the noun form "property sale" was absent from capital_gains.pos
    (only "sold property"/"property sold"/"house sale"/"land sale" existed),
    so the amount fell through to the profile default instead of booking as
    a property capital gain."""
    sess, _ = run_chat([
        "I got 20 lakhs from property sale last year",
    ])
    assert sess.get("capital_gains") == [
        {"type": "property_cg", "amount": 2_000_000, "holding": "unknown"}
    ]
    assert "rental" not in sess
    assert "other_income" not in sess


def test_capital_gains_gross_value_advisory() -> None:
    """C4c: the engine discloses the honest limitation that the declared
    amount is treated as the GAIN, on both regimes, whenever capital gains
    exist. (Sprint 2: tax_year pinned to the pre-Sprint-2 default
    "fy_2024_25"; the advisory strings are year-invariant.)"""
    result = engine.calculate_tax_advanced(
        {"capital_gains": [{"type": "equity_ltcg", "amount": 200_000}]},
        tax_year="fy_2024_25",
    )
    for regime in ("old_regime", "new_regime"):
        assert any(
            "GAIN (sale price minus cost of acquisition)" in obs
            for obs in result[regime].audit_observations
        )

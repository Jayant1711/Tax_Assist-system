"""Golden-file regression corpus — production misclassification patterns.

Source: docs/nlp-pipeline.md §11 (verified against current code 2026-10-31)
and the raw log entries in backend/logs/session_audit.json (221 April
entries; 226 total at extraction time). Corpus target per ADR-011
(docs/decisions.md) and docs/testing.md §4 item 3: replay the exact
misclassified utterances with pinned expected categories — the tests that
would have caught the April regressions.

Contract: five of the six patterns still reproduce in current code, so
their tests pin the DESIRED post-fix behavior and are marked
``xfail(strict=True)``. Under strict xfail an unexpected pass FAILS the
suite, which forces the fixing issue (#3, #4, #6, #7, #8) to delete its
marker — that removal is the issue's acceptance step. Do not "fix" these
tests by weakening assertions. The one pattern already fixed in current
code (education loan → 80E) is a normal test and must pass today.

Current (buggy) values below were re-verified by executing the engines on
2026-10-31; they are recorded here for the sprint log.
"""
from typing import Any, Dict, List, Tuple

import pytest

from nlp_engine import NLPEngine
from tax_engine import TaxEngine

nlp = NLPEngine()
engine = TaxEngine()


def run_chat(turns: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Simulate a full multi-turn chat. Returns (final session, responses)."""
    sess: Dict[str, Any] = {"id": f"pytest_golden_{id(turns)}"}
    responses: List[str] = []
    for msg in turns:
        result = nlp.process_message(msg, sess)
        responses.append(result["response"])
    return sess, responses


def test_tuition_does_not_overwrite_salary() -> None:
    """§11 "Tuition → salary" — audit entries idx 200-201, sid_1776965272179
    (2026-04-23 22:58-22:59); idx 201 is the exact turn "childs tution of 2
    Lakhs" ack'd as "Successfully mapped SALARY: ₹200,000", destroying the
    session's existing salary. Mechanism: bare "tution" (no "fee") matches
    no 80C keyword, so the score falls under threshold to the profile
    default "salary" and the OVERWRITE rule (nlp_engine.py:203-210) erases
    the prior value. FIXED in current code (ISSUE #6): bare "tution"/
    "tuition"/"child education" stems now score 80C directly (layer 1) and
    a default fall-through can no longer overwrite a positive income
    (layer 2). Normal test — must pass today; removing the xfail marker
    was ISSUE #6's acceptance step.

    Verified 2026-10-31 post-fix: salary == 4,500,000 (untouched) and
    80c == 200,000 (tuition booked to 80C).
    """
    sess, _ = run_chat([
        "I am a software engineer earning 45 lakhs per year",
        "childs tution of 2 Lakhs",
    ])
    assert sess.get("salary") == 4_500_000  # unchanged by the tuition turn
    assert sess.get("80c") == 200_000       # tuition fee booked to 80C


def test_ppf_and_health_insurance_split_correctly() -> None:
    """§11 "PPF → 80D" — audit entry idx 66, sid_1776883718048 (2026-04-23
    00:25): the sentence was ack'd as "80D: ₹150,000, 80D: ₹50,000".
    Mechanism: "health" sits in 80c's negative keywords (ai_models.py:218),
    so the sentence-global −10 penalty wipes the whole 80C category while
    80D keeps its content score plus the +30 asked-category prior.
    FIXED in current code (ISSUE #7): the per-sentence loop segments the
    sentence into clauses on coordinating "and"/"&", and each value is
    scored against its own clause — the negative-keyword environment is
    clause-local, so PPF books to 80C and health insurance to 80D. Normal
    test — must pass today; removing the xfail marker was ISSUE #7's
    acceptance step.

    Verified 2026-10-31 post-fix: 80c == 150,000 and 80d == 50,000.
    """
    sess, _ = run_chat([
        "I am a software engineer",
        "I invested 1.5L in PPF and 50k in health insurance",
    ])
    assert sess.get("80c") == 150_000
    assert sess.get("80d") == 50_000


def test_property_sale_books_capital_gains() -> None:
    """§11 "Property sale → income (not capital gains)" — audit entry idx
    15, test_1776875973906 (2026-04-22 22:10): all three amounts were
    logged as OTHER INCOME (3,000,000 + 1,400,000 + 500,000). Mechanism:
    "property sale" is absent from capital_gains.pos (ai_models.py:179-193
    has "property sold"/"house sale"/"land sale" but not this noun phrase),
    so the trailing "rental" keyword captures the whole sentence.
    FIXED in current code (ISSUES #7 + #8): clause segmentation binds each
    amount to its own clause (#7) and the noun-form keywords "property
    sale"/"flat sale"/"plot sale"/"sale of property" now score
    capital_gains directly (#8). Normal test — must pass today; removing
    the xfail marker was ISSUE #8's acceptance step.

    Verified 2026-10-31 post-fix: salary == 3,000,000, rental == 500,000
    (only the 5L rent), and the 14L books as a property capital gain.
    """
    sess, _ = run_chat([
        "i earned 30 lakhs from salary, 14 lakhs from property sale and 5 lakhs from rental",
    ])
    assert sess.get("salary") == 3_000_000
    assert sess.get("rental") == 500_000
    capital_gains = sess.get("capital_gains")
    assert isinstance(capital_gains, list)
    assert any(
        entry.get("amount") == 1_400_000 and entry.get("type") == "property_cg"
        for entry in capital_gains
    )


def test_education_loan_books_80e() -> None:
    """§11 "Education-loan interest → income" — audit entry idx 31,
    test_1776876480615 (2026-04-22 22:19): the turn grew other_income to
    ₹500,000. FIXED in current code: "education loan" was added to 80e.pos
    (ai_models.py:241-246), so the amount now books to 80E. Normal test —
    must pass today; this is the corpus's already-fixed control case.

    Current behavior (2026-10-31): 80e == 500,000.0 and no "other_income"
    key is created. Note (per §11) the amount semantics remain crude: the
    loan amount is booked as an interest deduction — out of scope here.
    """
    sess, _ = run_chat([
        "I am a shopkeeper",
        "yes 5 lakhs from education Loan",
    ])
    assert sess.get("80e") == 500_000
    assert "other_income" not in sess


def test_monthly_salary_annualized_once() -> None:
    """§11 "Double annualization" row — explicitly not in the April logs
    (the engine predated monthly annualization); verified live in current
    code. Mechanism: the parser annualizes "per month" utterances ×12
    (ai_models.py:85, 88-90) and the NLP engine annualizes the same value
    again ×12 (nlp_engine.py:179-185). FIXED in current code (ISSUE #3):
    the parser flags its own annualized matches ("annualized": True) and
    the engine converts only matches the parser left monthly. Normal test
    — must pass today; removing the xfail marker was ISSUE #3's
    acceptance step.

    Verified 2026-10-31: "my salary is 80,000 per month" → salary ==
    960,000.0 (exactly one ×12).
    """
    sess, _ = run_chat([
        "I am a software engineer",
        "my salary is 80,000 per month",
    ])
    assert sess.get("salary") == 960_000


def test_agricultural_income_exempt_in_old_regime() -> None:
    """Engine-level companion to the §11 corpus — docs/tax-rules.md C2:
    agricultural income is added to old-regime gross income
    (tax_engine.py:152) while the same output labels it "Exempt"
    (:202-203); the new regime excludes it (:241), biasing the regime
    comparison. FIXED in current code (ISSUE #4): agricultural income is
    excluded from old-regime gross/taxable income, the itemised Exempt
    entry is preserved, and a partial-integration observation is appended
    to both regimes when non-agricultural income exceeds ₹2.5L. Full
    10(1) partial integration remains out of scope. Normal test — must
    pass today; removing the xfail marker was ISSUE #4's acceptance step.

    Arithmetic ground truth (verified by running the engine 2026-10-31):
    with {"salary": 3_000_000} alone, old_regime.total_tax == 724,620.0
    (taxable 3,000,000 − 50,000 std deduction − 2,500 professional tax =
    2,947,500 → slab tax 696,750 × 1.04 cess).

    Verified 2026-10-31 post-fix: gross_total_income == 3,000,000.0 and
    total_tax == 724,620.0 with agriculture added.
    """
    result = engine.calculate_tax_advanced(
        {"salary": 3_000_000, "agriculture": 500_000}
    )
    old = result["old_regime"]
    assert old.gross_total_income == 3_000_000
    assert old.total_tax == 724_620.0
    assert any(
        "Agricultural" in detail.get("source", "")
        and detail.get("status") == "Exempt"
        for detail in old.income_details
    )

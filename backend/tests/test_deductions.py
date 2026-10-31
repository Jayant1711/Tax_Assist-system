"""Sprint 2 Step D — deduction correctness (80U/80DD, 80DDB, 80G, 80EEA, 80D parents).

Tests FIRST (red), per AI_RULES.md. Spec: docs/sprint2-design.md "Step D" +
docs/tax-verification.md §6 + expert rulings R-g/R-h/R-i (2026-10-31).

What this step fixes (the H4/M1 collection-vs-booking bugs):
  - 80U/80DD is a FLAT deduction driven by the disability CATEGORY
    ("none" | "40_79" | "80_plus" -> 0 / 75,000 / 1,25,000). The legacy
    numeric ``80u_80dd`` amount is NEVER guessed into a deduction — it
    books nothing and emits the verbatim legacy-amount advisory. Before
    this step the engine collected the amount and silently dropped it.
  - 80DDB = min(expenditure, tier) with the tier keyed on the SELF's age
    as the patient proxy (R-h): age >= 60 -> 1,00,000 else 40,000 — plus
    the patient-age advisory (the patient's real age is not collected).
    The legacy numeric ``80ddb`` amount books nothing + advisory.
  - 80G (R-g): one amount + category (4 options). Categories 3/4 count
    the donation only up to 10% of the ADJUSTED gross total income —
    GTI (before Ch VI-A) minus the special-rate CG entries (aggregate
    112A equity LTCG, Sec 112 property LTCG, 111A equity STCG). Default
    when the category is absent: category 4 + the default-category
    advisory; cash-mode cap advisory whenever the donation exceeds
    ₹2,000 (mode not collectible this sprint). New regime: generic 80G
    books 0 + the PM-CARES-class advisory.
  - 80EEA: REMOVED — the session key and the /calculate field now 422
    with the discontinuation message; chat mentions get the advisory
    keyword check (no state mutation).
  - 80D parents: base cap 25,000 (either parent 60+ would allow 50,000 —
    the seniority input lands in Sprint 3, ruling i) + the advisory.

GT12 composite cell (hand-computed, old regime, prof tax 0 explicit):
    GTI 10,00,000 (salary) - 50,000 std - 1,25,000 (80U "80_plus")
    - 1,00,000 (80DDB min(1,00,000 spent, 1,00,000 senior tier)) = TI
    7,25,000.  DEVIATION NOTE: the expert matrix pins 59,800.00 for this
    cell, which is the NON-senior (2.5L exemption) figure; the cell's own
    scenario requires age >= 60 (the senior 80DDB tier), and a 60+
    taxpayer gets the 3L basic exemption -> 10,000 + 45,000 = 55,000
    x1.04 cess = 57,200.00. The ruling-compliant figure is pinned here;
    the expert cell's arithmetic is internally inconsistent (verified
    against the registry slab walk for both registered years).

No-silent-collection meta-test: every collected session key must surface
(an explanation section, an income_details entry, or an advisory) or sit
in the documented ignored-list — the legacy 80u_80dd/80ddb amount keys,
whose advisory + no-deduction behavior is asserted by dedicated tests.
"""
import os
from typing import Any, Dict, List, Optional, Tuple

import pytest

from nlp_engine import NLPEngine
from tax_engine import TaxEngine
from tax_rules import get_rules

engine = TaxEngine()
nlp = NLPEngine()

YEAR = "fy_2024_25"  # old-regime deduction behavior is identical in FY 2025-26

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- verbatim advisories (sprint2-design.md Step D + ruling texts) ------
LEGACY_80U_ADVISORY = (
    "80U/80DD is a flat deduction based on disability category "
    "(₹75,000 / ₹1,25,000) — the amount entered was not used; provide the "
    "disability category."
)
LEGACY_80DDB_ADVISORY = (
    "80DDB is a tier-capped deduction on actual treatment expenditure "
    "(₹40,000 limit, ₹1,00,000 where the treated person is 60 or older) — "
    "the amount entered was not used; provide the treatment expenditure."
)
DDB_PATIENT_AGE_ADVISORY = (
    "If the treated person (e.g., a dependent parent) is 60 or older, the "
    "limit is ₹1,00,000 — verify."
)
G80_DEFAULT_CATEGORY_ADVISORY = (
    "Donation category not specified — computed as 50% subject to the 10% "
    "qualifying limit; verify the donee's 80G registration (Form 10BE) and "
    "category."
)
G80_CASH_CAP_ADVISORY = (
    "Cash donations qualify only up to ₹2,000 — verify your payment mode."
)
G80_NEW_REGIME_ADVISORY = (
    "Most 80G donations are not deductible under the new regime (specified "
    "funds like PM CARES remain eligible)."
)
D80_PARENTS_SENIOR_ADVISORY = (
    "If either parent is a senior citizen (60+), the parents' "
    "health-insurance limit is ₹50,000."
)
EEA_422_MESSAGE = (
    "Section 80EEA was discontinued — only loans sanctioned before "
    "1 April 2022 qualified"
)
EEA_CHAT_ADVISORY = (
    "Section 80EEA was discontinued (loans must have been sanctioned "
    "before April 2022) — no deduction available."
)


def _old(data: Dict[str, Any]):
    return engine.calculate_tax_advanced(dict(data), tax_year=YEAR)["old_regime"]


def _new(data: Dict[str, Any]):
    return engine.calculate_tax_advanced(dict(data), tax_year=YEAR)["new_regime"]


def _old_result(data: Dict[str, Any]):
    return engine.calculate_tax_advanced(dict(data), tax_year=YEAR)


def _section_amounts(result, section: str) -> List[float]:
    return [exp.amount for exp in result.explanations if exp.section == section]


def _section_reasons(result, section: str) -> List[str]:
    return [exp.reason for exp in result.explanations if exp.section == section]


def _base(salary: float = 1_000_000) -> Dict[str, Any]:
    # prof tax pinned to 0 so total_deductions is hand-computable (the
    # fy_2024_25 registry default of 2,500 would otherwise join the sum).
    return {"salary": salary, "professional_tax": 0, "tax_year": YEAR}


# =========================================================================
# 1. Section 80U / 80DD — category-driven flat amounts (old regime only)
# =========================================================================

def test_80u_category_40_79_books_75000() -> None:
    res = _old({**_base(), "80u_80dd_category": "40_79"})
    # std 50,000 + flat 75,000
    assert res.total_deductions == 125_000.0
    amounts = _section_amounts(res, "80U/80DD")
    assert amounts == [75_000.0]
    # the category is disclosed in the reason (never a bare amount)
    assert any("40_79" in reason for reason in _section_reasons(res, "80U/80DD"))


def test_80u_category_80_plus_books_125000() -> None:
    res = _old({**_base(), "80u_80dd_category": "80_plus"})
    # std 50,000 + flat 1,25,000
    assert res.total_deductions == 175_000.0
    assert _section_amounts(res, "80U/80DD") == [125_000.0]
    assert any("80_plus" in reason for reason in _section_reasons(res, "80U/80DD"))


def test_80u_category_none_books_zero() -> None:
    res = _old({**_base(), "80u_80dd_category": "none"})
    assert res.total_deductions == 50_000.0
    assert _section_amounts(res, "80U/80DD") == []


def test_80u_legacy_numeric_amount_books_nothing_with_advisory() -> None:
    """Never guess a deduction from the legacy amount (H4)."""
    res = _old({**_base(), "80u_80dd": 100_000})
    assert res.total_deductions == 50_000.0          # std deduction only
    assert _section_amounts(res, "80U/80DD") == []   # no 80U line at all
    assert LEGACY_80U_ADVISORY in res.audit_observations


def test_80u_legacy_amount_with_category_still_discloses() -> None:
    """The category books the flat amount; the ignored legacy amount is
    still disclosed (the advisory keys on presence + nonzero)."""
    res = _old({**_base(), "80u_80dd": 100_000, "80u_80dd_category": "40_79"})
    assert res.total_deductions == 125_000.0
    assert LEGACY_80U_ADVISORY in res.audit_observations


def test_80u_new_regime_has_no_80u_line() -> None:
    res = _new({**_base(), "80u_80dd_category": "80_plus"})
    assert res.total_deductions == 75_000.0  # new-regime std deduction only
    assert _section_amounts(res, "80U/80DD") == []


# =========================================================================
# 2. Section 80DDB — expenditure-capped, tier by the patient-age proxy
# =========================================================================

def test_80ddb_expenditure_capped_at_40k_below_60() -> None:
    res = _old({**_base(), "age": 45, "80ddb_expenditure": 150_000})
    # std 50,000 + min(1,50,000, 40,000)
    assert res.total_deductions == 90_000.0
    assert _section_amounts(res, "80DDB") == [40_000.0]
    assert DDB_PATIENT_AGE_ADVISORY in res.audit_observations


def test_80ddb_senior_tier_1l() -> None:
    res = _old({**_base(), "age": 65, "80ddb_expenditure": 150_000})
    # std 50,000 + min(1,50,000, 1,00,000)
    assert res.total_deductions == 150_000.0
    assert _section_amounts(res, "80DDB") == [100_000.0]
    assert DDB_PATIENT_AGE_ADVISORY in res.audit_observations


def test_80ddb_below_cap_books_actual_expenditure() -> None:
    res = _old({**_base(), "age": 65, "80ddb_expenditure": 20_000})
    # std 50,000 + min(20,000, 1,00,000)
    assert res.total_deductions == 70_000.0
    assert _section_amounts(res, "80DDB") == [20_000.0]


def test_80ddb_legacy_numeric_amount_books_nothing_with_advisory() -> None:
    res = _old({**_base(), "age": 45, "80ddb": 100_000})
    assert res.total_deductions == 50_000.0
    assert _section_amounts(res, "80DDB") == []
    assert LEGACY_80DDB_ADVISORY in res.audit_observations


def test_80ddb_new_regime_has_no_80ddb_line() -> None:
    res = _new({**_base(), "age": 65, "80ddb_expenditure": 150_000})
    assert res.total_deductions == 75_000.0
    assert _section_amounts(res, "80DDB") == []


# =========================================================================
# 3. Section 80G — categories + qualifying limit (R-g)
# =========================================================================

def test_80g_cat_100_no_limit_books_full_amount() -> None:
    res = _old({**_base(), "80g": 100_000, "80g_category": "cat_100_no_limit"})
    assert res.total_deductions == 150_000.0         # std 50,000 + 1,00,000
    assert _section_amounts(res, "80G") == [100_000.0]
    assert any(
        "cat_100_no_limit" in reason
        for reason in _section_reasons(res, "80G")
    )


def test_80g_cat_50_no_limit_books_half() -> None:
    res = _old({**_base(), "80g": 100_000, "80g_category": "cat_50_no_limit"})
    assert res.total_deductions == 100_000.0         # std 50,000 + 50,000
    assert _section_amounts(res, "80G") == [50_000.0]


def test_80g_cat_50_ql_gti_10l_limit_exactly_binds() -> None:
    # GTI 10,00,000 (other income, no salary -> no std deduction):
    # QL = 10% x 10L = 1,00,000; donation 1,00,000 -> 0.5 x 1,00,000.
    res = _old({
        "other_income": 1_000_000, "tax_year": YEAR,
        "80g": 100_000, "80g_category": "cat_50_qualifying_limit",
    })
    assert res.gross_total_income == 1_000_000.0
    assert res.total_deductions == 50_000.0
    assert _section_amounts(res, "80G") == [50_000.0]


def test_80g_cat_50_ql_gti_5l_limit_caps_the_donation() -> None:
    # GTI 5,00,000: QL = 50,000; donation 1,00,000 counted to 50,000
    # -> 0.5 x 50,000 = 25,000.
    res = _old({
        "other_income": 500_000, "tax_year": YEAR,
        "80g": 100_000, "80g_category": "cat_50_qualifying_limit",
    })
    assert res.total_deductions == 25_000.0
    assert _section_amounts(res, "80G") == [25_000.0]


def test_80g_qualifying_limit_excludes_special_rate_cg() -> None:
    """R-g: adjusted GTI = GTI (before Ch VI-A) minus the special-rate CG
    entries. other 10L + equity LTCG 8L -> GTI before Ch VI-A 18L, adjusted
    GTI 10L -> QL 1,00,000 (NOT 10% of 18L = 1.8L, and NOT the double-
    subtracted 10L - 8L = 2L which would cap the donation at 20,000)."""
    res = _old({
        "other_income": 1_000_000, "tax_year": YEAR,
        "capital_gains": [{"type": "equity_ltcg", "amount": 800_000}],
        "80g": 100_000, "80g_category": "cat_50_qualifying_limit",
    })
    assert res.total_deductions == 50_000.0
    assert _section_amounts(res, "80G") == [50_000.0]


def test_80g_default_category_is_cat_4_with_both_advisories() -> None:
    """80g > 0 with no category: category 4 (50% + QL) + the default-
    category advisory + the cash-cap advisory (1,00,000 > 2,000)."""
    res = _old({"other_income": 1_000_000, "tax_year": YEAR, "80g": 100_000})
    assert res.total_deductions == 50_000.0
    assert G80_DEFAULT_CATEGORY_ADVISORY in res.audit_observations
    assert G80_CASH_CAP_ADVISORY in res.audit_observations


def test_80g_cash_cap_advisory_fires_above_2000_only() -> None:
    above = _old({**_base(), "80g": 5_000, "80g_category": "cat_100_no_limit"})
    assert G80_CASH_CAP_ADVISORY in above.audit_observations
    assert _section_amounts(above, "80G") == [5_000.0]
    at_cap = _old({**_base(), "80g": 2_000, "80g_category": "cat_100_no_limit"})
    assert G80_CASH_CAP_ADVISORY not in at_cap.audit_observations


def test_80g_new_regime_zero_with_advisory() -> None:
    result = _old_result({**_base(), "80g": 100_000, "80g_category": "cat_100_no_limit"})
    new_res = result["new_regime"]
    assert new_res.total_deductions == 75_000.0      # std deduction only
    assert _section_amounts(new_res, "80G") == []
    assert G80_NEW_REGIME_ADVISORY in new_res.audit_observations


# =========================================================================
# 4. Section 80EEA — removed (engine + both endpoints + chat advisory)
# =========================================================================

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


def test_80eea_session_key_rejected_by_chat_422(client) -> None:
    response = client.post(
        "/chat",
        json={"message": "hi", "session": {"id": "sid_80eea", "80eea": 150_000}},
    )
    assert response.status_code == 422
    assert "discontinued" in response.text


def test_80eea_rejected_by_calculate_422(client) -> None:
    response = client.post("/calculate", json={"80eea": 150_000})
    assert response.status_code == 422
    assert "discontinued" in response.text


def test_80eea_engine_ignores_the_key_without_deduction() -> None:
    """Direct engine calls bypass the API 422; the removed key must book
    nothing (the pre-Step-D engine capped it into the ded dict)."""
    res = _old({**_base(), "80eea": 150_000})
    assert res.total_deductions == 50_000.0
    assert _section_amounts(res, "80EEA") == []


def test_80eea_chat_mention_gets_advisory_without_state_mutation() -> None:
    session: Dict[str, Any] = {"id": "sid_eea_kw"}
    result = nlp.process_message("I have 80eea interest", session)
    assert any(EEA_CHAT_ADVISORY in entry for entry in result["extracted"])
    # advisory-keyword check only — the session is never mutated with the
    # removed key (it would 422 on the very next /chat round-trip).
    assert "80eea" not in session


class TestNewKeyValidationRows:
    """Step D scope item 6: the new session keys carry their security-table
    rows (enum-strict categories, bounded 80ddb_expenditure) and the
    CalculateRequest mirrors round-trip them to the engine."""

    def test_chat_rejects_bad_80u_80dd_category(self, client) -> None:
        for bad in ("severe", "40-79", 2, True):
            response = client.post(
                "/chat",
                json={"message": "hi",
                      "session": {"id": "sid_cat1", "80u_80dd_category": bad}},
            )
            assert response.status_code == 422, bad

    def test_chat_accepts_the_three_80u_80dd_categories(self, client) -> None:
        for cat in ("none", "40_79", "80_plus", None):
            response = client.post(
                "/chat",
                json={"message": "hi",
                      "session": {"id": "sid_cat2", "80u_80dd_category": cat}},
            )
            assert response.status_code == 200, cat

    def test_chat_rejects_bad_80g_category(self, client) -> None:
        for bad in ("cat_90_no_limit", "100_no_limit", 4):
            response = client.post(
                "/chat",
                json={"message": "hi",
                      "session": {"id": "sid_cat3", "80g_category": bad}},
            )
            assert response.status_code == 422, bad

    def test_chat_accepts_the_four_80g_categories(self, client) -> None:
        for cat in ("cat_100_no_limit", "cat_50_no_limit",
                    "cat_100_qualifying_limit", "cat_50_qualifying_limit", None):
            response = client.post(
                "/chat",
                json={"message": "hi",
                      "session": {"id": "sid_cat4", "80g_category": cat}},
            )
            assert response.status_code == 200, cat

    def test_chat_80ddb_expenditure_bounded_numeric_row(self, client) -> None:
        ok = client.post(
            "/chat",
            json={"message": "hi",
                  "session": {"id": "sid_ddb1", "80ddb_expenditure": 1e11}},
        )
        assert ok.status_code == 200  # le=1e11 inclusive
        for bad in ("abc", -1, True, 1e11 + 1):
            response = client.post(
                "/chat",
                json={"message": "hi",
                      "session": {"id": "sid_ddb2", "80ddb_expenditure": bad}},
            )
            assert response.status_code == 422, bad

    def test_calculate_mirrors_reach_the_engine(self, client) -> None:
        # End-to-end: the aliased mirrors dump into the engine's raw keys.
        response = client.post("/calculate", json={
            "age": 65, "80ddb_expenditure": 20_000,
            "80u_80dd_category": "40_79", "80g": 100_000,
            "80g_category": "cat_50_qualifying_limit", "tax_year": YEAR,
        })
        assert response.status_code == 200
        body = response.json()
        # no salary -> no std deduction; old regime books 80DDB 20,000
        # (min of the actual) + 80U 75,000 + 80G 50,000 (GTI 0 -> QL 0...
        # wait: no income at all, so the qualifying limit is 0 and the
        # donation books 0; only 80U + 80DDB land).
        assert body["old_regime"]["total_deductions"] == 95_000.0
        sections = {
            exp["section"] for exp in body["old_regime"]["explanations"]
        }
        assert "80DDB" in sections and "80U/80DD" in sections
        assert "80G" not in sections  # QL 0 at zero GTI — nothing booked

    def test_calculate_rejects_bad_mirrors(self, client) -> None:
        response = client.post(
            "/calculate", json={"80u_80dd_category": "severe"},
        )
        assert response.status_code == 422
        response = client.post("/calculate", json={"80g_category": "cat_9"})
        assert response.status_code == 422
        response = client.post("/calculate", json={"80ddb_expenditure": -5})
        assert response.status_code == 422

    def test_calculate_request_mirror_round_trip(self) -> None:
        from main import CalculateRequest

        req = CalculateRequest(**{
            "80u_80dd_category": "80_plus",
            "80g_category": "cat_50_no_limit",
            "80ddb_expenditure": 5_000,
        })
        dumped = req.model_dump(by_alias=True)
        assert dumped["80u_80dd_category"] == "80_plus"
        assert dumped["80g_category"] == "cat_50_no_limit"
        assert dumped["80ddb_expenditure"] == 5_000.0

    def test_calculate_request_rejects_80eea_alias(self) -> None:
        from pydantic import ValidationError

        from main import CalculateRequest

        with pytest.raises(ValidationError) as exc_info:
            CalculateRequest(**{"80eea": 150_000})
        assert "discontinued" in str(exc_info.value)


# =========================================================================
# 5. Section 80D (parents) — 25,000 base cap + seniority advisory (R-i)
# =========================================================================

@pytest.mark.parametrize("claimed", [30_000, 40_000], ids=["30k", "40k"])
def test_80d_parents_capped_at_25000_with_advisory(claimed: int) -> None:
    res = _old({**_base(), "80d_parents": claimed})
    # std 50,000 + min(claimed, 25,000)
    assert res.total_deductions == 75_000.0
    parents = [
        exp for exp in res.explanations
        if exp.section == "80D" and "Parents" in exp.particular
    ]
    assert [exp.amount for exp in parents] == [25_000.0]
    assert D80_PARENTS_SENIOR_ADVISORY in res.audit_observations


# =========================================================================
# 6. Composite GT12 (hand-computed; see module docstring for the
#    expert-cell deviation note)
# =========================================================================

def test_gt12_composite_80u_plus_80ddb() -> None:
    res = _old({
        "salary": 1_000_000, "professional_tax": 0, "age": 60,
        "80u_80dd_category": "80_plus", "80ddb_expenditure": 100_000,
        "tax_year": YEAR,
    })
    # std 50,000 + 80U 1,25,000 + 80DDB min(1,00,000, senior tier 1,00,000)
    assert res.total_deductions == 275_000.0
    assert res.taxable_income == 725_000.0
    # senior exemption 3L: (5L-3L)*5% + (7,25,000-5L)*20% = 55,000 x1.04
    assert res.total_tax == 57_200.00
    assert DDB_PATIENT_AGE_ADVISORY in res.audit_observations


# =========================================================================
# 7. No-silent-collection meta-test (table-driven)
# =========================================================================

# Legacy numeric amount keys: their advisory + no-deduction behavior is
# asserted by the dedicated tests above (never guessed into a deduction).
ALLOWED_SILENT = {"80u_80dd", "80ddb"}

NEW_KEYS = ("80u_80dd_category", "80g_category", "80ddb_expenditure")

# (key, session fragment activating the key, artifact kind, expected text)
# kinds: income_source -> income_details[].source, explanation_section ->
# explanations[].section, observation -> audit_observations[] (substring).
_META_TABLE: List[Tuple[str, Dict[str, Any], str, str]] = [
    ("salary", {}, "income_source", "Income from Salary"),
    ("business", {"business": 100_000}, "income_source", "Business"),
    ("rental", {"rental": 100_000}, "income_source", "House Property"),
    ("other_income", {"other_income": 100_000}, "income_source", "Other Sources"),
    ("agriculture", {"agriculture": 100_000}, "income_source", "Agricultural"),
    ("80c", {"80c": 100_000}, "explanation_section", "80C"),
    ("80d", {"80d": 20_000}, "explanation_section", "80D"),
    ("80d_parents", {"80d_parents": 20_000}, "explanation_section", "80D"),
    ("80e", {"80e": 30_000}, "explanation_section", "80E"),
    ("80g", {"80g": 100_000, "80g_category": "cat_100_no_limit"},
     "explanation_section", "80G"),
    ("nps", {"nps": 50_000}, "explanation_section", "80CCD(1B)"),
    ("80tta", {"80tta": 5_000}, "explanation_section", "80TTA"),
    ("80ttb", {"age": 65, "80ttb": 20_000}, "explanation_section", "80TTB"),
    ("80gg", {"salary": 300_000, "80gg": 200_000},
     "explanation_section", "80GG"),
    ("24b", {"24b": 100_000}, "explanation_section", "24(b)"),
    ("hra", {"hra": 200_000}, "explanation_section", "10(13A)"),
    ("hra_received", {"hra_received": 200_000, "rent_paid": 250_000},
     "explanation_section", "10(13A)"),
    ("rent_paid", {"hra_received": 200_000, "rent_paid": 250_000},
     "explanation_section", "10(13A)"),
    ("professional_tax", {"professional_tax": 2_500},
     "explanation_section", "16(iii)"),
    ("80u_80dd_category", {"80u_80dd_category": "40_79"},
     "explanation_section", "80U/80DD"),
    ("80ddb_expenditure", {"age": 45, "80ddb_expenditure": 60_000},
     "explanation_section", "80DDB"),
    ("80g_category", {"80g": 100_000, "80g_category": "cat_100_no_limit"},
     "explanation_section", "80G"),
]

_TABLE_KEYS = {row[0] for row in _META_TABLE}


def _collected_keys() -> set:
    from main import _SESSION_NUMERIC_KEYS

    # main.py validates the Step B HRA legs in their own bounded loop
    # (outside _SESSION_NUMERIC_KEYS) — they are part of the collection
    # surface and belong in this audit.
    return set(_SESSION_NUMERIC_KEYS) | {"hra_received", "rent_paid"} | set(NEW_KEYS)


def test_meta_table_covers_every_collected_key() -> None:
    """Guard against future keys being collected silently: every key in
    the collection surface must have a meta-table row (or sit in the
    documented ignored-list)."""
    collected = _collected_keys()
    unlisted = collected - _TABLE_KEYS - ALLOWED_SILENT
    assert not unlisted, f"collected keys without a no-silent row: {sorted(unlisted)}"
    stale = _TABLE_KEYS - collected
    assert not stale, f"meta-table rows for keys no longer collected: {sorted(stale)}"


@pytest.mark.parametrize(
    "key,extra,kind,expected",
    _META_TABLE,
    ids=[row[0] for row in _META_TABLE],
)
def test_no_silent_collection(key: str, extra: Dict[str, Any], kind: str,
                              expected: str) -> None:
    res = _old({**_base(), **extra})
    if kind == "income_source":
        assert any(expected in entry["source"] for entry in res.income_details), (
            f"{key}: no income_details entry matching {expected!r}"
        )
    elif kind == "explanation_section":
        assert any(exp.section == expected for exp in res.explanations), (
            f"{key}: no explanation section {expected!r}"
        )
    else:
        assert any(expected in obs for obs in res.audit_observations), (
            f"{key}: no advisory matching {expected!r}"
        )


@pytest.mark.parametrize("key", sorted(ALLOWED_SILENT))
def test_legacy_amount_keys_still_disclose(key: str) -> None:
    """The documented ignored-list keys are not silently dropped either —
    each fires its legacy-amount advisory (never guessed into a
    deduction, so no explanation section appears)."""
    res = _old({**_base(), key: 100_000})
    assert _section_amounts(res, "80U/80DD") == []
    assert _section_amounts(res, "80DDB") == []
    advisory = LEGACY_80U_ADVISORY if key == "80u_80dd" else LEGACY_80DDB_ADVISORY
    assert advisory in res.audit_observations

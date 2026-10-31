"""Block 5 port — TaxEngine accuracy with exact-rupee expectations.

Ground truth hand-computed for FY 2024-25 (AY 2025-26) with the engine's
default professional tax of 2,500 for salaried income, then verified
against TaxEngine.calculate_tax_advanced output. The legacy harness's
+/-100, +/-2,000 and +/-5,000 tolerances are removed; T04/T05 assert
exact values instead of only "no crash and result >= 0".

Invariants asserted for every case: recommendation is one of the two
regime labels, savings >= 0, and 0 <= efficiency_score <= 100.

Sprint 2 (ADR-008): every calculate_tax_advanced call below passes
tax_year="fy_2024_25" explicitly — pinned to the pre-Sprint-2 default so
these exact-rupee expectations stay valid when Step A3 flips the registry
default to FY 2025-26.
"""
import pytest

from tax_engine import TaxEngine

engine = TaxEngine()

RECOMMENDATIONS = {"Old Regime", "New Regime"}


def _assert_result_invariants(result: dict) -> None:
    assert result["recommendation"] in RECOMMENDATIONS
    assert result["savings"] >= 0
    assert 0 <= result["efficiency_score"] <= 100


def test_t01_salary_5l_zero_tax_both_regimes() -> None:
    """Old: taxable 447,500 (500,000 - 50,000 std ded - 2,500 prof tax);
    slab tax 9,875 fully wiped by the 87A rebate (taxable <= 5L) -> 0.
    New: taxable 425,000 <= 7L -> 87A rebate -> 0."""
    result = engine.calculate_tax_advanced({"salary": 500_000}, tax_year="fy_2024_25")
    assert result["old_regime"].total_tax == 0.0
    assert result["new_regime"].total_tax == 0.0
    _assert_result_invariants(result)


def test_t02_salary_7l() -> None:
    """Old: taxable 647,500 -> 12,500 (2.5-5L @5%) + 29,500 (5-6.475L @20%)
    = 42,000; x1.04 cess = 43,680.
    New: taxable 625,000 <= 7L -> 87A rebate -> 0."""
    result = engine.calculate_tax_advanced({"salary": 700_000}, tax_year="fy_2024_25")
    assert result["old_regime"].total_tax == 43_680.0
    assert result["new_regime"].total_tax == 0.0
    _assert_result_invariants(result)


def test_t03_salary_12l_with_80c() -> None:
    """Old: taxable 997,500 (12L - 50,000 std - 2,500 prof - 150,000 80C)
    -> 12,500 + 99,500 = 112,000; x1.04 cess = 116,480.
    New: taxable 1,125,000 -> 20,000 + 30,000 + 18,750 = 68,750;
    x1.04 cess = 71,500."""
    result = engine.calculate_tax_advanced({"salary": 1_200_000, "80c": 150_000}, tax_year="fy_2024_25")
    assert result["old_regime"].total_tax == 116_480.0
    assert result["new_regime"].total_tax == 71_500.0
    _assert_result_invariants(result)


def test_t04_salary_50l_full_deductions() -> None:
    """Old: taxable 4,722,500 (50L - 50k std - 2.5k prof - 150k 80C
    - 25k 80D - 50k NPS) -> 1,116,750 + 100,000 + 12,500 = 1,229,250;
    income <= 50L so no surcharge; x1.04 cess = 1,278,420.
    New: taxable 4,925,000 -> 1,167,500; x1.04 cess = 1,214,200."""
    result = engine.calculate_tax_advanced(
        {"salary": 5_000_000, "80c": 150_000, "80d": 25_000, "nps": 50_000},
        tax_year="fy_2024_25",
    )
    assert result["old_regime"].total_tax == 1_278_420.0
    assert result["new_regime"].total_tax == 1_214_200.0
    _assert_result_invariants(result)


def test_t05_salary_1cr_surcharge_bracket() -> None:
    """Surcharge bracket: old-regime income 9,947,500 exceeds the 50L
    threshold, so the OLD regime total includes the 10% surcharge:
    slab tax 2,796,750 + surcharge 279,675 = 3,076,425; x1.04 cess
    = 3,199,482 (marginal relief does not bite: 279,675 < 4,947,500).
    New: taxable 9,925,000 -> 2,667,500 + 266,750 surcharge;
    x1.04 cess = 3,051,620."""
    result = engine.calculate_tax_advanced({"salary": 10_000_000}, tax_year="fy_2024_25")
    assert result["old_regime"].total_tax == 3_199_482.0
    assert result["new_regime"].total_tax == 3_051_620.0
    _assert_result_invariants(result)


# ── ISSUE #4 (C2): agricultural income is exempt (Section 10(1)) ────────

def test_agricultural_income_exempt_old_regime() -> None:
    """C2: agricultural income must be EXCLUDED from old-regime gross and
    taxable income (it was added to gross at tax_engine.py:152 while the
    same amount was labelled "Exempt" in income_details — taxing exempt
    income and biasing the regime comparison).

    Ground truth (engine-verified during the corpus work): with
    {"salary": 3_000_000} the old regime books taxable 2,947,500
    (3,000,000 - 50,000 std ded - 2,500 prof tax) -> slab tax 696,750
    x1.04 cess = 724,620.0. Adding 500,000 agriculture must not change
    that. The new regime never included agriculture, so its total_tax is
    byte-identical to the agriculture-free control."""
    result = engine.calculate_tax_advanced(
        {"salary": 3_000_000, "agriculture": 500_000}, tax_year="fy_2024_25"
    )
    old = result["old_regime"]
    assert old.gross_total_income == 3_000_000
    assert old.total_tax == 724_620.0
    assert any(
        "Agricultural" in detail.get("source", "")
        and detail.get("status") == "Exempt"
        for detail in old.income_details
    )
    # Partial-integration notice on BOTH regimes (non-agri income > 2.5L).
    assert any("Partial integration" in obs for obs in old.audit_observations)
    assert any(
        "Partial integration" in obs
        for obs in result["new_regime"].audit_observations
    )
    # New regime never included agriculture — identical to the control.
    control = engine.calculate_tax_advanced({"salary": 3_000_000}, tax_year="fy_2024_25")
    assert result["new_regime"].total_tax == control["new_regime"].total_tax
    _assert_result_invariants(result)


def test_pure_agricultural_income_exempt_no_integration_notice() -> None:
    """C2 control: agricultural income alone is simply exempt — zero tax
    in the old regime and NO partial-integration observation, because
    non-agricultural income never crosses the ₹2.5L threshold."""
    result = engine.calculate_tax_advanced({"agriculture": 500_000}, tax_year="fy_2024_25")
    assert result["old_regime"].total_tax == 0.0
    assert not any(
        "Partial integration" in obs
        for obs in result["old_regime"].audit_observations
    )
    _assert_result_invariants(result)

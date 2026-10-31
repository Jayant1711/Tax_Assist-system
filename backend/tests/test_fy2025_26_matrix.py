"""FY 2025-26 verified-constants matrix (Sprint 2 Step A3 — ADR-008).

Tests FIRST (red), per AI_RULES.md. Every engine cell below is FY 2025-26
(explicit tax_year="fy_2025_26"; one API cell pins the flipped DEFAULT) and
hand-computed from the tax-expert ground truths against the frozen record
docs/tax-verification.md as amended by the six tax-expert corrections
(2026-10-31).

FY 2025-26 new-regime structure (Sec 115BAC(1A), Finance Act 2025):
slabs 0-4L nil / 5% to 8L / 10% to 12L / 15% to 16L / 20% to 20L / 25% to
24L / 30% above; standard deduction 75,000; 87A rebate 60,000 with zero tax
up to TOTAL income 12,00,000 and the A2 POST-CESS band cap (payable total
capped at TI - 12,00,000; band endpoint 12,73,934 DERIVED, not stored).

Old regime FY 2025-26 is IDENTICAL to FY 2024-25 except the professional
tax DEFAULT (0 instead of 2,500 — state levy; advisory emitted when
defaulted), so old-regime cells are cross-checked against the FY 2024-25
values from tests/test_surcharge_87a.py.

Cell derivations (salaried = salary with std deduction 75,000):
- salary 12,00,000    -> TI 11,25,000; slab 20,000 + 10%x3,25,000 = 52,500;
                         TI <= 12L -> rebate min(52,500, 60,000) -> 0.
- salary 13,00,000    -> TI 12,25,000 > 12L (TI-keyed: NO rebate); slab
                         63,750; 1.04x = 66,300; post-cess cap 25,000.
- salary 13,25,000    -> TI 12,50,000; slab 67,500; cap 50,000.
- salary 13,48,934    -> TI 12,73,934; slab 71,090.10; 1.04x = 73,933.704
                         vs cap 73,934 — the DERIVED band endpoint (beyond
                         it the min() is inert).
- salary 24,00,000    -> TI 23,25,000; slab 2,81,250; x1.04 = 2,92,500.00.
- salary 24,75,000    -> TI 24,00,000; slab 3,00,000 (25% band full);
                         x1.04 = 3,12,000.00; salary 24,75,001 adds the
                         first rupee at 30%: 3,12,000.31 (true edge pair).
- old regime 5,50,001 -> TI 5,00,001 (prof tax 0 explicit): NO rebate
                         (TI-keyed), no band in the old regime; at 5,50,000
                         the rebate wipes the 12,500 slab tax -> 0.
- 112A aggregate      -> salary 20L (slab 19,25,000: 20,000+40,000+60,000
                         +20%x3,25,000 = 1,85,000) + LTCG 8L (12.5% over
                         the 1.25L aggregate exemption = 84,375) + STCG 5L
                         (20% = 1,00,000): 3,69,375 x1.04 = 3,84,150.00.

Deviations from the sprint-ticket ground truths (documented, statute-
consistent — same policy as tests/test_surcharge_87a.py; see the per-test
docstrings): the ticket's three old-regime "first rupee past 5L" cells
apply the 5% rate to the ENTIRE slice above the basic exemption (e.g.
5%x2,50,001 = 12,500.05 at TI 5,00,001; 5%x2,10,000 = 10,500 at senior TI
5,10,000). The statutory old-regime slab — verification record §7's own
"5% (to 5L), 20% (to 10L)" and the frozen FY 2024-25 parity fixture —
taxes the slice ABOVE 5L at 20%: TI 5,00,001 -> 12,500 + 0.20 = 12,500.20
(x1.04 = 13,000.21); senior TI 5,10,000 -> 10,000 + 2,000 = 12,000
(x1.04 = 12,480.00). The ticket values are unimplementable without forking
the old-regime slab per year and breaking parity, so the statute-
consistent figures are pinned here and the diff is reported to the
coordinator for expert re-verification.
"""
import os
from typing import Any, Dict

import pytest

from tax_engine import TaxEngine
from tax_rules import DEFAULT_TAX_YEAR, REGISTRY, get_rules
from tax_rules.fy_2024_25 import FY_2024_25
from tax_rules.fy_2025_26 import FY_2025_26

engine = TaxEngine()
YEAR = "fy_2025_26"

# Verbatim advisory the engine must emit when the registry professional-tax
# default is applied to salaried income (tax-expert ruling j).
PROF_TAX_ADVISORY = (
    "Professional tax is state-specific — enter your actual figure "
    "(commonly ₹200/month, capped ₹2,500/yr)."
)


def _old(data: dict) -> float:
    return engine.calculate_tax_advanced(dict(data), tax_year=YEAR)["old_regime"].total_tax


def _new(data: dict) -> float:
    return engine.calculate_tax_advanced(dict(data), tax_year=YEAR)["new_regime"].total_tax


def _new_result(data: dict) -> Dict[str, Any]:
    return engine.calculate_tax_advanced(dict(data), tax_year=YEAR)


# ── 1. Registry transcription audit (docs/tax-verification.md) ───────────

def test_registry_identity_and_defaults() -> None:
    assert FY_2025_26.tax_year == "2025-26"
    assert FY_2025_26.assessment_year == "2026-27"
    assert FY_2025_26.label == "FY 2025-26 (AY 2026-27)"
    # Step A3 flips the registry default (test_registry.py mirrors this).
    assert DEFAULT_TAX_YEAR == "fy_2025_26"
    assert set(REGISTRY) == {"fy_2024_25", "fy_2025_26"}


def test_new_regime_slabs_fa2025() -> None:
    edges = [(b.upper_bound, b.rate) for b in FY_2025_26.new_regime_slabs]
    assert edges == [
        (400_000, 0.0),      # nil band 0 - 4L
        (800_000, 0.05),     # 4L - 8L
        (1_200_000, 0.10),   # 8L - 12L
        (1_600_000, 0.15),   # 12L - 16L
        (2_000_000, 0.20),   # 16L - 20L
        (2_400_000, 0.25),   # 20L - 24L
        (None, 0.30),        # Above 24L
    ]


def test_old_regime_identical_to_fy_2024_25() -> None:
    """Correction 6: the old regime is unchanged for FY 2025-26 (slabs,
    age exemptions, and all Chapter VI-A caps except the retired 80EEA)."""
    assert [(b.upper_bound, b.rate) for b in FY_2025_26.old_regime_slabs] == [
        (b.upper_bound, b.rate) for b in FY_2024_25.old_regime_slabs
    ]
    assert dict(FY_2025_26.old_regime_exemption_by_age) == dict(
        FY_2024_25.old_regime_exemption_by_age
    )
    assert dict(FY_2025_26.standard_deduction) == {"old": 50_000, "new": 75_000}
    a, b = FY_2024_25.deduction_caps, FY_2025_26.deduction_caps
    for field in (
        "sec_80c", "sec_80d_self", "sec_80d_self_senior", "sec_80d_parents",
        "sec_80d_parents_senior",
        "sec_80ccd_1b", "sec_24b", "sec_80tta", "sec_80tta_senior",
        "sec_80ttb", "sec_80e", "sec_80gg_annual_max", "sec_80gg_income_pct",
        "sec_80gg_rent_excess_pct", "sec_80u_80dd_40_79", "sec_80u_80dd_80_plus",
        "sec_80ddb", "sec_80ddb_senior", "sec_80g",
    ):
        assert getattr(a, field) == getattr(b, field), field


def test_rebate_rules() -> None:
    old = FY_2025_26.rebate["old"]
    new = FY_2025_26.rebate["new"]
    assert (old.income_cap, old.max_amount, old.marginal_relief) == (500_000, 12_500, False)
    assert new.income_cap == 1_200_000
    assert new.max_amount == 60_000
    assert new.marginal_relief is True
    assert new.band_upper_bound is None          # endpoint derived, not stored
    assert new.band_cap_includes_cess is True    # post-cess band (Step A2 algorithm)


def test_surcharge_cg_cess_prof_tax() -> None:
    surcharge = FY_2025_26.surcharge
    assert surcharge.bands == (
        (5_000_000, 0.10), (10_000_000, 0.15), (20_000_000, 0.25), (50_000_000, 0.37),
    )
    assert surcharge.new_regime_cap == 0.25
    assert surcharge.old_regime_cap == 0.37
    assert surcharge.marginal_relief is True
    cg = FY_2025_26.cg
    assert cg.ltcg_112a_rate == 0.125
    assert cg.ltcg_112a_exemption == 125_000
    assert cg.stcg_111a_rate == 0.20
    # FY 2025-26 statute: 12.5% in BOTH regimes post-23-Jul-2024 (transfer-
    # date routing lands in Step C).
    assert dict(cg.property_rate_by_regime) == {"old": 0.125, "new": 0.125}
    assert cg.special_rate_excludes_87a is True
    assert FY_2025_26.cess_rate == 0.04
    # Ruling j: the state levy has no national default — the engine emits
    # the advisory instead of assuming 2,500.
    assert FY_2025_26.professional_tax_default == 0
    assert FY_2024_25.professional_tax_default == 2_500
    assert FY_2025_26.new_regime_cg_surcharge_cap == 0.15
    # 80EEA is REMOVED from the schema in Step D (31-Mar-2022 sunset): the
    # field must not exist on EITHER year's caps — validate_rules rejects
    # any re-introduction, and the engine/main.py reject the session key.
    assert not hasattr(FY_2025_26.deduction_caps, "sec_80eea")
    assert not hasattr(FY_2024_25.deduction_caps, "sec_80eea")


# ── 2. New-regime 87A band — salaried ground truths ──────────────────────

@pytest.mark.parametrize(
    ("salary", "expected_total"),
    [
        (12_00_000, 0.00),        # TI 11,25,000: rebate wipes 52,500
        (13_00_000, 25_000.00),   # TI 12,25,000: slab 63,750, cap 25,000
        (13_25_000, 50_000.00),   # TI 12,50,000: slab 67,500, cap 50,000
        (24_00_000, 2_92_500.00), # TI 23,25,000: slab 2,81,250 x1.04
        (24_75_000, 3_12_000.00), # TI 24,00,000: slab 3,00,000 x1.04
        (24_75_001, 3_12_000.31), # true 25% -> 30% edge: +Re 1 x0.30 x1.04
    ],
    ids=["rebate-zero", "band-25000", "band-50000", "slab-292500", "edge-pre", "edge-post"],
)
def test_87a_band_new_regime_salaried_fy2526(salary: int, expected_total: float) -> None:
    assert _new({"salary": salary}) == expected_total


def test_87a_band_derived_endpoint_fy2526() -> None:
    """The band endpoint EMERGES from the post-cess min(): at TI 12,73,934
    the 1.04 x slab (73,933.704) sits just under the cap (TI - 12,00,000 =
    73,934), so the natural computation applies. (Derived, never stored.)"""
    total = _new({"salary": 13_48_934})
    assert abs(total - 73_933.70) <= 0.5


def _slab_new_fy2526(v: float) -> float:
    """FY 2025-26 new-regime slab, restated independently for the test."""
    t = 0.0
    t += max(0.0, min(v, 800_000) - 400_000) * 0.05
    t += max(0.0, min(v, 1_200_000) - 800_000) * 0.10
    t += max(0.0, min(v, 1_600_000) - 1_200_000) * 0.15
    t += max(0.0, min(v, 2_000_000) - 1_600_000) * 0.20
    t += max(0.0, min(v, 2_400_000) - 2_000_000) * 0.25
    t += max(0.0, v - 2_400_000) * 0.30
    return t


@pytest.mark.parametrize("ti", [1_200_001 + 5_000 * k for k in range(15)])
def test_87a_band_post_cess_invariant_grid_fy2526(ti: int) -> None:
    """Band property mini-grid (TI 12,00,001 .. 12,70,001): payable ==
    min(1.04 x slab(TI), TI - 12,00,000) — the POST-CESS cap from the A2
    algorithm, now at the FY 2025-26 threshold. The cap stops binding at
    the derived endpoint 12,73,934; rows beyond it price normally."""
    slab = _slab_new_fy2526(ti)
    cap = float(ti - 1_200_000)
    expected = round(min(slab * 1.04, cap), 2)
    total = _new({"other_income": ti})
    assert total == expected
    if slab * 1.04 > cap:
        assert total == cap


# ── 3. Old regime — rebate cliff (unchanged year) ────────────────────────

@pytest.mark.parametrize(
    ("salary", "expected_total"),
    [
        (5_50_001, 13_000.21),  # TI 5,00,001: NO rebate (TI-keyed), no band
        (5_50_000, 0.00),       # TI 5,00,000: rebate wipes the 12,500 slab tax
    ],
    ids=["cliff-past-5l", "rebate-at-5l"],
)
def test_old_regime_rebate_cliff_fy2526(salary: int, expected_total: float) -> None:
    """Old regime, professional_tax=0 explicit (the state levy default is
    exercised separately below). No band may leak into the old regime.

    Ticket deviation (see module docstring): the ticket's 13,000.05 for TI
    5,00,001 applied 5% to the whole 2,50,001 slice above the exemption;
    statutorily (verification record §7) only (2.5L, 5L] is 5% and the Re 1
    above 5L is in the 20% band: 12,500 + 0.20 = 12,500.20 pre-cess ->
    x1.04 = 13,000.21 (identical under fy_2024_25 — the slab is shared)."""
    assert _old({"salary": salary, "professional_tax": 0}) == expected_total


# ── 4. Old regime surcharge relief — unchanged from FY 2024-25 ───────────

@pytest.mark.parametrize(
    ("income", "expected_total"),
    [
        (50_50_000, 14_17_000.00),     # S = 35,000
        (1_00_50_000, 32_69_500.00),   # S = 3,16,250
        (5_00_50_000, 1_93_08_250.00), # S = 37,38,125 (T_r1(5Cr) at 25%)
    ],
    ids=["50L+50k", "1Cr+50k", "5Cr+50k"],
)
def test_old_regime_surcharge_relief_fy2526(income: int, expected_total: float) -> None:
    """Same cells as the FY 2024-25 matrix in tests/test_surcharge_87a.py —
    the old regime (and its relief mechanics) is year-invariant."""
    assert _old({"other_income": income}) == expected_total


# ── 5. Cross-year old-regime consistency ─────────────────────────────────

def test_old_regime_invariance_prof_tax_explicit() -> None:
    """With professional_tax pinned to 2,500 the old regime must produce
    IDENTICAL totals under both registry years (only the default differs).
    salary 10,00,000: taxable 9,47,500 -> slab 1,02,000; x1.04 = 1,06,080."""
    data = {"salary": 1_000_000, "professional_tax": 2_500}
    fy24 = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
    fy25 = engine.calculate_tax_advanced(dict(data), tax_year="fy_2025_26")
    assert fy24["old_regime"].total_tax == fy25["old_regime"].total_tax == 1_06_080.00


def test_old_regime_default_prof_tax_difference() -> None:
    """Ruling j, default-difference cells (senior, age 60 — the 3,00,000
    basic exemption):

    salary 5,00,000, defaulted professional tax: fy_2025_26 TI 4,50,000 and
    fy_2024_25 TI 4,47,500 are both <= 5,00,000 -> rebate -> 0 in both.

    salary 5,60,000: fy_2025_26 TI 5,10,000 (no prof tax default) and
    fy_2024_25 TI 5,07,500 (2,500 default) are both past the 5L cliff, so
    neither rebates: slab = 5%x2,00,000 (3L-5L) + 20% of the slice above 5L
    — fy_2025_26: 10,000 + 2,000 = 12,000, x1.04 = 12,480.00; fy_2024_25:
    10,000 + 1,500 = 11,500, x1.04 = 11,960.00.

    Ticket deviation (see module docstring): the ticket's 10,920.00 /
    10,790.00 applied 5% to the ENTIRE slice above the 3L exemption
    (5%x2,10,000 = 10,500; 5%x2,07,500 = 10,375) — a slab shape matching
    neither verification record §7 ("5% (to 5L), 20% (to 10L)") nor the
    frozen FY 2024-25 parity fixture. The statute-consistent values are
    pinned here and the diff reported for expert re-verification."""
    data = {"salary": 5_00_000, "age": 60}
    fy24 = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
    fy25 = engine.calculate_tax_advanced(dict(data), tax_year="fy_2025_26")
    assert fy25["old_regime"].total_tax == 0.0
    assert fy24["old_regime"].total_tax == 0.0

    data = {"salary": 5_60_000, "age": 60}
    fy24 = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
    fy25 = engine.calculate_tax_advanced(dict(data), tax_year="fy_2025_26")
    assert fy25["old_regime"].total_tax == 12_480.00
    assert fy24["old_regime"].total_tax == 11_960.00


# ── 6. 112A/111A aggregate regression (expert GT9, FY 2025-26) ───────────

def test_112a_111a_aggregate_regression_fy2526() -> None:
    """salary 20L + equity LTCG 8L + equity STCG 5L, new regime: slab tax
    1,85,000 + 112A 12.5%x(8,00,000-1,25,000) = 84,375 + 111A 20%x5,00,000
    = 1,00,000 -> 3,69,375 x1.04 = 3,84,150.00. TI 32,25,000: no rebate
    (TI-keyed, > 12L), no surcharge (<= 50L)."""
    data = {
        "salary": 2_000_000,
        "capital_gains": [
            {"type": "equity_ltcg", "amount": 800_000},
            {"type": "equity_stcg", "amount": 500_000},
        ],
    }
    result = _new_result(data)
    assert result["new_regime"].total_tax == 3_84_150.00


# ── 7. Property CG — cross-regime identity (12.5% both regimes) ──────────

def test_property_cg_12_5_percent_both_regimes_fy2526() -> None:
    """FY 2025-26 statute: 12.5% without indexation for property gains in
    BOTH regimes post-23-Jul-2024 (the FY 2024-25 20%-old/12.5%-new split
    is year-specific; transfer-date routing lands in Step C)."""
    data = {"capital_gains": [{"type": "property_cg", "amount": 1_000_000}]}
    result = engine.calculate_tax_advanced(dict(data), tax_year=YEAR)
    assert result["old_regime"].total_tax == 1_30_000.00
    assert result["new_regime"].total_tax == 1_30_000.00


# ── 8. Professional-tax default advisory (ruling j) ──────────────────────

def test_prof_tax_default_advisory_both_years() -> None:
    """When professional tax was never provided and salary > 0, BOTH years
    emit the state-specific advisory on both regimes (FY 2024-25 keeps its
    2,500 default; FY 2025-26 defaults to 0)."""
    for tax_year in ("fy_2024_25", "fy_2025_26"):
        result = engine.calculate_tax_advanced({"salary": 8_00_000}, tax_year=tax_year)
        for regime in ("old_regime", "new_regime"):
            observations = result[regime].audit_observations
            assert PROF_TAX_ADVISORY in observations, (tax_year, regime)


def test_prof_tax_advisory_absent_when_explicit_or_no_salary() -> None:
    """An explicit professional_tax (even 0) or zero salary means the
    default was never applied — no advisory."""
    explicit = engine.calculate_tax_advanced(
        {"salary": 8_00_000, "professional_tax": 0}, tax_year=YEAR
    )
    for regime in ("old_regime", "new_regime"):
        assert PROF_TAX_ADVISORY not in explicit[regime].audit_observations
    no_salary = engine.calculate_tax_advanced({"other_income": 8_00_000}, tax_year=YEAR)
    for regime in ("old_regime", "new_regime"):
        assert PROF_TAX_ADVISORY not in no_salary[regime].audit_observations


# ── 9. API surface — /calculate and /chat ────────────────────────────────
#
#    Wave D adaptation (mechanical, documented — design §10 / ADR-013):
#    the state (salary + the optional tax_year pin) lives SERVER-SIDE, so
#    the rows seed the store (tests are trusted writers); /calculate takes
#    {session_id, tax_year?} and /chat takes {message, session_id} with an
#    AUTHED user (ADR-012). Every pinned label and 422 below is unchanged.

import json as _json

import db as _db


def _seed_state(session_id: str, state: Dict[str, Any]) -> None:
    seeded = {"id": session_id, **state}
    _db.execute(
        "UPDATE app_sessions SET state = ? WHERE id = ?",
        (_json.dumps(seeded, default=str), session_id),
    )


def test_calculate_fy_2025_26_label(authed_client, session_id) -> None:
    _seed_state(session_id, {"salary": 1_200_000})
    response = authed_client.post(
        "/calculate",
        json={"session_id": session_id, "tax_year": "fy_2025_26"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tax_year"] == "2025-26"
    assert body["assessment_year"] == "2026-27"
    assert body["fy_label"] == "FY 2025-26 (AY 2026-27)"


def test_calculate_default_year_is_fy_2025_26(authed_client, session_id) -> None:
    """Step A3 flips the registry default — an unpinned /calculate call now
    resolves FY 2025-26."""
    _seed_state(session_id, {"salary": 500_000})
    response = authed_client.post(
        "/calculate", json={"session_id": session_id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tax_year"] == "2025-26"
    assert body["fy_label"] == "FY 2025-26 (AY 2026-27)"


def test_calculate_unknown_year_422_lists_both(authed_client, session_id) -> None:
    _seed_state(session_id, {"salary": 500_000})
    response = authed_client.post(
        "/calculate",
        json={"session_id": session_id, "tax_year": "fy_2023_24"},
    )
    assert response.status_code == 422
    messages = [err["msg"] for err in response.json()["errors"]]
    assert any("fy_2024_25" in msg and "fy_2025_26" in msg for msg in messages)


def test_chat_accepts_fy_2025_26_session_year(authed_client, session_id) -> None:
    # The state tax_year pin is a state key now (validator-checked at the
    # load boundary); the chat income gate computes with it.
    _seed_state(session_id, {"tax_year": "fy_2025_26", "salary": 1_500_000})
    response = authed_client.post(
        "/chat",
        json={"message": "hi", "session_id": session_id},
    )
    assert response.status_code == 200
    body = response.json()
    tax_report = body.get("tax_report")
    assert tax_report is not None
    assert tax_report["fy_label"] == "FY 2025-26 (AY 2026-27)"


def test_chat_rejects_unknown_year_still_422(authed_client, session_id) -> None:
    # Was: the client session dict carried the bad pin -> 422 at the
    # request model. Wave D: the SAME registry row guards the state key at
    # the load boundary.
    _seed_state(session_id, {"tax_year": "fy_2023_24"})
    response = authed_client.post(
        "/chat",
        json={"message": "hi", "session_id": session_id},
    )
    assert response.status_code == 422


# Guard: get_rules round-trips both registered years (never silent).
def test_get_rules_both_years() -> None:
    assert get_rules("fy_2024_25").tax_year == "2024-25"
    assert get_rules("fy_2025_26").tax_year == "2025-26"

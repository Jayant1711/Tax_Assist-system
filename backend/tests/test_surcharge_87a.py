"""Statutory surcharge marginal relief + harmonized Section 87A (Sprint 2
Step A2/E — tax-expert rulings, 2026-10-31).

Tests FIRST (red), per AI_RULES.md. Every cell below is FY 2024-25
(explicit tax_year="fy_2024_25") and hand-computed from the statute:

Surcharge marginal relief (all four thresholds; old 50L/1Cr/2Cr/5Cr, new
50L/1Cr/2Cr — 5Cr unreachable in the new regime due to the 25% cap of
s.115BAC(6)): for x above the highest crossed threshold h_top,

    S_payable = min(S_band(x), max(0, T_r1(h_top) + (x - h_top) - T(x)))

where S_band(x) is the band-rate surcharge at x and
T_r1(h_top) = T_pre(h_top) * (1 + rate of the band CONTAINING h_top)
(50L->0%, 1Cr->10%, 2Cr->15%, 5Cr->25% — at exactly h the rate is the
LOWER band's). Cess (4%) is applied after, outside the comparison. At
x == h exactly there is no relief: the normal band computation applies.

Section 87A (harmonized both FYs): eligibility is keyed on TOTAL income
(incl. special-rate CG); rebate, when eligible, applies to normal-rate
tax only (never 112A/111A); in the new regime the PAYABLE total (after
rebate on normal income + special-rate tax + surcharge + cess) is capped
at (TOTAL INCOME - threshold) — the POST-CESS cap. The band endpoint
therefore EMERGES from min() (derived: 7,23,214 incl-cess for FY 2024-25;
the stored 727777 pre-cess band constant is retired in this step).

New-regime CG surcharge cap (s.115BAC(6)): the surcharge on the
special-rate (111A/112A) portion of tax is capped at 15%:
S = rate*T_normal + min(rate, 0.15)*T_special, before the relief
comparison. Old regime is uncapped.

Deviations from the sprint-ticket worked examples (documented, statute-
consistent — see the per-test docstrings):
- Ruling-(c) old-regime cell: the ruling's "slab(6,50,000)=17,500" is the
  NEW-regime slab; the old-regime slab on 6,50,000 is 42,500. The "current
  wrongly rebates -> 48,750" figure pins slab taxable 5,00,000 (slab tax
  12,500), so the TI-keyed cell below uses other_income 5,00,000 + LTCG
  5,00,000 -> 61,750.00, and the literal ruling input is pinned at its
  correct old-regime value 92,950.00.
- CG-cap cell: the ticket's "TI 89,25,000 -> surcharge 25%" contradicts
  the same document's ladder (25% applies only above 2Cr; 89,25,000 is in
  the 10% band) and its relief pieces do not sum. The specified algorithm
  yields 2,089,945.00 for that input; two x > 2Cr cells below exercise
  the 15% cap for real (one with relief binding simultaneously).
"""
from typing import List, Tuple

import pytest

from tax_engine import TaxEngine

engine = TaxEngine()
YEAR = "fy_2024_25"


def _old(data: dict) -> float:
    return engine.calculate_tax_advanced(dict(data), tax_year=YEAR)["old_regime"].total_tax


def _new(data: dict) -> float:
    return engine.calculate_tax_advanced(dict(data), tax_year=YEAR)["new_regime"].total_tax


# ── 1. Surcharge marginal relief — hand-computed ground truths ──────────
# Old regime, slab income = other_income, no deductions, non-senior.

@pytest.mark.parametrize(
    ("income", "expected_total"),
    [
        (5_050_000, 1_417_000.00),     # S = 35,000  (crude pre-A2: 1,432,600)
        (10_050_000, 3_269_500.00),    # S = 3,16,250 (T_r1(1Cr) at the 10% band rate)
        (20_050_000, 7_003_750.00),    # S = 9,06,875 (T_r1(2Cr) at the 15% band rate)
        (50_050_000, 19_308_250.00),   # S = 37,38,125 (T_r1(5Cr) at the 25% band rate)
    ],
    ids=["50L+50k", "1Cr+50k", "2Cr+50k", "5Cr+50k"],
)
def test_surcharge_marginal_relief_ground_truths(income: int, expected_total: float) -> None:
    """The four statutory relief cells (tax-expert GT, FY 2024-25).

    Derivation for 1Cr+50k: T(x) = 2,827,500; band 15% -> S_band = 424,125;
    T_r1(1Cr) = T(1Cr) x 1.10 = 2,812,500 x 1.10 = 3,093,750;
    ceiling = 3,093,750 + 50,000 - 2,827,500 = 316,250 -> S = 316,250;
    total = (2,827,500 + 316,250) x 1.04 = 3,269,500.
    """
    assert _old({"other_income": income}) == expected_total


@pytest.mark.parametrize(
    ("income", "expected_old", "expected_new"),
    [
        (5_000_000, 1_365_000.00, 1_237_600.00),
        (10_000_000, 3_217_500.00, 3_077_360.00),
        (20_000_000, 6_951_750.00, 6_805_240.00),
        (50_000_000, 19_256_250.00, 19_097_000.00),
    ],
    ids=["50L-exact", "1Cr-exact", "2Cr-exact", "5Cr-exact"],
)
def test_no_relief_at_exact_thresholds(income: int, expected_old: float, expected_new: float) -> None:
    """No relief at x == h exactly (both regimes): the rate at h is the
    LOWER band's and the relief ceiling at h_top degenerates. These pins
    are pre-A2-stable — the parity fixture cells at these incomes must
    stay byte-identical."""
    data = {"other_income": income}
    assert _old(data) == expected_old
    assert _new(data) == expected_new


def test_t05_salary_1cr_preserved() -> None:
    """T05 (legacy pin): salary 1Cr — surcharge 10% with no relief bite
    (slab taxable 9,947,500; relief ceiling 3,463,250 does not bind).
    Old total 3,199,482 must stay exactly as pinned pre-A2."""
    data = {"salary": 10_000_000}
    assert _old(data) == 3_199_482.00
    assert _new(data) == 3_051_620.00


# ── 2. Section 87A harmonized band — new regime, FY 2024-25 ─────────────

@pytest.mark.parametrize(
    ("salary", "expected_total"),
    [
        (7_80_000, 5_000.00),    # TI 7,05,000: slab 20,500; post-cess cap 5,000
        (7_95_000, 20_000.00),   # TI 7,20,000: slab 22,000; post-cess cap 20,000
        (7_60_000, 0.00),        # TI 6,85,000 <= 7L -> full rebate
    ],
    ids=["band-5000", "band-20000", "rebate-zero"],
)
def test_87a_band_new_regime_salaried(salary: int, expected_total: float) -> None:
    """Post-cess band cap: payable = min(1.04 x slab(TI), TI - 7,00,000).

    salary 7,80,000: TI 7,05,000 > 7,00,000 -> NO rebate (eligibility is
    keyed on TOTAL income); slab = 20,000 (3-7L) + 10% x 5,000 = 20,500;
    pre-cess 21,320 capped post-cess at 5,000 (the crude pre-A2 engine
    gave 5,200). salary 7,95,000: TI 7,20,000, slab 22,000, capped at
    20,000 (crude: 20,800).
    """
    assert _new({"salary": salary}) == expected_total


def _slab_new_fy2425(v: float) -> float:
    """FY 2024-25 new-regime slab, restated independently for the test."""
    t = 0.0
    t += max(0.0, min(v, 700_000) - 300_000) * 0.05
    t += max(0.0, min(v, 1_000_000) - 700_000) * 0.10
    t += max(0.0, min(v, 1_200_000) - 1_000_000) * 0.15
    t += max(0.0, min(v, 1_500_000) - 1_200_000) * 0.20
    t += max(0.0, v - 1_500_000) * 0.30
    return t


@pytest.mark.parametrize("ti", [700_001 + 5_000 * k for k in range(13)])
def test_87a_band_post_cess_invariant_grid(ti: int) -> None:
    """Band property mini-grid (TI 7,00,001 .. 7,60,001): payable ==
    min(1.04 x slab(TI), TI - 7,00,000) — the cap applies AFTER cess to
    the TOTAL, so inside the binding zone the total is exactly the
    integer excess (the pre-A2 crude engine capped pre-cess and produced
    excess x 1.04). The endpoint emerges: the cap stops binding at
    TI - 7,00,000 > 1.04 x slab(TI), i.e. TI = 7,23,214 (incl-cess QA
    expectation) — rows beyond it price normally."""
    slab = _slab_new_fy2425(ti)
    cap = float(ti - 700_000)
    expected = round(min(slab * 1.04, cap), 2)
    total = _new({"other_income": ti})
    assert total == expected
    if slab * 1.04 > cap:
        # inside the binding zone the POST-CESS total is the raw excess
        assert total == cap


# ── 3. TI-keyed eligibility (ruling (c)) ─────────────────────────────────

def test_87a_ti_keyed_eligibility_old_regime() -> None:
    """Old regime, no prof tax, other_income 5,00,000 + equity LTCG
    5,00,000: TOTAL income 10,00,000 > 5,00,000 -> NO rebate (the crude
    engine keyed eligibility on slab taxable 5,00,000 and wrongly rebated
    the 12,500 slab tax, giving 48,750). Statutory: slab 12,500 stays +
    CG 12.5% x 3,75,000 = 46,875 -> (12,500 + 46,875) x 1.04 = 61,750.00.

    (Ruling-(c) deviation note in the module docstring: the ruling's
    66,950 total used the new-regime slab on 6,50,000; the old-regime
    slab there is 42,500, and the ruling's own "current 48,750" pins
    slab taxable 5,00,000 — this cell realizes its intent.)"""
    data = {"other_income": 500_000, "capital_gains": [{"type": "equity_ltcg", "amount": 500_000}]}
    assert _old(data) == 61_750.00


def test_87a_ti_keyed_eligibility_old_regime_slab_pin() -> None:
    """Literal ruling-(c) input (other 6,50,000 + LTCG 5,00,000) pinned at
    the correct old-regime value: slab taxable 6,50,000 > 5L already, so
    neither engine rebates — old slab 12,500 + 30,000 = 42,500 + CG
    46,875 -> 89,375 x 1.04 = 92,950.00 (guards the old-slab
    transcription while the eligibility rework lands)."""
    data = {"other_income": 650_000, "capital_gains": [{"type": "equity_ltcg", "amount": 500_000}]}
    assert _old(data) == 92_950.00


def test_87a_ti_keyed_eligibility_new_regime_composite() -> None:
    """New regime: salary 11,00,000 (std ded 75,000 -> slab 10,25,000) +
    112A LTCG 2,00,000: TOTAL income 12,25,000 > 7,00,000 -> no rebate.
    slab(10,25,000) = 20,000 + 30,000 + 15% x 25,000 = 53,750; 112A =
    12.5% x 75,000 = 9,375; total = 63,125 x 1.04 = 65,650.00 (ruling-(c)
    GT; also stable pre-A2 — harmonization pin)."""
    data = {"salary": 1_100_000, "capital_gains": [{"type": "equity_ltcg", "amount": 200_000}]}
    assert _new(data) == 65_650.00


def test_87a_rebate_never_touches_special_rate_tax() -> None:
    """Eligible (TOTAL 6,90,000 <= 7L) with equity STCG present: the
    rebate wipes the normal slab tax (5% x 3,60,000 = 18,000) but never
    the 111A tax (20% x 30,000 = 6,000) -> total 6,240.00."""
    data = {"other_income": 660_000, "capital_gains": [{"type": "equity_stcg", "amount": 30_000}]}
    assert _new(data) == 6_240.00


def test_old_regime_rebate_stays_simple_no_band() -> None:
    """Old regime keeps the simple rebate (cap 5L, 12,500, no band):
    TI 5,10,000 with no CG -> no rebate, no band cap -> (12,500 + 2,000)
    x 1.04 = 15,080.00 (a new-regime-style band must NOT leak into the
    old regime)."""
    assert _old({"other_income": 510_000}) == 15_080.00


# ── 4. New-regime CG surcharge cap (s.115BAC(6)) ─────────────────────────

def test_cg_surcharge_split_normal_special_below_2cr() -> None:
    """New regime, salary 60,00,000 + equity LTCG 30,00,000: TI 89,25,000
    is in the 10% surcharge band (25% applies only above 2Cr), so
    S = 0.10 x T_normal + min(0.10, 0.15) x T_special = 146,750 +
    35,937.50 = 182,687.50 and the relief ceiling (2,542,500) does not
    bind: total = (14,67,500 + 3,59,375 + 1,82,687.50) x 1.04 =
    2,089,945.00.

    (Ticket deviation: the sprint example asserted 19,42,200 using a 25%
    band rate at 89,25,000 and relief pieces that do not sum; the
    governing algorithm and ladder produce the value above. See module
    docstring.)"""
    data = {"salary": 6_000_000, "capital_gains": [{"type": "equity_ltcg", "amount": 3_000_000}]}
    assert _new(data) == 2_089_945.00


def test_cg_surcharge_cap_and_relief_together_above_2cr() -> None:
    """New regime, salary 2,02,00,000 + equity LTCG 5,00,000: TI
    2,06,25,000 -> band 25%; T_normal 57,27,500, T_special 46,875.
    S_band = 0.25 x 57,27,500 + min(0.25, 0.15) x 46,875 = 14,31,875 +
    7,031.25 = 14,38,906.25 (15% CAP binds on the special portion).
    Relief at h_top = 2Cr (rate there 15%): T_r1 = 55,86,875 x 1.15 =
    64,24,906.25; ceiling = 64,24,906.25 + 6,25,000 - 57,74,375 =
    12,75,531.25 -> RELIEF binds. Total = (57,27,500 + 46,875 +
    12,75,531.25) x 1.04 = 7,331,902.50."""
    data = {"salary": 20_200_000, "capital_gains": [{"type": "equity_ltcg", "amount": 500_000}]}
    assert _new(data) == 7_331_902.50


def test_cg_surcharge_cap_without_relief_above_2cr() -> None:
    """New regime, salary 2,00,00,000 + equity LTCG 10,00,000: TI
    2,09,25,000 -> band 25%, cap binds (0.15 x 1,09,375 = 16,406.25
    instead of 27,343.75), relief does not (ceiling 15,72,406.25):
    total = (56,67,500 + 1,09,375 + 14,33,281.25) x 1.04 = 7,498,562.50."""
    data = {"salary": 20_000_000, "capital_gains": [{"type": "equity_ltcg", "amount": 1_000_000}]}
    assert _new(data) == 7_498_562.50


# ── 5. Monotonicity / no-cliff property (slow) ───────────────────────────

THRESHOLDS = (5_000_000, 10_000_000, 20_000_000, 50_000_000)
GRID_STEP = 25_000


@pytest.mark.slow
def test_surcharge_total_monotone_and_no_cliffs_old_regime() -> None:
    """Old-regime property grid, other_income 45,00,000 .. 1,10,00,000
    step 25,000 (261 cells):

    (a) total_tax is non-decreasing in income;
    (b) one step past each threshold the increment is bounded by the
        post-cess marginal-relief guarantee: total(h + step) - total(h)
        <= step x 1.04 + 0.05 (the crude engine produced 33,800 at 50L
        and 155,220 at 1Cr — cliffs the statutory relief removes);
    (c) globally past each threshold, total(x) - total(h) <= 1.04 x
        (x - h) + 0.05 (marginal relief guarantee, post-cess)."""
    incomes = list(range(4_500_000, 11_000_000 + 1, GRID_STEP))
    totals: List[Tuple[int, float]] = [
        (x, _old({"other_income": x})) for x in incomes
    ]
    for (_, prev), (x, cur) in zip(totals, totals[1:]):
        assert cur >= prev - 0.005, f"total decreased between {prev} and {cur} at x={x}"

    totals_by_income = dict(totals)
    for h in THRESHOLDS:
        if h not in totals_by_income:
            continue
        step_total = totals_by_income[h + GRID_STEP]
        increment = step_total - totals_by_income[h]
        assert increment <= GRID_STEP * 1.04 + 0.05, (
            f"cliff at {h}: +{increment:,.2f} for +{GRID_STEP} income"
        )
        for x, total in totals:
            if x > h:
                assert total - totals_by_income[h] <= (x - h) * 1.04 + 0.05, (
                    f"guarantee violated past {h} at x={x}"
                )

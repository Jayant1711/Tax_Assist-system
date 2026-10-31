"""Frozen schema for the versioned tax-rules registry (ADR-008).

Sprint 2 Objective A, Step A1. Every constant carried by these dataclasses
is TRANSCRIBED FROM THE CURRENT tax_engine.py for FY 2024-25 — the registry
must reproduce the engine's behavior bit-for-bit (proven by
tests/fixtures/parity_fy2425.json). The authoritative FY 2025-26 constants
record is docs/tax-verification.md; that data lands in Step A3.

Slab semantics (one convention for both regimes): a SlabBand taxes the
slice of taxable income from the PREVIOUS band's upper_bound (or `floor`
for the first band) up to this band's upper_bound, at `rate`.
upper_bound None marks the top band (infinity). A leading band with
rate 0.0 is the nil band (new regime, floor 0). The old regime instead
carries its age-dependent basic exemption as the `floor` (see
old_regime_exemption_by_age), so its nil region is [0, floor].
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

_TAX_YEAR_PATTERN = re.compile(r"^\d{4}-\d{2}$")


@dataclass(frozen=True)
class SlabBand:
    """One slab slice (see module docstring for the slicing convention)."""

    upper_bound: Optional[float]  # None = top band (income above last bound)
    rate: float


@dataclass(frozen=True)
class RebateRule:
    """Section 87A rebate parameters for one regime.

    max_amount None means the rebate wipes out the entire slab tax (full
    rebate) while TOTAL income is at or below income_cap; a numeric
    max_amount caps the rebate (old regime: 12,500). Step A2 harmonized
    eligibility: it is keyed on TOTAL income (slab taxable + special-rate
    CG), and a rebate, when eligible, applies to the normal-rate tax only
    — never to 111A/112A.

    When marginal_relief is True (new regime), the PAYABLE total (income-
    tax after rebate + special-rate tax + surcharge + cess) is capped at
    (TOTAL INCOME - income_cap) AFTER cess: band_cap_includes_cess is
    True from Step A2 ("harmonized per the FA-2025 Explanation; was
    pre-cess"). The band's upper endpoint EMERGES from that min() — for
    FY 2024-25 it derives to 7,23,214 incl-cess — so no bound is stored:
    band_upper_bound remains only as an optional informational field and
    is None from Step A2 on.
    """

    income_cap: float
    max_amount: Optional[float]  # None = full rebate of the computed (normal-rate) tax
    marginal_relief: bool
    # Removed in Step A2; derived endpoint 7,23,214 incl-cess is a QA
    # expectation only (kept as a field so older year modules stay valid).
    band_upper_bound: Optional[int]
    band_cap_includes_cess: bool


@dataclass(frozen=True)
class SurchargeRule:
    """Section 2(3)/115BAC surcharge ladder shared by both regimes.

    bands: ascending (threshold, rate) pairs; the rate applies to income
    strictly above the threshold. new_regime_cap caps the effective rate
    under Section 115BAC(6) regardless of band; old_regime_cap is the old
    regime's ceiling (37%). marginal_relief (Step A2) is the band-based
    threshold comparison: S_payable = min(S_band(x), max(0, T_r1(h_top) +
    (x - h_top) - T(x))) with T_r1(h_top) carrying the band rate that
    CONTAINS h_top; cess is applied after, outside the comparison.
    """

    bands: Tuple[Tuple[float, float], ...]
    new_regime_cap: float
    old_regime_cap: float
    marginal_relief: bool


@dataclass(frozen=True)
class CGRules:
    """Capital-gains rates (Budget 2024, FY 2024-25)."""

    ltcg_112a_rate: float                  # 12.5% on equity LTCG
    ltcg_112a_exemption: float             # 1,25,000 exemption per taxpayer
    stcg_111a_rate: float                  # 20% on equity STCG
    property_rate_by_regime: Mapping[str, float]  # "old" 20% / "new" 12.5%
    special_rate_excludes_87a: bool        # CG tax sits outside the 87A rebate


@dataclass(frozen=True)
class DeductionCaps:
    """Chapter VI-A / Chapter VI statutory caps (per registered year).

    Fields the current engine books UNCAPPED (80E, 80G, 80U/80DD, 80DDB)
    still record their statutory caps for auditability; the engine's
    unchanged booking behavior is preserved in Step A1 and the caps become
    enforceable in a later step.

    Sprint 2 Step D: sec_80eea is REMOVED from the schema (the section was
    discontinued by its 31-Mar-2022 loan-sanction sunset — verification
    record §6; the engine stops reading the key in the same step), and
    sec_80d_parents splits into the base + senior pair (ruling i): the
    engine books the 25,000 base until the parents_senior input lands in
    Sprint 3, with the unverified seniority disclosed via an advisory.
    """

    sec_80c: float                          # 1,50,000
    sec_80d_self: float                     # 25,000 (below 60)
    sec_80d_self_senior: float              # 50,000 (60+)
    sec_80d_parents: float                  # 25,000 base (parents below 60)
    sec_80d_parents_senior: float           # 50,000 (either parent 60+)
    sec_80ccd_1b: float                     # 50,000 NPS extra
    sec_24b: float                          # 2,00,000 home-loan interest
    sec_80tta: float                        # 10,000 savings interest (below 60)
    sec_80tta_senior: float                 # 0 — 80TTA unavailable at 60+ (80TTB instead)
    sec_80ttb: float                        # 50,000 senior deposits interest
    sec_80e: Optional[float]                # None — no statutory upper limit
    sec_80gg_annual_max: float              # 60,000 (5,000/month)
    sec_80gg_income_pct: float              # 25% of total income
    sec_80gg_rent_excess_pct: float         # rent minus 10% of total income
    sec_80u_80dd_40_79: float               # 75,000 (disability 40%-79%)
    sec_80u_80dd_80_plus: float             # 1,25,000 (severe disability 80%+)
    sec_80ddb: float                        # 40,000 medical treatment (patient below 60)
    sec_80ddb_senior: float                 # 1,00,000 senior medical treatment
    # sec_80eea deliberately ABSENT (removed in Step D): the deduction was
    # discontinued by its 31-Mar-2022 loan-sanction sunset and validate_rules
    # rejects any year module that re-introduces the field.
    sec_80g: Optional[float] = None         # placeholder — category model is engine-side


@dataclass(frozen=True)
class HRARules:
    """Section 10(13A) HRA exemption parameters.

    The current engine computes the non-metro baseline only (no city
    input); metro_pct/metro_cities are recorded here so the statutory 50%
    metro case is registry-visible for the next step.
    """

    metro_cities: Tuple[str, ...]           # statutory metro cities
    metro_pct: float                        # 50% of salary in metros
    non_metro_pct: float                    # 40% of salary elsewhere
    salary_pct: float                       # 10% of salary (rent excess test)


@dataclass(frozen=True)
class AgriRules:
    """Section 10(1) agricultural-income treatment."""

    exempt: bool                            # agricultural income is exempt
    integration_threshold_non_agri: float   # 2,50,000 partial-integration flag


@dataclass(frozen=True)
class FYRules:
    """Complete rule set for one financial year."""

    tax_year: str                            # "2024-25"
    assessment_year: str                     # "2025-26"
    label: str                               # "FY 2024-25 (AY 2025-26)"

    new_regime_slabs: Tuple[SlabBand, ...]   # Section 115BAC slabs
    old_regime_slabs: Tuple[SlabBand, ...]   # regular slabs
    old_regime_exemption_by_age: Mapping[int, float]  # {min_age: basic exemption}
    standard_deduction: Mapping[str, float]  # {"old": 50,000, "new": 75,000}
    rebate: Mapping[str, RebateRule]         # {"old": ..., "new": ...}
    surcharge: SurchargeRule
    cg: CGRules
    deduction_caps: DeductionCaps
    hra: HRARules
    agri: AgriRules

    cess_rate: float                         # 4% health & education cess
    professional_tax_default: float          # 2,500 default when salaried
    # Section 115BAC(6): surcharge on special-rate (111A/112A) income is
    # capped at 15%. Registry constant added in Step A1; the engine starts
    # using it in Step A2/E.
    new_regime_cg_surcharge_cap: float


def _validate_bands(bands: Tuple[SlabBand, ...], regime: str) -> None:
    if not bands:
        raise ValueError(f"{regime}: at least one slab band is required")
    if bands[-1].upper_bound is not None:
        raise ValueError(f"{regime}: the last band must be the top band (upper_bound None)")
    prev: Optional[float] = None
    for index, band in enumerate(bands):
        if band.upper_bound is not None:
            if band.upper_bound <= 0:
                raise ValueError(f"{regime}: band {index} upper_bound must be positive")
            if prev is not None and band.upper_bound <= prev:
                raise ValueError(
                    f"{regime}: band upper_bounds must be strictly increasing "
                    f"({band.upper_bound} follows {prev})"
                )
            prev = band.upper_bound
        if index == 0:
            # Only the leading nil band (new regime) may carry rate 0.0.
            if not 0.0 <= band.rate <= 1.0:
                raise ValueError(f"{regime}: band 0 rate must be within [0, 1]")
        elif not 0.0 < band.rate <= 1.0:
            raise ValueError(f"{regime}: band {index} rate must be within (0, 1]")
        if band.rate == 0.0 and index != 0:
            raise ValueError(f"{regime}: only the leading nil band may have rate 0.0")


def _derive_assessment_year(tax_year: str) -> str:
    """'2024-25' -> '2025-26' (AY starts the year after the FY ends)."""
    start = int(tax_year.split("-")[0])
    return f"{start + 1}-{(start + 2) % 100:02d}"


def validate_rules(rules: FYRules) -> None:
    """Structural validation; raises ValueError on the first violation.

    Called for every registered year at package import time so a corrupt
    registry can never load silently.
    """
    if not _TAX_YEAR_PATTERN.match(rules.tax_year):
        raise ValueError(f"tax_year {rules.tax_year!r} must match YYYY-YY")
    derived_ay = _derive_assessment_year(rules.tax_year)
    if rules.assessment_year != derived_ay:
        raise ValueError(
            f"assessment_year {rules.assessment_year!r} does not match the "
            f"derived value {derived_ay!r} for tax_year {rules.tax_year!r}"
        )
    if not rules.label:
        raise ValueError("label must be a non-empty string")

    _validate_bands(rules.new_regime_slabs, "new_regime_slabs")
    _validate_bands(rules.old_regime_slabs, "old_regime_slabs")

    for regime, rebate in rules.rebate.items():
        if rebate.income_cap <= 0:
            raise ValueError(f"rebate[{regime}]: income_cap must be positive")
        if rebate.band_upper_bound is not None:
            if rebate.income_cap > rebate.band_upper_bound:
                raise ValueError(
                    f"rebate[{regime}]: income_cap {rebate.income_cap} exceeds "
                    f"band_upper_bound {rebate.band_upper_bound}"
                )
            if not rebate.marginal_relief:
                raise ValueError(
                    f"rebate[{regime}]: a relief band requires marginal_relief"
                )

    surcharge = rules.surcharge
    if not surcharge.bands:
        raise ValueError("surcharge: at least one band is required")
    prev_threshold: Optional[float] = None
    for index, (threshold, rate) in enumerate(surcharge.bands):
        if threshold <= 0:
            raise ValueError(f"surcharge: band {index} threshold must be positive")
        if prev_threshold is not None and threshold <= prev_threshold:
            raise ValueError("surcharge: thresholds must be strictly increasing")
        prev_threshold = threshold
        if not 0.0 < rate <= 1.0:
            raise ValueError(f"surcharge: band {index} rate must be within (0, 1]")
        if rate > surcharge.old_regime_cap:
            raise ValueError(
                f"surcharge: band rate {rate} exceeds old_regime_cap "
                f"{surcharge.old_regime_cap}"
            )
    if not 0.0 < surcharge.new_regime_cap <= surcharge.old_regime_cap:
        raise ValueError(
            "surcharge: new_regime_cap must be within (0, old_regime_cap]"
        )
    if not 0.0 <= rules.cess_rate < 1.0:
        raise ValueError("cess_rate must be within [0, 1)")

    # Sprint 2 Step D: deduction-cap consistency. sec_80eea must stay
    # REMOVED (the section was discontinued — a re-introduced field is a
    # registry corruption, never a silent revival), and the parents' 80D
    # pair must be a sane base <= senior ladder.
    if hasattr(rules.deduction_caps, "sec_80eea"):
        raise ValueError(
            "deduction_caps: sec_80eea was removed in Step D (the section "
            "was discontinued) — it must not be re-introduced"
        )
    caps = rules.deduction_caps
    if caps.sec_80d_parents < 0 or caps.sec_80d_parents_senior < caps.sec_80d_parents:
        raise ValueError(
            "deduction_caps: sec_80d_parents_senior must be >= "
            "sec_80d_parents >= 0"
        )

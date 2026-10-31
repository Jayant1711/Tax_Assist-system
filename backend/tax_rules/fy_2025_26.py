"""FY 2025-26 (AY 2026-27) rule set — transcribed 1:1 from the frozen
verification record docs/tax-verification.md (Sprint 2 Step A3, ADR-008).

Every constant below comes from docs/tax-verification.md as AMENDED by the
six tax-expert corrections (2026-10-31); each field cites its section.
Summary of what differs from FY 2024-25 (all other fields are identical):

- New-regime slabs re-cut per Finance Act 2025 (nil to 4L, edges every 4L
  to 24L) — verification record §1.
- New-regime 87A rebate enlarged: 60,000, zero tax to TOTAL income 12L,
  with the Step A2 POST-CESS band cap (endpoint 12,73,934 DERIVED from the
  min(), never stored) — §2 + tax-expert corrections 1/3/5.
- Property CG is 12.5% in BOTH regimes (post-23-Jul-2024 statute; the
  20%-old-regime split was FY 2024-25-specific) — §5; transfer-date
  routing lands in Step C.
- 80EEA is REMOVED from the schema entirely (31-Mar-2022 sunset) — §6;
  the engine/validator removal landed in Step D.
- professional_tax_default is 0 (state levy; the engine emits the advisory
  when the default applies) — §6 + tax-expert ruling j.
- Old regime otherwise unchanged (§7), and the surcharge ladder, cess and
  HRA/agri treatment carry over unchanged.

The generalized 87A (TI-keyed eligibility, post-cess band) and statutory
surcharge relief algorithms live in tax_engine.py and serve both years
without forks — proven by tests/test_fy2025_26_matrix.py.
"""
from __future__ import annotations

from types import MappingProxyType

# Relative import keeps the package importable both as the flat "tax_rules"
# (backend on sys.path, the project convention) and as a proper submodule.
from .schema import (
    AgriRules,
    CGRules,
    DeductionCaps,
    FYRules,
    HRARules,
    RebateRule,
    SlabBand,
    SurchargeRule,
)

FY_2025_26 = FYRules(
    # docs/tax-verification.md header (AY = FY + 1; enforced by schema).
    # Source: docs/tax-verification.md title.
    tax_year="2025-26",
    assessment_year="2026-27",
    label="FY 2025-26 (AY 2026-27)",

    # Sec 115BAC(1A) slabs, Finance Act 2025 (nil to 4L; 5%/10%/15%/20%/25%
    # bands of 4L each; 30% above 24L), re-expressed in the registry's
    # (upper_bound, rate) slice convention — see schema.py / fy_2024_25.py.
    # The level pair (400000, 0.05) becomes the 0% band ending at 400000
    # plus the 5% band ending at 800000, and so on. Floor 0 — the nil band
    # starts at 0.
    # Source: docs/tax-verification.md §1.
    new_regime_slabs=(
        SlabBand(400000, 0.0),      # nil band: 0 - 4L
        SlabBand(800000, 0.05),     # 4L - 8L
        SlabBand(1200000, 0.10),    # 8L - 12L
        SlabBand(1600000, 0.15),    # 12L - 16L
        SlabBand(2000000, 0.20),    # 16L - 20L
        SlabBand(2400000, 0.25),    # 20L - 24L
        SlabBand(None, 0.30),       # Above 24L
    ),

    # Old regime unchanged for FY 2025-26: 2.5L/5L/10L structure — (ex, 5L]
    # at 5%, (5L, 10L] at 20%, above 10L at 30%, with the age-dependent
    # basic exemption supplied as the walk floor below.
    # Source: docs/tax-verification.md §7 (+ tax-expert correction 6:
    # identical to FY 2024-25 except professional_tax_default).
    old_regime_slabs=(
        SlabBand(500000, 0.05),     # {ex}L - 5L
        SlabBand(1000000, 0.20),    # 5L - 10L
        SlabBand(None, 0.30),       # Above 10L
    ),

    # Basic exemption: 2.5L / 3L (60+) / 5L (80+) — keys are minimum ages.
    # Source: docs/tax-verification.md §7.
    old_regime_exemption_by_age=MappingProxyType({0: 250000, 60: 300000, 80: 500000}),

    # Standard deduction unchanged: 50,000 old / 75,000 new (Budget 2024
    # levels carried into FY 2025-26).
    # Source: docs/tax-verification.md §3.
    standard_deduction=MappingProxyType({"old": 50000, "new": 75000}),

    # Old regime: min(tax, 12,500) while TOTAL income <= 5,00,000 —
    # unchanged, simple rebate, no band.
    # New regime (Finance Act 2025): rebate up to 60,000 while TOTAL income
    # <= 12,00,000 (slab tax at 12L is exactly 60,000, so eligibility means
    # zero tax). Above it, the Step A2 POST-CESS band cap applies to the
    # payable total: min(payable incl. cess, TOTAL income - 12,00,000) —
    # the band endpoint 12,73,934 EMERGES from that min() and is therefore
    # not stored (band_upper_bound None).
    # Source: docs/tax-verification.md §2 (+ tax-expert corrections 1, 3
    # and 5: post-cess cap; TI-keyed eligibility, rebate on normal-rate
    # tax only; 112A excluded statutorily, 111A excluded conservatively —
    # ⚠ re-verify ITR-utility behavior at merge).
    rebate=MappingProxyType({
        "old": RebateRule(
            income_cap=500000,
            max_amount=12500,
            marginal_relief=False,
            band_upper_bound=None,
            band_cap_includes_cess=False,
        ),
        "new": RebateRule(
            income_cap=1200000,
            max_amount=60000,       # == slab tax at the 12L threshold
            marginal_relief=True,
            band_upper_bound=None,  # endpoint 12,73,934 derived, not stored
            band_cap_includes_cess=True,
        ),
    }),

    # Surcharge ladder unchanged: 10% above 50L, 15% above 1Cr, 25% above
    # 2Cr, 37% above 5Cr — new regime capped at 25% (115BAC(6)). Step A2
    # marginal relief is the band-based threshold comparison at ALL FOUR
    # thresholds: S_payable = min(S_band(x), max(0, T_r1(h_top) +
    # (x - h_top) - T(x))), T_r1(h_top) at the band rate CONTAINING h_top
    # (50L->0%, 1Cr->10%, 2Cr->15%, 5Cr->25%); cess applied after, OUTSIDE
    # the comparison; relief only for x > h.
    # Source: docs/tax-verification.md §4 (+ tax-expert correction 2).
    surcharge=SurchargeRule(
        bands=(
            (5000000, 0.10),
            (10000000, 0.15),
            (20000000, 0.25),
            (50000000, 0.37),
        ),
        new_regime_cap=0.25,
        old_regime_cap=0.37,
        marginal_relief=True,
    ),

    # Budget 2024 rates unchanged for FY 2025-26: equity LTCG 12.5% over
    # the 1.25L aggregate exemption, equity STCG 20%. Property: FY 2025-26
    # statute is 12.5% WITHOUT indexation in BOTH regimes post-23-Jul-2024
    # (the old-regime 20% split was FY 2024-25-specific; 20%-with-indexation
    # survives only as the transitional election for pre-23-Jul-2024
    # acquisitions — transfer-date routing lands in Step C). The CG tax is
    # added outside the 87A rebate (special_rate_excludes_87a).
    # Source: docs/tax-verification.md §5 (+ tax-expert correction 3).
    cg=CGRules(
        ltcg_112a_rate=0.125,
        ltcg_112a_exemption=125000,
        stcg_111a_rate=0.20,
        property_rate_by_regime=MappingProxyType({"old": 0.125, "new": 0.125}),
        special_rate_excludes_87a=True,
    ),

    # Chapter VI-A caps unchanged. Step D: sec_80eea is REMOVED from the
    # schema itself (the deduction was discontinued by its 31-Mar-2022
    # loan-sanction sunset; the engine stops reading the key in the same
    # step and validate_rules rejects any re-introduction).
    # 80DDB is min(expenditure, tier-cap) with the PATIENT's age deciding
    # the tier (40,000 / 1,00,000 senior); specialist prescription required
    # per Budget 2019 — the caps below record the tiers; tier selection
    # tooling defaults to the self age with an advisory. The parents' 80D
    # cap splits into base 25,000 + senior 50,000 (ruling i; the engine
    # books the base until the Sprint 3 parents_senior input lands).
    # Source: docs/tax-verification.md §6 (+ tax-expert corrections 4 and 5).
    deduction_caps=DeductionCaps(
        sec_80c=150000,
        sec_80d_self=25000,
        sec_80d_self_senior=50000,
        sec_80d_parents=25000,
        sec_80d_parents_senior=50000,
        sec_80ccd_1b=50000,
        sec_24b=200000,
        sec_80tta=10000,
        sec_80tta_senior=0,
        sec_80ttb=50000,
        sec_80e=None,
        sec_80gg_annual_max=60000,
        sec_80gg_income_pct=0.25,
        sec_80gg_rent_excess_pct=0.10,
        sec_80u_80dd_40_79=75000,
        sec_80u_80dd_80_plus=125000,
        sec_80ddb=40000,
        sec_80ddb_senior=100000,
        # sec_80eea deliberately ABSENT (removed in Step D).
        sec_80g=None,
    ),

    # Sec 10(13A) HRA parameters unchanged (the engine still computes the
    # 40% non-metro baseline only; the 50% metro case stays recorded).
    # Source: docs/tax-verification.md §8.
    hra=HRARules(
        metro_cities=("Delhi", "Mumbai", "Kolkata", "Chennai"),
        metro_pct=0.50,
        non_metro_pct=0.40,
        salary_pct=0.10,
    ),

    # Agricultural income is exempt (Section 10(1)); partial integration is
    # flagged when non-agricultural income exceeds 2,50,000. The
    # verification record notes no FY 2025-26 change.
    # Source: docs/tax-verification.md (no FY 2025-26 change recorded;
    # unchanged from FY_2024_25).
    agri=AgriRules(
        exempt=True,
        integration_threshold_non_agri=250000,
    ),

    # 4% Health & Education Cess, applied multiplicatively after surcharge
    # (and OUTSIDE the 87A-band and surcharge-relief comparisons).
    # Source: docs/tax-verification.md §3 (+ tax-expert correction 5:
    # missing constant made explicit).
    cess_rate=0.04,

    # Professional tax is a STATE levy — no national default (ruling j).
    # The engine books 0 when the input is absent and emits the advisory:
    # "Professional tax is state-specific — enter your actual figure
    # (commonly ₹200/month, capped ₹2,500/yr)." (FY 2024-25 keeps its
    # 2,500 default + the same advisory.)
    # Source: docs/tax-verification.md §6 professional-tax row (+ tax-expert
    # correction 6).
    professional_tax_default=0,

    # Section 115BAC(6): surcharge on the special-rate (111A/112A) portion
    # of tax is capped at 15% in the new regime; the old regime is uncapped.
    # Source: docs/tax-verification.md §4 (+ tax-expert correction 5:
    # missing constant made explicit).
    new_regime_cg_surcharge_cap=0.15,
)

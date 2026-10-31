"""FY 2024-25 (AY 2025-26) rule set — transcribed from the current
tax_engine.py (Sprint 2 Step A1, ADR-008).

Every constant below reproduces tax_engine.py's FY 2024-25 behavior
EXACTLY; parity is proven by tests/fixtures/parity_fy2425.json (frozen at
commit d6a6609+). The FY 2025-26 constants record is docs/tax-verification.md
and lands in Step A3 — do not "update" values here before then.
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

FY_2024_25 = FYRules(
    # tax_engine.py header: "FY 2024-25 (AY 2025-26)".
    tax_year="2024-25",
    assessment_year="2025-26",
    label="FY 2024-25 (AY 2025-26)",

    # _slab_new levels, transcribed as-is: [(300000, 0.05), (700000, 0.10),
    # (1000000, 0.15), (1200000, 0.20), (1500000, 0.30)] are (threshold,
    # rate) pairs — income above the threshold pays the rate up to the next
    # threshold, and [0, 300000] is the nil band. Re-expressed below in the
    # registry's (upper_bound, rate) slice convention so ONE slab walk
    # serves both regimes bit-for-bit: the level pair (300000, 0.05) becomes
    # the 0% band ending at 300000 plus the 5% band ending at 700000, and so
    # on. Floor 0 — the nil band starts at 0.
    new_regime_slabs=(
        SlabBand(300000, 0.0),      # nil band: 0 - 3L
        SlabBand(700000, 0.05),     # 3L - 7L   (level (300000, 0.05))
        SlabBand(1000000, 0.10),    # 7L - 10L  (level (700000, 0.10))
        SlabBand(1200000, 0.15),    # 10L - 12L (level (1000000, 0.15))
        SlabBand(1500000, 0.20),    # 12L - 15L (level (1200000, 0.20))
        SlabBand(None, 0.30),       # Above 15L (level (1500000, 0.30))
    ),

    # _slab_old bands: 2.5L/5L/10L structure — (ex, 5L] at 5%, (5L, 10L] at
    # 20%, above 10L at 30%, where `ex` is the age-dependent basic exemption
    # supplied as the walk floor from old_regime_exemption_by_age.
    old_regime_slabs=(
        SlabBand(500000, 0.05),     # {ex}L - 5L
        SlabBand(1000000, 0.20),    # 5L - 10L
        SlabBand(None, 0.30),       # Above 10L
    ),

    # _slab_old: ex = 500000 if vsr else 300000 if senior else 250000
    # (keys are minimum ages; 0 is the default).
    old_regime_exemption_by_age=MappingProxyType({0: 250000, 60: 300000, 80: 500000}),

    # _calc_old std_ded 50000 / _calc_new std_ded 75000 (Budget 2024).
    standard_deduction=MappingProxyType({"old": 50000, "new": 75000}),

    # Old regime: min(tax, 12500) while taxable <= 500000.
    # New regime: full rebate while taxable <= 700000, then the crude
    # marginal-relief zone up to 727777 — the 727777 band constant is
    # transcribed as-is; superseded in Step A2 per tax-expert ruling
    # Rs 7,23,214 incl-cess.
    rebate=MappingProxyType({
        "old": RebateRule(
            income_cap=500000,
            max_amount=12500,
            marginal_relief=False,
            band_upper_bound=None,
            band_cap_includes_cess=False,
        ),
        "new": RebateRule(
            income_cap=700000,
            max_amount=None,        # full rebate of the computed tax
            marginal_relief=True,
            band_upper_bound=727777,
            band_cap_includes_cess=False,
        ),
    }),

    # _apply_marginal_relief ladder: 10% above 50L, 15% above 1Cr, 25% above
    # 2Cr, 37% above 5Cr — with the new regime capped at 25% (115BAC(6)) and
    # marginal relief min(surcharge, income - 50L).
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

    # _calc_cg: Budget 2024 rates — equity LTCG 12.5% over the 1.25L
    # exemption, equity STCG 20%, property LTCG 20% old / 12.5% new. The CG
    # tax is added outside the 87A rebate (special_rate_excludes_87a).
    cg=CGRules(
        ltcg_112a_rate=0.125,
        ltcg_112a_exemption=125000,
        stcg_111a_rate=0.20,
        property_rate_by_regime=MappingProxyType({"old": 0.20, "new": 0.125}),
        special_rate_excludes_87a=True,
    ),

    # _calc_old deduction caps. 80E/80G/80U-80DD/80DDB caps are recorded for
    # completeness; the current engine books the declared amounts for those
    # sections (unchanged in Step A1 — parity first).
    deduction_caps=DeductionCaps(
        sec_80c=150000,
        sec_80d_self=25000,
        sec_80d_self_senior=50000,
        sec_80d_parents=50000,
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
        # 80EEA stays at 1,50,000 for FY 2024-25; the deduction (and this
        # cap) is REMOVED in Step A3 per docs/tax-verification.md.
        sec_80eea=150000,
        sec_80g=None,
    ),

    # _calc_hra uses the 40% non-metro baseline only (no city input yet);
    # the 50% metro case is recorded for the next step.
    hra=HRARules(
        metro_cities=("Delhi", "Mumbai", "Kolkata", "Chennai"),
        metro_pct=0.50,
        non_metro_pct=0.40,
        salary_pct=0.10,
    ),

    # Agricultural income is exempt (Section 10(1)); partial integration is
    # flagged when non-agricultural income exceeds 2,50,000.
    agri=AgriRules(
        exempt=True,
        integration_threshold_non_agri=250000,
    ),

    # cess: * 1.04 in _calc_old/_calc_new.
    cess_rate=0.04,

    # professional_tax default of 2500 when salary > 0.
    professional_tax_default=2500,

    # Section 115BAC(6) special-rate surcharge cap — registry constant added
    # now per the ADR; the engine starts using it in Step A2/E.
    new_regime_cg_surcharge_cap=0.15,
)

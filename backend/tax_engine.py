# Summer internship project
"""
Tax Engine v5.0 — Professional Grade Auditor
FY 2024-25 (AY 2025-26) | Indian Tax Laws (Direct Tax Compliance)
Fixes:
- Added missing Section 24(b) Home Loan Interest deduction to Old Regime
- Added Section 80D Parents, 80E Education Loan, 80TTA/80TTB, 80GG to Old Regime total deductions
- Applied statutory 30% standard deduction on rental income (Sec 24a) uniformly
- Added Section 87A marginal relief at the ₹7 Lakh boundary in New Regime
- Enhanced itemized Computation Statement for CA-level reporting

Sprint 2 (ADR-008): all FY 2024-25 constants now load from the versioned
registry in the tax_rules package; calculate_tax_advanced accepts a tax_year
key (default "fy_2024_25") and results report top-level tax_year /
assessment_year / fy_label. Behavior is byte-identical to the pre-registry
engine for FY 2024-25 — proven by tests/fixtures/parity_fy2425.json
(generated with tests/tools/generate_parity_snapshot.py).

Sprint 2 Step A2/E (documented statutory bug fixes per tax-expert rulings,
2026-10-31): the surcharge marginal relief is reworked to the band-based
threshold comparison (T_r1(h_top) at the band rate containing h_top; relief
at ALL FOUR thresholds, not just 50L) and Section 87A is harmonized —
eligibility keyed on TOTAL income (incl. special-rate CG), rebate on
normal-rate tax only, and the new-regime band cap applied AFTER cess to the
payable total (endpoint emerges from min(); the stored 727777 pre-cess band
bound is retired). The new regime also gains the s.115BAC(6) 15% cap on the
surcharge over the special-rate (111A/112A) portion. These changes apply
ONLY inside the surcharge-relief zones and the 87A band — the parity
fixture's other cells remain byte-identical (relief-zone cells were
re-pinned with citations by tests/tools/apply_a2_fixture_updates.py).

Sprint 2 Step A3: the registry default flips to "fy_2025_26"
(docs/tax-verification.md + the six tax-expert corrections, 2026-10-31).
No algorithm forks per year — every slab/rebate/surcharge/CG/cess/prof-tax
constant is read from the registered rule set, so both years run through
the identical generalized A2 algorithms. One behavior addition: when the
professional-tax input is absent (registry default applied) and salary > 0,
a state-specific advisory is appended to the audit observations for BOTH
years (FY 2024-25 keeps its 2,500 default; FY 2025-26 defaults to 0 —
ruling j). "tax_year": "fy_2024_25" reproduces every pre-A3 figure.

Sprint 2 Step C (capital gains — tax-expert rulings R-e/R-f, 2026-10-31):
_calc_cg now AGGREGATES every equity_ltcg entry and deducts the Section
112A ₹1.25L exemption ONCE before applying 12.5% to the excess (the H1
bug applied it per entry — [2L, 2L] double-dipped to 18,750 instead of
34,375); 111A STCG remains a full 20% per entry with no exemption share,
and property gains book per rules.cg.property_rate_by_regime. This
deliberately changes the FY 2024-25 parity-fixture cells whose scenario
carries multiple equity_ltcg entries (re-pinned with citations by
tests/tools/apply_s2c_fixture_updates.py). Property gains additionally
gain the R-e disclosures: a holding-period assumption line whenever
property_cg exists, plus a transfer-date note keyed on the tri-state
flag cg_transfer_before_2024_07_23 (False = post-cutoff note; True/null/
absent = election advisory — the 20%-with-indexation election is never
computed or fabricated).

Sprint 2 Step B (HRA — Section 10(13A) Rule 2A, tax-expert rulings +
tax-verification.md §8): _calc_hra now runs the full statutory least-of
test over THREE inputs — (a) HRA received, (b) rent paid minus 10% of
salary, (c) 50% of salary in the statutory metros (Delhi/Mumbai/Kolkata/
Chennai) or 40% elsewhere — returning 0 when salary, rent_paid or
hra_received is non-positive. The new session keys hra_received/rent_paid
are authoritative per leg; the legacy "hra" key maps to BOTH legs and
therefore reproduces the legacy formula min(0.4*salary, hra,
hra - 0.1*salary) exactly (parity cell in tests/test_hra.py; the FY
2024-25 parity fixture is untouched). The 80GG guard switches to
hra_received > 0 (receiving any HRA disqualifies 80GG even when the
exemption computes to 0), and an unstated metro status assumes non-metro
with the disclosure "Metro status not provided — non-metro 40% assumption
applied" appended to the audit observations whenever an HRA computation
ran. The new regime continues to ignore all three inputs.

Sprint 2 Step D (deduction correctness — tax-expert rulings R-g/R-h/R-i,
2026-10-31, docs/tax-verification.md §6): the three collect-and-drop
deductions are now booked and disclosed.
  - 80U/80DD is FLAT and category-driven: the new session key
    "80u_80dd_category" ("none" | "40_79" | "80_plus") books 0 /
    rules.sec_80u_80dd_40_79 / rules.sec_80u_80dd_80_plus (75,000 /
    1,25,000). The legacy numeric "80u_80dd" amount is NEVER guessed into
    a deduction — it books nothing and emits the verbatim legacy-amount
    advisory (H4 fix).
  - 80DDB is min(expenditure, tier) with the tier keyed on the SELF's age
    as the patient proxy (R-h): 60+ -> rules.sec_80ddb_senior (1,00,000)
    else rules.sec_80ddb (40,000); the new key is "80ddb_expenditure".
    The patient-age advisory fires whenever the deduction runs (the
    patient's real age is not collected). The legacy numeric "80ddb"
    amount books nothing + the legacy-amount advisory.
  - 80G (R-g) books rate x amount per category —
    "80g_category" in {cat_100_no_limit, cat_50_no_limit,
    cat_100_qualifying_limit, cat_50_qualifying_limit} — where categories
    3/4 count the donation only up to the qualifying limit: 10% of the
    ADJUSTED gross total income (GTI before Ch VI-A minus the special-
    rate CG entries; see _80g_qualifying_limit). An absent/unknown
    category defaults to category 4 + the default-category advisory; the
    cash-mode cap advisory fires whenever the donation exceeds ₹2,000
    (mode not collectible this sprint). The new regime books generic 80G
    at 0 with the PM-CARES-class advisory.
  - 80EEA is REMOVED (discontinued — only loans sanctioned before
    1 April 2022 qualified): the ded entry is gone, main.py 422s the key
    on both endpoints, and direct engine calls ignore it.
  - 80D parents books the 25,000 base cap (rules.sec_80d_parents); the
    50,000 senior-parent cap is registered (sec_80d_parents_senior) for
    the Sprint 3 parents_senior input (ruling i) and the assumption is
    disclosed via the seniority advisory whenever 80d_parents > 0.
Every new advisory lands in the shared audit observations (never silent);
tests/test_deductions.py pins the matrix, the GT12 composite cell and the
no-silent-collection meta-table.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
try:
    import numpy as np
except ImportError:
    np = None
import tax_rules
from tax_rules.schema import SlabBand
from ai_models import ANFIS

logger = logging.getLogger(__name__)

# Sprint 2 Step C (tax-expert ruling R-e): property-gains disclosures.
# The 20%-with-indexation election is NOT built — it is disclosed, never
# fabricated; evaluating it needs the (uncollected) cost-of-acquisition
# figures, so the advisory defers to a CA. The holding-period assumption
# is stated whenever property gains exist (property_cg is booked LTCG;
# short-term property gains would be slab-taxed).
PROPERTY_ELECTION_ADVISORY = (
    "Property gains default to the 12.5% post-23-Jul-2024 route. If the "
    "property was acquired before 23-Jul-2024 by a resident individual/HUF, "
    "a 20%-with-indexation election may be available if it yields lower tax "
    "— this tool cannot evaluate the election; consult a CA with your cost "
    "figures."
)
PROPERTY_POST_CUTOFF_NOTE = (
    "Transfer on/after 23-Jul-2024: 12.5% without indexation applies."
)
PROPERTY_HOLDING_ASSUMPTION = (
    "Property gains are treated as long-term; short-term property gains "
    "are taxed at slab rates — verify your holding period."
)

# Sprint 2 Step B (Section 10(13A) Rule 2A — tax-verification.md §8): the
# metro leg of the least-of test needs a third input (metro status). When
# the session never states it, the engine assumes NON-METRO (40%) and
# discloses the assumption — never silent (R-e disclosure pattern). Both
# registered years carry non_metro_pct 0.40, so the "40%" wording is
# registry-stable.
HRA_METRO_ASSUMPTION_OBSERVATION = (
    "Metro status not provided — non-metro 40% assumption applied"
)

# Sprint 2 Step D advisories (verbatim wording pinned by
# tests/test_deductions.py). None of the deduction corrections below is
# ever silent: the legacy numeric amounts, the patient-age proxy, the
# unverified seniority, the default donation category, the cash cap and
# the new-regime 80G exclusion each surface in the shared audit
# observations.
DED_80U_LEGACY_AMOUNT_OBSERVATION = (
    "80U/80DD is a flat deduction based on disability category "
    "(₹75,000 / ₹1,25,000) — the amount entered was not used; provide the "
    "disability category."
)
DED_80DDB_LEGACY_AMOUNT_OBSERVATION = (
    "80DDB is a tier-capped deduction on actual treatment expenditure "
    "(₹40,000 limit, ₹1,00,000 where the treated person is 60 or older) — "
    "the amount entered was not used; provide the treatment expenditure."
)
DED_80DDB_PATIENT_AGE_OBSERVATION = (
    "If the treated person (e.g., a dependent parent) is 60 or older, the "
    "limit is ₹1,00,000 — verify."
)
DED_80G_DEFAULT_CATEGORY_OBSERVATION = (
    "Donation category not specified — computed as 50% subject to the 10% "
    "qualifying limit; verify the donee's 80G registration (Form 10BE) and "
    "category."
)
DED_80G_CASH_CAP_OBSERVATION = (
    "Cash donations qualify only up to ₹2,000 — verify your payment mode."
)
DED_80G_NEW_REGIME_OBSERVATION = (
    "Most 80G donations are not deductible under the new regime (specified "
    "funds like PM CARES remain eligible)."
)
DED_80D_PARENTS_SENIOR_OBSERVATION = (
    "If either parent is a senior citizen (60+), the parents' "
    "health-insurance limit is ₹50,000."
)

@dataclass
class Explanation:
    particular: str
    reason: str
    section: str
    amount: float
    status: str = "Valid"
    eli5: str = ""

@dataclass
class TaxResult:
    income_details: List[Dict] = field(default_factory=list)
    deduction_details: List[Dict] = field(default_factory=list)
    gross_total_income: float = 0.0
    total_deductions: float = 0.0
    taxable_income: float = 0.0
    total_tax: float = 0.0
    recommendation: str = ""
    savings: float = 0.0
    explanations: List[Explanation] = field(default_factory=list)
    slabs_breakdown: List[Dict] = field(default_factory=list)
    efficiency_score: float = 0.0
    savings_tips: List[str] = field(default_factory=list)
    audit_observations: List[str] = field(default_factory=list)
    risk_level: str = "Low"

class TaxEngine:
    # Sprint 2 Step D (ruling R-g): the four 80G donation categories —
    # (rate, subject to the qualifying limit). The registry's sec_80g
    # placeholder stays None; the category MODEL is engine-side until a
    # donee-registry input layer exists.
    _80G_CATEGORY_RATES = {
        "cat_100_no_limit": (1.0, False),
        "cat_50_no_limit": (0.5, False),
        "cat_100_qualifying_limit": (1.0, True),
        "cat_50_qualifying_limit": (0.5, True),
    }
    # R-g default when the category is absent/unknown: category 4 (50%
    # subject to the qualifying limit) — always disclosed via the
    # default-category advisory in calculate_tax_advanced.
    _80G_DEFAULT_CATEGORY = "cat_50_qualifying_limit"
    # Statutory qualifying limit: 10% of the adjusted gross total income.
    _80G_QUALIFYING_LIMIT_PCT = 0.10

    def __init__(self):
        self.anfis = ANFIS()

    def calculate_tax_advanced(self, data: Dict[str, Any], tax_year: Optional[str] = None) -> Dict[str, Any]:
        # ADR-008: resolve the versioned rule set. None selects the registry
        # default; an unknown key raises UnknownTaxYearError — never a
        # silent fallback.
        rules = tax_rules.get_rules(
            tax_year if tax_year is not None else tax_rules.DEFAULT_TAX_YEAR
        )
        logger.debug("TaxEngine computing with rules %s", rules.label)

        # Basic Inputs
        salary       = float(data.get("salary", 0) or 0)
        business     = float(data.get("business", 0) or 0)
        agri         = float(data.get("agriculture", 0) or 0)
        rental_gross = float(data.get("rental", 0) or 0)
        other_income = float(data.get("other_income", 0) or 0)
        cg_data      = data.get("capital_gains", [])
        if not isinstance(cg_data, list):
            cg_data = []

        # Sprint 2 Step B: the HRA exemption needs THREE statutory inputs
        # (Sec 10(13A) Rule 2A — verification record §8). The new session
        # keys hra_received/rent_paid are authoritative per leg when present;
        # the LEGACY session key "hra" (frontend-suggested) maps to BOTH
        # legs, which reproduces the legacy formula
        #   min(0.4*salary, hra, hra - 0.1*salary)
        # exactly (leg (a) = hra, leg (b) = hra - 10%*salary, leg (c) =
        # 0.4*salary non-metro baseline) — proven by the parity cell in
        # tests/test_hra.py. A None value counts as absent (sessions may
        # carry explicit nulls until the slot is collected).
        legacy_hra = data.get("hra", 0)
        hra_received_raw = data.get("hra_received")
        rent_paid_raw = data.get("rent_paid")
        hra_leg = float(
            hra_received_raw if hra_received_raw is not None else legacy_hra or 0
        )
        rent_leg = float(
            rent_paid_raw if rent_paid_raw is not None else legacy_hra or 0
        )
        # is_metro is bool-strict at the API boundary; anything else (None,
        # absent, junk on direct engine calls) assumes non-metro and is
        # disclosed via the audit observation below.
        is_metro_raw = data.get("is_metro")
        is_metro = is_metro_raw if isinstance(is_metro_raw, bool) else None

        age       = int(data.get("age", 30) or 30)
        is_senior = age >= 60
        is_vsr    = age >= 80

        # Deductions & Caps (FY 2024-25, from the registry rules)
        caps = rules.deduction_caps
        sec_80d_self_limit = caps.sec_80d_self_senior if is_senior else caps.sec_80d_self
        # Step D (ruling i): the parents' 80D cap is gated on the PARENTS'
        # seniority — the 25,000 base applies until the parents_senior
        # input lands (Sprint 3); the 50,000 senior cap is registered as
        # sec_80d_parents_senior and the unverified seniority is disclosed
        # via the advisory below.
        sec_80d_parents_limit = caps.sec_80d_parents

        # Sprint 2 Step D — deduction correctness (H4/M1 fixes; rulings
        # R-g/R-h/R-i, docs/tax-verification.md §6). The 80U/80DD and
        # 80DDB amounts are no longer collected-and-dropped:
        #   - 80U/80DD is FLAT and category-driven ("none" | "40_79" |
        #     "80_plus" -> 0 / sec_80u_80dd_40_79 / sec_80u_80dd_80_plus).
        #     The legacy numeric amount is never guessed into a deduction.
        #   - 80DDB is min(expenditure, tier), tier keyed on the SELF's
        #     age as the patient proxy (the patient's real age is not
        #     collected — disclosed via the advisory below).
        #   - 80EEA is REMOVED (discontinued — only loans sanctioned
        #     before 1 April 2022 qualified): the API boundary 422s the
        #     key and direct engine calls simply ignore it.
        u80_category_raw = data.get("80u_80dd_category")
        u80_category = u80_category_raw if u80_category_raw in ("40_79", "80_plus") else None
        ded_80u = (
            float(caps.sec_80u_80dd_40_79)
            if u80_category == "40_79"
            else float(caps.sec_80u_80dd_80_plus)
            if u80_category == "80_plus"
            else 0.0
        )
        legacy_80u_amount = float(data.get("80u_80dd", 0) or 0)

        ddb_expenditure = max(0.0, float(data.get("80ddb_expenditure", 0) or 0))
        ddb_tier = float(caps.sec_80ddb_senior if is_senior else caps.sec_80ddb)
        ded_80ddb = min(ddb_expenditure, ddb_tier)
        legacy_80ddb_amount = float(data.get("80ddb", 0) or 0)

        g80_amount = float(data.get("80g", 0) or 0)
        g80_category = data.get("80g_category")

        ded = {
            "80c":   min(float(data.get("80c", 0) or 0), caps.sec_80c),
            "80d":   min(float(data.get("80d", 0) or 0), sec_80d_self_limit),
            "80d_p": min(float(data.get("80d_parents", 0) or 0), sec_80d_parents_limit),
            "80e":   float(data.get("80e", 0) or 0), # No upper limit on interest
            "80g":   g80_amount,
            # Step B: the two Rule 2A legs (the legacy "hra" entry is gone —
            # it lives on only through the mapping above).
            "hra_received": hra_leg,
            "rent_paid":    rent_leg,
            "24b":   min(float(data.get("24b", 0) or 0), caps.sec_24b), # Max 2L for self-occupied
            # Step D: 80EEA removed (discontinued) — the key is 422'd at
            # the API boundary and ignored here.
            "nps":   min(float(data.get("nps", 0) or 0), caps.sec_80ccd_1b), # 80CCD(1B) extra 50k
            "80tta": min(float(data.get("80tta", 0) or 0), caps.sec_80tta) if not is_senior else 0,
            "80ttb": min(float(data.get("80ttb", 0) or 0), caps.sec_80ttb) if is_senior else 0,
            "80gg":  float(data.get("80gg", 0) or 0),
            # Step D: category/expenditure-driven amounts — the legacy
            # numeric keys never book (see the block above).
            "80u":   ded_80u,
            "80ddb": ded_80ddb,
            # Step D carriers for the _calc_old explanations (not
            # deductions themselves).
            "80u_category":      u80_category,
            "80ddb_expenditure": ddb_expenditure,
            "80g_category":      g80_category if isinstance(g80_category, str) else None,
        }

        prof_tax = float(data.get("professional_tax", rules.professional_tax_default if salary > 0 else 0) or 0)

        old_res = self._calc_old(salary, business, agri, rental_gross, other_income, cg_data, ded, prof_tax, is_senior, is_vsr, rules, is_metro)
        new_res = self._calc_new(salary, business, agri, rental_gross, other_income, cg_data, is_senior, rules)

        # Optimizer Logic
        rec     = "New Regime" if new_res.total_tax <= old_res.total_tax else "Old Regime"
        savings = abs(old_res.total_tax - new_res.total_tax)

        # ANFIS Industrial Audit Score
        final_res = old_res if rec == "Old Regime" else new_res
        eff_score = self.anfis.score_efficiency(data, final_res.__dict__)

        old_res.efficiency_score = eff_score
        new_res.efficiency_score = eff_score
        old_res.recommendation   = rec
        new_res.recommendation   = rec
        old_res.savings          = savings
        new_res.savings          = savings

        # Risk Analysis
        total_inc = salary + business + rental_gross + other_income
        cg_total  = sum(c.get("amount", 0) for c in cg_data)
        risk = "Low"
        observations = []
        # Step B: the risk check keys on the HRA RECEIVED leg — for
        # legacy-key sessions the leg equals the old ded["hra"] value, so
        # the behavior is unchanged there.
        if hra_leg > 0.5 * (salary or 1):
            risk = "Medium"
            observations.append("HRA Claim vs Salary ratio is unusually high (>50%). Rent receipts & landlord PAN are mandatory.")
        if ded["80g"] > 0.1 * (total_inc or 1):
            risk = "High"
            observations.append("Significant Section 80G donations detected. Verify Form 10BE from recipient trust.")
        if cg_total > 1000000:
            observations.append("Capital Gains exceed ₹10 Lakhs. Reconcile with Annual Information Statement (AIS / TIS).")
        if ded["24b"] > 0 and salary == 0 and business == 0:
            observations.append("Home loan interest claimed without declared primary taxable income.")

        # C2: agricultural income is exempt under Section 10(1) (excluded
        # from gross in _calc_old/_calc_new). Flag possible partial
        # integration only when non-agricultural income exceeds the
        # ₹2,50,000 basic-exemption threshold — pure agricultural income is
        # simply exempt. net_rental mirrors the 30% standard deduction of
        # Section 24(a) applied in _calc_old/_calc_new.
        non_agri_income = (
            salary + business
            + (round(rental_gross * 0.7, 2) if rental_gross > 0 else 0)
            + other_income
        )
        if agri > 0 and non_agri_income > rules.agri.integration_threshold_non_agri:
            observations.append(
                "Agricultural income is exempt under Section 10(1). Partial integration "
                "with non-agricultural income may apply — verify with a tax professional."
            )

        # C4c: honest limitation disclosure — the engine taxes the declared
        # amount as the gain; remind the user to confirm it is the GAIN, not
        # the gross sale value. (The existing CG > 10L observation above is
        # unchanged.)
        if cg_data:
            observations.append(
                "Capital gains are booked at the declared amount — confirm this is the "
                "GAIN (sale price minus cost of acquisition), not the gross sale value, "
                "before filing."
            )

        # Step C (ruling R-e): property-gains disclosure. The holding-period
        # assumption is stated whenever property gains exist (they are
        # booked as LTCG). The tri-state transfer-date flag then selects the
        # route note: explicitly False (transfer on/after 23-Jul-2024) gets
        # the post-cutoff note; True (pre-cutoff) and null/absent (unknown —
        # the default post-cutoff route is booked either way) get the
        # election advisory. The election itself is NEVER computed or
        # fabricated — indexation needs the uncollected cost figures.
        if any(c.get("type") == "property_cg" for c in cg_data):
            observations.append(PROPERTY_HOLDING_ASSUMPTION)
            if data.get("cg_transfer_before_2024_07_23") is False:
                observations.append(PROPERTY_POST_CUTOFF_NOTE)
            else:
                observations.append(PROPERTY_ELECTION_ADVISORY)

        # Step A3 (ruling j): professional tax is a state levy with no
        # national rate. When the input was never provided (the registry
        # default applies — 2,500 for FY 2024-25, 0 for FY 2025-26) and
        # there is salary income, disclose it so the default is never
        # silent. An explicit professional_tax (even 0) suppresses this.
        if salary > 0 and "professional_tax" not in data:
            observations.append(
                "Professional tax is state-specific — enter your actual figure "
                "(commonly ₹200/month, capped ₹2,500/yr)."
            )

        # Step B (Rule 2A): the metro leg is assumed NON-METRO whenever the
        # session never states it — disclosed whenever an HRA computation
        # was attempted (any HRA received declared), even when the exemption
        # ends up 0 (rent below the 10% excess, zero salary). An explicit
        # is_metro False is a definitive non-metro answer, not an assumption.
        if hra_leg > 0 and is_metro is None:
            observations.append(HRA_METRO_ASSUMPTION_OBSERVATION)

        # Sprint 2 Step D: the deduction corrections are never silent
        # (shared with both regimes, like the HRA metro disclosure above).
        if legacy_80u_amount > 0:
            observations.append(DED_80U_LEGACY_AMOUNT_OBSERVATION)
        if legacy_80ddb_amount > 0:
            observations.append(DED_80DDB_LEGACY_AMOUNT_OBSERVATION)
        if ded_80ddb > 0:
            # R-h: the tier above keyed on the SELF's age as the patient
            # proxy — the treated person's real age is not collected.
            observations.append(DED_80DDB_PATIENT_AGE_OBSERVATION)
        if float(data.get("80d_parents", 0) or 0) > 0:
            # R-i: the 50,000 senior-parent cap needs the parents_senior
            # input (Sprint 3); the 25,000 base assumption is disclosed.
            observations.append(DED_80D_PARENTS_SENIOR_OBSERVATION)
        if g80_amount > 0:
            if not (isinstance(g80_category, str) and g80_category in self._80G_CATEGORY_RATES):
                observations.append(DED_80G_DEFAULT_CATEGORY_OBSERVATION)
            if g80_amount > 2000:
                observations.append(DED_80G_CASH_CAP_OBSERVATION)
            observations.append(DED_80G_NEW_REGIME_OBSERVATION)

        old_res.risk_level = risk
        old_res.audit_observations = observations
        new_res.risk_level = risk
        new_res.audit_observations = observations

        try:
            from ai_models import ReasoningAgent
            tips = ReasoningAgent().get_savings_tips(data)
            old_res.savings_tips = tips
            new_res.savings_tips = tips
        except Exception:
            pass

        return {
            "tax_year": rules.tax_year,
            "assessment_year": rules.assessment_year,
            "fy_label": rules.label,
            "old_regime": old_res,
            "new_regime": new_res,
            "recommendation": rec,
            "savings": round(savings, 2),
            "efficiency_score": round(eff_score, 1),
        }

    def _calc_old(self, salary, business, agri, rental, other, cg_data, ded, prof_tax, is_senior, is_vsr, rules, is_metro=None) -> TaxResult:
        res = TaxResult()
        std_ded = rules.standard_deduction["old"] if salary > 0 else 0
        # Step B: three-leg Rule 2A least-of test (legs carried in ded).
        hra_ex  = self._calc_hra(rules, salary, ded["hra_received"], ded["rent_paid"], is_metro)

        # Net rental income after 30% statutory deduction under Section 24(a)
        net_rental = round(rental * 0.7, 2) if rental > 0 else 0

        # C2: agricultural income is exempt under Section 10(1) and is
        # EXCLUDED from gross total income (the itemised "Exempt" entry in
        # income_details below must stay truthful). Partial integration is
        # flagged as an audit observation in calculate_tax_advanced.
        gross = salary + business + net_rental + other
        res.gross_total_income = round(gross, 2)

        # Calculate 80GG if applicable (rent paid without HRA). Step B: the
        # guard keys on the HRA RECEIVED leg — a user who receives HRA can
        # never claim 80GG, even when the Rule 2A exemption computes to 0.
        ded_80gg = self._calc_80gg(ded["80gg"], gross, ded["hra_received"], rules)

        # Full Chapter VI-A + Section 24(b) deductions. Step D: the 80G
        # booking is category- and qualifying-limit-driven (R-g), and the
        # 80U/80DD + 80DDB amounts join the sum for the first time (they
        # were collected and silently dropped before — the H4 bug).
        g80_deduction, g80_reason = self._calc_80g(
            ded["80g"], ded.get("80g_category"), gross, cg_data
        )
        total_ded = (
            std_ded +
            hra_ex +
            prof_tax +
            ded["24b"] +
            ded["80c"] +
            ded["80d"] +
            ded["80d_p"] +
            ded["nps"] +
            ded["80e"] +
            g80_deduction +
            ded_80gg +
            ded["80tta"] +
            ded["80ttb"] +
            ded["80u"] +
            ded["80ddb"]
        )
        res.total_deductions = round(total_ded, 2)

        taxable = max(0.0, gross - total_ded)
        cg_tax, cg_inc = self._calc_cg(cg_data, "old", rules)

        tax_norm, slabs = self._slab_old(taxable, is_senior, is_vsr, rules)
        res.slabs_breakdown = slabs

        # Section 87A rebate (old regime: up to 12,500 while TOTAL income
        # <= 5,00,000). Step A2: eligibility is keyed on TOTAL income
        # (slab taxable + special-rate CG) per the tax-expert rulings —
        # the rebate, when eligible, touches the normal-rate tax only and
        # stays band-free.
        rebate_rule = rules.rebate["old"]
        total_income = taxable + cg_inc
        if total_income <= rebate_rule.income_cap:
            if rebate_rule.max_amount is None:
                tax_norm = 0.0
            else:
                tax_norm = max(0.0, tax_norm - min(tax_norm, rebate_rule.max_amount))

        surcharge = self._apply_marginal_relief(
            tax_norm,
            cg_tax,
            taxable,
            cg_inc,
            "old",
            rules,
            lambda v: self._slab_old(v, is_senior, is_vsr, rules)[0],
        )
        total_tax = (tax_norm + cg_tax + surcharge) * (1 + rules.cess_rate)

        res.total_tax = round(total_tax, 2)
        res.taxable_income = round(taxable + cg_inc, 2)

        # Itemized Income Details
        res.income_details = []
        if salary > 0:
            res.income_details.append({"source": "Income from Salary", "amount": salary, "section": "17(1)", "status": "Reported"})
        if business > 0:
            res.income_details.append({"source": "Profits & Gains of Business/Profession (PGBP)", "amount": business, "section": "28", "status": "Taxable"})
        if rental > 0:
            res.income_details.append({"source": f"Income from House Property (Net of 30% std ded)", "amount": net_rental, "section": "24(a)", "status": "Taxable"})
        if other > 0:
            res.income_details.append({"source": "Income from Other Sources", "amount": other, "section": "56", "status": "Taxable"})
        if agri > 0:
            res.income_details.append({"source": "Agricultural Income (Exempt with integration)", "amount": agri, "section": "10(1)", "status": "Exempt"})

        # Itemized Deduction Explanations
        res.explanations = []
        if std_ded > 0:
            res.explanations.append(Explanation("Standard Deduction", "Flat deduction for salaried employees.", "16(ia)", std_ded))
        if prof_tax > 0:
            res.explanations.append(Explanation("Professional Tax", "State statutory tax on employment.", "16(iii)", prof_tax))
        if hra_ex > 0:
            res.explanations.append(Explanation("HRA Exemption", "House Rent Allowance exemption.", "10(13A)", hra_ex))
        if ded["24b"] > 0:
            res.explanations.append(Explanation("Home Loan Interest", "Interest paid on housing loan for self-occupied property.", "24(b)", ded["24b"]))
        if ded["80c"] > 0:
            res.explanations.append(Explanation("Section 80C", "PF, PPF, ELSS, Life Insurance, School Fees.", "80C", ded["80c"]))
        if ded["80d"] > 0:
            res.explanations.append(Explanation("Section 80D (Self & Family)", "Health insurance premium and preventive checkup.", "80D", ded["80d"]))
        if ded["80d_p"] > 0:
            res.explanations.append(Explanation("Section 80D (Parents)", "Health insurance for parents.", "80D", ded["80d_p"]))
        if ded["nps"] > 0:
            res.explanations.append(Explanation("NPS Section 80CCD(1B)", "Additional voluntary contribution to National Pension System.", "80CCD(1B)", ded["nps"]))
        if ded["80e"] > 0:
            res.explanations.append(Explanation("Section 80E", "Interest on higher education loan.", "80E", ded["80e"]))
        if g80_deduction > 0:
            res.explanations.append(Explanation("Section 80G", g80_reason, "80G", g80_deduction))
        if ded["80u"] > 0:
            # Step D: the flat amount is booked from the disability
            # CATEGORY; the reason names it (never a bare amount).
            ded_caps = rules.deduction_caps
            res.explanations.append(Explanation(
                "Section 80U/80DD",
                f"Flat deduction for disability category "
                f"{ded['80u_category']} (₹{ded_caps.sec_80u_80dd_40_79:,.0f} / "
                f"₹{ded_caps.sec_80u_80dd_80_plus:,.0f}) — actual expenditure "
                f"is irrelevant.",
                "80U/80DD",
                ded["80u"],
            ))
        if ded["80ddb"] > 0:
            ddb_tier = (
                rules.deduction_caps.sec_80ddb_senior if is_senior
                else rules.deduction_caps.sec_80ddb
            )
            res.explanations.append(Explanation(
                "Section 80DDB",
                f"Treatment expenditure ₹{ded['80ddb_expenditure']:,.0f} "
                f"allowed up to the ₹{ddb_tier:,.0f} tier limit.",
                "80DDB",
                ded["80ddb"],
            ))
        if ded_80gg > 0:
            res.explanations.append(Explanation(
                "Section 80GG",
                "Rent paid where no HRA is received (least-of test).",
                "80GG",
                ded_80gg,
            ))
        if ded["80tta"] > 0:
            res.explanations.append(Explanation("Section 80TTA", "Savings bank account interest deduction.", "80TTA", ded["80tta"]))
        if ded["80ttb"] > 0:
            res.explanations.append(Explanation("Section 80TTB", "Senior citizen interest income from deposits.", "80TTB", ded["80ttb"]))

        return res

    def _calc_new(self, salary, business, agri, rental, other, cg_data, is_senior, rules) -> TaxResult:
        res = TaxResult()
        # Budget 2024: Standard deduction increased to ₹75,000 for New Tax Regime
        std_ded = rules.standard_deduction["new"] if salary > 0 else 0
        cg_tax, cg_inc = self._calc_cg(cg_data, "new", rules)

        net_rental = round(rental * 0.7, 2) if rental > 0 else 0
        gross = salary + business + net_rental + other
        res.gross_total_income = round(gross, 2)

        taxable = max(0.0, gross - std_ded)
        res.total_deductions = round(std_ded, 2)

        tax, slabs = self._slab_new(taxable, rules)
        res.slabs_breakdown = slabs

        # Section 87A in the New Regime — harmonized in Step A2/E per the
        # tax-expert rulings (FA-2025 Explanation):
        #   1. Eligibility is keyed on TOTAL income (slab taxable +
        #      special-rate CG), NOT the slab taxable alone. When eligible,
        #      the rebate wipes the normal-rate tax only (max_amount None =
        #      full rebate) — 111A/112A tax is never rebated.
        #   2. When TOTAL income exceeds the threshold, the PAYABLE total
        #      (income-tax after rebate + special-rate tax + surcharge +
        #      cess) is capped at (TOTAL INCOME - threshold) AFTER cess —
        #      the band endpoint EMERGES from that min() (derived:
        #      7,23,214 incl-cess for FY 2024-25; the stored 727777
        #      pre-cess band constant is retired in this step).
        rebate_rule = rules.rebate["new"]
        total_income = taxable + cg_inc
        if total_income <= rebate_rule.income_cap:
            if rebate_rule.max_amount is None:
                tax = 0.0
            else:
                tax = max(0.0, tax - min(tax, rebate_rule.max_amount))

        surcharge = self._apply_marginal_relief(
            tax,
            cg_tax,
            taxable,
            cg_inc,
            "new",
            rules,
            lambda v: self._slab_new(v, rules)[0],
        )
        total_tax = (tax + cg_tax + surcharge) * (1 + rules.cess_rate)
        if rebate_rule.marginal_relief and total_income > rebate_rule.income_cap:
            # Post-cess 87A band cap (Step A2): the payable TOTAL, including
            # surcharge and cess, cannot exceed the income excess over the
            # rebate threshold. Beyond the emergent band endpoint the
            # excess exceeds the payable and the min() is inert — no stored
            # band bound is needed.
            total_tax = min(total_tax, float(total_income - rebate_rule.income_cap))
        res.total_tax = round(total_tax, 2)
        res.taxable_income = round(taxable + cg_inc, 2)

        # New Regime Breakdown
        res.income_details = []
        if salary > 0:
            res.income_details.append({"source": "Income from Salary", "amount": salary, "section": "17(1)", "status": "Reported"})
        if business > 0:
            res.income_details.append({"source": "Business / Professional Income", "amount": business, "section": "28", "status": "Taxable"})
        if rental > 0:
            res.income_details.append({"source": "Rental Income (after 30% std ded)", "amount": net_rental, "section": "24(a)", "status": "Taxable"})
        if other > 0:
            res.income_details.append({"source": "Income from Other Sources", "amount": other, "section": "56", "status": "Taxable"})

        res.explanations = []
        if std_ded > 0:
            res.explanations.append(Explanation("Standard Deduction", "Budget 2024 enhanced flat deduction.", "16(ia)", std_ded))
        res.explanations.append(Explanation("Section 115BAC", "Default New Tax Regime with concessional slab rates.", "115BAC", 0, eli5="Lower progressive tax rates; itemized 80C/80D/HRA foregone."))

        return res

    def _apply_marginal_relief(
        self,
        tax_normal: float,
        tax_special: float,
        slab_income: float,
        cg_income: float,
        regime: str,
        rules,
        slab_tax_fn: Callable[[float], float],
    ) -> float:
        """Section 2(3) surcharge with the statutory band-based marginal
        relief (reworked in Step A2/E per the tax-expert rulings).

        For total income x (slab income + special-rate CG income) above
        the highest crossed threshold h_top:

            S_payable = min(S_band(x), max(0, T_r1(h_top) + (x - h_top) - T(x)))

        where S_band(x) is the band-rate surcharge at x — split into the
        normal-rate and special-rate portions, with the s.115BAC(6) cap
        (rules.new_regime_cg_surcharge_cap, 15%) applied to the special
        portion in the new regime; the old regime is uncapped — and
        T_r1(h_top) is the total pre-surcharge tax at h_top WITH the
        surcharge rate of the band CONTAINING h_top (50L->0%, 1Cr->10%,
        2Cr->15%, 5Cr->25%: at exactly h the LOWER band's rate applies).
        Cess is applied by the caller, OUTSIDE this comparison.

        At x == h exactly no relief is due: h_top is then the previous
        threshold and the band rate at x is the lower band's, so the
        comparison degenerates to the normal band computation.

        The pre-surcharge tax at h_top keeps the composition frozen at x:
        the slab portion absorbs the (x - h_top) reduction first (re-walked
        exactly through the slab via slab_tax_fn); only a residual beyond
        the slab income — reachable only when surcharge is triggered
        almost exclusively by capital gains — shrinks the special-rate
        portion proportionally to the CG income.
        """
        surcharge_rule = rules.surcharge
        income = slab_income + cg_income  # TOTAL income drives every threshold test
        first_threshold = surcharge_rule.bands[0][0]
        if income <= first_threshold:
            return 0.0

        def effective_rates(band_rate: float) -> Tuple[float, float]:
            """(normal-rate, special-rate) surcharge pair at a band rate."""
            if regime == "new":
                normal_rate = min(band_rate, surcharge_rule.new_regime_cap)
                # s.115BAC(6): surcharge on the 111A/112A portion is capped.
                return normal_rate, min(normal_rate, rules.new_regime_cg_surcharge_cap)
            uncapped = min(band_rate, surcharge_rule.old_regime_cap)
            return uncapped, uncapped

        def special_tax_at(income_at: float) -> float:
            """Special-rate tax on the composition reduced to income_at."""
            excess = income - income_at
            if excess <= slab_income or cg_income <= 0.0:
                return tax_special
            return tax_special * max(0.0, 1.0 - (excess - slab_income) / cg_income)

        pre_surcharge_tax = tax_normal + tax_special

        # Band walk: the applicable rate is the first band (from the top)
        # whose threshold is strictly below the income. income >
        # first_threshold guarantees a band matches.
        band_rate = next(
            rate for threshold, rate in reversed(surcharge_rule.bands) if income > threshold
        )
        normal_rate, special_rate = effective_rates(band_rate)
        band_surcharge = tax_normal * normal_rate + tax_special * special_rate
        if not surcharge_rule.marginal_relief:
            return band_surcharge

        h_top = max(t for t, _ in surcharge_rule.bands if income > t)
        # Rate of the band CONTAINING h_top (the lower band's rate at h).
        rate_at_h = next(
            (
                rate
                for threshold, rate in reversed(surcharge_rule.bands)
                if h_top > threshold
            ),
            0.0,
        )
        normal_rate_at_h, special_rate_at_h = effective_rates(rate_at_h)
        slab_income_at_h = max(0.0, slab_income - (income - h_top))
        tax_r1 = (
            slab_tax_fn(slab_income_at_h) * (1.0 + normal_rate_at_h)
            + special_tax_at(h_top) * (1.0 + special_rate_at_h)
        )
        relief_ceiling = max(0.0, tax_r1 + (income - h_top) - pre_surcharge_tax)
        if relief_ceiling < band_surcharge:
            logger.debug(
                "Surcharge marginal relief bound at h_top=%s: band %.2f capped to %.2f",
                h_top, band_surcharge, relief_ceiling,
            )
        return min(band_surcharge, relief_ceiling)

    def _calc_cg(self, cg_data: list, regime: str, rules) -> Tuple[float, float]:
        """Special-rate capital-gains tax and CG income for one regime.

        Sprint 2 Step C (tax-expert ruling R-f — the documented H1 fix):
        the Section 112A ₹1,25,000 exemption is an ANNUAL AGGREGATE across
        ALL equity_ltcg entries — the entries are summed first, the
        exemption is deducted ONCE, and rules.cg.ltcg_112a_rate applies to
        the excess. The previous per-entry application double-dipped the
        exemption on multi-entry portfolios ([2L, 2L] booked 18,750
        instead of 34,375) and starved partial pairs ([1L, 50k] booked 0
        instead of 3,125). Section 111A STCG stays a FULL
        rules.cg.stcg_111a_rate on every entry — the exemption is never
        shared with (nor diverted to) STCG — and property gains book at
        rules.cg.property_rate_by_regime (FY 2025-26: 12.5% in both
        regimes; the 20%-with-indexation election is disclosed as an
        advisory in calculate_tax_advanced, never fabricated here).
        """
        tax, inc = 0.0, 0.0
        cg_rules = rules.cg
        ltcg_112a_total = 0.0
        for cg in cg_data:
            a = float(cg.get("amount", 0) or 0)
            inc += a
            t = cg.get("type", "")
            if t == "equity_ltcg":
                ltcg_112a_total += a
            elif t == "equity_stcg":
                # Budget 2024: STCG on equity shares increased to 20% —
                # taxed in FULL; the 112A exemption is LTCG-only.
                tax += a * cg_rules.stcg_111a_rate
            elif t == "property_cg":
                tax += a * cg_rules.property_rate_by_regime[regime]
        # Budget 2024: LTCG on equity shares/equity mutual funds 12.5% on
        # the aggregate above the ₹1.25L ANNUAL exemption (deducted ONCE).
        tax += max(0.0, ltcg_112a_total - cg_rules.ltcg_112a_exemption) * cg_rules.ltcg_112a_rate
        return tax, inc

    def _calc_80gg(self, ded_80gg, adj_total, hra_received, rules) -> float:
        # Step B: the guard switches from the computed Rule 2A exemption to
        # the HRA RECEIVED leg — receiving any HRA disqualifies 80GG even
        # when the exemption computes to 0 (e.g. rent below 10% of salary).
        if hra_received > 0 or ded_80gg <= 0:
            return 0.0
        caps = rules.deduction_caps
        # Least of: ₹5,000/month (₹60,000/yr), 25% of total income, rent paid minus 10% of total income
        return max(0.0, min(caps.sec_80gg_annual_max, caps.sec_80gg_income_pct * adj_total, ded_80gg - caps.sec_80gg_rent_excess_pct * adj_total))

    def _calc_80g(self, amount: float, category: Optional[str], gross: float,
                  cg_data: list) -> Tuple[float, str]:
        """Section 80G deduction for one donation amount + category (Step D).

        Ruling R-g (docs/sprint2-design.md): categories 1/2 book
        rate x amount; categories 3/4 count the donation only up to the
        qualifying limit — 10% of the ADJUSTED gross total income — and
        book rate x min(amount, limit). An absent/unknown category falls
        back to the default (category 4), which calculate_tax_advanced
        discloses via the default-category advisory; the cash-mode cap
        (₹2,000) is advisory-only this sprint (mode not collected).

        Returns (deduction, explanation reason) — reason "" when nothing
        is booked.
        """
        if amount <= 0:
            return 0.0, ""
        rates = self._80G_CATEGORY_RATES
        known = category in rates
        rate, applies_limit = rates.get(category, rates[self._80G_DEFAULT_CATEGORY])
        category_label = category if known else self._80G_DEFAULT_CATEGORY
        if not applies_limit:
            return (
                rate * amount,
                f"Donation of ₹{amount:,.0f} eligible at {rate * 100:.0f}% under "
                f"category {category_label} (no qualifying limit).",
            )
        adjusted_gti, limit = self._80g_qualifying_limit(gross, cg_data)
        eligible = min(amount, limit)
        reason = (
            f"Donation of ₹{amount:,.0f} eligible at {rate * 100:.0f}% under "
            f"category {category_label}; counted up to the qualifying limit of "
            f"₹{limit:,.0f} ({self._80G_QUALIFYING_LIMIT_PCT * 100:.0f}% of the "
            f"adjusted GTI ₹{adjusted_gti:,.0f})"
            + (" — capped." if amount > limit else ".")
        )
        return rate * eligible, reason

    @staticmethod
    def _80g_qualifying_limit(gross: float, cg_data: list) -> Tuple[float, float]:
        """R-g qualifying limit: 10% of the ADJUSTED gross total income.

        Adjusted GTI = GTI (before Ch VI-A) minus the special-rate capital
        gains — the aggregate Sec 112A equity LTCG, the Sec 112 property
        LTCG and the Sec 111A equity STCG. The engine's `gross` EXCLUDES
        the special-rate CG entries (they join only the special-rate tax
        and taxable_income), so GTI before Ch VI-A is gross + every CG
        amount and the adjustment strips the special-rate entries back
        out; a non-special-rate CG type (none registered today) would be
        slab income and stay in the adjusted GTI.

        Returns (adjusted GTI, qualifying limit) — the limit floors at 0.
        """
        all_cg = 0.0
        special_rate_cg = 0.0
        for cg in cg_data:
            if not isinstance(cg, dict):
                continue
            entry_amount = float(cg.get("amount", 0) or 0)
            all_cg += entry_amount
            if cg.get("type") in ("equity_ltcg", "equity_stcg", "property_cg"):
                special_rate_cg += entry_amount
        gti_before_ch_via = gross + all_cg
        adjusted_gti = gti_before_ch_via - special_rate_cg
        return adjusted_gti, max(0.0, TaxEngine._80G_QUALIFYING_LIMIT_PCT * adjusted_gti)

    def _calc_hra(self, rules, salary, hra_received, rent_paid, is_metro) -> float:
        """Section 10(13A) exemption — Rule 2A least-of test (Step B).

        Least of: (a) actual HRA received; (b) rent paid minus 10% of
        salary; (c) salary x rules.hra.metro_pct (the statutory metros
        Delhi/Mumbai/Kolkata/Chennai) or rules.hra.non_metro_pct elsewhere.
        Zero when salary <= 0, rent_paid <= 0 or hra_received <= 0 (an HRA
        received leg of 0 also blocks 80GG via _calc_80gg's guard).

        is_metro None assumes non-metro; the assumption is disclosed by the
        caller via HRA_METRO_ASSUMPTION_OBSERVATION, never silent. Legacy
        compat: callers mapping the legacy "hra" key to BOTH hra_received
        and rent_paid reproduce the legacy formula
        min(0.4*salary, hra, hra - 0.1*salary) exactly.
        """
        if salary <= 0 or rent_paid <= 0 or hra_received <= 0:
            return 0.0
        pct = rules.hra.metro_pct if is_metro else rules.hra.non_metro_pct
        return max(0.0, min(hra_received, rent_paid - rules.hra.salary_pct * salary, salary * pct))

    def _slab_old(self, v, senior, vsr, rules) -> Tuple[float, List[Dict[str, Any]]]:
        exemption_by_age = rules.old_regime_exemption_by_age
        ex = exemption_by_age[80] if vsr else exemption_by_age[60] if senior else exemption_by_age[0]
        return self._slab_from_bands(v, rules.old_regime_slabs, ex)

    def _slab_new(self, v, rules) -> Tuple[float, List[Dict[str, Any]]]:
        # FY 2024-25 Budget updated slabs: the registry bands carry the nil
        # band as the leading 0% slice and the walk floor is 0.
        return self._slab_from_bands(v, rules.new_regime_slabs, 0)

    def _slab_from_bands(self, values, bands: Tuple[SlabBand, ...], floor) -> Tuple[float, List[Dict[str, Any]]]:
        """Unified slab walk (consolidates the legacy _slab_old/_slab_new
        loops) producing the IDENTICAL slabs_breakdown dicts, including the
        legacy "range" string formats.

        bands are (upper_bound, rate) slices: band i taxes the slice from
        the previous band's upper_bound (or `floor` for the first band) up
        to its own upper_bound at `rate`; upper_bound None is the top band.
        A leading 0%-rate band is the nil band (new regime, floor 0). When
        the list has none (old regime), the region [0, floor] — floor being
        the age-dependent basic exemption — is emitted as the nil band.

        Label formats preserved exactly for FY 2024-25: new regime
        "0 - 3L", "3L - 7L", ..., "Above 15L"; old regime "0 - 2.5L",
        "2.5L - 5L", "5L - 10L", "Above 10L". Legacy interpolates the
        exemption `ex` with f"{ex/100000:.1f}L" into exactly two edges —
        the FIRST positive band's lower edge and the nil band's upper edge
        — while every other bound (including a deeper band whose lower edge
        numerically equals a 500000 very-senior exemption, legacy-hardcoded
        "5L - 10L") uses the compact f"{v/100000:g}L" lakh form.
        """
        slabs: List[Dict[str, Any]] = []
        t = 0.0
        rem = values
        has_nil_band = bool(bands) and bands[0].rate == 0.0

        # Index of the first positive-rate band; its lower edge is the
        # exemption floor and keeps the one-decimal lakh formatting.
        first_positive = next(
            (i for i, band in enumerate(bands) if band.rate > 0.0), None
        )

        def fmt_bound(amount: float, exemption_edge: bool = False) -> str:
            if exemption_edge:
                return f"{amount / 100000:.1f}L"
            return f"{amount / 100000:g}L"

        # Lower edge of each slice: the previous band's upper bound, or the
        # floor for the first band.
        lower_edges: List[float] = []
        prev = floor
        for band in bands:
            lower_edges.append(prev)
            prev = float("inf") if band.upper_bound is None else band.upper_bound

        for index in range(len(bands) - 1, -1, -1):
            band = bands[index]
            lower = lower_edges[index]
            upper = band.upper_bound
            if band.rate == 0.0:
                # Nil band: always emitted (legacy behavior), "0 - X" label.
                # Its upper edge carries the exemption formatting when the
                # nil region is the exemption floor (old regime).
                slabs.append({
                    "range": f"0 - {fmt_bound(upper, exemption_edge=floor > 0)}",
                    "rate": "0%",
                    "income": rem,
                    "tax": 0.0,
                })
                rem = 0.0
                continue
            if rem > lower:
                tax = (rem - lower) * band.rate
                t += tax
                is_exemption_edge = index == first_positive and lower == floor
                if upper is None:
                    label = f"Above {fmt_bound(lower, is_exemption_edge)}"
                else:
                    label = f"{fmt_bound(lower, is_exemption_edge)} - {fmt_bound(upper)}"
                slabs.append({"range": label, "rate": f"{int(band.rate * 100)}%", "income": rem - lower, "tax": tax})
                rem = lower

        if not has_nil_band:
            # Old regime: the region below the exemption floor is untaxed.
            slabs.append({"range": f"0 - {fmt_bound(floor, exemption_edge=floor > 0)}", "rate": "0%", "income": rem, "tax": 0.0})

        return t, slabs

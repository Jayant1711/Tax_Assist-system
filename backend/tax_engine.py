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

        age       = int(data.get("age", 30) or 30)
        is_senior = age >= 60
        is_vsr    = age >= 80

        # Deductions & Caps (FY 2024-25, from the registry rules)
        caps = rules.deduction_caps
        sec_80d_self_limit = caps.sec_80d_self_senior if is_senior else caps.sec_80d_self
        sec_80d_parents_limit = caps.sec_80d_parents

        ded = {
            "80c":   min(float(data.get("80c", 0) or 0), caps.sec_80c),
            "80d":   min(float(data.get("80d", 0) or 0), sec_80d_self_limit),
            "80d_p": min(float(data.get("80d_parents", 0) or 0), sec_80d_parents_limit),
            "80e":   float(data.get("80e", 0) or 0), # No upper limit on interest
            "80g":   float(data.get("80g", 0) or 0),
            "hra":   float(data.get("hra", 0) or 0),
            "24b":   min(float(data.get("24b", 0) or 0), caps.sec_24b), # Max 2L for self-occupied
            "80eea": min(float(data.get("80eea", 0) or 0), caps.sec_80eea),
            "nps":   min(float(data.get("nps", 0) or 0), caps.sec_80ccd_1b), # 80CCD(1B) extra 50k
            "80tta": min(float(data.get("80tta", 0) or 0), caps.sec_80tta) if not is_senior else 0,
            "80ttb": min(float(data.get("80ttb", 0) or 0), caps.sec_80ttb) if is_senior else 0,
            "80gg":  float(data.get("80gg", 0) or 0),
            "80u":   float(data.get("80u_80dd", 0) or 0),
            "80ddb": float(data.get("80ddb", 0) or 0),
        }

        prof_tax = float(data.get("professional_tax", rules.professional_tax_default if salary > 0 else 0) or 0)

        old_res = self._calc_old(salary, business, agri, rental_gross, other_income, cg_data, ded, prof_tax, is_senior, is_vsr, rules)
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
        if ded["hra"] > 0.5 * (salary or 1):
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

    def _calc_old(self, salary, business, agri, rental, other, cg_data, ded, prof_tax, is_senior, is_vsr, rules) -> TaxResult:
        res = TaxResult()
        std_ded = rules.standard_deduction["old"] if salary > 0 else 0
        hra_ex  = self._calc_hra(salary, ded["hra"], rules)

        # Net rental income after 30% statutory deduction under Section 24(a)
        net_rental = round(rental * 0.7, 2) if rental > 0 else 0

        # C2: agricultural income is exempt under Section 10(1) and is
        # EXCLUDED from gross total income (the itemised "Exempt" entry in
        # income_details below must stay truthful). Partial integration is
        # flagged as an audit observation in calculate_tax_advanced.
        gross = salary + business + net_rental + other
        res.gross_total_income = round(gross, 2)

        # Calculate 80GG if applicable (rent paid without HRA)
        ded_80gg = self._calc_80gg(ded["80gg"], gross, hra_ex, rules)

        # Full Chapter VI-A + Section 24(b) deductions
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
            ded["80g"] +
            ded_80gg +
            ded["80tta"] +
            ded["80ttb"]
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
        if ded["80g"] > 0:
            res.explanations.append(Explanation("Section 80G", "Eligible charitable donations & relief funds.", "80G", ded["80g"]))
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
        tax, inc = 0.0, 0.0
        cg_rules = rules.cg
        for cg in cg_data:
            a = float(cg.get("amount", 0) or 0)
            inc += a
            t = cg.get("type", "")
            if t == "equity_ltcg":
                # Budget 2024: LTCG on equity shares/equity mutual funds increased from 10% to 12.5% (exemption raised to ₹1.25L)
                tax += max(0.0, a - cg_rules.ltcg_112a_exemption) * cg_rules.ltcg_112a_rate
            elif t == "equity_stcg":
                # Budget 2024: STCG on equity shares increased to 20%
                tax += a * cg_rules.stcg_111a_rate
            elif t == "property_cg":
                tax += a * cg_rules.property_rate_by_regime[regime]
        return tax, inc

    def _calc_80gg(self, ded_80gg, adj_total, hra_claimed, rules) -> float:
        if hra_claimed > 0 or ded_80gg <= 0:
            return 0.0
        caps = rules.deduction_caps
        # Least of: ₹5,000/month (₹60,000/yr), 25% of total income, rent paid minus 10% of total income
        return max(0.0, min(caps.sec_80gg_annual_max, caps.sec_80gg_income_pct * adj_total, ded_80gg - caps.sec_80gg_rent_excess_pct * adj_total))

    def _calc_hra(self, salary, hra_claimed, rules) -> float:
        if salary <= 0 or hra_claimed <= 0:
            return 0.0
        # Baseline non-metro: 40% of salary
        baseline = salary * rules.hra.non_metro_pct
        return max(0.0, min(baseline, hra_claimed, hra_claimed - rules.hra.salary_pct * salary))

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

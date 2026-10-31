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
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
try:
    import numpy as np
except ImportError:
    np = None
from ai_models import ANFIS

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

    def calculate_tax_advanced(self, data: Dict[str, Any]) -> Dict[str, Any]:
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

        # Deductions & Caps (FY 2024-25)
        sec_80d_self_limit = 50000 if is_senior else 25000
        sec_80d_parents_limit = 50000

        ded = {
            "80c":   min(float(data.get("80c", 0) or 0), 150000),
            "80d":   min(float(data.get("80d", 0) or 0), sec_80d_self_limit),
            "80d_p": min(float(data.get("80d_parents", 0) or 0), sec_80d_parents_limit),
            "80e":   float(data.get("80e", 0) or 0), # No upper limit on interest
            "80g":   float(data.get("80g", 0) or 0),
            "hra":   float(data.get("hra", 0) or 0),
            "24b":   min(float(data.get("24b", 0) or 0), 200000), # Max 2L for self-occupied
            "80eea": min(float(data.get("80eea", 0) or 0), 150000),
            "nps":   min(float(data.get("nps", 0) or 0), 50000), # 80CCD(1B) extra 50k
            "80tta": min(float(data.get("80tta", 0) or 0), 10000) if not is_senior else 0,
            "80ttb": min(float(data.get("80ttb", 0) or 0), 50000) if is_senior else 0,
            "80gg":  float(data.get("80gg", 0) or 0),
            "80u":   float(data.get("80u_80dd", 0) or 0),
            "80ddb": float(data.get("80ddb", 0) or 0),
        }

        prof_tax = float(data.get("professional_tax", 2500 if salary > 0 else 0) or 0)

        old_res = self._calc_old(salary, business, agri, rental_gross, other_income, cg_data, ded, prof_tax, is_senior, is_vsr)
        new_res = self._calc_new(salary, business, agri, rental_gross, other_income, cg_data, is_senior)

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
        if agri > 0 and non_agri_income > 250000:
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
            "old_regime": old_res,
            "new_regime": new_res,
            "recommendation": rec,
            "savings": round(savings, 2),
            "efficiency_score": round(eff_score, 1),
        }

    def _calc_old(self, salary, business, agri, rental, other, cg_data, ded, prof_tax, is_senior, is_vsr) -> TaxResult:
        res = TaxResult()
        std_ded = 50000 if salary > 0 else 0
        hra_ex  = self._calc_hra(salary, ded["hra"])

        # Net rental income after 30% statutory deduction under Section 24(a)
        net_rental = round(rental * 0.7, 2) if rental > 0 else 0

        # C2: agricultural income is exempt under Section 10(1) and is
        # EXCLUDED from gross total income (the itemised "Exempt" entry in
        # income_details below must stay truthful). Partial integration is
        # flagged as an audit observation in calculate_tax_advanced.
        gross = salary + business + net_rental + other
        res.gross_total_income = round(gross, 2)

        # Calculate 80GG if applicable (rent paid without HRA)
        ded_80gg = self._calc_80gg(ded["80gg"], gross, hra_ex)

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
        cg_tax, cg_inc = self._calc_cg(cg_data, regime="old")

        tax_norm, slabs = self._slab_old(taxable, is_senior, is_vsr)
        res.slabs_breakdown = slabs

        # Section 87A rebate (Up to 12,500 if taxable income <= 5L)
        rebate = min(tax_norm, 12500) if taxable <= 500000 else 0
        tax_norm = max(0.0, tax_norm - rebate)

        surcharge = self._apply_marginal_relief(tax_norm, cg_tax, taxable + cg_inc, "old")
        total_tax = (tax_norm + cg_tax + surcharge) * 1.04

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

    def _calc_new(self, salary, business, agri, rental, other, cg_data, is_senior) -> TaxResult:
        res = TaxResult()
        # Budget 2024: Standard deduction increased to ₹75,000 for New Tax Regime
        std_ded = 75000 if salary > 0 else 0
        cg_tax, cg_inc = self._calc_cg(cg_data, regime="new")

        net_rental = round(rental * 0.7, 2) if rental > 0 else 0
        gross = salary + business + net_rental + other
        res.gross_total_income = round(gross, 2)

        taxable = max(0.0, gross - std_ded)
        res.total_deductions = round(std_ded, 2)

        tax, slabs = self._slab_new(taxable)
        res.slabs_breakdown = slabs

        # Section 87A Rebate in New Regime:
        # Full rebate if taxable income <= 7,00,000 (Tax = 0)
        # Marginal relief if taxable income is slightly above 7,00,000:
        # The tax payable cannot exceed (Taxable Income - 7,00,000)
        if taxable <= 700000:
            tax = 0.0
        elif taxable <= 727777:
            # Marginal relief under Sec 87A: tax is capped at the excess income over 7L
            excess_over_7l = taxable - 700000
            tax = min(tax, excess_over_7l)

        surcharge = self._apply_marginal_relief(tax, cg_tax, taxable + cg_inc, "new")
        res.total_tax = round((tax + cg_tax + surcharge) * 1.04, 2)
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

    def _apply_marginal_relief(self, tax, cg_tax, income, regime) -> float:
        total_tax_base = tax + cg_tax
        if income <= 5000000:
            return 0.0

        rate = 0.10 if income <= 10000000 else 0.15 if income <= 20000000 else 0.25 if (regime == "new" or income <= 50000000) else 0.37
        surcharge = total_tax_base * rate

        # Marginal Relief Check at 50 Lakhs surcharge threshold
        return min(surcharge, max(0.0, income - 5000000))

    def _calc_cg(self, cg_data: list, regime: str):
        tax, inc = 0.0, 0.0
        for cg in cg_data:
            a = float(cg.get("amount", 0) or 0)
            inc += a
            t = cg.get("type", "")
            if t == "equity_ltcg":
                # Budget 2024: LTCG on equity shares/equity mutual funds increased from 10% to 12.5% (exemption raised to ₹1.25L)
                tax += max(0.0, a - 125000) * 0.125
            elif t == "equity_stcg":
                # Budget 2024: STCG on equity shares increased to 20%
                tax += a * 0.20
            elif t == "property_cg":
                tax += a * (0.125 if regime == "new" else 0.20)
        return tax, inc

    def _calc_80gg(self, ded_80gg, adj_total, hra_claimed):
        if hra_claimed > 0 or ded_80gg <= 0:
            return 0.0
        # Least of: ₹5,000/month (₹60,000/yr), 25% of total income, rent paid minus 10% of total income
        return max(0.0, min(60000.0, 0.25 * adj_total, ded_80gg - 0.1 * adj_total))

    def _calc_hra(self, salary, hra_claimed):
        if salary <= 0 or hra_claimed <= 0:
            return 0.0
        # Baseline non-metro: 40% of salary
        baseline = salary * 0.4
        return max(0.0, min(baseline, hra_claimed, hra_claimed - 0.1 * salary))

    def _slab_old(self, v, senior, vsr):
        slabs = []
        t = 0.0
        rem = v
        ex = 500000 if vsr else 300000 if senior else 250000

        if rem > 1000000:
            tax = (rem - 1000000) * 0.3
            t += tax
            slabs.append({"range": "Above 10L", "rate": "30%", "income": rem - 1000000, "tax": tax})
            rem = 1000000
        if rem > 500000:
            tax = (rem - 500000) * 0.2
            t += tax
            slabs.append({"range": "5L - 10L", "rate": "20%", "income": rem - 500000, "tax": tax})
            rem = 500000
        if rem > ex:
            tax = (rem - ex) * 0.05
            t += tax
            slabs.append({"range": f"{ex/100000:.1f}L - 5L", "rate": "5%", "income": rem - ex, "tax": tax})
            rem = ex
        slabs.append({"range": f"0 - {ex/100000:.1f}L", "rate": "0%", "income": rem, "tax": 0.0})

        return t, slabs

    def _slab_new(self, v):
        slabs = []
        t = 0.0
        rem = v
        # FY 2024-25 Budget updated slabs:
        levels = [
            (1500000, 0.30, "Above 15L"),
            (1200000, 0.20, "12L - 15L"),
            (1000000, 0.15, "10L - 12L"),
            (700000,  0.10, "7L - 10L"),
            (300000,  0.05, "3L - 7L"),
        ]

        for limit, rate, label in levels:
            if rem > limit:
                tax = (rem - limit) * rate
                t += tax
                slabs.append({"range": label, "rate": f"{int(rate*100)}%", "income": rem - limit, "tax": tax})
                rem = limit
        slabs.append({"range": "0 - 3L", "rate": "0%", "income": rem, "tax": 0.0})
        return t, slabs

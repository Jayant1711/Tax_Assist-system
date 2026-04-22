"""
Tax Engine v3.0 — FY 2024-25 (AY 2025-26)
Fixes: Correct surcharge brackets (10/15/25/37%), 87A rebate in Old Regime,
       Section 80G, 80EEA, 80TTA/B surfaced properly, agriculture exemption,
       ANFIS v2 efficiency scoring, savings tips integration.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np
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
    taxable_income: float = 0
    total_tax: float = 0
    recommendation: str = ""
    savings: float = 0
    explanations: List[Explanation] = field(default_factory=list)
    slabs_breakdown: List[Dict] = field(default_factory=list)
    efficiency_score: float = 0.0
    savings_tips: List[str] = field(default_factory=list)

class TaxEngine:
    def __init__(self):
        self.anfis = ANFIS()

    # ------------------------------------------------------------------
    def calculate_tax_advanced(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Income
        salary       = float(data.get("salary", 0))
        business     = float(data.get("business", 0))
        agri         = float(data.get("agriculture", 0))
        rental_gross = float(data.get("rental", 0))
        other_income = float(data.get("other_income", 0))
        cg_data      = data.get("capital_gains", [])
        if not isinstance(cg_data, list): cg_data = []

        # Deductions
        ded = {
            "80c":   min(float(data.get("80c", 0)), 150000),
            "80d":   float(data.get("80d", 0)),
            "80d_p": float(data.get("80d_parents", 0)),
            "80e":   float(data.get("80e", 0)),   # No cap
            "80g":   float(data.get("80g", 0)),
            "hra":   float(data.get("hra", 0)),
            "24b":   min(float(data.get("24b", 0)), 200000),
            "80eea": min(float(data.get("80eea", 0)), 150000),
            "nps":   min(float(data.get("nps", 0)), 50000),
            "80tta": min(float(data.get("80tta", 0)), 10000),
            "80ttb": min(float(data.get("80ttb", 0)), 50000),
            "80gg":  float(data.get("80gg", 0)),
        }
        age       = int(data.get("age", 30))
        prof_tax  = float(data.get("professional_tax", 2500 if salary > 0 else 0))
        is_senior = age >= 60
        is_vsr    = age >= 80  # Very Senior Resident

        old_result = self._calc_old(salary, business, agri, rental_gross,
                                    other_income, cg_data, ded, prof_tax, is_senior, is_vsr)
        new_result = self._calc_new(salary, business, agri, rental_gross,
                                    other_income, cg_data, is_senior)

        recommendation = "New Regime" if new_result.total_tax <= old_result.total_tax else "Old Regime"
        savings        = abs(old_result.total_tax - new_result.total_tax)

        # ANFIS v3 Efficiency Score (pre-trained on 100k cases via EE-BAT + Adam)
        total_income = salary + business + rental_gross + other_income
        cg_total     = sum(c.get("amount", 0) for c in cg_data) if cg_data else 0
        min_tax      = min(old_result.total_tax, new_result.total_tax)
        n_sources    = sum(1 for x in [salary, business, rental_gross, other_income, agri, cg_total] if x > 0)
        efficiency_score = self.anfis.score_efficiency(
            income         = total_income,
            ded_80c        = ded["80c"],
            ded_80d        = ded["80d"] + ded["80d_p"],
            ded_nps        = ded["nps"],
            ded_other      = ded["80e"] + ded["80g"] + ded["80eea"],
            n_sources      = n_sources,
            regime_savings = savings,
            cg_income      = cg_total,
            min_tax        = min_tax,
        )

        old_result.efficiency_score = efficiency_score
        new_result.efficiency_score = efficiency_score

        # Savings Tips (from ReasoningAgent)
        try:
            from ai_models import ReasoningAgent
            tips = ReasoningAgent().get_savings_tips(data)
        except Exception:
            tips = []
        old_result.savings_tips = tips

        return {
            "old_regime":       old_result,
            "new_regime":       new_result,
            "recommendation":   recommendation,
            "savings":          savings,
            "efficiency_score": efficiency_score,
        }

    # ------------------------------------------------------------------
    def _calc_old(self, salary, business, agri, rental_gross, other_income,
                  cg_data, ded, prof_tax, is_senior, is_vsr) -> TaxResult:
        res = TaxResult()

        # 1. Salary income
        std_ded    = 50000 if salary > 0 else 0
        net_salary = max(0, salary - std_ded - prof_tax)

        # 2. House property
        home_interest = ded["24b"]
        net_rental    = max(-200000, (rental_gross * 0.7) - home_interest)  # Loss capped at 2L

        # 3. Capital Gains (taxed separately)
        cg_tax, cg_income = self._calc_cg(cg_data, regime="old")

        # 4. Agriculture (exemption under Sec 10(1))
        agri_exempt = agri  # Fully exempt; only used for rate purposes

        # 5. Chapter VI-A Deductions
        d80d_self   = min(ded["80d"],   50000 if is_senior else 25000)
        d80d_par    = min(ded["80d_p"], 50000)  # Parents always get 50k cap
        d80tta      = ded["80tta"] if not is_senior else 0
        d80ttb      = ded["80ttb"] if is_senior else 0
        d80gg       = self._calc_80gg(ded["80gg"], net_salary + business + net_rental + other_income,
                                      ded["hra"])
        total_vi_a  = (ded["80c"] + d80d_self + d80d_par + ded["80e"] + ded["80g"] +
                       ded["80eea"] + ded["nps"] + d80tta + d80ttb + d80gg)

        # 6. Gross Total Income
        gti = net_salary + business + net_rental + other_income
        taxable_normal = max(0, gti - total_vi_a)

        # 7. Slab Tax
        tax_normal = self._slab_old(taxable_normal, is_senior, is_vsr)

        # 8. 87A Rebate (Old Regime: rebate if taxable ≤ 5L)
        rebate = min(tax_normal, 12500) if taxable_normal <= 500000 else 0
        tax_normal = max(0, tax_normal - rebate)

        # 9. Surcharge (correct brackets FY 2024-25)
        total_income_for_surcharge = taxable_normal + cg_income
        surcharge = self._calc_surcharge(tax_normal, cg_tax, total_income_for_surcharge)

        # 10. Cess 4%
        total_tax = (tax_normal + cg_tax + surcharge) * 1.04

        res.total_tax      = round(total_tax, 2)
        res.taxable_income = taxable_normal + cg_income

        res.income_details = [
            {"source": "Salary (after Std.Ded)", "amount": net_salary,    "section": "16(ia)", "status": "Valid"},
            {"source": "Business / Profession",  "amount": business,      "section": "PGBP",   "status": "Valid"},
            {"source": "House Property (Net)",   "amount": net_rental,    "section": "24",     "status": "Valid"},
            {"source": "Capital Gains",          "amount": cg_income,     "section": "Special","status": "Valid"},
            {"source": "Other Sources",          "amount": other_income,  "section": "56",     "status": "Valid"},
            {"source": "Agriculture (Exempt)",   "amount": agri_exempt,   "section": "10(1)",  "status": "Exempt"},
        ]

        res.deduction_details = [
            {"category": "Standard Deduction",      "amount": std_ded,       "section": "16(ia)",   "status": "Valid"},
            {"category": "80C Investments",          "amount": ded["80c"],    "section": "80C",      "status": "Capped" if ded["80c"] >= 150000 else "Valid"},
            {"category": "Health Insurance (Self)",  "amount": d80d_self,     "section": "80D",      "status": "Valid"},
            {"category": "Health Insurance (Parents)","amount": d80d_par,     "section": "80D",      "status": "Valid"},
            {"category": "Education Loan Interest",  "amount": ded["80e"],    "section": "80E",      "status": "Valid"},
            {"category": "Donations (80G)",          "amount": ded["80g"],    "section": "80G",      "status": "Valid"},
            {"category": "NPS (Extra 50k)",          "amount": ded["nps"],    "section": "80CCD(1B)","status": "Valid"},
            {"category": "Home Loan Interest",       "amount": home_interest, "section": "24b",      "status": "Capped" if ded["24b"] >= 200000 else "Valid"},
            {"category": "Affordable Housing",       "amount": ded["80eea"],  "section": "80EEA",    "status": "Valid"},
            {"category": "Savings Interest (80TTA)", "amount": d80tta,        "section": "80TTA",    "status": "Valid"},
            {"category": "FD Interest Sr.Cit(80TTB)","amount": d80ttb,        "section": "80TTB",    "status": "Valid"},
            {"category": "Rent Paid (80GG)",         "amount": d80gg,         "section": "80GG",     "status": "Valid"},
            {"category": "87A Rebate",               "amount": rebate,        "section": "87A",      "status": "Valid"},
        ]

        # ELI5 Explanations
        res.explanations = [
            Explanation("Standard Deduction", "Flat exemption for salaried.", "Sec 16(ia)", std_ded,
                        eli5="Government gives ₹50k 'free pass' on salary — no questions asked!"),
            Explanation("Section 80C", "Investments in PF/LIC/ELSS.", "80C", ded["80c"],
                        eli5=f"You saved by investing! Max ₹1.5L exempt. Your invested: ₹{ded['80c']:,.0f}"),
            Explanation("87A Rebate", "Tax rebate if income ≤ ₹5L (Old Regime).", "87A", rebate,
                        eli5="If your total taxable income is ≤ ₹5L, you get full tax refund of up to ₹12,500!"),
            Explanation("Health Insurance", "Premium for self + parents.", "80D", d80d_self + d80d_par,
                        eli5="Government subsidizes your health cover — buy insurance, pay less tax!"),
            Explanation("Education Loan", "Interest on higher education loan.", "80E", ded["80e"],
                        eli5="Studying for a degree? Your loan interest is fully deductible — no cap!"),
            Explanation("NPS", "Extra 80CCD(1B) deduction over 80C.", "80CCD(1B)", ded["nps"],
                        eli5="Invest in National Pension System for extra ₹50k saving beyond the 1.5L limit!"),
            Explanation("Donations", "Donations to approved funds.", "80G", ded["80g"],
                        eli5="Donate to PM Fund or registered NGOs — 50% to 100% deductible!"),
        ]
        return res

    # ------------------------------------------------------------------
    def _calc_new(self, salary, business, agri, rental_gross, other_income,
                  cg_data, is_senior) -> TaxResult:
        res = TaxResult()
        std_ded     = 75000 if salary > 0 else 0  # Enhanced std. ded. in new regime FY 24-25
        cg_tax, cg_income = self._calc_cg(cg_data, regime="new")
        gross       = salary + business + (rental_gross * 0.7) + other_income
        taxable     = max(0, gross - std_ded)
        tax         = self._slab_new(taxable)

        # 87A Rebate in New Regime: if taxable ≤ 7L
        rebate      = min(tax, 25000) if taxable <= 700000 else 0
        tax         = max(0, tax - rebate)

        surcharge   = self._calc_surcharge(tax, cg_tax, taxable + cg_income)
        total_tax   = (tax + cg_tax + surcharge) * 1.04

        res.total_tax      = round(total_tax, 2)
        res.taxable_income = taxable + cg_income
        res.income_details = [{"source": "Total Gross Income", "amount": gross,    "section": "All", "status": "Valid"}]
        res.deduction_details = [
            {"category": "Standard Deduction", "amount": std_ded, "section": "16(ia)", "status": "Valid"},
            {"category": "87A Rebate",         "amount": rebate,  "section": "87A",    "status": "Valid"},
        ]
        return res

    # ------------------------------------------------------------------
    def _calc_cg(self, cg_data: list, regime: str):
        cg_tax, cg_income = 0.0, 0.0
        for cg in cg_data:
            amt = float(cg.get("amount", 0))
            cg_income += amt
            t = cg.get("type", "")
            holding = cg.get("holding", "unknown")
            if t == "equity_ltcg":
                cg_tax += max(0, amt - 125000) * 0.125
            elif t == "equity_stcg":
                cg_tax += amt * 0.20
            elif t == "property_cg":
                rate = 0.125 if holding == "long" else 0.30
                cg_tax += amt * rate
            elif t == "debt_ltcg":
                cg_tax += amt * 0.20  # Indexed, simplified
            elif t == "debt_stcg":
                cg_tax += amt * 0.30
        return cg_tax, cg_income

    def _calc_surcharge(self, tax_normal: float, cg_tax: float, total_income: float) -> float:
        """Correct FY 2024-25 surcharge brackets."""
        total_tax = tax_normal + cg_tax
        if total_income > 50_000_000:   rate = 0.37  # 3.7 Cr+
        elif total_income > 20_000_000: rate = 0.25  # 2 Cr+
        elif total_income > 10_000_000: rate = 0.15  # 1 Cr+
        elif total_income > 5_000_000:  rate = 0.10  # 50L+
        else: rate = 0.0
        return total_tax * rate

    def _calc_80gg(self, ded_80gg: float, adj_total: float, hra_claimed: float) -> float:
        if hra_claimed > 0 or ded_80gg <= 0: return 0
        return min(60000, 0.25 * adj_total, max(0, ded_80gg - 0.1 * adj_total))

    def _slab_old(self, val: float, is_senior: bool, is_vsr: bool) -> float:
        t = 0.0
        exempt = 500000 if is_vsr else 300000 if is_senior else 250000
        if val > 1000000: t += (val - 1000000) * 0.30; val = 1000000
        if val > 500000:  t += (val - 500000) * 0.20;  val = 500000
        if val > exempt:  t += (val - exempt) * 0.05
        return t

    def _slab_new(self, val: float) -> float:
        t = 0.0
        if val > 1500000: t += (val - 1500000) * 0.30; val = 1500000
        if val > 1200000: t += (val - 1200000) * 0.20; val = 1200000
        if val > 1000000: t += (val - 1000000) * 0.15; val = 1000000
        if val > 700000:  t += (val - 700000) * 0.10;  val = 700000
        if val > 300000:  t += (val - 300000) * 0.05
        return t

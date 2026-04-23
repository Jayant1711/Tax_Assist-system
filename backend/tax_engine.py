"""
Tax Engine v4.0 — Professional Grade Auditor
FY 2024-25 (AY 2025-26) | Indian Tax Laws
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
    gross_total_income: float = 0
    total_deductions: float = 0
    taxable_income: float = 0
    total_tax: float = 0
    recommendation: str = ""
    savings: float = 0
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
        salary       = float(data.get("salary", 0))
        business     = float(data.get("business", 0))
        agri         = float(data.get("agriculture", 0))
        rental_gross = float(data.get("rental", 0))
        other_income = float(data.get("other_income", 0))
        cg_data      = data.get("capital_gains", [])
        if not isinstance(cg_data, list): cg_data = []

        # Deductions & Caps (FY 24-25)
        ded = {
            "80c":   min(float(data.get("80c", 0)), 150000),
            "80d":   float(data.get("80d", 0)),
            "80d_p": float(data.get("80d_parents", 0)),
            "80e":   float(data.get("80e", 0)),
            "80g":   float(data.get("80g", 0)),
            "hra":   float(data.get("hra", 0)),
            "24b":   min(float(data.get("24b", 0)), 200000),
            "80eea": min(float(data.get("80eea", 0)), 150000),
            "nps":   min(float(data.get("nps", 0)), 50000),
            "80tta": min(float(data.get("80tta", 0)), 10000),
            "80ttb": min(float(data.get("80ttb", 0)), 50000),
            "80gg":  float(data.get("80gg", 0)),
            "80u":   float(data.get("80u_80dd", 0)),
            "80ddb": float(data.get("80ddb", 0)),
        }
        age       = int(data.get("age", 30))
        prof_tax  = float(data.get("professional_tax", 2500 if salary > 0 else 0))
        is_senior = age >= 60
        is_vsr    = age >= 80

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
        old_res.recommendation = rec
        new_res.recommendation = rec
        old_res.savings = savings
        new_res.savings = savings
        
        # Risk Analysis
        total_inc = salary + business + rental_gross + other_income
        cg_total  = sum(c.get("amount", 0) for c in cg_data)
        risk = "Low"
        observations = []
        if ded["hra"] > 0.5 * salary:
            risk = "Medium"; observations.append("HRA Claim vs Salary ratio is unusually high (>50%).")
        if ded["80g"] > 0.1 * total_inc:
            risk = "High"; observations.append("Significant 80G donations detected. Ensure 100% deduction receipts are available.")
        if cg_total > 1000000:
            observations.append("Large Capital Gains detected. Verify holding periods for STCG/LTCG classification.")

        old_res.risk_level = risk; old_res.audit_observations = observations
        new_res.risk_level = risk; new_res.audit_observations = observations

        try:
            from ai_models import ReasoningAgent
            tips = ReasoningAgent().get_savings_tips(data)
            old_res.savings_tips = tips; new_res.savings_tips = tips
        except: pass

        return {
            "old_regime": old_res, "new_regime": new_res,
            "recommendation": rec, 
            "savings": round(savings, 2), 
            "efficiency_score": round(eff_score, 1)
        }

    def _calc_old(self, salary, business, agri, rental, other, cg_data, ded, prof_tax, is_senior, is_vsr) -> TaxResult:
        res = TaxResult()
        std_ded = 50000 if salary > 0 else 0
        hra_ex = self._calc_hra(salary, ded["hra"])
        
        gross = salary + business + rental + other + agri
        res.gross_total_income = round(gross, 2)
        
        total_ded = std_ded + hra_ex + ded["80c"] + ded["80d"] + ded["nps"] + ded["80g"] + prof_tax
        res.total_deductions = round(total_ded, 2)
        
        taxable = max(0, gross - total_ded)
        cg_tax, cg_inc = self._calc_cg(cg_data, regime="old")
        
        tax_norm, slabs = self._slab_old(taxable, is_senior, is_vsr)
        res.slabs_breakdown = slabs
        
        rebate = min(tax_norm, 12500) if taxable <= 500000 else 0
        tax_norm = max(0, tax_norm - rebate)
        
        surcharge = self._apply_marginal_relief(tax_norm, cg_tax, taxable + cg_inc, "old")
        total_tax = (tax_norm + cg_tax + surcharge) * 1.04
        
        res.total_tax = round(total_tax, 2)
        res.taxable_income = round(taxable + cg_inc, 2)
        
        # --- DYNAMIC ITEMIZATION ---
        res.income_details = []
        if salary > 0: res.income_details.append({"source": "Gross Salary", "amount": salary, "section": "17(1)", "status": "Reported"})
        if hra_ex > 0: res.income_details.append({"source": "HRA Exemption", "amount": hra_ex, "section": "10(13A)", "status": "Exempt"})
        if business > 0: res.income_details.append({"source": "Business Income", "amount": business, "section": "PGBP", "status": "Taxable"})
        if rental > 0: res.income_details.append({"source": "Rental Income", "amount": rental, "section": "24", "status": "Taxable"})
        
        res.explanations = []
        if ded["80c"] > 0: res.explanations.append(Explanation("Section 80C", "PF/LIC/ELSS aggregation.", "80C", min(150000, ded["80c"])))
        if ded["80d"] > 0: res.explanations.append(Explanation("Section 80D", "Health Insurance.", "80D", ded["80d"]))
        if ded["nps"] > 0: res.explanations.append(Explanation("Section 80CCD", "NPS Contribution.", "80CCD", ded["nps"]))
        
        return res

    def _calc_new(self, salary, business, agri, rental, other, cg_data, is_senior) -> TaxResult:
        res = TaxResult()
        std_ded = 75000 if salary > 0 else 0
        cg_tax, cg_inc = self._calc_cg(cg_data, regime="new")
        
        gross = salary + business + (rental * 0.7) + other
        res.gross_total_income = round(gross, 2)
        
        taxable = max(0, gross - std_ded)
        res.total_deductions = round(std_ded, 2)
        
        tax, slabs = self._slab_new(taxable)
        res.slabs_breakdown = slabs
        
        rebate = min(tax, 25000) if taxable <= 700000 else 0
        tax = max(0, tax - rebate)
        
        surcharge = self._apply_marginal_relief(tax, cg_tax, taxable + cg_inc, "new")
        res.total_tax = round((tax + cg_tax + surcharge) * 1.04, 2)
        res.taxable_income = round(taxable + cg_inc, 2)
        
        # --- NEW REGIME BREAKDOWN ---
        res.income_details = []
        if salary > 0: 
            res.income_details.append({"source": "Gross Salary", "amount": salary, "section": "17(1)", "status": "Reported"})
            res.income_details.append({"source": "Standard Deduction", "amount": std_ded, "section": "16(ia)", "status": "Deducted"})
        if business > 0: res.income_details.append({"source": "Business Income", "amount": business, "section": "PGBP", "status": "Taxable"})
        
        res.explanations = [Explanation("Section 115BAC", "Simplified New Regime default.", "115BAC", 0, eli5="Lower rates but no exemptions.")]
        return res

    def _apply_marginal_relief(self, tax, cg_tax, income, regime) -> float:
        total_tax_base = tax + cg_tax
        if income <= 5000000: return 0
        
        rate = 0.10 if income <= 10000000 else 0.15 if income <= 20000000 else 0.25 if (regime=="new" or income <= 50000000) else 0.37
        surcharge = total_tax_base * rate
        
        # Marginal Relief Check
        return min(surcharge, max(0, income - 5000000))

    def _calc_cg(self, cg_data: list, regime: str):
        tax, inc = 0.0, 0.0
        for cg in cg_data:
            a = float(cg.get("amount", 0)); inc += a
            t = cg.get("type", "")
            if t == "equity_ltcg": tax += max(0, a - 125000) * 0.125
            elif t == "equity_stcg": tax += a * 0.20
            elif t == "property_cg": tax += a * (0.125 if regime=="new" else 0.20)
        return tax, inc

    def _calc_80gg(self, ded_80gg, adj_total, hra_claimed):
        if hra_claimed > 0 or ded_80gg <= 0: return 0
        return min(60000, 0.25 * adj_total, max(0, ded_80gg - 0.1 * adj_total))

    def _calc_hra(self, salary, hra_claimed):
        if salary <= 0 or hra_claimed <= 0: return 0
        # Industrial standard: 40% of salary as baseline for non-metro
        baseline = salary * 0.4
        return min(baseline, hra_claimed, max(0, hra_claimed - 0.1 * salary))

    def _slab_old(self, v, senior, vsr):
        slabs = []
        t = 0.0; rem = v; ex = 500000 if vsr else 300000 if senior else 250000
        
        if rem > 1000000:
            tax = (rem-1000000)*0.3; t += tax
            slabs.append({"range": "Above 10L", "rate": "30%", "income": rem-1000000, "tax": tax})
            rem = 1000000
        if rem > 500000:
            tax = (rem-500000)*0.2; t += tax
            slabs.append({"range": "5L - 10L", "rate": "20%", "income": rem-500000, "tax": tax})
            rem = 500000
        if rem > ex:
            tax = (rem-ex)*0.05; t += tax
            slabs.append({"range": f"{ex/100000}L - 5L", "rate": "5%", "income": rem-ex, "tax": tax})
            rem = ex
        slabs.append({"range": f"0 - {ex/100000}L", "rate": "0%", "income": rem, "tax": 0})
        
        return t, slabs

    def _slab_new(self, v):
        slabs = []
        t = 0.0; rem = v
        levels = [(1500000, 0.3, "Above 15L"), (1200000, 0.2, "12L - 15L"), 
                  (1000000, 0.15, "10L - 12L"), (700000, 0.1, "7L - 10L"), 
                  (300000, 0.05, "3L - 7L")]
        
        for limit, rate, label in levels:
            if rem > limit:
                tax = (rem-limit)*rate; t += tax
                slabs.append({"range": label, "rate": f"{int(rate*100)}%", "income": rem-limit, "tax": tax})
                rem = limit
        slabs.append({"range": "0 - 3L", "rate": "0%", "income": rem, "tax": 0})
        return t, slabs

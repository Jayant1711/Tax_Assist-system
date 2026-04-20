from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class Explanation:
    particular: str
    reason: str
    section: str
    amount: float

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

class TaxEngine:
    """
    Advanced Tax Engine for Indian Income Tax Laws (FY 2024-25)
    Includes July 2024 Budget Updates
    """
    
    def calculate_rental_income(self, gross_rent: float) -> Dict:
        # Section 24(a): Standard deduction of 30%
        std_deduction = gross_rent * 0.30
        taxable_rent = gross_rent - std_deduction
        return {
            "source": "Rental Income",
            "gross": gross_rent,
            "deduction": std_deduction,
            "taxable": taxable_rent,
            "explanation": Explanation(
                particular="Rental Income",
                reason="Standard deduction of 30% allowed on gross rent received.",
                section="Section 24(a)",
                amount=std_deduction
            )
        }

    def calculate_capital_gains(self, gains: List[Dict]) -> Dict:
        """
        gains: list of {"type": "equity_ltcg", "amount": float, "holding_period": int}
        Rates (Post July 23, 2024):
        Equity LTCG: 12.5% (Exemption up to 1.25L)
        Equity STCG: 20%
        Debt/Other: Slab rates
        """
        total_cg_tax = 0
        details = []
        explanations = []
        
        equity_ltcg_sum = 0
        
        for g in gains:
            g_type = g.get("type", "").lower()
            amount = g.get("amount", 0)
            
            if "equity_ltcg" in g_type:
                equity_ltcg_sum += amount
            elif "equity_stcg" in g_type:
                tax = amount * 0.20
                total_cg_tax += tax
                details.append({"source": "Equity STCG", "tax": tax, "rate": "20%"})
                explanations.append(Explanation("Equity STCG", "Short-term capital gains on listed equity taxed at 20%.", "Section 111A", tax))
            elif "other" in g_type or "debt" in g_type:
                # Debt/Gold CG added to total income (slab)
                pass 
                
        # Handle Equity LTCG with exemption
        if equity_ltcg_sum > 125000:
            taxable_ltcg = equity_ltcg_sum - 125000
            tax = taxable_ltcg * 0.125
            total_cg_tax += tax
            details.append({"source": "Equity LTCG", "tax": tax, "rate": "12.5%"})
            explanations.append(Explanation("Equity LTCG", "Long-term capital gains on listed equity taxed at 12.5% after 1.25L exemption.", "Section 112A", tax))
        
        return {"total_tax": total_cg_tax, "details": details, "explanations": explanations}

    def calculate_tax_advanced(self, data: Dict[str, Any]) -> Dict[str, TaxResult]:
        # Sources of Gain
        salary = data.get("salary", 0)
        business = data.get("business", 0)
        agri = data.get("agriculture", 0)
        rental_gross = data.get("rental", 0)
        other_income = data.get("other_income", 0)
        cg_data = data.get("capital_gains", [])
        
        # Deductions
        ded_80c = data.get("80c", 0)
        ded_80d = data.get("80d", 0) # Self/Family
        ded_80d_parents = data.get("80d_parents", 0)
        ded_80e = data.get("80e", 0)
        ded_80g = data.get("80g", 0)
        hra_claimed = data.get("hra", 0)
        
        # 1. Old Regime Calculation
        old_result = self._calc_old(salary, business, agri, rental_gross, other_income, cg_data, 
                                   ded_80c, ded_80d, ded_80d_parents, ded_80e, ded_80g, hra_claimed)
        
        # 2. New Regime Calculation
        new_result = self._calc_new(salary, business, agri, rental_gross, other_income, cg_data)
        
        recommendation = "New Regime" if new_result.total_tax < old_result.total_tax else "Old Regime"
        savings = abs(old_result.total_tax - new_result.total_tax)
        
        return {
            "old_regime": old_result,
            "new_regime": new_result,
            "recommendation": recommendation,
            "savings": savings
        }

    def _calc_old(self, salary, business, agri, rental_gross, other_income, cg_data, 
                  ded_80c, ded_80d, ded_80d_parents, ded_80e, ded_80g, hra_claimed) -> TaxResult:
        res = TaxResult()
        
        # Income Breakdown
        rental = self.calculate_rental_income(rental_gross)
        gross_total = salary + business + rental['taxable'] + other_income
        
        res.income_details = [
            {"source": "Salary", "amount": salary, "tax_pct": "Slab"},
            {"source": "Business", "amount": business, "tax_pct": "Slab"},
            {"source": "Rental (Net)", "amount": rental['taxable'], "tax_pct": "Slab"},
            {"source": "Other", "amount": other_income, "tax_pct": "Slab"}
        ]
        if agri > 0:
            res.income_details.append({"source": "Agriculture", "amount": agri, "tax_pct": "Exempt*"})
            res.explanations.append(Explanation("Agriculture Income", "Agri income is exempt but used for rate determination via Partial Integration.", "Section 10(1)", 0))

        # Deductions
        std_ded = 50000 if salary > 0 else 0
        total_80c = min(ded_80c, 150000)
        total_80d = min(ded_80d, 25000) + min(ded_80d_parents, 50000)
        
        res.deduction_details = [
            {"category": "Standard Deduction", "amount": std_ded, "section": "Sec 16(ia)"},
            {"category": "Section 80C", "amount": total_80c, "section": "80C"},
            {"category": "Health Insurance (80D)", "amount": total_80d, "section": "80D"},
            {"category": "Education Loan (80E)", "amount": ded_80e, "section": "80E"},
            {"category": "Donations (80G)", "amount": ded_80g, "section": "80G"}
        ]
        
        total_deductions = std_ded + total_80c + total_80d + ded_80e + ded_80g + hra_claimed
        taxable_slab_income = max(0, gross_total - total_deductions)
        
        # Slab Calculation with Partial Integration for Agri
        tax = self._slab_calc_old(taxable_slab_income, agri)
        
        # Capital Gains Tax
        cg_res = self.calculate_capital_gains(cg_data)
        tax += cg_res['total_tax']
        res.explanations.extend(cg_res['explanations'])
        
        # Rebate 87A
        rebate = 0
        if (taxable_slab_income + agri) <= 500000:
            rebate = min(tax, 12500)
            tax -= rebate
            
        cess = tax * 0.04
        res.total_tax = tax + cess
        res.taxable_income = taxable_slab_income
        
        return res

    def _calc_new(self, salary, business, agri, rental_gross, other_income, cg_data) -> TaxResult:
        res = TaxResult()
        
        rental = self.calculate_rental_income(rental_gross)
        gross_total = salary + business + rental['taxable'] + other_income
        
        # New Regime Standard Deduction (FY 24-25)
        std_ded = 75000 if salary > 0 else 0
        taxable_slab_income = max(0, gross_total - std_ded)
        
        # Slab Calculation
        tax = self._slab_calc_new(taxable_slab_income)
        
        # Capital Gains
        cg_res = self.calculate_capital_gains(cg_data)
        tax += cg_res['total_tax']
        
        # Rebate 87A New Regime: Taxable income <= 7,00,000
        if taxable_slab_income <= 700000:
            tax = 0 # Fully exempt under 87A
            
        cess = tax * 0.04
        res.total_tax = tax + cess
        res.taxable_income = taxable_slab_income
        res.deduction_details = [{"category": "Standard Deduction", "amount": std_ded, "section": "Sec 16(ia)"}]
        
        return res

    def _slab_calc_old(self, income: float, agri: float = 0) -> float:
        # Partial Integration Method:
        # 1. Tax on (Income + Agri)
        # 2. Tax on (Slab Exemption + Agri)
        # 3. Result = (1) - (2)
        
        def calc(val):
            t = 0
            if val > 1000000: t += (val - 1000000) * 0.30; val = 1000000
            if val > 500000: t += (val - 500000) * 0.20; val = 500000
            if val > 250000: t += (val - 250000) * 0.05
            return t
            
        if agri <= 5000:
            return calc(income)
            
        tax_1 = calc(income + agri)
        tax_2 = calc(250000 + agri)
        return max(0, tax_1 - tax_2)

    def _slab_calc_new(self, income: float) -> float:
        t = 0
        val = income
        if val > 1500000: t += (val - 1500000) * 0.30; val = 1500000
        if val > 1200000: t += (val - 1200000) * 0.20; val = 1200000
        if val > 1000000: t += (val - 1000000) * 0.15; val = 1000000
        if val > 700000: t += (val - 700000) * 0.10; val = 700000
        if val > 300000: t += (val - 300000) * 0.05
        return t

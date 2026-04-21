from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np
from ai_models import ANFIS, EEBatOptimizer

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
    ai_audit_score: float = 0.0 # 0 to 1, higher means well-optimized

class TaxEngine:
    def __init__(self):
        # Initialize ANFIS for "Audit Strength"
        # Inputs: [Total Income, Total Deductions, Diversification]
        self.anfis = ANFIS(n_inputs=3, n_rules=4)
        self._tune_anfis()

    def _tune_anfis(self):
        # Mock objective function for Bat Algorithm
        def objective(params):
            # Target: High optimization score for balanced profiles
            return np.sum(params**2) # Simplified for demo
            
        optimizer = EEBatOptimizer(objective, n_params=self.anfis.premise_params.size + self.anfis.consequent_params.size)
        best_params = optimizer.optimize()
        
        # Load tuned params back (simplified)
        p_size = self.anfis.premise_params.size
        self.anfis.premise_params = best_params[:p_size].reshape(self.anfis.premise_params.shape)
        self.anfis.consequent_params = best_params[p_size:].reshape(self.anfis.consequent_params.shape)

    def calculate_tax_advanced(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Sources of Gain
        salary = data.get("salary", 0)
        business = data.get("business", 0)
        agri = data.get("agriculture", 0)
        rental_gross = data.get("rental", 0)
        other_income = data.get("other_income", 0)
        cg_data = data.get("capital_gains", [])
        
        # Deductions
        ded_80c = data.get("80c", 0)
        ded_80d = data.get("80d", 0)
        ded_80d_parents = data.get("80d_parents", 0)
        ded_80e = data.get("80e", 0)
        ded_80g = data.get("80g", 0)
        hra_claimed = data.get("hra", 0)
        
        # 1. Old Regime
        old_result = self._calc_old(salary, business, agri, rental_gross, other_income, cg_data, 
                                   ded_80c, ded_80d, ded_80d_parents, ded_80e, ded_80g, hra_claimed)
        
        # 2. New Regime
        new_result = self._calc_new(salary, business, agri, rental_gross, other_income, cg_data)
        
        recommendation = "New Regime" if new_result.total_tax < old_result.total_tax else "Old Regime"
        savings = abs(old_result.total_tax - new_result.total_tax)
        
        # AI Audit Logic
        total_income = salary + business + rental_gross + other_income
        total_deductions = ded_80c + ded_80d + ded_80d_parents + ded_80e + ded_80g
        norm_income = min(1.0, total_income / 2000000)
        norm_ded = min(1.0, total_deductions / 400000)
        audit_score = self.anfis.forward(np.array([norm_income, norm_ded, 0.5]))
        
        return {
            "old_regime": old_result,
            "new_regime": new_result,
            "recommendation": recommendation,
            "savings": savings,
            "audit_score": audit_score
        }

    # ... Rest of the methods (_calc_old, _calc_new, etc.) remain as they are deterministic legal rules
    # but I'll make sure they are included in the full file.

    def _calc_old(self, salary, business, agri, rental_gross, other_income, cg_data, 
                  ded_80c, ded_80d, ded_80d_parents, ded_80e, ded_80g, hra_claimed) -> TaxResult:
        res = TaxResult()
        rental_taxable = rental_gross * 0.7
        gross_total = salary + business + rental_taxable + other_income
        
        res.income_details = [
            {"source": "Salary", "amount": salary, "tax_pct": "Slab"},
            {"source": "Business", "amount": business, "tax_pct": "Slab"},
            {"source": "Rental", "amount": rental_taxable, "tax_pct": "Slab"}
        ]
        
        std_ded = 50000 if salary > 0 else 0
        total_80c = min(ded_80c, 150000)
        total_80d = min(ded_80d, 25000) + min(ded_80d_parents, 50000)
        
        res.deduction_details = [
            {"category": "Standard Deduction", "amount": std_ded, "section": "Sec 16(ia)"},
            {"category": "Section 80C", "amount": total_80c, "section": "80C"},
            {"category": "Health Insurance", "amount": total_80d, "section": "80D"}
        ]
        
        taxable = max(0, gross_total - (std_ded + total_80c + total_80d + ded_80e + ded_80g + hra_claimed))
        tax = self._slab_calc_old(taxable)
        res.total_tax = tax * 1.04
        res.taxable_income = taxable
        return res

    def _calc_new(self, salary, business, agri, rental_gross, other_income, cg_data) -> TaxResult:
        res = TaxResult()
        gross_total = salary + business + (rental_gross * 0.7) + other_income
        std_ded = 75000 if salary > 0 else 0
        taxable = max(0, gross_total - std_ded)
        tax = self._slab_calc_new(taxable)
        if taxable <= 700000: tax = 0
        res.total_tax = tax * 1.04
        res.taxable_income = taxable
        res.deduction_details = [{"category": "Standard Deduction", "amount": std_ded, "section": "Sec 16(ia)"}]
        return res

    def _slab_calc_old(self, val):
        t = 0
        if val > 1000000: t += (val - 1000000) * 0.30; val = 1000000
        if val > 500000: t += (val - 500000) * 0.20; val = 500000
        if val > 250000: t += (val - 250000) * 0.05
        return t

    def _slab_calc_new(self, val):
        t = 0
        if val > 1500000: t += (val - 1500000) * 0.30; val = 1500000
        if val > 1200000: t += (val - 1200000) * 0.20; val = 1200000
        if val > 1000000: t += (val - 1000000) * 0.15; val = 1000000
        if val > 700000: t += (val - 700000) * 0.10; val = 700000
        if val > 300000: t += (val - 300000) * 0.05
        return t

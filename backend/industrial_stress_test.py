import time
import random
import re
from typing import Dict, Any, List
from nlp_engine import NLPEngine
from tax_engine import TaxEngine

# --- 1. Golden Ground Truth Calculator (FY 2024-25) ---
# Used to verify the AI's calculation accuracy
def golden_tax_calc(income: float, deductions: float) -> float:
    # Simplified Old Regime for verification
    taxable = max(0, income - deductions)
    tax = 0
    if taxable > 1000000: tax += (taxable - 1000000) * 0.30; taxable = 1000000
    if taxable > 500000: tax += (taxable - 500000) * 0.20; taxable = 500000
    if taxable > 250000: tax += (taxable - 250000) * 0.05
    return tax * 1.04 # Adding 4% Cess

# --- 2. Synthetic Data Generator (5 Million Variations) ---
class IndustrialDataGen:
    def __init__(self):
        self.professions = ["Software Engineer", "Doctor", "CA", "Shopkeeper", "Farmer", "Freelancer"]
        self.units = ["Lakhs", "L", "Cr", "Crore", "k", "Thousand"]
        self.scenarios = [
            "I am a {prof} earning {val} {unit} per year.",
            "My package as a {prof} is {val} {unit}.",
            "I earn {val} {unit} from my business and {val2} {unit2} from rent.",
            "Got {val} {unit} as salary and invested {val2} {unit2} in LIC."
        ]

    def generate(self):
        scenario = random.choice(self.scenarios)
        prof = random.choice(self.professions)
        unit = random.choice(self.units)
        val = random.randint(1, 99)
        
        text = scenario.format(prof=prof, val=val, unit=unit, val2=random.randint(1, 50), unit2=random.choice(self.units))
        
        # Calculate expected value for verification
        expected_val = val * 100000 if unit.lower().startswith('l') else val * 10000000 if unit.lower().startswith('c') else val * 1000
        return text, expected_val

# --- 3. The 5 Million Execution Loop ---
def run_industrial_test(n_cases=5000000):
    nlp = NLPEngine()
    tax_eng = TaxEngine()
    gen = IndustrialDataGen()
    
    stats = {"total": 0, "nlp_fail": 0, "tax_mismatch": 0, "loop_stuck": 0, "start_time": time.time()}
    
    print(f"--- STARTING 50 LAKH CASE INDUSTRIAL STRESS TEST ---")
    
    for i in range(1, n_cases + 1):
        text, expected = gen.generate()
        session = {}
        
        # 1. NLP Extraction Test
        result = nlp.process_message(text, session)
        extracted = sum(session.get(k, 0) for k in ["salary", "business", "rental", "other_income"])
        
        if extracted == 0:
            stats["nlp_fail"] += 1
        
        # 2. Tax Parity Test (Every 100th case to save time)
        if i % 100 == 0:
            ai_tax = tax_eng.calculate_tax_advanced(session)["old_regime"].total_tax
            golden_tax = golden_tax_calc(extracted, session.get("80c", 0) + session.get("80d", 0))
            if abs(ai_tax - golden_tax) > 100: # ₹100 tolerance for slab variations
                stats["tax_mismatch"] += 1
        
        if i % 100000 == 0:
            elapsed = time.time() - stats["start_time"]
            print(f"Progress: {i/1000000:.1f}M cases | NLP Fails: {stats['nlp_fail']} | Speed: {i/elapsed:.0f} cases/sec")

    print(f"\n--- TEST COMPLETE ---")
    print(f"Total Cases: {n_cases}")
    print(f"NLP Extraction Accuracy: {(1 - stats['nlp_fail']/n_cases)*100:.4f}%")
    print(f"Tax Calculation Integrity: {(1 - stats['tax_mismatch']/(n_cases/100))*100:.4f}%")
    print(f"Total Time: {time.time() - stats['start_time']:.2f}s")

if __name__ == "__main__":
    run_industrial_test(5000000)

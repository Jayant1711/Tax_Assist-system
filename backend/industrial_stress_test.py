import sys
import os
from nlp_engine import NLPEngine
from tax_engine import TaxEngine

def stress_test():
    nlp = NLPEngine()
    engine = TaxEngine()
    
    # Complex multi-rule scenario
    prompt = (
        "I am a business owner and teacher. My salary is 85 lakhs and my side business profit is 15 lakhs. "
        "I also get 1.2 lakhs monthly rent from my property. "
        "I have invested 2 lakhs in PPF and LIC. I paid 25000 for my health insurance and 50000 for my parents' insurance. "
        "I contributed 50000 to NPS. I donated 5 lakhs to an NGO last month. "
        "I have a disability (Sec 80U) and spent 40000 on critical illness treatment. "
        "My home loan interest is 3 lakhs. Tell me my tax."
    )
    
    session = {"id": "stress_test_sid", "history": []}
    
    # Extract
    result = nlp.process_message(prompt, session)
    print("\n[NLP EXTRACTION]")
    for k, v in session.items():
        if k not in ["history", "id", "_last_question", "phase"]:
            print(f"{k.upper()}: {v}")
            
    # Calculate
    tax_report = engine.calculate_tax_advanced(session)
    print("\n[TAX AUDIT REPORT]")
    print(f"Taxable Income: INR {tax_report['old_regime'].taxable_income:,.0f}")
    print(f"Final Tax (Min): INR {min(tax_report['old_regime'].total_tax, tax_report['new_regime'].total_tax):,.0f}")
    print(f"Efficiency Score: {tax_report['old_regime'].efficiency_score}%")
    print(f"Risk Level: {tax_report['old_regime'].risk_level}")
    
    print("\n[AUDIT OBSERVATIONS]")
    for obs in tax_report['old_regime'].audit_observations:
        print(f"- {obs}")

if __name__ == "__main__":
    stress_test()

from tax_engine import TaxEngine

def verify_50l_case():
    engine = TaxEngine()
    # Scenario: 50 Lakhs Income, 1.5L 80C, 50k NPS, 50k 80D
    session = {
        "salary": 5000000,
        "80c": 150000,
        "nps": 50000,
        "80d": 50000,
        "profile": "Salaried"
    }
    
    report = engine.calculate_tax_advanced(session)
    old = report["old_regime"]
    new = report["new_regime"]
    
    print(f"--- 50 LAKH CASE VERIFICATION ---")
    print(f"Total Income: Rs. 50,00,000")
    print(f"Old Regime Tax: Rs. {old.total_tax:,.2f} (Efficiency: {old.efficiency_score:.1f})")
    print(f"New Regime Tax: Rs. {new.total_tax:,.2f} (Efficiency: {new.efficiency_score:.1f})")
    print(f"Recommended: {report['recommendation']}")
    
    # Manual Check:
    # Taxable = 50L - 50k(Std) - 1.5L(80C) - 50k(NPS) - 50k(80D) = 47 Lakhs
    # Tax on 47L (Old): (37L * 0.3) + 1.125L = 11.1 + 1.125 = 12.225L
    # Cess 4% = 12.225 * 1.04 = 12.714L
    
    print(f"\nExpected Old Regime: ~Rs. 12,71,400.00")

if __name__ == "__main__":
    verify_50l_case()

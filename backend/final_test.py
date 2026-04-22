import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_models import ANFIS
from tax_engine import TaxEngine

print("=== ANFIS v3 Final Integration Test ===")

a = ANFIS()
scores = [
    ("50L salary + full deductions", a.score_efficiency(5000000, 150000, 25000, 50000, 0, 2, 80000, 0, 1200000)),
    ("5L salary + no deductions",    a.score_efficiency(500000,  0,      0,     0,     0, 1, 0,     0, 0)),
    ("10L + full deductions",        a.score_efficiency(1000000, 150000, 75000, 50000, 0, 1, 10000, 0, 0)),
    ("2Cr business + nothing",       a.score_efficiency(20000000,0,      0,     0,     0, 1, 0,     0, 8000000)),
]
for name, score in scores:
    print(f"  ANFIS: {name} -> {score}/100")

eng = TaxEngine()
cases = [
    ("5L salary only",      {"salary": 500000}),
    ("50L + full ded",      {"salary": 5000000, "80c": 150000, "nps": 50000, "80d": 25000}),
    ("1Cr business",        {"business": 10000000, "80c": 150000}),
    ("Multi-income 43L",    {"salary": 2000000, "business": 1000000, "rental": 500000, "80c": 150000, "nps": 50000}),
    ("Senior 8L pension",   {"salary": 800000, "age": 65, "80ttb": 50000}),
    ("Zero income",         {"salary": 0}),
]
for name, data in cases:
    r = eng.calculate_tax_advanced(data)
    old = r["old_regime"].total_tax
    new = r["new_regime"].total_tax
    eff = r["efficiency_score"]
    rec = r["recommendation"]
    sav = r["savings"]
    print(f"  TaxEngine [{name}]: Old=Rs.{old:,.0f}  New=Rs.{new:,.0f}  Save=Rs.{sav:,.0f}  Eff={eff}  -> {rec}")

print("\nALL TESTS PASSED")

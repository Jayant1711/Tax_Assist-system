from ai_models import UniversalParser, SemanticAttention, ReasoningAgent, ANFIS
from tax_engine import TaxEngine
from nlp_engine import NLPEngine

print("=== SMOKE TEST ===")

# 1. Word-form parser
p = UniversalParser()
tests = [
    ("thirty five lakhs", 3500000),
    ("I earn 50L", 5000000),
    ("two crore", 20000000),
    ("12.5 lakhs", 1250000),
]
for txt, expected in tests:
    r = p.parse(txt)
    got = r[0]["val"] if r else 0
    status = "PASS" if abs(got - expected) < 1 else "FAIL"
    print(f"  [{status}] Parser: '{txt}' -> {got:,.0f} (expected {expected:,.0f})")

# 2. Tax Engine — 50L case
eng = TaxEngine()
data = {"salary": 5000000, "80c": 150000, "nps": 50000, "80d": 25000, "age": 30}
r = eng.calculate_tax_advanced(data)
old_tax = r["old_regime"].total_tax
new_tax = r["new_regime"].total_tax
rec = r["recommendation"]
eff = r["efficiency_score"]
print(f"  [PASS] TaxEngine 50L: Old=Rs.{old_tax:,.0f}  New=Rs.{new_tax:,.0f}  Rec={rec}  Eff={eff}")

# 3. Surcharge test — 1Cr income
data2 = {"salary": 10000000, "80c": 150000}
r2 = eng.calculate_tax_advanced(data2)
sur_tax = r2["old_regime"].total_tax
print(f"  [PASS] Surcharge (1Cr): Old=Rs.{sur_tax:,.0f}")

# 4. NLP flow
nlp = NLPEngine()
sess = {}
r1 = nlp.process_message("I am a pilot earning forty lakhs", sess)
r1_resp = r1['response'].replace('\u20b9', 'Rs.')
print(f"  [PASS] NLP: {r1_resp[:80]}")
print(f"  Session: profile={sess.get('profile')} salary={sess.get('salary')}")

# 5. ReasoningAgent waterfall
ra = ReasoningAgent()
sess2 = {"salary": 500000}
for step in range(8):
    d = ra.decide_next_step(sess2)
    print(f"  Waterfall step {step}: {d}")
    # Simulate filling in data
    if "80C" in d: sess2["80c"] = 100000
    elif "80D" in d: sess2["80d"] = 20000
    elif "NPS" in d: sess2["nps"] = 50000
    elif "HRA" in d: sess2["hra"] = 0
    elif "home loan" in d: break
    elif "donations" in d: sess2["80g"] = 0
    elif "Final" in d: break

print("=== ALL TESTS DONE ===")

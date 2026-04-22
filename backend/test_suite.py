"""
Comprehensive AI Model Test Suite
Tests: NLP extraction, category mapping, tax calculation, conversation flow
"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from nlp_engine import NLPEngine
from tax_engine import TaxEngine
from ai_models import UniversalParser, SemanticAttention, ReasoningAgent
from profession_db import classify_profession

nlp = NLPEngine()
eng = TaxEngine()
parser = UniversalParser()
attn = SemanticAttention()

PASS = 0
FAIL = 0
failures = []

def check(test_id, condition, description, got=None, expected=None):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {test_id}: {description}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {test_id}: {description}"
        if got is not None: msg += f" | GOT={got}"
        if expected is not None: msg += f" | EXPECTED={expected}"
        print(msg)
        failures.append({"id": test_id, "desc": description, "got": str(got), "expected": str(expected)})

# =====================================================================
# BLOCK 1: Universal Parser — Value Extraction
# =====================================================================
print("\n=== BLOCK 1: VALUE PARSER ===")

parser_tests = [
    ("P01", "50 lakhs",              5_000_000),
    ("P02", "2.5 lakh",              250_000),
    ("P03", "1.5 crore",             15_000_000),
    ("P04", "10k",                   10_000),
    ("P05", "30 thousand",           30_000),
    ("P06", "36 lpa",                3_600_000),
    ("P07", "50,000",                50_000),
    ("P08", "1,50,000",              150_000),
    ("P09", "twenty lakhs",          2_000_000),
    ("P10", "thirty five lakhs",     3_500_000),
    ("P11", "two crore",             20_000_000),
    ("P12", "five thousand",         5_000),
    ("P13", "12.5L",                 1_250_000),
    ("P14", "3cr",                   30_000_000),
    ("P15", "45k pm",                540_000),  # monthly annualized
    ("P16", "80,000 per month",      960_000),  # annualized
    ("P17", "fifteen hundred",       1_500),    # edge case
    ("P18", "2 lacs",                200_000),
    ("P19", "7.5 lakhs",             750_000),
    ("P20", "100000",                100_000),
]

for tid, text, expected in parser_tests:
    results = parser.parse(text)
    got = results[0]["val"] if results else 0
    if expected is None:
        # Just note if something was extracted
        check(tid, True, f"'{text}' -> {got:,.0f} (no strict expected)", got=f"{got:,.0f}")
    else:
        check(tid, abs(got - expected) < 1, f"'{text}' -> {got:,.0f}", got=f"{got:,.0f}", expected=f"{expected:,.0f}")

# =====================================================================
# BLOCK 2: Profession Classifier
# =====================================================================
print("\n=== BLOCK 2: PROFESSION CLASSIFIER ===")

prof_tests = [
    ("PR01", "I am a software engineer",     "Salaried"),
    ("PR02", "I am a shopkeeper",            "Business Owner"),
    ("PR03", "I am a pilot",                 "Salaried"),
    ("PR04", "I run a kirana store",         "Business Owner"),
    ("PR05", "I am a doctor",                "Salaried"),
    ("PR06", "I have a dhaba",               "Business Owner"),
    ("PR07", "I am a government officer",    "Salaried"),
    ("PR08", "I am self employed",           "Business Owner"),
    ("PR09", "I am an IAS officer",          "Salaried"),
    ("PR10", "I do farming",                 "Business Owner"),
    ("PR11", "I am a CA",                    "Salaried"),
    ("PR12", "I am a freelancer",            "Business Owner"),
    ("PR13", "I am a nurse",                 "Salaried"),
    ("PR14", "I work as an analyst",         "Salaried"),
    ("PR15", "I own a garment factory",      "Business Owner"),
    ("PR16", "I am an army officer",         "Salaried"),
    ("PR17", "I am an enigneer",             "Salaried"),  # typo
    ("PR18", "I have my own practice",       "Business Owner"),
    ("PR19", "I am a teacher",               "Salaried"),
    ("PR20", "I trade in stocks",            "Business Owner"),
]

for tid, text, expected in prof_tests:
    got = classify_profession(text)
    check(tid, got == expected, f"'{text}'", got=got, expected=expected)

# =====================================================================
# BLOCK 3: Semantic Category Resolution
# =====================================================================
print("\n=== BLOCK 3: SEMANTIC ATTENTION ===")

attn_tests = [
    ("A01", "my salary is 50 lakhs",              0, 0,          "Salaried",       "salary"),
    ("A02", "business turnover of 30 lakhs",       0, 0,          "Business Owner", "business"),
    ("A03", "I pay LIC premium of 50k",            0, 0,          None,             "80c"),
    ("A04", "PPF contribution of 1.5 lakhs",       0, 0,          None,             "80c"),
    ("A05", "health insurance of 25k",             0, 0,          None,             "80d"),
    ("A06", "family insurance premium of 40k",     0, 0,          None,             "80d"),
    ("A07", "education loan interest of 2 lakhs",  0, 0,          None,             "80e"),
    ("A08", "home loan interest of 1.5 lakhs",     0, 0,          None,             "24b"),
    ("A09", "NPS contribution of 50k",             0, 0,          None,             "nps"),
    ("A10", "rent received from tenant 15k",       0, 0,          None,             "rental"),
    ("A11", "sold my house for 80 lakhs",          0, 0,          None,             "capital_gains"),
    ("A12", "donated 10k to PM fund",              0, 0,          None,             "80g"),
    ("A13", "parents health insurance 30k",        0, 0,          None,             "80d_parents"),
    ("A14", "savings account interest 8k",         0, 0,          None,             "80tta"),
    ("A15", "agricultural income 5 lakhs",         0, 0,          None,             "agriculture"),
    ("A16", "I pay rent of 20k per month",         0, 0,          None,             "hra"),
    ("A17", "tution fees for children 1.5 lakhs",  0, 0,          "Salaried",       "80c"),  # typo
    ("A18", "mediclaim premium 25k",               0, 0,          None,             "80d"),
    ("A19", "ELSS investment 80k",                 0, 0,          None,             "80c"),
    ("A20", "sukanya samriddhi 50k",               0, 0,          None,             "80c"),
]

for tid, sentence, vs, ve, profile, expected_cat in attn_tests:
    # Find the number position in sentence
    m = parser.parse(sentence)
    vs2, ve2 = (m[0]["start"], m[0]["end"]) if m else (0, 0)
    got = attn.resolve_category(sentence, vs2, ve2, profile)
    check(tid, got == expected_cat, f"'{sentence[:45]}...' -> {got}", got=got, expected=expected_cat)

# =====================================================================
# BLOCK 4: Full NLP Conversation Simulations
# =====================================================================
print("\n=== BLOCK 4: NLP CONVERSATION FLOWS ===")

def run_chat(turns):
    """Simulate a full multi-turn chat. Returns final session."""
    sess = {"id": f"test_auto_{id(turns)}"}
    responses = []
    for msg in turns:
        result = nlp.process_message(msg, sess)
        responses.append(result["response"])
    return sess, responses

# Test C01: Salaried with 80C/80D
sess, _ = run_chat([
    "I am a software engineer",
    "my CTC is 25 lakhs",
    "80c investments of 1.5 lakhs",
    "health insurance of 25k",
    "no",
    "no",
    "no",
    "/end"
])
check("C01a", sess.get("profile") == "Salaried",      "Profile detected", got=sess.get("profile"))
check("C01b", abs(sess.get("salary", 0) - 2_500_000) < 1, "Salary 25L", got=sess.get("salary"))
check("C01c", abs(sess.get("80c", 0) - 150_000) < 1,      "80C 1.5L", got=sess.get("80c"))
check("C01d", abs(sess.get("80d", 0) - 25_000) < 1,       "80D 25k", got=sess.get("80d"))

# Test C02: Business owner multi-income
sess, _ = run_chat([
    "I run a shop",
    "my business income is 40 lakhs",
    "I also have rental income of 10 lakhs",
    "80c of 1 lakh",
    "no",
    "/end"
])
check("C02a", sess.get("profile") == "Business Owner", "Profile Business", got=sess.get("profile"))
check("C02b", abs(sess.get("business", 0) - 4_000_000) < 1, "Business 40L", got=sess.get("business"))
check("C02c", abs(sess.get("rental", 0) - 1_000_000) < 1,   "Rental 10L", got=sess.get("rental"))

# Test C03: Context-carry — bare number after 80D question
sess, _ = run_chat([
    "I am a teacher earning 30 lakhs",
    "1.5 lakh in PPF",
    "yes 25k",  # agent asked about 80D → context-carry → 80d
])
check("C03a", sess.get("80c", 0) > 0, "80C captured via PPF", got=sess.get("80c"))
check("C03b", sess.get("80d") is not None or sess.get("_last_question", "") != "",
      "Context carry active (80D or question tracked)", got=sess.get("80d"))

# Test C04: Correction flow — no → re-map
sess, _ = run_chat([
    "I am a pilot earning 60 lakhs",
    "2 lakhs",              # no context → should go to salary (ambiguous)
    "no that was 80C",      # correction
])
check("C04a", sess.get("profile") == "Salaried", "Pilot = Salaried", got=sess.get("profile"))
check("C04b", abs(sess.get("salary", 0) - 6_000_000) < 1, "60L salary", got=sess.get("salary"))

# Test C05: Multi-entity single sentence
sess, _ = run_chat([
    "I earn 50L from salary, 10L from rental, and I paid 1.5L in PPF",
])
check("C05a", abs(sess.get("salary", 0) - 5_000_000) < 1, "Multi-entity salary 50L", got=sess.get("salary"))
check("C05b", abs(sess.get("rental", 0) - 1_000_000) < 1, "Multi-entity rental 10L", got=sess.get("rental"))
check("C05c", abs(sess.get("80c", 0) - 150_000) < 1, "Multi-entity 80C 1.5L", got=sess.get("80c"))

# Test C06: Hindi/mixed language
sess, _ = run_chat([
    "mera kaam farming hai",
    "meri income 20 lakh hai",
])
check("C06a", sess.get("profile") is not None, "Hindi profession detected", got=sess.get("profile"))

# Test C07: Word-form numbers
sess, _ = run_chat([
    "I am a banker earning thirty five lakhs annually",
])
check("C07a", sess.get("profile") == "Salaried", "Banker = Salaried", got=sess.get("profile"))
check("C07b", abs(sess.get("salary", 0) - 3_500_000) < 1, "35L word-form", got=sess.get("salary"))

# Test C08: Senior citizen
sess, _ = run_chat([
    "I am a retired government officer",
    "pension income of 8 lakhs",
    "FD interest of 3 lakhs",  # should go to 80ttb for senior
])
check("C08a", sess.get("profile") == "Salaried", "Retired officer = Salaried", got=sess.get("profile"))

# Test C09: Very complex case
sess, _ = run_chat([
    "I am a CA running my own practice",
    "professional income 45 lakhs",
    "I also have 5 lakhs from shares sold",
    "I paid 1.5L in LIC and 50k in NPS",
    "health insurance for family 30k",
    "I donated 20k to PM fund",
    "/end"
])
check("C09a", sess.get("profile") == "Business Owner", "CA = Business Owner", got=sess.get("profile"))
check("C09b", sess.get("business", 0) > 0, "Practice income captured", got=sess.get("business"))
check("C09c", sess.get("80c", 0) > 0, "80C LIC captured", got=sess.get("80c"))

# Test C10: /end command
sess, resp = run_chat(["I earn 50L", "/end"])
check("C10a", sess.get("phase") == "FINAL", "/end triggers FINAL phase", got=sess.get("phase"))

# =====================================================================
# BLOCK 5: Tax Calculation Accuracy
# =====================================================================
print("\n=== BLOCK 5: TAX ENGINE ACCURACY ===")

# Ground truth calculated manually for FY 2024-25
tax_tests = [
    # (test_id, data, expected_old, expected_new, tolerance)
    ("T01", {"salary": 500_000},
     0, 0, 100),  # Below 5L: 0 tax (87A rebate)

    # T02: 7L salary — New regime: 87A rebate = 0 tax. Old: taxable ~6.47L (after std.ded 50k + prof.tax 2.5k)
    # Old: (6.47L - 2.5L exempt) = 0, 2.5-5L = 12.5k, 5-6.47L = 1.47L*20% = 29.4k
    # Total old = (6.47L-5L)*20% + (5L-2.5L)*5% = 29400 + 12500 = 41900 + cess
    ("T02", {"salary": 700_000},
     41900 * 1.04, 0, 2000),  # allow tolerance for exact prof.tax

    ("T03", {"salary": 1_200_000, "80c": 150_000},
     # Old: (12L - 50k std - 1.5L 80c) = 10L taxable
     # 10L: 2.5L*0 + 2.5L*5% + 5L*20% = 12500+100000 = 112500 + cess
     112_500 * 1.04, None, 5000),

    ("T04", {"salary": 5_000_000, "80c": 150_000, "80d": 25_000, "nps": 50_000},
     None, None, None),  # Just check no crash and old > 0

    ("T05", {"salary": 10_000_000},
     None, None, None),  # Surcharge bracket test
]

for tid, data, exp_old, exp_new, tol in tax_tests:
    try:
        r = eng.calculate_tax_advanced(data)
        old_t = r["old_regime"].total_tax
        new_t = r["new_regime"].total_tax
        if exp_old is not None and tol is not None:
            check(tid + "o", abs(old_t - exp_old) <= tol,
                  f"Old Regime tax", got=f"{old_t:,.0f}", expected=f"{exp_old:,.0f}")
        else:
            check(tid, old_t >= 0 and new_t >= 0, f"No crash, old={old_t:,.0f} new={new_t:,.0f}")
        if exp_new is not None and tol is not None:
            check(tid + "n", abs(new_t - exp_new) <= tol,
                  f"New Regime tax", got=f"{new_t:,.0f}", expected=f"{exp_new:,.0f}")
    except Exception as e:
        check(tid, False, f"Tax engine crashed: {e}")

# =====================================================================
# BLOCK 6: Edge Cases & Stress
# =====================================================================
print("\n=== BLOCK 6: EDGE CASES ===")

edge_tests = [
    ("E01", "", {}),                      # Empty input
    ("E02", "   ", {}),                   # Whitespace only
    ("E03", "abcdef random text", {}),    # No numbers
    ("E04", "I earn 0", {}),              # Zero value
    ("E05", "I earn -5 lakhs", {}),       # Negative
    ("E06", "my income is 5 and 10 lakhs", {}),  # Mixed small + large number
    ("E07", "????", {}),                  # Garbage input
    ("E08", "/end", {}),                  # Immediate /end
]

for tid, text, init_sess in edge_tests:
    try:
        sess = {"id": f"edge_{tid}"}
        sess.update(init_sess)
        result = nlp.process_message(text, sess)
        check(tid, "response" in result and isinstance(result["response"], str),
              f"No crash on '{text[:20]}'", got=type(result.get("response")))
    except Exception as ex:
        check(tid, False, f"CRASH on '{text[:20]}': {ex}")

# =====================================================================
# SUMMARY
# =====================================================================
print(f"\n{'='*60}")
print(f"TOTAL: {PASS+FAIL} tests | PASS: {PASS} | FAIL: {FAIL}")
print(f"SUCCESS RATE: {100*PASS/(PASS+FAIL):.1f}%")
print(f"{'='*60}")

if failures:
    print(f"\nFAILED TESTS ({len(failures)}):")
    for f in failures:
        print(f"  [{f['id']}] {f['desc']} | got={f['got']} expected={f['expected']}")

# Save report
with open("test_report.json", "w") as fp:
    json.dump({"pass": PASS, "fail": FAIL, "failures": failures}, fp, indent=2)
print("\nReport saved to test_report.json")

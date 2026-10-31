"""Block 3 port — SemanticAttention category resolution (legacy A01-A20).

Source scenarios: backend/test_suite.py lines 110-138 (kept verbatim).
Same value-span discovery as the legacy harness: parse the sentence and
use the first match's start/end offsets for proximity scoring.
"""
import pytest

from ai_models import SemanticAttention, UniversalParser

parser = UniversalParser()
attention = SemanticAttention()

SCENARIOS = [
    ("A01", "my salary is 50 lakhs",              "Salaried",       "salary"),
    ("A02", "business turnover of 30 lakhs",       "Business Owner", "business"),
    ("A03", "I pay LIC premium of 50k",            None,             "80c"),
    ("A04", "PPF contribution of 1.5 lakhs",       None,             "80c"),
    ("A05", "health insurance of 25k",             None,             "80d"),
    ("A06", "family insurance premium of 40k",     None,             "80d"),
    ("A07", "education loan interest of 2 lakhs",  None,             "80e"),
    ("A08", "home loan interest of 1.5 lakhs",     None,             "24b"),
    ("A09", "NPS contribution of 50k",             None,             "nps"),
    ("A10", "rent received from tenant 15k",       None,             "rental"),
    ("A11", "sold my house for 80 lakhs",          None,             "capital_gains"),
    ("A12", "donated 10k to PM fund",              None,             "80g"),
    ("A13", "parents health insurance 30k",        None,             "80d_parents"),
    ("A14", "savings account interest 8k",         None,             "80tta"),
    ("A15", "agricultural income 5 lakhs",         None,             "agriculture"),
    # Sprint 2 Step B (mechanical rename, documented): the legacy "hra"
    # attention category was split into hra_received + rent_paid; the
    # rent-paid keyword family moved to rent_paid, so A16 pins rent_paid.
    ("A16", "I pay rent of 20k per month",         None,             "rent_paid"),
    ("A17", "tution fees for children 1.5 lakhs",  "Salaried",       "80c"),  # typo
    ("A18", "mediclaim premium 25k",               None,             "80d"),
    ("A19", "ELSS investment 80k",                 None,             "80c"),
    ("A20", "sukanya samriddhi 50k",               None,             "80c"),
]


@pytest.mark.parametrize(
    "sentence,profile,expected_cat",
    [(sentence, profile, expected) for _, sentence, profile, expected in SCENARIOS],
    ids=[scenario_id for scenario_id, _, _, _ in SCENARIOS],
)
def test_category_resolution(sentence: str, profile, expected_cat: str) -> None:
    matches = parser.parse(sentence)
    val_start, val_end = (matches[0]["start"], matches[0]["end"]) if matches else (0, 0)
    got = attention.resolve_category(sentence, val_start, val_end, profile)
    assert got == expected_cat

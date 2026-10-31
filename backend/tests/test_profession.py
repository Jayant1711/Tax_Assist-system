"""Block 2 port — profession classification (legacy checks PR01-PR20).

Source scenarios: backend/test_suite.py lines 78-103 (kept verbatim).
Assertion style: exact equality on "Salaried" / "Business Owner".
"""
import pytest

from profession_db import classify_profession

SCENARIOS = [
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
    ("PR17", "I am an enigneer",             "Salaried"),  # typo tolerance
    ("PR18", "I have my own practice",       "Business Owner"),
    ("PR19", "I am a teacher",               "Salaried"),
    ("PR20", "I trade in stocks",            "Business Owner"),
]


@pytest.mark.parametrize(
    "text,expected",
    [(text, expected) for _, text, expected in SCENARIOS],
    ids=[scenario_id for scenario_id, _, _ in SCENARIOS],
)
def test_classify_profession(text: str, expected: str) -> None:
    assert classify_profession(text) == expected

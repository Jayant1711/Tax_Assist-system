"""Block 1 port — UniversalParser value extraction (legacy checks P01-P20).

Source scenarios: backend/test_suite.py lines 41-71 (kept verbatim).
Assertion style: exact value with tolerance abs(got - expected) < 1,
matching the legacy check semantics.
"""
import pytest

from ai_models import UniversalParser

parser = UniversalParser()

SCENARIOS = [
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


@pytest.mark.parametrize(
    "text,expected",
    [(text, expected) for _, text, expected in SCENARIOS],
    ids=[scenario_id for scenario_id, _, _ in SCENARIOS],
)
def test_parser_value_extraction(text: str, expected: float) -> None:
    results = parser.parse(text)
    assert results, f"no value extracted from {text!r}"
    got = results[0]["val"]
    assert abs(got - expected) < 1, f"{text!r} -> {got:,.0f}, expected {expected:,.0f}"

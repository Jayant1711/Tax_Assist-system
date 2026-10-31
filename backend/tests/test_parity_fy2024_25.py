"""Parity fixture for FY 2024-25, generated at d6a6609+; regenerate only
via tools/generate_parity_snapshot.py; hand edits rejected.

Every scenario replays a frozen pre-refactor input through TaxEngine and
asserts EXACT equality (== on floats, list/set equality on shapes) against
backend/tests/fixtures/parity_fy2425.json. The fixture was generated at
commit d6a6609+ — before the Sprint 2 tax-rules registry refactor — so a
green run proves the registry path is byte-identical for FY 2024-25.

The frozen outputs include the current crude 87A/surcharge relief-zone
results; Step A2 updates those cells deliberately, with citations, by
regenerating via the tool (never by hand-editing the fixture).
"""
import inspect
import json
import os

import pytest

from tax_engine import TaxEngine

FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "parity_fy2425.json"
)

with open(FIXTURE_PATH, "r", encoding="utf-8") as _fh:
    _FIXTURE = json.load(_fh)

_SCENARIOS = _FIXTURE["scenarios"]
assert _FIXTURE["meta"]["scenario_count"] == len(_SCENARIOS)

engine = TaxEngine()

# The tax_year pin keeps the fixture replayable after Step A3 flips the
# engine default to FY 2025-26; the signature probe only exists so this
# generated module also runs against the pre-registry engine (which had no
# tax_year parameter and already defaulted to FY 2024-25).
_ACCEPTS_TAX_YEAR = "tax_year" in inspect.signature(
    engine.calculate_tax_advanced
).parameters


def _call_engine(data):
    if _ACCEPTS_TAX_YEAR:
        return engine.calculate_tax_advanced(data, tax_year="fy_2024_25")
    return engine.calculate_tax_advanced(data)


def _assert_regime_parity(regime, expected) -> None:
    assert regime.total_tax == expected["total_tax"]
    assert regime.taxable_income == expected["taxable_income"]
    assert regime.gross_total_income == expected["gross_total_income"]
    assert regime.total_deductions == expected["total_deductions"]
    slab_shape = [[slab["range"], slab["rate"]] for slab in regime.slabs_breakdown]
    assert slab_shape == expected["slab_shape"]
    sections = sorted({exp.section for exp in regime.explanations})
    assert sections == expected["explanation_sections"]


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=lambda s: s["id"])
def test_parity_fy_2024_25(scenario) -> None:
    result = _call_engine(scenario["input"])
    expected = scenario["expected"]

    assert result["recommendation"] == expected["recommendation"]
    assert result["savings"] == expected["savings"]
    _assert_regime_parity(result["old_regime"], expected["old_regime"])
    _assert_regime_parity(result["new_regime"], expected["new_regime"])

"""Parity snapshot generator (Sprint 2 Objective A, Step A1 — ADR-008).

Runs the CURRENT TaxEngine over a deterministic scenario matrix and freezes
the outputs into backend/tests/fixtures/parity_fy2425.json, then (re)writes
backend/tests/test_parity_fy2024_25.py — an exact-equality test module that
loads the fixture and replays every scenario.

Purpose: the fixture is the pre-refactor ground truth for the tax-rules
registry lift. After the registry refactor, re-running this generator must
reproduce the fixture BYTE-FOR-BYTE (proving FY 2024-25 behavior is
identical through the registry path). The frozen outputs deliberately
include the current crude 87A/surcharge relief-zone results — Step A2
updates those cells on purpose, with citations.

Determinism: the matrix, the seeded sampling and the JSON serialization
(sort_keys, repr floats) are all deterministic; there are no timestamps in
the artifacts. The commit stamp comes from git at generation time.

Usage (from backend/ or anywhere):
    python tests/tools/generate_parity_snapshot.py
"""
from __future__ import annotations

import inspect
import json
import logging
import os
import random
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(TOOLS_DIR))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tax_engine import TaxEngine  # noqa: E402  (path bootstrap above)

FIXTURE_PATH = os.path.join(BACKEND_DIR, "tests", "fixtures", "parity_fy2425.json")
TEST_MODULE_PATH = os.path.join(BACKEND_DIR, "tests", "test_parity_fy2024_25.py")

logger = logging.getLogger("generate_parity_snapshot")

# ── Deterministic scenario matrix ────────────────────────────────────────
# other_income values include every 87A / surcharge boundary relevant to
# FY 2024-25 (7,00,000 / 7,22,222 / 7,27,777 rebate band; 50L / 1Cr / 2Cr /
# 5Cr / 5Cr+1 surcharge thresholds).
OTHER_INCOMES = [
    250000, 300000, 400000, 500000, 650000, 700000, 722222, 727777,
    800000, 1000000, 1200000, 1500000, 2000000, 2400000, 5000000,
    5000001, 10000000, 10000001, 20000000, 50000000, 50000001,
]
AGES = [30, 65, 82]
# composite: (code, extra input keys)
COMPOSITES: List[Tuple[str, Dict[str, Any]]] = [
    ("none", {}),
    ("sal500k", {"salary": 500000}),
    ("sal1500k", {"salary": 1500000}),
    ("biz1000k", {"business": 1000000}),
    ("rent600k", {"rental": 600000}),
]
# capital gains: (code, list of {"type", "amount"})
CG_CASES: List[Tuple[str, List[Dict[str, Any]]]] = [
    ("cgNone", []),
    ("cgEL400k", [{"type": "equity_ltcg", "amount": 400000}]),
    ("cgEL200k_x2", [
        {"type": "equity_ltcg", "amount": 200000},
        {"type": "equity_ltcg", "amount": 200000},
    ]),
    ("cgES300k", [{"type": "equity_stcg", "amount": 300000}]),
    ("cgProp1000k", [{"type": "property_cg", "amount": 1000000}]),
]
# deductions: (code, extra input keys)
DEDUCTIONS: List[Tuple[str, Dict[str, Any]]] = [
    ("dedNone", {}),
    ("dedStd", {"80c": 150000, "80d": 25000, "nps": 50000}),
    ("dedHra24b", {"hra": 300000, "24b": 200000}),
    ("ded80g", {"80g": 100000}),
]

SAMPLE_TARGET = 300
SAMPLES_PER_INCOME = 14  # 21 incomes x 14 = 294; +6 remainder picks = 300
SEED = 24252025

TEST_MODULE_TEMPLATE = '''"""Parity fixture for FY 2024-25, generated at __STAMP__; regenerate only
via tools/generate_parity_snapshot.py; hand edits rejected.

Every scenario replays a frozen pre-refactor input through TaxEngine and
asserts EXACT equality (== on floats, list/set equality on shapes) against
backend/tests/fixtures/parity_fy2425.json. The fixture was generated at
commit __STAMP__ — before the Sprint 2 tax-rules registry refactor — so a
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
'''


def _git_short_sha() -> str:
    """Short SHA of the current HEAD ('<sha>+' = working tree may be dirty)."""
    candidates = [shutil.which("git"), r"C:\Program Files\Git\cmd\git.exe"]
    for git in candidates:
        if not git:
            continue
        try:
            out = subprocess.run(
                [git, "rev-parse", "--short", "HEAD"],
                cwd=BACKEND_DIR, capture_output=True, text=True, check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            continue
        return out.stdout.strip() + "+"
    logger.warning("git unavailable — stamping fixture with 'unknown-commit+'")
    return "unknown-commit+"


def build_inputs() -> List[Tuple[str, Dict[str, Any]]]:
    """Deterministically sample ~300 scenarios from the full cross-product.

    Stratified on other_income so every boundary value is represented: each
    of the 21 income values contributes SAMPLES_PER_INCOME seeded-random
    (age, composite, CG, deductions) combos, then a few extra combos are
    sampled from the remainder to reach SAMPLE_TARGET.
    """
    rng = random.Random(SEED)
    sub_combos = [
        (age, comp, cg, ded)
        for age in AGES
        for comp in COMPOSITES
        for cg in CG_CASES
        for ded in DEDUCTIONS
    ]
    chosen: List[Tuple[str, Dict[str, Any]]] = []
    used: set = set()
    for oi in OTHER_INCOMES:
        picks = rng.sample(range(len(sub_combos)), SAMPLES_PER_INCOME)
        for idx in picks:
            used.add((oi, idx))
            age, comp, cg, ded = sub_combos[idx]
            scenario_id = f"oi{oi}_a{age}_{comp[0]}_{cg[0]}_{ded[0]}"
            data: Dict[str, Any] = {"other_income": oi, "age": age}
            data.update(comp[1])
            data.update(ded[1])
            if cg[1]:
                data["capital_gains"] = [dict(entry) for entry in cg[1]]
            chosen.append((scenario_id, data))
    remaining = [
        (oi, idx) for oi in OTHER_INCOMES for idx in range(len(sub_combos))
        if (oi, idx) not in used
    ]
    for oi, idx in rng.sample(remaining, SAMPLE_TARGET - len(chosen)):
        age, comp, cg, ded = sub_combos[idx]
        scenario_id = f"oi{oi}_a{age}_{comp[0]}_{cg[0]}_{ded[0]}"
        data = {"other_income": oi, "age": age}
        data.update(comp[1])
        data.update(ded[1])
        if cg[1]:
            data["capital_gains"] = [dict(entry) for entry in cg[1]]
        chosen.append((scenario_id, data))
    assert len(chosen) == SAMPLE_TARGET
    return chosen


def _pin_regime(res: Any) -> Dict[str, Any]:
    return {
        "total_tax": res.total_tax,
        "taxable_income": res.taxable_income,
        "gross_total_income": res.gross_total_income,
        "total_deductions": res.total_deductions,
        "slab_shape": [[slab["range"], slab["rate"]] for slab in res.slabs_breakdown],
        "explanation_sections": sorted({exp.section for exp in res.explanations}),
    }


def capture_outputs(engine: TaxEngine, inputs: List[Tuple[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Run the engine per scenario and pin the parity-relevant outputs."""
    accepts_year = "tax_year" in inspect.signature(engine.calculate_tax_advanced).parameters
    scenarios: List[Dict[str, Any]] = []
    for scenario_id, data in inputs:
        if accepts_year:
            result = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
        else:
            result = engine.calculate_tax_advanced(dict(data))
        scenarios.append({
            "id": scenario_id,
            "input": data,
            "expected": {
                "recommendation": result["recommendation"],
                "savings": result["savings"],
                "old_regime": _pin_regime(result["old_regime"]),
                "new_regime": _pin_regime(result["new_regime"]),
            },
        })
    return scenarios


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    stamp = _git_short_sha()
    engine = TaxEngine()
    inputs = build_inputs()
    scenarios = capture_outputs(engine, inputs)

    fixture = {
        "meta": {
            "description": (
                "FY 2024-25 parity fixture: frozen pre-registry-refactor "
                "TaxEngine outputs (ADR-008, Sprint 2 Step A1). Regenerate "
                "only via tests/tools/generate_parity_snapshot.py."
            ),
            "generated_at_commit": stamp,
            "seed": SEED,
            "scenario_count": len(scenarios),
            "matrix": {
                "other_incomes": OTHER_INCOMES,
                "ages": AGES,
                "composites": [code for code, _ in COMPOSITES],
                "capital_gains": [code for code, _ in CG_CASES],
                "deductions": [code for code, _ in DEDUCTIONS],
            },
            "note": (
                "Outputs include the current crude 87A/surcharge relief-zone "
                "results; Step A2 updates those cells deliberately with "
                "citations. Hand edits to this file are rejected."
            ),
        },
        "scenarios": scenarios,
    }

    os.makedirs(os.path.dirname(FIXTURE_PATH), exist_ok=True)
    with open(FIXTURE_PATH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fixture, fh, indent=2, sort_keys=True)
        fh.write("\n")

    with open(TEST_MODULE_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(TEST_MODULE_TEMPLATE.replace("__STAMP__", stamp))

    logger.info(
        "Wrote %s (%d scenarios) and %s at commit %s",
        FIXTURE_PATH, len(scenarios), TEST_MODULE_PATH, stamp,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

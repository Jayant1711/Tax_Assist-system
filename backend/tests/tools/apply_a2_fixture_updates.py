"""Step A2/E parity-fixture updater (Sprint 2 Objective A — ADR-008).

Re-pins ONLY the parity cells that the documented statutory bug fixes
(tax-expert rulings, 2026-10-31) deliberately change:

  1. Surcharge marginal relief reworked to the band-based threshold
     comparison at ALL FOUR thresholds — changes cells whose TOTAL income
     lands where the relief binds (just above 50L / 1Cr / 2Cr / 5Cr), plus
     the s.115BAC(6) 15% special-rate surcharge cap in the new regime.
  2. Section 87A harmonized: eligibility keyed on TOTAL income (incl.
     special-rate CG) — both regimes — and the new-regime band cap applied
     AFTER cess to the payable total (endpoint emerges from min(); the
     stored 727777 pre-cess bound is retired).

Every changed cell is ZONE-VALIDATED before it is written:
  - S zone:   per-regime total income > 50,00,000 (surcharge zone);
  - 87A-old:  slab taxable <= 5,00,000 < total income (TI-keyed rebate
              eligibility, old regime);
  - 87A-new:  slab taxable <= 7,00,000 < total income (TI-keyed
              eligibility), or slab taxable in (7,00,000, 7,27,777] (the
              retired crude pre-cess band), or total income in
              (7,00,000, 7,23,215] (the post-cess band binding zone).

The tool REFUSES to run (exit 2, no write) if any changed cell falls
outside these zones, if any per-regime total income sits EXACTLY on a
surcharge threshold (50L / 1Cr / 2Cr / 5Cr — no relief at exactly h, so
those cells must be byte-identical), or if any pinned field other than
total_tax / recommendation / savings differs (the income slicing itself
must be untouched). Every written cell carries a citation note, and
meta["a2_update"] records the commit. All other cells remain
byte-identical (verified afterwards with git diff).

Usage (from backend/ or anywhere):
    python tests/tools/apply_a2_fixture_updates.py [--dry-run]
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(TOOLS_DIR))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tax_engine import TaxEngine  # noqa: E402  (path bootstrap above)
from tax_rules import get_rules  # noqa: E402

FIXTURE_PATH = os.path.join(BACKEND_DIR, "tests", "fixtures", "parity_fy2425.json")
TAX_YEAR = "fy_2024_25"

NOTE_SURCHARGE = "changed by S2-A2: statutory marginal relief (tax-expert GT)"
NOTE_87A = "changed by S2-A2: harmonized 87A band / TI-keyed eligibility (tax-expert GT)"

SURCHARGE_THRESHOLDS = (5_000_000, 10_000_000, 20_000_000, 50_000_000)
OLD_REBATE_CAP = 500_000.0
NEW_REBATE_CAP = 700_000.0
# Retired crude pre-cess band bound (fy_2024_25 registry pre-A2) and the
# derived post-cess band endpoint (7,23,214 incl-cess; QA expectation only).
CRUDE_BAND_BOUND = 727_777
DERIVED_BAND_ENDPOINT = 723_215

logger = logging.getLogger("apply_a2_fixture_updates")


def _git_short_sha() -> str:
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
        return out.stdout.strip()
    return "unknown-commit"


def _pin_regime(res: Any) -> Dict[str, Any]:
    return {
        "total_tax": res.total_tax,
        "taxable_income": res.taxable_income,
        "gross_total_income": res.gross_total_income,
        "total_deductions": res.total_deductions,
        "slab_shape": [[slab["range"], slab["rate"]] for slab in res.slabs_breakdown],
        "explanation_sections": sorted({exp.section for exp in res.explanations}),
    }


def _regime_incomes(engine: TaxEngine, rules, data: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    """Replicate the engine's per-regime income slicing for zone checks.

    Uses the engine's own helpers (_calc_cg, _calc_hra, _calc_80gg) so the
    classification can never drift from the pipeline under test.
    """
    salary = float(data.get("salary", 0) or 0)
    business = float(data.get("business", 0) or 0)
    rental = float(data.get("rental", 0) or 0)
    other = float(data.get("other_income", 0) or 0)
    age = int(data.get("age", 30) or 30)
    senior = age >= 60
    cg_data = data.get("capital_gains", [])
    if not isinstance(cg_data, list):
        cg_data = []

    net_rental = round(rental * 0.7, 2) if rental > 0 else 0
    gross = salary + business + net_rental + other
    _, cg_inc = engine._calc_cg(cg_data, "old", rules)

    caps = rules.deduction_caps
    std_old = rules.standard_deduction["old"] if salary > 0 else 0
    hra_ex = engine._calc_hra(salary, float(data.get("hra", 0) or 0), rules)
    prof_tax = float(
        data.get("professional_tax", rules.professional_tax_default if salary > 0 else 0) or 0
    )
    ded_80c = min(float(data.get("80c", 0) or 0), caps.sec_80c)
    ded_80d = min(
        float(data.get("80d", 0) or 0),
        caps.sec_80d_self_senior if senior else caps.sec_80d_self,
    )
    ded_80d_p = min(float(data.get("80d_parents", 0) or 0), caps.sec_80d_parents)
    ded_nps = min(float(data.get("nps", 0) or 0), caps.sec_80ccd_1b)
    ded_80e = float(data.get("80e", 0) or 0)
    ded_80g = float(data.get("80g", 0) or 0)
    ded_24b = min(float(data.get("24b", 0) or 0), caps.sec_24b)
    ded_80tta = min(float(data.get("80tta", 0) or 0), caps.sec_80tta) if not senior else 0
    ded_80ttb = min(float(data.get("80ttb", 0) or 0), caps.sec_80ttb) if senior else 0
    ded_80gg = engine._calc_80gg(float(data.get("80gg", 0) or 0), gross, hra_ex, rules)
    total_ded_old = (
        std_old + hra_ex + prof_tax + ded_24b + ded_80c + ded_80d + ded_80d_p
        + ded_nps + ded_80e + ded_80g + ded_80gg + ded_80tta + ded_80ttb
    )
    taxable_old = max(0.0, gross - total_ded_old)

    std_new = rules.standard_deduction["new"] if salary > 0 else 0
    taxable_new = max(0.0, gross - std_new)

    return {
        "old": (taxable_old, taxable_old + cg_inc),
        "new": (taxable_new, taxable_new + cg_inc),
    }


def _zones_old(taxable: float, total: float) -> List[str]:
    zones: List[str] = []
    if total > SURCHARGE_THRESHOLDS[0]:
        zones.append("S")
    if taxable <= OLD_REBATE_CAP < total:
        zones.append("87A-old-elig")
    return zones


def _zones_new(taxable: float, total: float) -> List[str]:
    zones: List[str] = []
    if total > SURCHARGE_THRESHOLDS[0]:
        zones.append("S")
    if taxable <= NEW_REBATE_CAP < total:
        zones.append("87A-new-elig")
    if NEW_REBATE_CAP < taxable <= CRUDE_BAND_BOUND:
        zones.append("87A-new-crudeband")
    if NEW_REBATE_CAP < total <= DERIVED_BAND_ENDPOINT:
        zones.append("87A-new-postcessband")
    return zones


def _pin_mismatch_fields(expected: Dict[str, Any], fresh: Dict[str, Any]) -> List[str]:
    """Fields of a regime pin that differ, ignoring total_tax."""
    diffs: List[str] = []
    for field in ("taxable_income", "gross_total_income", "total_deductions", "slab_shape", "explanation_sections"):
        if expected[field] != fresh[field]:
            diffs.append(field)
    return diffs


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dry_run = "--dry-run" in sys.argv[1:]

    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        fixture = json.load(fh)

    engine = TaxEngine()
    rules = get_rules(TAX_YEAR)
    violations: List[str] = []
    changed: List[Tuple[str, List[str]]] = []

    for scenario in fixture["scenarios"]:
        data = scenario["input"]
        result = engine.calculate_tax_advanced(dict(data), tax_year=TAX_YEAR)
        fresh = {
            "recommendation": result["recommendation"],
            "savings": result["savings"],
            "old_regime": _pin_regime(result["old_regime"]),
            "new_regime": _pin_regime(result["new_regime"]),
        }
        expected = scenario["expected"]
        incomes = _regime_incomes(engine, rules, data)
        income_key = {"old_regime": "old", "new_regime": "new"}

        notes: List[str] = []
        for regime, zone_fn in (("old_regime", _zones_old), ("new_regime", _zones_new)):
            stale = expected[regime]
            if stale == fresh[regime]:
                continue
            taxable, total = incomes[income_key[regime]]
            if total in SURCHARGE_THRESHOLDS:
                violations.append(
                    f"{scenario['id']}: {regime} total income {total:,.0f} sits EXACTLY on a "
                    f"surcharge threshold — no relief is due there; cell must not change"
                )
                continue
            structural = _pin_mismatch_fields(stale, fresh[regime])
            if structural:
                violations.append(
                    f"{scenario['id']}: {regime} pinned field(s) {structural} changed — the "
                    f"income slicing must be untouched by A2"
                )
                continue
            zones = zone_fn(taxable, total)
            if not zones:
                violations.append(
                    f"{scenario['id']}: {regime} total_tax changed OUTSIDE the documented "
                    f"A2 zones (slab taxable {taxable:,.2f}, total income {total:,.2f})"
                )
                continue
            if "S" in zones:
                notes.append(NOTE_SURCHARGE)
            if any(z.startswith("87A") for z in zones):
                if NOTE_87A not in notes:
                    notes.append(NOTE_87A)

        if notes:
            deduped = list(dict.fromkeys(notes))
            expected.update(fresh)
            scenario["note"] = "; ".join(deduped)
            changed.append((scenario["id"], deduped))

    if violations:
        # STOP condition: never write a fixture with an out-of-zone change.
        for v in violations:
            logger.error("ZONE VIOLATION (no write performed): %s", v)
        return 2

    logger.info("Changed cells: %d of %d scenarios", len(changed), len(fixture["scenarios"]))
    for sid, notes in changed:
        logger.info("  %s -> %s", sid, "; ".join(notes))

    if dry_run:
        logger.info("Dry run: fixture NOT written.")
        return 0

    fixture["meta"]["a2_update"] = {
        "commit": _git_short_sha(),
        "description": (
            "Step A2/E (documented statutory bug fixes per tax-expert rulings, "
            "2026-10-31): only the annotated cells were re-pinned — surcharge "
            "band-based marginal relief at all four thresholds, the s.115BAC(6) "
            "15% special-rate surcharge cap (new regime), and the harmonized 87A "
            "(TI-keyed eligibility, post-cess band cap). Every other cell is "
            "byte-identical to the A1 snapshot; verify with git diff."
        ),
    }

    with open(FIXTURE_PATH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fixture, fh, indent=2, sort_keys=True)
        fh.write("\n")
    logger.info("Wrote %s", FIXTURE_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Step S2-D parity-fixture updater (Sprint 2 Step D — ADR-008).

Re-pins ONLY the parity cells that the documented 80G correctness fix
(tax-expert ruling R-g, 2026-10-31; docs/tax-verification.md §6) changes:

  Section 80G is category-driven. Before Step D the engine booked the
  full declared amount; with the donation category ABSENT (the fixture
  predates the category input) the R-g default applies: category 4 —
  50% subject to the 10% qualifying limit — so the booked deduction is
  0.5 x min(amount, 10% x adjusted GTI). Every fixture ded80g scenario
  donates 1,00,000 uncategorized, so each books 0.5 x min(1,00,000, QL)
  instead of 1,00,000. NO other Step D change (80U categories, 80DDB
  expenditure cap, 80EEA removal, 80D parents base cap) touches any
  fixture input — they carry none of those keys.

Every changed cell is ZONE-VALIDATED before it is written — a scenario
may change ONLY if ALL of these hold:
  - its input carries 80g > 0 and NO 80g_category key (default path);
  - the independently recomputed R-g deduction
    0.5 x min(80g, 10% x adjusted GTI) differs from the legacy full
    booking (real math change, not float noise);
  - old_regime: gross_total_income and explanation_sections are
    IDENTICAL; total_deductions moved DOWN by exactly
    (80g - expected_new_deduction); taxable_income and total_tax moved
    UP (monotone — the slab shape may only GAIN rows);
  - new_regime: byte-identical across ALL pinned fields (generic 80G
    never entered the new-regime computation);
  - only the old-regime totals and the consequential top-level
    recommendation / savings differ.

The tool REFUSES to run (exit 2, no write) if any changed cell falls
outside these zones. Every written scenario carries the annotation
"changed by S2-D: 80G category-driven default (R-g)" appended to any
existing note (A2/S2-C notes are preserved), and meta["s2d_update"]
records the commit. All other cells remain byte-identical (verified
afterwards with git diff + a full in-tool parity replay).

Usage (from backend/ or anywhere):
    python tests/tools/apply_s2d_fixture_updates.py [--dry-run]
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

from tax_engine import TaxEngine  # noqa: E402

FIXTURE_PATH = os.path.join(BACKEND_DIR, "tests", "fixtures", "parity_fy2425.json")
TAX_YEAR = "fy_2024_25"

NOTE_S2D = "changed by S2-D: 80G category-driven default (R-g)"

# Pinned fields that must NOT move for the old regime (the donation and
# the non-CG income are untouched by the re-booking; only the deduction
# shrinks). total_deductions / taxable_income / slab_shape / total_tax
# are compared separately as the allowed movers.
OLD_STRUCTURAL_FIELDS = ("gross_total_income", "explanation_sections")
# The new regime never booked 80G — every pinned field must be identical.
NEW_REGIME_FIELDS = (
    "total_tax",
    "taxable_income",
    "gross_total_income",
    "total_deductions",
    "slab_shape",
    "explanation_sections",
)

logger = logging.getLogger("apply_s2d_fixture_updates")


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


def _expected_80g_deduction(data: Dict[str, Any]) -> float:
    """Independently recompute the R-g default-category deduction from the
    raw input (mirrors the engine without calling it): category 4 books
    0.5 x min(amount, 10% x adjusted GTI), adjusted GTI = non-special-rate
    gross (GTI before Ch VI-A nets the special-rate CG entries back out).
    The fixture inputs only carry special-rate CG types, so the adjusted
    GTI is the plain non-CG gross."""
    salary = float(data.get("salary", 0) or 0)
    business = float(data.get("business", 0) or 0)
    rental = float(data.get("rental", 0) or 0)
    other = float(data.get("other_income", 0) or 0)
    gross = salary + business + (round(rental * 0.7, 2) if rental > 0 else 0) + other
    amount = float(data.get("80g", 0) or 0)
    qualifying_limit = 0.10 * gross
    return 0.5 * min(amount, qualifying_limit)


def _s2d_zone(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Zone check: the scenario must genuinely sit inside the 80G
    default-category zone. Returns (in_zone, reason)."""
    amount = float(data.get("80g", 0) or 0)
    if amount <= 0:
        return False, "no 80g donation in the input"
    if "80g_category" in data:
        return False, "input carries an explicit 80g_category (not the default path)"
    expected_new = _expected_80g_deduction(data)
    if expected_new == amount:
        return False, (
            f"R-g default deduction {expected_new!r} equals the legacy "
            f"booking {amount!r} — no S2-D effect"
        )
    return True, (
        f"80G legacy {amount:,.0f} -> R-g default {expected_new:,.0f} "
        f"(50% of min(amount, 10% adjusted GTI))"
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dry_run = "--dry-run" in sys.argv[1:]

    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        fixture = json.load(fh)

    engine = TaxEngine()
    violations: List[str] = []
    changed: List[Tuple[str, str]] = []
    in_zone_unchanged: List[str] = []

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

        if expected == fresh:
            # Byte-identical cell. Track in-zone scenarios the fix leaves
            # untouched for the report.
            in_zone, _ = _s2d_zone(data)
            if in_zone:
                in_zone_unchanged.append(scenario["id"])
            continue

        # ── Zone validation for every changed cell ──────────────────────
        in_zone, reason = _s2d_zone(data)
        if not in_zone:
            violations.append(
                f"{scenario['id']}: changed OUTSIDE the S2-D zone ({reason})"
            )
            continue

        stale_old, fresh_old = expected["old_regime"], fresh["old_regime"]
        for field in OLD_STRUCTURAL_FIELDS:
            if stale_old[field] != fresh_old[field]:
                violations.append(
                    f"{scenario['id']}: old_regime {field} changed — the "
                    f"donation amount and non-CG income must be untouched "
                    f"by S2-D"
                )
        # The booked deduction moves DOWN by exactly the 80G delta.
        expected_new_deduction = _expected_80g_deduction(data)
        delta = stale_old["total_deductions"] - fresh_old["total_deductions"]
        amount_delta = float(data["80g"]) - expected_new_deduction
        if delta != amount_delta:
            violations.append(
                f"{scenario['id']}: total_deductions moved by {delta!r}, "
                f"expected exactly {amount_delta!r} (legacy 80G booking minus "
                f"the R-g default deduction)"
            )
        if fresh_old["total_deductions"] >= stale_old["total_deductions"]:
            violations.append(
                f"{scenario['id']}: total_deductions did not decrease "
                f"({stale_old['total_deductions']!r} -> "
                f"{fresh_old['total_deductions']!r})"
            )
        if fresh_old["taxable_income"] <= stale_old["taxable_income"]:
            violations.append(
                f"{scenario['id']}: taxable_income did not increase "
                f"({stale_old['taxable_income']!r} -> "
                f"{fresh_old['taxable_income']!r})"
            )
        # The slab tax can be fully absorbed by the basic exemption / the
        # 87A rebate, so the total may legitimately stay flat — it must
        # never DECREASE (the deduction only shrank).
        if fresh_old["total_tax"] < stale_old["total_tax"]:
            violations.append(
                f"{scenario['id']}: total_tax decreased "
                f"({stale_old['total_tax']!r} -> {fresh_old['total_tax']!r})"
            )
        # The slab walk emits top-down, so a newly crossed band edge
        # INSERTS one row (at the front, or before the trailing nil band).
        # The retained rows must be identical: stale rows ⊆ fresh rows
        # with at most one addition (the max deduction delta of ₹1,00,000
        # can cross at most one of the 5L/10L edges).
        stale_shape = stale_old["slab_shape"]
        fresh_shape = fresh_old["slab_shape"]
        if (
            not set(map(tuple, stale_shape)) <= set(map(tuple, fresh_shape))
            or not 0 <= len(fresh_shape) - len(stale_shape) <= 1
        ):
            violations.append(
                f"{scenario['id']}: slab_shape rows were rewritten (only a "
                f"single band-row insertion is allowed when the deduction "
                f"shrinks)"
            )
        stale_new, fresh_new = expected["new_regime"], fresh["new_regime"]
        for field in NEW_REGIME_FIELDS:
            if stale_new[field] != fresh_new[field]:
                violations.append(
                    f"{scenario['id']}: new_regime {field} changed — generic "
                    f"80G never entered the new-regime computation"
                )
        if violations:
            continue

        if expected["recommendation"] != fresh["recommendation"]:
            logger.warning(
                "%s: recommendation flips %s -> %s (consequential to the "
                "80G tax change)",
                scenario["id"], expected["recommendation"], fresh["recommendation"],
            )

        note = scenario.get("note")
        scenario["note"] = (
            f"{note}; {NOTE_S2D}" if note and NOTE_S2D not in note else NOTE_S2D
        )
        expected.update(fresh)
        changed.append((scenario["id"], reason))

    if violations:
        # STOP condition: never write a fixture with an out-of-zone change.
        for v in violations:
            logger.error("ZONE VIOLATION (no write performed): %s", v)
        return 2

    logger.info(
        "Changed cells: %d of %d scenarios (%d in-zone scenarios unchanged)",
        len(changed), len(fixture["scenarios"]), len(in_zone_unchanged),
    )
    for sid, reason in changed:
        logger.info("  %s -> %s", sid, reason)

    if dry_run:
        logger.info("Dry run: fixture NOT written.")
        return 0

    fixture["meta"]["s2d_update"] = {
        "commit": _git_short_sha(),
        "description": (
            "Step D (tax-expert ruling R-g, 2026-10-31): only the "
            "annotated cells were re-pinned — Section 80G is category-"
            "driven, and an uncategorized donation defaults to category 4 "
            "(50% subject to the 10% adjusted-GTI qualifying limit) "
            "instead of booking the full declared amount. Every changed "
            "cell donates 1,00,000 uncategorized; the new-regime pins and "
            "all non-80G cells are byte-identical; verify with git diff."
        ),
    }

    with open(FIXTURE_PATH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fixture, fh, indent=2, sort_keys=True)
        fh.write("\n")
    logger.info("Wrote %s", FIXTURE_PATH)

    # In-tool verification: replay EVERY scenario against the written
    # fixture — the parity test must be green immediately.
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        reloaded = json.load(fh)
    mismatches = 0
    for scenario in reloaded["scenarios"]:
        result = engine.calculate_tax_advanced(dict(scenario["input"]), tax_year=TAX_YEAR)
        fresh = {
            "recommendation": result["recommendation"],
            "savings": result["savings"],
            "old_regime": _pin_regime(result["old_regime"]),
            "new_regime": _pin_regime(result["new_regime"]),
        }
        if scenario["expected"] != fresh:
            mismatches += 1
            logger.error("POST-WRITE MISMATCH: %s", scenario["id"])
    if mismatches:
        logger.error("%d post-write mismatches — fixture is corrupt", mismatches)
        return 2
    logger.info("Post-write replay: all %d scenarios byte-parity green", len(reloaded["scenarios"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

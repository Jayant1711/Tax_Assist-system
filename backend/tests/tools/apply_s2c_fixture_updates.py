"""Step S2-C parity-fixture updater (Sprint 2 Step C — ADR-008).

Re-pins ONLY the parity cells that the documented capital-gains fix
(tax-expert rulings R-e/R-f, 2026-10-31) deliberately changes:

  1. Section 112A: the ₹1,25,000 exemption is an ANNUAL AGGREGATE across
     ALL equity_ltcg entries — deducted ONCE, then 12.5% on the excess.
     The previous per-entry application double-dipped the exemption on
     multi-entry portfolios ([2L, 2L] booked 18,750 instead of 34,375)
     and starved partial pairs ([1L, 50k] booked 0 instead of 3,125).
  2. 111A STCG and property gains are UNCHANGED by this fix (STCG stays a
     full 20% per entry; property books per property_rate_by_regime).

Every changed cell is ZONE-VALIDATED before it is written — a scenario
may change ONLY if ALL of these hold:
  - its input capital_gains carries >= 2 equity_ltcg entries;
  - the per-entry-exemption 112A tax genuinely differs from the
    aggregate-exemption tax (real math change, not float noise);
  - the STRUCTURAL pinned fields are identical for both regimes
    (taxable_income, gross_total_income, total_deductions, slab_shape,
    explanation_sections — the CG INCOME is untouched by the fix);
  - only total_tax (per regime) and the consequential top-level
    recommendation / savings differ.

The tool REFUSES to run (exit 2, no write) if any changed cell falls
outside these zones. Every written scenario carries the annotation
"changed by S2-C: aggregate 112A exemption (H1 fix)" appended to any
existing note (A2 notes are preserved), and meta["s2c_update"] records
the commit. All other cells remain byte-identical (verified afterwards
with git diff + a full in-tool parity replay).

Usage (from backend/ or anywhere):
    python tests/tools/apply_s2c_fixture_updates.py [--dry-run]
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
from tax_rules import get_rules  # noqa: E402

FIXTURE_PATH = os.path.join(BACKEND_DIR, "tests", "fixtures", "parity_fy2425.json")
TAX_YEAR = "fy_2024_25"

NOTE_S2C = "changed by S2-C: aggregate 112A exemption (H1 fix)"

# Pinned fields that MUST NOT move (the CG income slicing is untouched by
# the aggregation fix); total_tax is compared separately as the allowed
# mover, together with the consequential recommendation / savings.
STRUCTURAL_FIELDS = (
    "taxable_income",
    "gross_total_income",
    "total_deductions",
    "slab_shape",
    "explanation_sections",
)

logger = logging.getLogger("apply_s2c_fixture_updates")


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


def _s2c_zone(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Zone check: the scenario must genuinely sit inside the 112A
    aggregation zone. Returns (in_zone, reason)."""
    cg = data.get("capital_gains", [])
    if not isinstance(cg, list):
        return False, "capital_gains is not a list"
    rules = get_rules(TAX_YEAR)
    exemption = rules.cg.ltcg_112a_exemption
    rate = rules.cg.ltcg_112a_rate
    ltcg_amounts = [
        float(c.get("amount", 0) or 0)
        for c in cg
        if isinstance(c, dict) and c.get("type") == "equity_ltcg"
    ]
    if len(ltcg_amounts) < 2:
        return False, (
            f"scenario carries {len(ltcg_amounts)} equity_ltcg entries "
            f"(aggregate fix needs >= 2)"
        )
    # Real math difference, not float noise: per-entry exemption sum vs
    # the once-deducted aggregate.
    per_entry = sum(max(0.0, a - exemption) * rate for a in ltcg_amounts)
    aggregate = max(0.0, sum(ltcg_amounts) - exemption) * rate
    if per_entry == aggregate:
        return False, (
            "per-entry and aggregate 112A taxes coincide "
            f"({per_entry!r}) — no S2-C effect"
        )
    return True, f"112A per-entry {per_entry!r} -> aggregate {aggregate!r}"


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
            # Byte-identical cell. Track in-zone scenarios that the fix
            # leaves untouched (e.g. relief-absorbed) for the report.
            in_zone, _ = _s2c_zone(data)
            if in_zone:
                in_zone_unchanged.append(scenario["id"])
            continue

        # ── Zone validation for every changed cell ──────────────────────
        in_zone, reason = _s2c_zone(data)
        if not in_zone:
            violations.append(
                f"{scenario['id']}: changed OUTSIDE the S2-C zone ({reason})"
            )
            continue

        for regime in ("old_regime", "new_regime"):
            stale, updated = expected[regime], fresh[regime]
            structural = [f for f in STRUCTURAL_FIELDS if stale[f] != updated[f]]
            if structural:
                violations.append(
                    f"{scenario['id']}: {regime} structural pinned field(s) "
                    f"{structural} changed — the CG income slicing must be "
                    f"untouched by S2-C"
                )
        if expected["recommendation"] != fresh["recommendation"]:
            logger.warning(
                "%s: recommendation flips %s -> %s (consequential to the "
                "CG tax change)",
                scenario["id"], expected["recommendation"], fresh["recommendation"],
            )
        if violations:
            continue

        for regime in ("old_regime", "new_regime"):
            stale, updated = expected[regime], fresh[regime]
            if stale["total_tax"] != updated["total_tax"]:
                logger.info(
                    "  %s %s.total_tax: %r -> %r",
                    scenario["id"], regime, stale["total_tax"], updated["total_tax"],
                )

        note = scenario.get("note")
        scenario["note"] = (
            f"{note}; {NOTE_S2C}" if note and NOTE_S2C not in note else NOTE_S2C
        )
        expected.update(fresh)
        changed.append((scenario["id"], reason))

    if violations:
        # STOP condition: never write a fixture with an out-of-zone change.
        for v in violations:
            logger.error("ZONE VIOLATION (no write performed): %s", v)
        return 2

    logger.info(
        "Changed cells: %d of %d scenarios (%d in-zone scenarios unchanged — "
        "relief/band absorbed or already-agreeing cells)",
        len(changed), len(fixture["scenarios"]), len(in_zone_unchanged),
    )
    for sid, reason in changed:
        logger.info("  %s -> %s", sid, reason)

    if dry_run:
        logger.info("Dry run: fixture NOT written.")
        return 0

    fixture["meta"]["s2c_update"] = {
        "commit": _git_short_sha(),
        "description": (
            "Step C (tax-expert rulings R-e/R-f, 2026-10-31): only the "
            "annotated cells were re-pinned — the Section 112A ₹1,25,000 "
            "exemption is now deducted ONCE across the AGGREGATE of all "
            "equity_ltcg entries (12.5% on the excess) instead of per "
            "entry. STCG/property cells and every CG-income-derived pin "
            "are byte-identical to the A2 snapshot; verify with git diff."
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

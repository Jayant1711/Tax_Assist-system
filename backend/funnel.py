# Summer internship project
"""Sprint 4 P0 — conversation funnel analytics.

Spec: docs/sprint4-execution.md P0 item 5. Reads the LIVE session store
(db.app_sessions) and reports, per discovery phase:

- sessions per phase (the phase each session is in RIGHT NOW),
- turns per phase (from the state's ``history`` length — the NLP
  conversation log the engine appends to every turn),
- completion rate (sessions whose phase is FINAL),
- drop-off per phase transition.

Phase order is the engine's machine (nlp_engine.process_message sets
PROFILING / INCOME / EXPENDITURE / FINAL). ``reached`` counts a session
toward every phase up to and including its current one — this assumes
the documented monotone phase advance (the engine only moves phases
forward; the frontend stepper's RECALL phase is never produced, per
docs/architecture.md §4).

Output: a JSON report (funnel_json) and a rendered markdown table
(funnel_markdown). CLI: ``python -m funnel`` prints the markdown report
from the live store (``--json`` for machine-readable output); tests run
against a seeded temp store via TAX_DB_PATH + db.init_db().
"""
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if __package__ in (None, ""):  # direct script execution: python funnel.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import db

logger = logging.getLogger(__name__)

PHASES: Tuple[str, ...] = ("PROFILING", "INCOME", "EXPENDITURE", "FINAL")
FINAL_PHASE = "FINAL"

_TRANSITIONS = tuple(
    f"{PHASES[i]}->{PHASES[i + 1]}" for i in range(len(PHASES) - 1)
)


def collect_rows(store=None) -> Tuple[List[dict], int]:
    """Read every app_sessions row; parse the state JSON.

    Returns (rows, skipped) where rows are
    ``{"id", "phase", "turns"}`` dicts and *skipped* counts rows whose
    state column is not parseable JSON (never fatal — a corrupt row is
    reported, not crashed on).
    """
    store = store if store is not None else db
    rows: List[dict] = []
    skipped = 0
    for row in store.query_all(
            "SELECT id, state FROM app_sessions ORDER BY created_at"):
        try:
            state = json.loads(row["state"])
            if not isinstance(state, dict):
                raise ValueError("state is not a JSON object")
        except (ValueError, TypeError) as exc:
            logger.warning("funnel: skipping unreadable session state "
                           "(%s): %s", row["id"][:8], exc)
            skipped += 1
            continue
        rows.append({
            "id": row["id"],
            "phase": state.get("phase"),
            "turns": len(state.get("history") or []),
        })
    return rows, skipped


def compute_funnel(rows: List[dict], skipped: int = 0) -> dict:
    """Aggregate funnel metrics from collected rows (pure)."""
    sessions_per_phase = {phase: 0 for phase in PHASES}
    unknown_phases: Dict[str, int] = {}
    turns_per_phase = {
        phase: {"total": 0, "avg": 0.0} for phase in PHASES
    }
    reached = {phase: 0 for phase in PHASES}
    _phase_index = {phase: i for i, phase in enumerate(PHASES)}

    for row in rows:
        phase = row["phase"]
        turns = row["turns"]
        if phase in _phase_index:
            sessions_per_phase[phase] += 1
            turns_per_phase[phase]["total"] += turns
            for phase_up_to in PHASES[:_phase_index[phase] + 1]:
                reached[phase_up_to] += 1
        else:
            key = str(phase) if phase is not None else "(missing)"
            unknown_phases[key] = unknown_phases.get(key, 0) + 1

    total = len(rows)
    for phase in PHASES:
        count = sessions_per_phase[phase]
        turns_per_phase[phase]["avg"] = (
            turns_per_phase[phase]["total"] / count) if count else 0.0

    dropoff = {}
    for i, transition in enumerate(_TRANSITIONS):
        dropped = reached[PHASES[i]] - reached[PHASES[i + 1]]
        dropoff[transition] = {
            "dropped": dropped,
            "rate": (dropped / reached[PHASES[i]])
            if reached[PHASES[i]] else 0.0,
        }

    completed = sessions_per_phase[FINAL_PHASE]
    return {
        "phases": list(PHASES),
        "total_sessions": total,
        "sessions_per_phase": sessions_per_phase,
        "unknown_phases": unknown_phases,
        "turns_per_phase": turns_per_phase,
        "reached": reached,
        "dropoff": dropoff,
        "completed_sessions": completed,
        "completion_rate": (completed / total) if total else 0.0,
        "malformed_state_rows": skipped,
    }


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)


def to_markdown(report: dict) -> str:
    # defensive reads: injected summaries may carry only the headline keys
    reached = report.get("reached", {})
    turns_per_phase = report.get("turns_per_phase", {})
    dropoff = report.get("dropoff", {})
    sessions_per_phase = report.get(
        "sessions_per_phase",
        {p: 0 for p in report.get("phases", [])})
    lines = [
        "# Funnel report",
        "",
        f"Total sessions: {report['total_sessions']}  |  "
        f"completed (FINAL): {report['completed_sessions']}  |  "
        f"completion rate: {report['completion_rate']:.1%}",
    ]
    if report.get("malformed_state_rows"):
        lines.append(
            f"Unreadable state rows skipped: "
            f"{report['malformed_state_rows']}")
    if report.get("unknown_phases"):
        rendered = ", ".join(
            f"{phase}: {count}"
            for phase, count in sorted(report["unknown_phases"].items()))
        lines.append(f"Unknown phases: {rendered}")
    lines += [
        "",
        "| Phase | Sessions (current) | Reached | Total turns | "
        "Avg turns | Drop-off from previous | Drop-off rate |",
        "|---|---|---|---|---|---|---|",
    ]
    previous = None
    for phase in report["phases"]:
        if previous is None:
            drop_cell, rate_cell = "—", "—"
        else:
            stats = dropoff.get(f"{previous}->{phase}",
                                {"dropped": 0, "rate": 0.0})
            drop_cell = str(stats["dropped"])
            rate_cell = f"{stats['rate']:.1%}"
        turns = turns_per_phase.get(phase, {"total": 0, "avg": 0.0})
        lines.append(
            f"| {phase} | {sessions_per_phase[phase]} | "
            f"{reached.get(phase, 0)} | {turns['total']} | "
            f"{turns['avg']:.1f} | {drop_cell} | {rate_cell} |")
        previous = phase
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    rows, skipped = collect_rows()
    report = compute_funnel(rows, skipped=skipped)
    if "--json" in argv:
        print(to_json(report))
    else:
        print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

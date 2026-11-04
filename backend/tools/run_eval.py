# Summer internship project
"""Run the P0 evaluation framework over the eval split — CLI runner.

The nlp_eval module is a library (driven by tests); this tool makes the
measurement reproducible from the command line:

    python tools/run_eval.py                      # eval split (data/validation)
    python tools/run_eval.py --split training     # any split directory
    python tools/run_eval.py --save baseline.json # persist a baseline JSON

Output: a human-readable report on stdout (micro/macro P/R/F1, per-category
table, gate verdict, confusion matrix) plus a machine-readable JSON when
--save is given. The ground truth is ALWAYS the committed corpus labels —
never invented (ADR-001 boundary: measurement only, no behavior change).

Sprint 4 P0/P2 — docs/sprint4-execution.md §P2 output requirement:
"Output: KEEP/IMPROVE/REPLACE verdict per NLP component, recorded in
NLP_Evaluation_Report.md".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nlp_eval  # noqa: E402


def load_split(data_dir: Path, split: str) -> List[dict]:
    """Load every JSONL record of a split directory (sorted, stable)."""
    records: List[dict] = []
    split_dir = data_dir / split
    for path in sorted(split_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if isinstance(rec, dict):
                    records.append(rec)
    return records


def render_report(report: dict, split: str) -> str:
    """Human-readable rendering of an nlp_eval report dict."""
    lines: List[str] = []
    gate = report.get("gate") or {}
    lines.append(f"NLP EXTRACTION EVALUATION — split '{split}'")
    lines.append(f"records: {report['record_count']}  "
                 f"labeled spans: {report['labeled_span_count']}  "
                 f"predicted spans: {report['predicted_span_count']}  "
                 f"matched: {report['matched_span_count']}")
    micro = report["micro"]
    lines.append(f"MICRO  P={micro['precision']}  R={micro['recall']}  "
                 f"F1={micro['f1']}")
    macro = report["macro"]
    lines.append(f"MACRO  P={macro['precision']}  R={macro['recall']}  "
                 f"F1={macro['f1']}")
    mb = report.get("macro_bookable") or {}
    lines.append(f"MACRO (bookable only)  P={mb.get('precision')}  "
                 f"R={mb.get('recall')}  F1={mb.get('f1')}")
    lines.append("")
    lines.append(f"{'category':<16}{'true':>7}{'pred':>7}{'P':>9}{'R':>9}{'F1':>9}")
    for cat in sorted(report["per_category"]):
        st = report["per_category"][cat]
        lines.append(f"{cat:<16}{st['support_true']:>7}{st['support_pred']:>7}"
                     f"{str(st['precision']):>9}{str(st['recall']):>9}"
                     f"{str(st['f1']):>9}")
    lines.append("")
    lines.append(f"GATE (>= {gate.get('threshold')}): "
                 f"{'PASS' if gate.get('pass') else 'FAIL'}"
                 f"{'  failing: ' + ', '.join(gate['failing']) if gate.get('failing') else ''}")
    if report.get("errors"):
        lines.append(f"pipeline errors: {len(report['errors'])}")
        for e in report["errors"][:10]:
            lines.append(f"  {e['id']}: {e['error']}")
    cm = report.get("confusion_matrix") or {}
    cats = cm.get("labels") or []
    rows = cm.get("matrix") or {}
    if cats:
        lines.append("")
        lines.append("true\\pred".ljust(16) + "".join(c.ljust(14) for c in cats))
        for i, true_cat in enumerate(cats):
            row = rows[i] if i < len(rows) else []
            cells = "".join(str(row[j] if j < len(row) else 0).ljust(14)
                            for j in range(len(cats)))
            lines.append(true_cat.ljust(16) + cells)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="validation",
                        help="split directory under data/ (default: validation)")
    parser.add_argument("--save", default=None,
                        help="optional path for the baseline JSON")
    parser.add_argument("--out", default=None,
                        help="optional path for the markdown report")
    args = parser.parse_args()

    data_dir = Path(__file__).resolve().parents[2] / "data"
    records = load_split(data_dir, args.split)
    if not records:
        print(f"no records found in {data_dir / args.split}", file=sys.stderr)
        return 2

    report = nlp_eval.evaluate_extraction(records)
    text = render_report(report, args.split)
    print(text)

    if args.save:
        nlp_eval.save_baseline(report, args.save,
                               baseline_name=f"sprint4-p1-{args.split}")
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

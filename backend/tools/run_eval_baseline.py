# Summer internship project
"""Sprint 4 P0 — eval baseline runner.

Runs the extraction eval (nlp_eval.evaluate_extraction) on the eval
split (data/validation) with the CURRENT deterministic pipeline and
persists the report as the named baseline JSON (default
``data/baseline_sprint3.json``). This file is THE P/R number P1 must
improve against (docs/sprint4-execution.md P0 item 3 + P1 gate).

Usage (from backend/):
    python tools/run_eval_baseline.py                     # sprint3 baseline
    python tools/run_eval_baseline.py --name sprint4_p1   # P1's own baseline
    python tools/run_eval_baseline.py --split test        # holdout, P3 only

Prints the health summary (micro/macro + the gate table) to stdout.
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import corpus  # noqa: E402
import nlp_eval  # noqa: E402


def run(baseline_name: str = nlp_eval.BASELINE_NAME,
        split: str = corpus.EVAL_SPLIT,
        out_path: Optional[Path] = None,
        threshold: float = nlp_eval.GATE_THRESHOLD) -> dict:
    records = corpus.load_split(split)
    report = nlp_eval.evaluate_extraction(records)
    path = out_path or (corpus.dataset_root()
                        / f"baseline_{baseline_name}.json")
    payload = nlp_eval.save_baseline(report, path,
                                     baseline_name=baseline_name)
    gate = nlp_eval.gate_report(report, threshold=threshold)
    payload["gate"]["threshold"] = gate["threshold"]
    return payload


def _print_summary(payload: dict) -> None:
    print("=" * 64)
    print(f"Extraction eval baseline — {payload['baseline_name']}")
    print("=" * 64)
    print(f"records: {payload['record_count']}  "
          f"labeled spans: {payload['labeled_span_count']}  "
          f"predicted: {payload['predicted_span_count']}  "
          f"matched: {payload['matched_span_count']}")
    micro, macro = payload["micro"], payload["macro"]
    print(f"micro  P={micro['precision']:.4f} "
          f"R={micro['recall']:.4f} F1={micro['f1']:.4f}")
    print(f"macro  P={macro['precision']:.4f} "
          f"R={macro['recall']:.4f} F1={macro['f1']:.4f}")
    gate = payload["gate"]
    print(f"gate (>= {gate['threshold']:.0%} on income heads + major "
          f"sections): {'PASS' if gate['pass'] else 'FAIL'}")
    if not gate["pass"]:
        for cat in gate["failing"]:
            stats = gate["categories"][cat]
            p = stats.get("precision")
            r = stats.get("recall")
            print(f"  FAIL {cat:<14} P={p if p is not None else float('nan'):.4f} "
                  f"R={r if r is not None else float('nan'):.4f}")
    print(f"baseline file: data/baseline_{payload['baseline_name']}.json")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=nlp_eval.BASELINE_NAME)
    parser.add_argument("--split", default=corpus.EVAL_SPLIT,
                        choices=("training", "validation", "test"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    payload = run(baseline_name=args.name, split=args.split,
                  out_path=Path(args.out) if args.out else None)
    _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Summer internship project
"""Sprint 4 P0 — Dataset Health Report generator.

Spec: docs/sprint4-execution.md P0 item 6. Reads the committed dataset
(corpus.load_all + manifest.json), the committed eval baseline
(data/baseline_sprint3.json) and the live funnel (funnel.collect_rows on
the app_sessions store), and writes ``Dataset_Health_Report.md`` at the
repository root — totals, per-category coverage vs the floors, source /
language distribution, template diversity, split sizes + leakage status,
the eval baseline summary (the P/R number P1 must improve) and the
funnel baseline.

Usage (from backend/):
    python tools/dataset_health_report.py
    python tools/dataset_health_report.py --out ../Dataset_Health_Report.md
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import corpus  # noqa: E402
import funnel  # noqa: E402
import nlp_eval  # noqa: E402

DEFAULT_REPORT_NAME = "Dataset_Health_Report.md"


def _floor_status(count: int, floor: int) -> str:
    return "met" if count >= floor else f"MISSED ({count}/{floor})"


def generate(out_path: Optional[Path] = None,
             funnel_report: Optional[dict] = None) -> str:
    """Build and write the report; returns the markdown text."""
    root = corpus.dataset_root()
    loaded = corpus.load_all(root)
    manifest = corpus.load_manifest(root)
    quality = corpus.corpus_quality(loaded)
    total = quality["total_records"]

    counts_total = corpus.coverage_counts(
        [r for recs in loaded.values() for r in recs])
    counts_val = corpus.coverage_counts(loaded[corpus.EVAL_SPLIT])
    counts_train = corpus.coverage_counts(loaded["training"])
    counts_test = corpus.coverage_counts(loaded[corpus.HOLDOUT_SPLIT])

    dups = corpus.find_cross_split_duplicates(loaded)
    try:
        corpus.assert_splits_disjoint(manifest)
        disjoint = "OK — template-disjoint and session-disjoint"
    except corpus.CorpusLeakageError as exc:
        disjoint = f"LEAKAGE DETECTED: {exc}"

    hinglish = quality["lang_distribution"]["hinglish"]

    lines: list = []
    lines.append("# Dataset Health Report")
    lines.append("")
    lines.append(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        f"  |  corpus schema v{corpus.CORPUS_SCHEMA_VERSION}  |  "
        f"build seed {manifest['build']['seed']}  |  built "
        f"{manifest['build']['built_on']}")
    lines.append("")
    lines.append("Source of truth: `data/{training,validation,test,corpus}"
                 "/*.jsonl` + `data/manifest.json` (content-addressed; "
                 "byte-identical rebuild pinned by "
                 "`tests/test_nlp_eval.py::"
                 "TestCommittedDatasetMeta::"
                 "test_rebuild_reproduces_the_committed_manifest`).")
    lines.append("")

    # Totals ------------------------------------------------------------
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Total labeled records: **{total}** "
                 f"(spans: **{quality['total_spans']}**)")
    lines.append(f"- Split sizes: training {quality['splits']['training']}, "
                 f"validation {quality['splits']['validation']} (eval "
                 f"split), test {quality['splits']['test']} (holdout), "
                 f"corpus (runtime capture stream) "
                 f"{quality['splits']['corpus']}")
    lines.append(f"- Distinct template families: "
                 f"{quality['template_diversity']['unique_templates']} "
                 f"(max renders per family "
                 f"{quality['template_diversity']['max_renders_per_template']})")
    lines.append("")

    # Per-category coverage ----------------------------------------------
    lines.append("## Per-category coverage")
    lines.append("")
    lines.append("Floors: >=50 spans per bookable category corpus-wide, "
                 ">=15 in the eval split (validation).")
    lines.append("")
    lines.append("| Category | Total | Training | Validation | Test | "
                 "Floor 50 | Eval floor 15 |")
    lines.append("|---|---|---|---|---|---|---|")
    missed = []
    for label in corpus.TAXONOMY:
        c_total = counts_total.get(label, 0)
        c_val = counts_val.get(label, 0)
        floor_50 = _floor_status(c_total, corpus.CATEGORY_FLOOR_TOTAL)
        floor_15 = _floor_status(c_val, corpus.CATEGORY_FLOOR_EVAL)
        if "MISSED" in floor_50 or "MISSED" in floor_15:
            missed.append(label)
        lines.append(
            f"| {label} | {c_total} | {counts_train.get(label, 0)} | "
            f"{c_val} | {counts_test.get(label, 0)} | {floor_50} | "
            f"{floor_15} |")
    lines.append("")
    if missed:
        lines.append(f"**Shortfall (synthetic-backed, listed per gate 3): "
                     f"{', '.join(missed)}**")
    else:
        lines.append("All category floors met (synthetic-backed where the "
                     "organic ledger slice is thin — every synthetic record "
                     "carries `provenance.note`).")
    lines.append("")

    # Distribution --------------------------------------------------------
    lines.append("## Source and language distribution")
    lines.append("")
    sources = quality["source_distribution"]
    lines.append(f"- Sources: synthetic {sources['synthetic']} "
                 f"({sources['synthetic'] / total:.1%}), ledger "
                 f"{sources['ledger']} ({sources['ledger'] / total:.1%}), "
                 f"organic {sources['organic']} "
                 f"({sources['organic'] / total:.1%})")
    lines.append(f"- Languages: en {quality['lang_distribution']['en']} "
                 f"({quality['lang_distribution']['en'] / total:.1%}), "
                 f"hinglish {hinglish} ({hinglish / total:.1%} — the "
                 f"mandatory Hinglish slice)")
    lines.append("")

    # Leakage ---------------------------------------------------------------
    lines.append("## Split integrity / leakage")
    lines.append("")
    lines.append(f"- Manifest disjointness: {disjoint}")
    lines.append(f"- Cross-split near-duplicates (normalized-text hash): "
                 f"**{len(dups)}**")
    lines.append("- Ledger gold labels (docs/nlp-pipeline.md §11 + the "
                 "Sprint 2/3 ledger items) are eval material only: never "
                 "written to the training split.")
    lines.append("")

    # Eval baseline ---------------------------------------------------------
    baseline_path = root / f"baseline_{nlp_eval.BASELINE_NAME}.json"
    lines.append(f"## Eval baseline ({nlp_eval.BASELINE_NAME})")
    lines.append("")
    if baseline_path.exists():
        with open(baseline_path, encoding="utf-8") as handle:
            baseline = json.load(handle)
        micro, macro = baseline["micro"], baseline["macro"]
        gate = baseline.get("gate", {})
        lines.append(f"- Pipeline: {baseline.get('pipeline', 'n/a')}")
        lines.append(f"- Records evaluated: {baseline['record_count']} "
                     f"({corpus.EVAL_SPLIT} split)")
        lines.append(f"- Micro: P={micro['precision']:.4f} "
                     f"R={micro['recall']:.4f} F1={micro['f1']:.4f}")
        lines.append(f"- Macro: P={macro['precision']:.4f} "
                     f"R={macro['recall']:.4f} F1={macro['f1']:.4f}")
        failing = gate.get("failing", [])
        lines.append(
            f"- Gate (>= {gate.get('threshold', 0.95):.0%} on income "
            f"heads + major sections): "
            f"{'PASS' if gate.get('pass') else 'FAIL'}"
            + (f" — failing: {', '.join(failing)}" if failing else ""))
        lines.append("- This is THE P/R number P1 must improve "
                     "(docs/sprint4-execution.md P1 gate).")
    else:
        lines.append(f"- baseline_{nlp_eval.BASELINE_NAME}.json not found "
                     f"under {root} — run tools/run_eval_baseline.py.")
    lines.append("")
    lines.append("**Eval-marker flip plan:** the >=95% gate ships ADVISORY "
                 "(`pytest -m eval` reports it; the default run excludes it "
                 "via `addopts = -m \"not eval\"` in backend/pytest.ini). At "
                 "the P1 verdict the exclusion is removed so the gate binds "
                 "in CI (red = merge blocker).")
    lines.append("")

    # Funnel ------------------------------------------------------------
    lines.append("## Funnel baseline (live session store)")
    lines.append("")
    if funnel_report is None:
        rows, skipped = funnel.collect_rows()
        funnel_report = funnel.compute_funnel(rows, skipped=skipped)
    lines.append(f"- Sessions: {funnel_report['total_sessions']}  |  "
                 f"completed (FINAL): {funnel_report['completed_sessions']}  "
                 f"|  completion rate: "
                 f"{funnel_report['completion_rate']:.1%}")
    lines.append("")
    lines.append("### Funnel detail (live store)")
    lines.append("")
    lines.append(funnel.to_markdown(funnel_report).replace(
        "# Funnel report\n", ""))

    text = "\n".join(lines)
    if out_path is None:
        out_path = (corpus.dataset_root().parent / DEFAULT_REPORT_NAME)
    out_path = Path(out_path)
    out_path.write_text(text, encoding="utf-8")
    print(f"Dataset health report written to {out_path}")
    return text


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None,
                        help=f"output path (default: repo root / "
                             f"{DEFAULT_REPORT_NAME})")
    args = parser.parse_args(argv)
    generate(out_path=Path(args.out) if args.out else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

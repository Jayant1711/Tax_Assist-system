# Summer internship project
"""Sprint 4 P0 — NLP extraction evaluation framework.

Spec: docs/sprint4-execution.md P0 item 3. Measures the CURRENT
deterministic pipeline (nlp_engine.NLPEngine.process_message) against the
labeled corpus (corpus.py): per-category precision/recall/F1 (macro +
micro), the 21x21 confusion matrix (20 bookable categories + ABSTAIN),
and per-record span correctness.

Design:

- **Pure metric core**: :func:`evaluate_predictions` maps predictions to
  records and computes every metric. It is deliberately decoupled from
  the pipeline so the metric self-tests can drive it with hand-built
  predictions (perfect / known-bad / shuffled canaries) — if the metric
  cannot distinguish a sabotaged predictor from a correct one, the
  metric design has failed.
- **Pipeline adapter**: :func:`evaluate_extraction` runs
  ``pipeline(text, session)`` per record (turn records sequentially
  through ONE session) and reads the booked session keys via the
  corpus.CATEGORY_SESSION_KEYS mapping.
- **Amount-anchored matching**: a labeled span matches a predicted span
  with the same booked amount; same amount + different category is the
  confusion cell (true -> predicted). A labeled span with no booking at
  its amount counts as predicted-ABSTAIN (the pipeline effectively
  abstained); a booking with no labeled span at its amount is spurious
  (true ABSTAIN -> predicted). Correct abstentions (labeled ABSTAIN,
  nothing booked) are true negatives on the ABSTAIN diagonal.
- **Amounts** compare as booked rupees (int-rounded): labels are
  post-annualization, post-clamp values — the documented ADR-001
  derivations — so annualized monthly utterances compare exactly.

The >=95% gate (income heads + major deduction sections) is implemented
by :func:`gate_report`; the advisory pytest wrapper lives in
tests/test_nlp_eval.py marked ``eval`` (excluded from the default run
until P1's verdict — flip plan documented there and in pytest.ini).
"""
import json
import logging
import random
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import corpus

logger = logging.getLogger(__name__)

GATE_THRESHOLD = 0.95

# docs/Sprint4_AI_Modernization.md §3: ">=95% target on income heads
# (salary, business, rental, other_income, agriculture, capital_gains)
# and the major deduction sections (80C, 80D, 80E, 80G, 80TTA/TTB, NPS,
# HRA, 24B, 80U/80DD, 80DDB)". HRA covers both Sprint-2 split legs; the
# 80D family includes 80d_parents. 80GG is measured but not gated (the
# §3 list does not name it).
INCOME_HEADS: Tuple[str, ...] = (
    "salary", "business", "rental", "other_income", "agriculture",
    "capital_gains",
)
MAJOR_SECTIONS: Tuple[str, ...] = (
    "80c", "80d", "80d_parents", "80e", "80g", "80tta", "80ttb", "nps",
    "hra_received", "rent_paid", "24b", "80u_80dd", "80ddb",
)
GATE_CATEGORIES: Tuple[str, ...] = INCOME_HEADS + MAJOR_SECTIONS

SpanKey = Tuple[str, Optional[int]]  # (category, amount|None)


# ---------------------------------------------------------------------------
# Prediction extraction from a booked session
# ---------------------------------------------------------------------------

def predicted_session_spans(session: Dict) -> List[SpanKey]:
    """The (category, amount) spans the pipeline booked into *session*.

    Numeric bookable keys -> (category, round(amount)); the
    capital_gains list -> one span per entry; the 80U/80DD enum counts
    as an (80u_80dd, None) span only when no numeric amount was booked
    (the enum is the primary collection for the flat deduction).
    """
    spans: List[SpanKey] = []
    for category, keys in corpus.CATEGORY_SESSION_KEYS.items():
        for key in keys:
            value = session.get(key)
            if isinstance(value, bool) or \
                    not isinstance(value, (int, float)):
                continue
            spans.append((category, int(round(float(value)))))
    gains = session.get("capital_gains")
    if isinstance(gains, list):
        for entry in gains:
            if not isinstance(entry, dict):
                continue
            amount = entry.get("amount")
            if isinstance(amount, bool) or \
                    not isinstance(amount, (int, float)):
                continue
            spans.append(("capital_gains", int(round(float(amount)))))
    if not any(cat == "80u_80dd" for cat, _ in spans):
        if isinstance(session.get("80u_80dd_category"), str):
            spans.append(("80u_80dd", None))
    return spans


def _amount_key(amount) -> Optional[int]:
    if amount is None:
        return None
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise corpus.CorpusSchemaError(
            f"span.amount must be a number or null, got {amount!r}")
    return int(round(float(amount)))


# ---------------------------------------------------------------------------
# Amount-anchored matching (pure)
# ---------------------------------------------------------------------------

def _match_record(labeled: List[SpanKey],
                  predicted: List[SpanKey]) -> Tuple[Dict[SpanKey, int],
                                                     Dict[str, int]]:
    """Multiset-match labeled spans to predicted spans by amount.

    Returns (confusion cell increments, per-record counters). Cells are
    (true_category, predicted_category) with ABSTAIN as the pseudo
    prediction for missed spans and the pseudo truth for spurious ones.
    """
    cells: Dict[SpanKey, int] = {}
    counters = {"matched": 0, "misclassified": 0, "missed": 0,
                "spurious": 0}
    unconsumed = list(predicted)

    def consume(pred_cat, pred_amt):
        for i, (cat, amt) in enumerate(unconsumed):
            if cat == pred_cat and amt == pred_amt:
                del unconsumed[i]
                return True
        return False

    remaining_labeled = []
    for lab_cat, lab_amt in labeled:  # pass 1: exact category + amount
        if consume(lab_cat, lab_amt):
            cells[(lab_cat, lab_cat)] = cells.get((lab_cat, lab_cat), 0) + 1
            counters["matched"] += 1
        else:
            remaining_labeled.append((lab_cat, lab_amt))

    still_remaining = []
    for lab_cat, lab_amt in remaining_labeled:  # pass 2: same amount,
        hit = None                              # different category
        for i, (cat, amt) in enumerate(unconsumed):
            if amt == lab_amt and lab_amt is not None:
                hit = i
                break
        if hit is not None:
            pred_cat, _ = unconsumed.pop(hit)
            cells[(lab_cat, pred_cat)] = \
                cells.get((lab_cat, pred_cat), 0) + 1
            counters["misclassified"] += 1
        else:
            still_remaining.append((lab_cat, lab_amt))

    for lab_cat, _lab_amt in still_remaining:  # pass 3: missed -> ABSTAIN
        cells[(lab_cat, corpus.ABSTAIN)] = \
            cells.get((lab_cat, corpus.ABSTAIN), 0) + 1
        counters["missed"] += 1
    for pred_cat, _pred_amt in unconsumed:     # spurious -> true ABSTAIN
        cells[(corpus.ABSTAIN, pred_cat)] = \
            cells.get((corpus.ABSTAIN, pred_cat), 0) + 1
        counters["spurious"] += 1
    return cells, counters


# ---------------------------------------------------------------------------
# Pure metric core
# ---------------------------------------------------------------------------

def evaluate_predictions(records: Sequence[dict],
                         predictions: Dict[str, List[SpanKey]]) -> dict:
    """Compute the full metric report for per-record predictions.

    *predictions* maps record id -> the (category, amount) spans the
    predictor produced for that record. Pure: no pipeline is run.
    """
    labels = list(corpus.TAXONOMY)
    matrix = {t: {p: 0 for p in labels} for t in labels}
    record_details = []
    totals = {"labeled": 0, "predicted": 0, "matched": 0,
              "misclassified": 0, "missed": 0, "spurious": 0}

    for record in records:
        rid = record["id"]
        labeled = [(span["category"], _amount_key(span["amount"]))
                   for span in record.get("spans") or []]
        predicted = [(cat, amt) for cat, amt in
                     predictions.get(rid, [])]
        cells, counters = _match_record(labeled, predicted)
        for (true_cat, pred_cat), count in cells.items():
            matrix[true_cat][pred_cat] += count
        for key in ("matched", "misclassified", "missed", "spurious"):
            totals[key] += counters[key]
        totals["labeled"] += len(labeled)
        totals["predicted"] += len(predicted)
        record_details.append({
            "id": rid,
            "correct": (counters["matched"] == len(labeled)
                        and counters["spurious"] == 0
                        and counters["misclassified"] == 0),
            "labeled": len(labeled),
            "matched": counters["matched"],
            "misclassified": counters["misclassified"],
            "missed": counters["missed"],
            "spurious": counters["spurious"],
        })

    per_category = {}
    for cat in labels:
        tp = matrix[cat][cat]
        row = sum(matrix[cat].values())          # true labels of cat
        col = sum(matrix[t][cat] for t in labels)  # predictions of cat
        precision = (tp / col) if col > 0 else None
        recall = (tp / row) if row > 0 else None
        f1 = None
        if precision is not None and recall is not None:
            f1 = (2 * precision * recall / (precision + recall)
                  if (precision + recall) > 0 else 0.0)
        per_category[cat] = {
            "precision": precision, "recall": recall, "f1": f1,
            "tp": tp, "support_true": row, "support_pred": col,
        }

    tp_total = totals["matched"]
    micro = {
        "precision": (tp_total / totals["predicted"])
        if totals["predicted"] else None,
        "recall": (tp_total / totals["labeled"])
        if totals["labeled"] else None,
        "tp": tp_total,
        "predicted": totals["predicted"],
        "labeled": totals["labeled"],
    }
    micro["f1"] = _harmonic(micro["precision"], micro["recall"])

    def _macro(cats: Sequence[str]) -> dict:
        ps = [per_category[c]["precision"] for c in cats
              if per_category[c]["precision"] is not None]
        rs = [per_category[c]["recall"] for c in cats
              if per_category[c]["recall"] is not None]
        fs = [per_category[c]["f1"] for c in cats
              if per_category[c]["f1"] is not None]
        return {
            "precision": sum(ps) / len(ps) if ps else None,
            "recall": sum(rs) / len(rs) if rs else None,
            "f1": sum(fs) / len(fs) if fs else None,
            "labels_with_support": [
                c for c in cats
                if per_category[c]["support_true"] > 0
                or per_category[c]["support_pred"] > 0
            ],
        }

    supported = [c for c in labels
                 if per_category[c]["support_true"] > 0
                 or per_category[c]["support_pred"] > 0]
    macro = _macro(supported)
    macro_bookable = _macro([c for c in corpus.BOOKABLE_CATEGORIES
                             if c in supported])

    return {
        "record_count": len(records),
        "correct_record_count": sum(
            1 for r in record_details if r["correct"]),
        "labeled_span_count": totals["labeled"],
        "predicted_span_count": totals["predicted"],
        "matched_span_count": totals["matched"],
        "micro": micro,
        "macro": macro,
        "macro_bookable": macro_bookable,
        "per_category": per_category,
        "confusion_matrix": {"labels": labels, "matrix": [
            [matrix[t][p] for p in labels] for t in labels]},
        "records": record_details,
    }


def _harmonic(p: Optional[float], r: Optional[float]) -> Optional[float]:
    if p is None or r is None:
        return None
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


# ---------------------------------------------------------------------------
# Pipeline adapter
# ---------------------------------------------------------------------------

_pipeline_singleton = None


def default_pipeline() -> Callable[[str, Dict], Dict]:
    """The CURRENT deterministic extraction pipeline (lazy singleton)."""
    global _pipeline_singleton
    if _pipeline_singleton is None:
        from nlp_engine import NLPEngine

        _pipeline_singleton = NLPEngine().process_message
    return _pipeline_singleton


def run_pipeline(records: Sequence[dict],
                 pipeline: Callable[[str, Dict], Dict]) -> Dict[str,
                                                                List[SpanKey]]:
    """Run *pipeline* per record (turn records sequentially through ONE
    session) and return {record_id: predicted spans}.

    A pipeline exception on one record never aborts the run: the record
    is reported with an error note and empty predictions.
    """
    predictions: Dict[str, List[SpanKey]] = {}
    for record in records:
        session: Dict = {"id": f"eval_{record['id']}"}
        error = None
        try:
            if "turns" in record:
                for turn in record["turns"]:
                    pipeline(turn["text"], session)
            else:
                pipeline(record["text"], session)
        except Exception as exc:  # noqa: BLE001 — eval must not crash
            error = f"{type(exc).__name__}: {exc}"
            logger.warning("eval pipeline error on record %s: %s",
                           record["id"], error)
        predictions[record["id"]] = predicted_session_spans(session)
        record["_eval_error"] = error
    return predictions


def evaluate_extraction(records: Sequence[dict],
                        pipeline: Optional[Callable[[str, Dict], Dict]]
                        = None) -> dict:
    """Evaluate *records* against the extraction *pipeline* (default:
    the current NLPEngine.process_message)."""
    pipeline = pipeline if pipeline is not None else default_pipeline()
    predictions = run_pipeline(records, pipeline)
    report = evaluate_predictions(records, predictions)
    report["errors"] = [
        {"id": r["id"], "error": r["_eval_error"]}
        for r in records if r.get("_eval_error")
    ]
    for r in records:
        r.pop("_eval_error", None)
    return report


# ---------------------------------------------------------------------------
# Canary predictors (for the metric self-tests and gate demos)
# ---------------------------------------------------------------------------

def label_predictions(records: Sequence[dict]) -> Dict[str, List[SpanKey]]:
    """The PERFECT predictor: the labels themselves."""
    return {r["id"]: [(s["category"], _amount_key(s["amount"]))
                      for s in r.get("spans") or []]
            for r in records}


def shuffled_predictions(records: Sequence[dict],
                         seed: int) -> Dict[str, List[SpanKey]]:
    """The CHANCE predictor: label spans permuted across records with a
    seeded RNG (deterministic in *seed*)."""
    rng = random.Random(seed)
    pool = [list(spans) for spans in label_predictions(records).values()]
    rng.shuffle(pool)
    shuffled: Dict[str, List[SpanKey]] = {}
    for record, spans in zip(records, pool):
        shuffled[record["id"]] = spans
    return shuffled


def sabotaged_predictions(records: Sequence[dict],
                          category: str = "other_income") \
        -> Dict[str, List[SpanKey]]:
    """The KNOWN-BAD predictor: every span booked to one fixed wrong
    category at the right amount (category resolution destroyed)."""
    return {
        r["id"]: [(category,
                   s["amount"] if s["amount"] is not None else 0)
                  for s in r.get("spans") or []]
        for r in records
    }


# ---------------------------------------------------------------------------
# The >=95% gate
# ---------------------------------------------------------------------------

def gate_report(report: dict,
                threshold: float = GATE_THRESHOLD) -> dict:
    """Income-head + major-section gate: every gate category with any
    support must reach *threshold* precision AND recall.

    - no truth and no predictions -> excluded (nothing to get right);
    - predictions but no truth (or vice versa) -> the category FAILS.
    """
    categories = {}
    failing = []
    for cat in GATE_CATEGORIES:
        stats = report["per_category"].get(cat, {})
        support_true = stats.get("support_true", 0)
        support_pred = stats.get("support_pred", 0)
        if support_true == 0 and support_pred == 0:
            categories[cat] = {"pass": None, "excluded": True,
                               "precision": stats.get("precision"),
                               "recall": stats.get("recall")}
            continue
        precision = stats.get("precision")
        recall = stats.get("recall")
        passed = (precision is not None and precision >= threshold) and \
                 (recall is None or recall >= threshold)
        categories[cat] = {"pass": passed, "excluded": False,
                           "precision": precision, "recall": recall,
                           "support_true": support_true,
                           "support_pred": support_pred}
        if not passed:
            failing.append(cat)
    return {
        "threshold": threshold,
        "income_heads": list(INCOME_HEADS),
        "major_sections": list(MAJOR_SECTIONS),
        "categories": categories,
        "failing": sorted(failing),
        "pass": not failing,
    }


# ---------------------------------------------------------------------------
# Baseline persistence
# ---------------------------------------------------------------------------

BASELINE_NAME = "sprint3"
PIPELINE_DESCRIPTION = (
    "NLPEngine.process_message (the current deterministic pipeline, "
    "keyword-proximity attention + scripted waterfall), pre-P1"
)


def save_baseline(report: dict, path, baseline_name: str = BASELINE_NAME,
                  pipeline_description: str = PIPELINE_DESCRIPTION) -> dict:
    """Persist the eval report as the named baseline (JSON)."""
    payload = {
        "baseline_name": baseline_name,
        "pipeline": pipeline_description,
        "record_count": report["record_count"],
        "labeled_span_count": report["labeled_span_count"],
        "predicted_span_count": report["predicted_span_count"],
        "matched_span_count": report["matched_span_count"],
        "micro": report["micro"],
        "macro": report["macro"],
        "macro_bookable": report["macro_bookable"],
        "per_category": report["per_category"],
        "confusion_matrix": report["confusion_matrix"],
        "gate": gate_report(report),
    }
    path = str(path)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    logger.info("eval baseline %s written to %s", baseline_name, path)
    return payload


def load_baseline(path) -> dict:
    with open(str(path), encoding="utf-8") as handle:
        return json.load(handle)

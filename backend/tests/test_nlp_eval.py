"""Sprint 4 P0 — NLP extraction eval framework (backend/nlp_eval.py).

Tests FIRST (AI_RULES.md). Spec: docs/sprint4-execution.md P0 item 3.

Sections:
1. Metric self-tests on a TOY corpus with hand-computed P/R/F1 to 4
   decimals — including a KNOWN-BAD predictor. THE METRIC MUST BE ABLE
   TO FAIL: if the metric cannot distinguish a sabotaged predictor from
   a correct one, the metric design failed (STOP condition).
2. Perfect-predictor (1.0) and label-shuffled (chance) canaries.
3. A real-pipeline canary: the CURRENT pipeline misbooks the P1-gap
   utterance "shares sold for 5 lakhs" — the harness must see the miss.
4. The >=95% income-head + major-section gate, marked ADVISORY
   (pytest.mark.eval — excluded from the default run until P1's verdict;
   run explicitly with `pytest -m eval`).
5. Meta-tests on the COMMITTED dataset: no-leakage, coverage floors,
   rebuild reproducibility, baseline file integrity.

Toy corpus (labels; predictor outputs in TestHandComputedMetrics):

  record  labeled spans     predicted spans   effect
  r1      (A, 100)          (A, 100)          TP for A
  r2      (A, 200)          (B, 200)          confusion A->B
  r3      (B, 300)          (B, 300)          TP for B
  r4      (none)            (A, 400)          spurious: ABSTAIN->A
  r5      (A, 500)          (none)            missed: A->ABSTAIN

  P_A = 1/2 = 0.5000   R_A = 1/3 = 0.3333   F1_A = 0.4000
  P_B = 1/2 = 0.5000   R_B = 1/1 = 1.0000   F1_B = 0.6667
  P_ABSTAIN = 0/1 = 0  R_ABSTAIN = 0/1 = 0  F1_ABSTAIN = 0
  micro: P = 2/4 = 0.5000  R = 2/4 = 0.5000  F1 = 0.5000
  macro(21-label support): P = 1/3 = 0.3333  R = 4/9 = 0.4444
                           F1 = 0.3556
  confusion (rows=true, cols=predicted), labels [A, B, ABSTAIN]:
      A:       [1, 1, 1]
      B:       [0, 1, 0]
      ABSTAIN: [1, 0, 0]
"""
import json
from pathlib import Path

import pytest

import corpus
import nlp_eval
from nlp_eval import evaluate_predictions

A, B = "salary", "80c"  # real taxonomy labels standing in for toy A/B
TOY_LABELS = [A, B, corpus.ABSTAIN]


def _rec(rid, spans):
    return {
        "id": rid,
        "text": f"toy {rid}",
        "source": "synthetic",
        "template_id": f"toy-{rid}",
        "lang": "en",
        "spans": [{"text": str(a), "category": c, "amount": a,
                   "annualized": False}
                  for c, a in spans],
        "provenance": {"builder": "test", "built_on": "2026-11-01",
                       "corpus_version": 1},
    }


TOY_RECORDS = [
    _rec("r1", [(A, 100)]),
    _rec("r2", [(A, 200)]),
    _rec("r3", [(B, 300)]),
    _rec("r4", []),
    _rec("r5", [(A, 500)]),
]


def _pred(cat, amount):
    return (cat, amount)


# ---------------------------------------------------------------------------
# 1. Hand-computed metric self-tests (the metric must be able to fail)
# ---------------------------------------------------------------------------

class TestHandComputedMetrics:
    def setup_method(self) -> None:
        self.predictions = {
            "r1": [_pred(A, 100)],
            "r2": [_pred(B, 200)],
            "r3": [_pred(B, 300)],
            "r4": [_pred(A, 400)],
            "r5": [],
        }
        self.report = evaluate_predictions(TOY_RECORDS, self.predictions)

    def test_precision_recall_f1_per_category(self) -> None:
        per_cat = self.report["per_category"]
        assert per_cat[A]["precision"] == pytest.approx(0.5, abs=1e-4)
        assert per_cat[A]["recall"] == pytest.approx(1 / 3, abs=1e-4)
        assert per_cat[A]["f1"] == pytest.approx(0.4, abs=1e-4)
        assert per_cat[B]["precision"] == pytest.approx(0.5, abs=1e-4)
        assert per_cat[B]["recall"] == pytest.approx(1.0, abs=1e-4)
        assert per_cat[B]["f1"] == pytest.approx(2 / 3, abs=1e-4)
        abstain = per_cat[corpus.ABSTAIN]
        assert abstain["precision"] == pytest.approx(0.0, abs=1e-4)
        assert abstain["recall"] == pytest.approx(0.0, abs=1e-4)
        assert abstain["f1"] == pytest.approx(0.0, abs=1e-4)

    def test_micro_averages(self) -> None:
        micro = self.report["micro"]
        assert micro["precision"] == pytest.approx(0.5, abs=1e-4)
        assert micro["recall"] == pytest.approx(0.5, abs=1e-4)
        assert micro["f1"] == pytest.approx(0.5, abs=1e-4)
        assert micro["tp"] == 2
        assert micro["predicted"] == 4
        assert micro["labeled"] == 4

    def test_macro_averages(self) -> None:
        macro = self.report["macro"]
        assert macro["precision"] == pytest.approx(1 / 3, abs=1e-4)
        assert macro["recall"] == pytest.approx(4 / 9, abs=1e-4)
        assert macro["f1"] == pytest.approx(0.3556, abs=1e-4)

    def test_confusion_matrix(self) -> None:
        cm = self.report["confusion_matrix"]
        labels = cm["labels"]
        matrix = cm["matrix"]
        idx = {label: i for i, label in enumerate(labels)}
        # rows = true, cols = predicted
        assert matrix[idx[A]][idx[A]] == 1          # r1 TP
        assert matrix[idx[A]][idx[B]] == 1          # r2 confusion A->B
        assert matrix[idx[A]][idx[corpus.ABSTAIN]] == 1  # r5 missed
        assert matrix[idx[B]][idx[B]] == 1          # r3 TP
        assert matrix[idx[corpus.ABSTAIN]][idx[A]] == 1  # r4 spurious
        # everything else zero
        total = sum(sum(row) for row in matrix)
        assert total == 5

    def test_known_bad_predictor_is_detectable(self) -> None:
        """THE CANARY: a sabotaged predictor must produce strictly worse
        metrics than a perfect one — the metric can fail."""
        perfect = evaluate_predictions(
            TOY_RECORDS,
            {r["id"]: [(s["category"], s["amount"])
                       for s in r["spans"]] for r in TOY_RECORDS},
        )
        assert perfect["micro"]["f1"] == pytest.approx(1.0, abs=1e-4)
        assert self.report["micro"]["f1"] < perfect["micro"]["f1"]
        assert self.report["macro"]["f1"] < perfect["macro"]["f1"]

    def test_every_span_has_a_true_label_in_the_taxonomy(self) -> None:
        assert set(self.report["per_category"]) == set(corpus.TAXONOMY)

    def test_per_record_correctness(self) -> None:
        records = {r["id"]: r for r in self.report["records"]}
        assert records["r1"]["correct"] is True
        assert records["r2"]["correct"] is False
        assert records["r4"]["correct"] is False  # spurious booking
        assert records["r5"]["correct"] is False  # missed span
        assert self.report["correct_record_count"] == 2


# ---------------------------------------------------------------------------
# 2. Perfect + label-shuffled canaries
# ---------------------------------------------------------------------------

class TestCanaries:
    def test_perfect_predictor_scores_one_everywhere(self) -> None:
        predictions = {r["id"]: [(s["category"], s["amount"])
                                 for s in r["spans"]]
                       for r in TOY_RECORDS}
        report = evaluate_predictions(TOY_RECORDS, predictions)
        assert report["micro"]["f1"] == pytest.approx(1.0, abs=1e-4)
        assert report["macro"]["f1"] == pytest.approx(1.0, abs=1e-4)
        matrix = report["confusion_matrix"]["matrix"]
        for i, row in enumerate(matrix):
            for j, cell in enumerate(row):
                if i != j:
                    assert cell == 0

    def test_label_shuffled_predictor_lands_at_chance(self) -> None:
        predictions = nlp_eval.shuffled_predictions(
            TOY_RECORDS, seed=7)
        report = evaluate_predictions(TOY_RECORDS, predictions)
        perfect_f1 = 1.0
        assert report["micro"]["f1"] < perfect_f1
        assert report["micro"]["f1"] < 0.5  # 3-label toy: chance < 0.5
        again = evaluate_predictions(
            TOY_RECORDS, nlp_eval.shuffled_predictions(TOY_RECORDS, seed=7))
        assert again["micro"]["f1"] == pytest.approx(
            report["micro"]["f1"], abs=1e-12)  # deterministic in seed

    def test_sabotaged_pipeline_fails_the_gate(self) -> None:
        """Every span booked to one wrong category: the >=95% gate must
        FAIL — the gate is not decorative."""
        bad = {r["id"]: [( "other_income",
                           s["amount"] if s["amount"] is not None else 0)]
               for r in TOY_RECORDS for s in r["spans"]}
        report = evaluate_predictions(TOY_RECORDS, bad)
        gate = nlp_eval.gate_report(report)
        assert gate["pass"] is False
        assert set(gate["failing"]) >= {"salary"}


# ---------------------------------------------------------------------------
# 3. Real-pipeline canary — the current pipeline must be measurable
# ---------------------------------------------------------------------------

class TestRealPipelineIntegration:
    def test_pipeline_books_the_correct_families(self) -> None:
        records = [
            _rec("ok1", [("salary", 5_000_000)]),
            _rec("ok2", [("80c", 150_000)]),
        ]
        records[0]["text"] = "my salary is 50 lakhs"
        records[1]["text"] = "PPF contribution of 1.5 lakhs"
        report = nlp_eval.evaluate_extraction(records)
        assert report["per_category"]["salary"]["recall"] == \
            pytest.approx(1.0, abs=1e-4)
        assert report["per_category"]["80c"]["recall"] == \
            pytest.approx(1.0, abs=1e-4)

    def test_pipeline_miss_is_visible(self) -> None:
        """P1 item 3: the current pipeline misbooks the noun-form
        'shares sold' — the harness must register the miss (this test
        documents the baseline gap; it flips when P1 lands)."""
        records = [_rec("gap1", [("capital_gains", 500_000)])]
        records[0]["text"] = "shares sold for 5 lakhs"
        report = nlp_eval.evaluate_extraction(records)
        assert report["per_category"]["capital_gains"]["recall"] < 1.0

    def test_turn_records_run_through_one_session(self) -> None:
        rec = _rec("turn1", [("salary", 1_800_000), ("80c", 150_000)])
        rec["turns"] = [
            {"text": "I am a software engineer earning 18 LPA",
             "spans": [{"text": "18 LPA", "category": "salary",
                        "amount": 1_800_000, "annualized": False}]},
            {"text": "1.5 lakhs in PPF",
             "spans": [{"text": "1.5 lakhs", "category": "80c",
                        "amount": 150_000, "annualized": False}]},
        ]
        report = nlp_eval.evaluate_extraction([rec])
        assert report["per_category"]["salary"]["recall"] == \
            pytest.approx(1.0, abs=1e-4)
        assert report["per_category"]["80c"]["recall"] == \
            pytest.approx(1.0, abs=1e-4)

    def test_enum_collection_span_matches(self) -> None:
        rec = _rec("enum1", [("80u_80dd", None)])
        rec["text"] = "I have severe disability"
        report = nlp_eval.evaluate_extraction([rec])
        assert report["per_category"]["80u_80dd"]["recall"] == \
            pytest.approx(1.0, abs=1e-4)

    def test_abstain_span_matches_when_nothing_books(self) -> None:
        rec = _rec("abs1", [(corpus.ABSTAIN, None)])
        rec["text"] = "I am 67 years old"
        report = nlp_eval.evaluate_extraction([rec])
        assert report["per_category"][corpus.ABSTAIN]["recall"] == \
            pytest.approx(1.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 4. The >=95% gate — ADVISORY this wave (pytest.mark.eval)
# ---------------------------------------------------------------------------

@pytest.mark.eval
class TestExtractionGateAdvisory:
    """Run with: pytest -m eval

    ADVISORY until P1's verdict (docs/sprint4-execution.md P0 item 3):
    excluded from the default run via pytest.ini addopts. Flip plan: at
    the P1/P3 verdict the `-m "not eval"` exclusion is removed from
    pytest.ini so this gate BINDS in CI (red = merge blocker), per
    Sprint4_AI_Modernization.md §3 ("a red eval is a merge blocker").
    """

    def test_income_heads_and_major_sections_at_95_percent(self) -> None:
        records = corpus.load_split(corpus.EVAL_SPLIT)
        report = nlp_eval.evaluate_extraction(records)
        gate = nlp_eval.gate_report(report)
        assert gate["pass"], (
            "income-head/major-section gate below "
            f"{gate['threshold']:.0%}: failing = {gate['failing']}"
        )


# ---------------------------------------------------------------------------
# 5. Meta-tests on the committed dataset (default run)
# ---------------------------------------------------------------------------

class TestCommittedDatasetMeta:
    def test_committed_dataset_loads_and_validates(self) -> None:
        loaded = corpus.load_all()
        assert set(loaded) == {"training", "validation", "test", "corpus"}
        total = sum(len(v) for v in loaded.values())
        assert total >= 1000

    def test_no_leakage_in_the_committed_dataset(self) -> None:
        manifest = corpus.load_manifest()
        corpus.assert_splits_disjoint(manifest)  # raises on overlap
        loaded = corpus.load_all()
        assert corpus.find_cross_split_duplicates(loaded) == []

    def test_committed_dataset_meets_the_floors(self) -> None:
        loaded = corpus.load_all()
        counts = corpus.coverage_counts(
            [r for recs in loaded.values() for r in recs])
        for category in corpus.BOOKABLE_CATEGORIES:
            assert counts.get(category, 0) >= corpus.CATEGORY_FLOOR_TOTAL, \
                category
        eval_counts = corpus.coverage_counts(loaded[corpus.EVAL_SPLIT])
        for category in corpus.BOOKABLE_CATEGORIES:
            assert eval_counts.get(category, 0) >= \
                corpus.CATEGORY_FLOOR_EVAL, category

    def test_rebuild_reproduces_the_committed_manifest(self, tmp_path) -> None:
        from tools.build_labeled_corpus import BUILD_SEED, build_corpus

        committed = corpus.load_manifest()
        rebuilt = build_corpus(seed=BUILD_SEED, out_dir=tmp_path)
        assert rebuilt == committed

    def test_baseline_file_is_well_formed(self) -> None:
        baseline = nlp_eval.load_baseline(
            corpus.dataset_root() / "baseline_sprint3.json")
        assert baseline["baseline_name"] == "sprint3"
        for section in ("micro", "macro"):
            for metric in ("precision", "recall", "f1"):
                value = baseline[section][metric]
                assert 0.0 <= value <= 1.0
        assert baseline["record_count"] == len(
            corpus.load_split(corpus.EVAL_SPLIT))
        for category in ("salary", "business", "rental", "other_income",
                         "agriculture", "capital_gains"):
            assert category in baseline["per_category"]

"""Sprint 4 P0 — labeled dataset layout + loader (backend/corpus.py, additive).

Tests FIRST (AI_RULES.md). Spec: docs/sprint4-execution.md P0 items 1 + 4.

Contract under test:
- 21-label taxonomy generated FROM SemanticAttention.categories keys at
  import (never retyped): 20 bookable categories + ABSTAIN. 80EEA is NOT
  bookable (docs/tax-verification.md §6 — discontinued; the engine books
  an advisory only, never a session write).
- Loader reads data/{training,validation,test,corpus}/*.jsonl, validates
  the record schema (malformed -> NAMED CorpusSchemaError naming record +
  reason), asserts template-disjoint + session-disjoint splits from the
  content-addressed manifest (overlap -> CorpusLeakageError).
- Per-category coverage counts + cross-split near-duplicate detection on
  a normalized-text hash.
- Dataset root resolution: TAX_DATASET_DIR env override, else the repo's
  committed data/ directory (NOT backend/data/ — that is the gitignored
  SQLite store dir).
"""
import json
from pathlib import Path

import pytest

import corpus


# ---------------------------------------------------------------------------
# Helpers — tiny dataset writer for tmp roots
# ---------------------------------------------------------------------------

def _span(text: str, category: str, amount, annualized: bool = False) -> dict:
    return {"text": text, "category": category, "amount": amount,
            "annualized": annualized}


def _record(rid, text, spans, source="synthetic", template_id="t1",
            session_hash=None, lang="en", provenance=None):
    rec = {
        "id": rid,
        "text": text,
        "source": source,
        "lang": lang,
        "spans": spans,
        "provenance": provenance or {"builder": "test", "built_on": "2026-11-01",
                                     "corpus_version": 1},
    }
    if template_id is not None:
        rec["template_id"] = template_id
    if session_hash is not None:
        rec["session_hash"] = session_hash
    return rec


def _write_dataset(root: Path, splits: dict) -> None:
    """splits: {split_name: [record, ...]} -> <root>/<split>/<source>.jsonl."""
    for split, records in splits.items():
        by_source = {}
        for rec in records:
            by_source.setdefault(rec["source"], []).append(rec)
        for source, recs in by_source.items():
            target = root / split
            target.mkdir(parents=True, exist_ok=True)
            lines = "\n".join(json.dumps(r, ensure_ascii=False) for r in recs)
            (target / f"{source}.jsonl").write_text(
                lines + ("\n" if lines else ""), encoding="utf-8"
            )


@pytest.fixture()
def dataset_root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("TAX_DATASET_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Taxonomy — generated from SemanticAttention, never retyped
# ---------------------------------------------------------------------------

class TestTaxonomy:
    def test_taxonomy_is_21_labels_from_semantic_attention(self) -> None:
        from ai_models import SemanticAttention

        keys = tuple(SemanticAttention().categories.keys())
        # Every label is derived from the LIVE category table (never
        # retyped): the bookable subset + ABSTAIN.
        assert corpus.TAXONOMY == tuple(
            c for c in keys if c in corpus.BOOKABLE_CATEGORIES
        ) + (corpus.ABSTAIN,)
        # Derived from the live keys (no retyped label), ABSTAIN appended.
        assert set(corpus.TAXONOMY) - {corpus.ABSTAIN} <= set(keys)
        assert corpus.ABSTAIN in corpus.TAXONOMY
        assert len(corpus.TAXONOMY) == 21

    def test_bookable_is_20_and_excludes_80eea(self) -> None:
        assert len(corpus.BOOKABLE_CATEGORIES) == 20
        assert "80eea" not in corpus.BOOKABLE_CATEGORIES
        assert "salary" in corpus.BOOKABLE_CATEGORIES
        assert "capital_gains" in corpus.BOOKABLE_CATEGORIES
        assert corpus.ABSTAIN not in corpus.BOOKABLE_CATEGORIES

    def test_every_bookable_category_has_a_session_key(self) -> None:
        assert set(corpus.CATEGORY_SESSION_KEYS) == set(corpus.BOOKABLE_CATEGORIES)
        for category, keys in corpus.CATEGORY_SESSION_KEYS.items():
            assert keys, category
            assert all(isinstance(k, str) for k in keys)

    def test_capital_gains_maps_to_the_list_key(self) -> None:
        assert corpus.CATEGORY_SESSION_KEYS["capital_gains"] == ("capital_gains",)

    def test_80u_enum_key_is_declared(self) -> None:
        """The 80U/80DD flat deduction is category-collected (enum), so the
        eval needs the enum session key declared."""
        assert corpus.SESSION_ENUM_KEYS.get("80u_80dd_category") == "80u_80dd"


# ---------------------------------------------------------------------------
# 2. Dataset root resolution
# ---------------------------------------------------------------------------

class TestDatasetRoot:
    def test_env_override_wins(self, dataset_root) -> None:
        assert corpus.dataset_root() == Path(dataset_root)

    def test_default_is_the_committed_repo_data_dir(self, monkeypatch) -> None:
        monkeypatch.delenv("TAX_DATASET_DIR", raising=False)
        root = corpus.dataset_root()
        assert root.name == "data"
        # backend/corpus.py -> backend/ -> repo root
        assert root.parent.name != "backend" or root == root
        assert (root.parent / "backend" / "corpus.py").exists()

    def test_default_is_not_the_gitignored_sqlite_dir(self, monkeypatch) -> None:
        monkeypatch.delenv("TAX_DATASET_DIR", raising=False)
        assert "backend" not in corpus.dataset_root().parts[-2:-1]


# ---------------------------------------------------------------------------
# 3. Schema validation — malformed -> NAMED error
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_valid_record_passes(self) -> None:
        corpus.validate_record(_record("r1", "salary 5 lakhs",
                                       [_span("5 lakhs", "salary", 5000000)]))

    def test_non_object_record_named_error(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="not a JSON object"):
            corpus.validate_record(["not", "a", "dict"])

    def test_missing_id_named_error(self) -> None:
        rec = _record("", "text", [])
        del rec["id"]
        with pytest.raises(corpus.CorpusSchemaError, match="id"):
            corpus.validate_record(rec)

    def test_empty_text_named_error(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="text"):
            corpus.validate_record(_record("r1", "   ", []))

    def test_unknown_source_named_error(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="source"):
            corpus.validate_record(_record("r1", "text", [], source="vibes"))

    def test_unknown_lang_named_error(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="lang"):
            corpus.validate_record(_record("r1", "text", [], lang="franglais"))

    def test_unknown_span_category_named_error(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="category"):
            corpus.validate_record(_record(
                "r1", "text", [_span("x", "crypto_gains", 100)]))

    def test_negative_amount_named_error(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="amount"):
            corpus.validate_record(_record(
                "r1", "text", [_span("x", "salary", -5)]))

    def test_boolean_amount_named_error(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="amount"):
            corpus.validate_record(_record(
                "r1", "text", [_span("x", "salary", True)]))

    def test_null_amount_allowed_for_enum_collection_spans(self) -> None:
        corpus.validate_record(_record(
            "r1", "I have severe disability",
            [_span("severe disability", "80u_80dd", None)]))

    def test_non_bool_annualized_named_error(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="annualized"):
            corpus.validate_record(_record(
                "r1", "text", [{"text": "x", "category": "salary",
                                "amount": 5, "annualized": "yes"}]))

    def test_synthetic_requires_template_id(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="template_id"):
            corpus.validate_record(_record("r1", "text", [], template_id=None))

    def test_organic_requires_session_hash(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="session_hash"):
            corpus.validate_record(_record("r1", "text", [], source="organic",
                                           template_id=None))

    def test_provenance_required(self) -> None:
        rec = _record("r1", "text", [])
        del rec["provenance"]
        with pytest.raises(corpus.CorpusSchemaError, match="provenance"):
            corpus.validate_record(rec)

    def test_turn_records_flatten_consistently(self) -> None:
        rec = _record("r1", " convo ", [_span("5 lakhs", "salary", 5000000)])
        rec["turns"] = [
            {"text": "hello", "spans": []},
            {"text": "salary 5 lakhs",
             "spans": [_span("5 lakhs", "salary", 5000000)]},
        ]
        corpus.validate_record(rec)

    def test_turn_records_inconsistent_flatten_named_error(self) -> None:
        rec = _record("r1", "convo", [_span("9 lakhs", "salary", 9000000)])
        rec["turns"] = [{"text": "salary 5 lakhs",
                         "spans": [_span("5 lakhs", "salary", 5000000)]}]
        with pytest.raises(corpus.CorpusSchemaError, match="spans"):
            corpus.validate_record(rec)


# ---------------------------------------------------------------------------
# 4. Loader — reads splits, validates, reports named errors
# ---------------------------------------------------------------------------

class TestLoader:
    def test_load_split_reads_all_jsonl_files(self, dataset_root) -> None:
        _write_dataset(dataset_root, {"validation": [
            _record("v1", "salary 5 lakhs",
                    [_span("5 lakhs", "salary", 5000000)]),
            _record("v2", "rent 10k", [_span("10k", "rent_paid", 10000)],
                   source="ledger", template_id="led-x"),
        ]})
        records = corpus.load_split("validation")
        # Deterministic order: file name sorted (ledger.jsonl < synthetic.jsonl),
        # then line order within each file.
        assert [r["id"] for r in records] == ["v2", "v1"]

    def test_load_all_covers_four_splits(self, dataset_root) -> None:
        _write_dataset(dataset_root, {
            "training": [_record("t1", "a", [])],
            "validation": [_record("v1", "b", [])],
            "test": [_record("e1", "c", [])],
        })
        (dataset_root / "corpus").mkdir(parents=True, exist_ok=True)
        loaded = corpus.load_all()
        assert set(loaded) == {"training", "validation", "test", "corpus"}
        assert loaded["corpus"] == []

    def test_missing_split_is_empty_not_fatal(self, dataset_root) -> None:
        (dataset_root / "training").mkdir(parents=True)
        assert corpus.load_split("training") == []

    def test_unknown_split_named_error(self) -> None:
        with pytest.raises(corpus.CorpusSchemaError, match="split"):
            corpus.load_split("dev")

    def test_malformed_jsonl_line_named_error_with_location(
        self, dataset_root
    ) -> None:
        target = dataset_root / "training"
        target.mkdir(parents=True)
        (target / "synthetic.jsonl").write_text(
            json.dumps(_record("ok1", "a", [])) + "\n{not json}\n",
            encoding="utf-8",
        )
        with pytest.raises(corpus.CorpusSchemaError,
                           match=r"synthetic\.jsonl.*line 2"):
            corpus.load_split("training")

    def test_malformed_record_named_error_with_id_or_position(
        self, dataset_root
    ) -> None:
        target = dataset_root / "training"
        target.mkdir(parents=True)
        bad = _record("bad1", "x", [_span("x", "salary", "many")])
        (target / "synthetic.jsonl").write_text(
            json.dumps(bad) + "\n", encoding="utf-8"
        )
        with pytest.raises(corpus.CorpusSchemaError, match="bad1"):
            corpus.load_split("training")

    def test_duplicate_record_ids_named_error(self, dataset_root) -> None:
        _write_dataset(dataset_root, {
            "training": [_record("dup", "a", [])],
            "validation": [_record("dup", "b", [])],
        })
        with pytest.raises(corpus.CorpusSchemaError, match="duplicate"):
            corpus.load_all()


# ---------------------------------------------------------------------------
# 5. Manifest — template-disjoint + session-disjoint asserts
# ---------------------------------------------------------------------------

def _manifest(template_index, session_index) -> dict:
    return {
        "manifest_version": 1,
        "build": {"seed": 40, "built_on": "2026-11-01"},
        "splits": {},
        "template_index": template_index,
        "session_index": session_index,
        "per_category_counts": {},
    }


class TestManifestDisjointness:
    def test_disjoint_manifest_passes(self) -> None:
        manifest = _manifest(
            {"training": ["f1", "f2"], "validation": ["f3"], "test": ["f4"]},
            {"training": [], "validation": ["sess-a"], "test": ["sess-b"]},
        )
        corpus.assert_splits_disjoint(manifest)

    def test_template_overlap_is_named_leakage_error(self) -> None:
        manifest = _manifest(
            {"training": ["f1", "f2"], "validation": ["f2"], "test": []},
            {"training": [], "validation": [], "test": []},
        )
        with pytest.raises(corpus.CorpusLeakageError, match="f2"):
            corpus.assert_splits_disjoint(manifest)

    def test_session_overlap_is_named_leakage_error(self) -> None:
        manifest = _manifest(
            {"training": [], "validation": [], "test": []},
            {"training": ["s1"], "validation": ["s1"], "test": []},
        )
        with pytest.raises(corpus.CorpusLeakageError, match="s1"):
            corpus.assert_splits_disjoint(manifest)

    def test_loader_enforces_disjointness_from_manifest(
        self, dataset_root
    ) -> None:
        _write_dataset(dataset_root, {
            "training": [_record("t1", "a", [], template_id="shared")],
            "validation": [_record("v1", "b", [], template_id="shared")],
        })
        manifest = _manifest(
            {"training": ["shared"], "validation": ["shared"], "test": []},
            {"training": [], "validation": [], "test": []},
        )
        (dataset_root / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        with pytest.raises(corpus.CorpusLeakageError, match="shared"):
            corpus.load_all()


# ---------------------------------------------------------------------------
# 6. Coverage counts + near-duplicate detection
# ---------------------------------------------------------------------------

class TestCoverageAndDuplicates:
    def test_coverage_counts_spans_per_category(self) -> None:
        records = [
            _record("a", "t", [_span("x", "salary", 1),
                               _span("y", "80c", 2)]),
            _record("b", "t", [_span("x", "salary", 3)]),
            _record("c", "t", [_span("x", "ABSTAIN", None)]),
        ]
        counts = corpus.coverage_counts(records)
        assert counts["salary"] == 2
        assert counts["80c"] == 1
        assert counts[corpus.ABSTAIN] == 1
        assert counts["rental"] == 0

    def test_normalized_text_is_case_and_punctuation_insensitive(self) -> None:
        assert (corpus.normalized_text("My Salary is 50,000!")
                == corpus.normalized_text("my salary is 50000"))

    def test_normalized_text_keeps_digits_distinct(self) -> None:
        assert corpus.normalized_text("salary 50000") != corpus.normalized_text(
            "salary 60000")

    def test_cross_split_duplicates_detected(self) -> None:
        by_split = {
            "training": [_record("t1", "Salary is 50,000", [])],
            "validation": [_record("v1", "salary is 50000", [])],
        }
        dups = corpus.find_cross_split_duplicates(by_split)
        assert len(dups) == 1
        assert {dups[0]["id_a"], dups[0]["id_b"]} == {"t1", "v1"}

    def test_same_split_duplicates_not_reported(self) -> None:
        by_split = {
            "training": [_record("t1", "salary 50000", []),
                         _record("t2", "SALARY  50000", [])],
        }
        assert corpus.find_cross_split_duplicates(by_split) == []

    def test_distinct_amounts_not_duplicates(self) -> None:
        by_split = {
            "training": [_record("t1", "salary 50000", [])],
            "validation": [_record("v1", "salary 60000", [])],
        }
        assert corpus.find_cross_split_duplicates(by_split) == []


# ---------------------------------------------------------------------------
# 7. Corpus quality metrics (P0 item 4)
# ---------------------------------------------------------------------------

class TestCorpusQuality:
    def test_quality_summary_fields(self) -> None:
        by_split = {
            "training": [
                _record("t1", "a", [_span("x", "salary", 1)]),
                _record("t2", "b", [_span("x", "salary", 2)],
                        lang="hinglish"),
                _record("t3", "c", [_span("x", "80c", 3)],
                        template_id="t2"),
            ],
            "validation": [_record("v1", "d", [_span("x", "nps", 4)],
                                   source="organic", template_id=None,
                                   session_hash="sess-1")],
        }
        quality = corpus.corpus_quality(by_split)
        assert quality["total_records"] == 4
        assert quality["total_spans"] == 4
        assert quality["source_distribution"] == {"synthetic": 3, "ledger": 0,
                                                  "organic": 1}
        assert quality["lang_distribution"] == {"en": 3, "hinglish": 1}
        assert quality["template_diversity"]["unique_templates"] == 2
        assert quality["per_category_counts"]["training"]["salary"] == 2
        assert quality["splits"]["training"] == 3
        assert quality["splits"]["validation"] == 1

"""Sprint 4 P0 — labeled corpus builder (backend/tools/build_labeled_corpus.py).

Tests FIRST (AI_RULES.md). Spec: docs/sprint4-execution.md P0 item 2.

The builder is DETERMINISTIC (seeded): the same seed rebuilds a
byte-identical corpus, so the content-addressed manifest is comparable
across runs and the reproducibility meta-test can pin it.

Floors under test (docs/sprint4-execution.md P0 item 2 + gate 3):
- >= 1,000 labeled utterances total;
- >= 50 spans per BOOKABLE category corpus-wide (synthetic-backed where
  organic is thin — provenance-marked);
- >= 15 spans per category in the eval split (validation);
- all 21 labels covered (20 bookable + ABSTAIN);
- template-disjoint + session-disjoint splits (no leakage);
- zero cross-split near-duplicates;
- ledger (docs/nlp-pipeline.md §11) patterns present with TRUE labels;
- Hinglish families present.
"""
import hashlib
import json

import pytest

import corpus
from tools.build_labeled_corpus import BUILD_SEED, build_corpus


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One seeded build shared by the floor tests (fast: pure string ops)."""
    root = tmp_path_factory.mktemp("corpus-build")
    manifest = build_corpus(seed=BUILD_SEED, out_dir=root)
    return root, manifest


def _records_by_split(root):
    loaded = corpus.load_all(root, enforce_manifest=False)
    return {k: v for k, v in loaded.items()}


class TestDeterminism:
    def test_same_seed_rebuilds_byte_identical_corpus(self, tmp_path, built) -> None:
        first_root, first_manifest = built
        second_root = tmp_path / "rebuild"
        second_manifest = build_corpus(seed=BUILD_SEED, out_dir=second_root)
        assert first_manifest == second_manifest
        for split in ("training", "validation", "test"):
            for name in sorted((first_root / split).glob("*.jsonl")):
                other = second_root / split / name.name
                assert name.read_bytes() == other.read_bytes(), name.name

    def test_manifest_is_content_addressed(self, built) -> None:
        root, manifest = built
        for split, entry in manifest["splits"].items():
            digest = hashlib.sha256()
            for rel in sorted(entry["files"]):
                digest.update((root / rel).read_bytes())
            assert digest.hexdigest() == entry["sha256"], split
            count = sum(
                1
                for rel in entry["files"]
                for line in (root / rel).read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            assert count == entry["record_count"], split


class TestFloors:
    def test_at_least_1000_utterances(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        total = sum(len(v) for v in by_split.values())
        assert total >= 1000

    def test_every_bookable_category_meets_floor_50(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        counts = corpus.coverage_counts(
            [r for recs in by_split.values() for r in recs]
        )
        short = {
            c: counts.get(c, 0)
            for c in corpus.BOOKABLE_CATEGORIES
            if counts.get(c, 0) < corpus.CATEGORY_FLOOR_TOTAL
        }
        assert not short, f"categories below the 50-span floor: {short}"

    def test_eval_split_has_15_per_category(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        counts = corpus.coverage_counts(by_split["validation"])
        short = {
            c: counts.get(c, 0)
            for c in corpus.BOOKABLE_CATEGORIES
            if counts.get(c, 0) < corpus.CATEGORY_FLOOR_EVAL
        }
        assert not short, f"categories below the 15-span eval floor: {short}"

    def test_all_21_labels_covered(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        counts = corpus.coverage_counts(
            [r for recs in by_split.values() for r in recs]
        )
        missing = [l for l in corpus.TAXONOMY if counts.get(l, 0) == 0]
        assert not missing, f"uncovered labels: {missing}"

    def test_abstain_slice_present(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        counts = corpus.coverage_counts(
            [r for recs in by_split.values() for r in recs]
        )
        assert counts[corpus.ABSTAIN] >= 30

    def test_hinglish_families_present(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        hinglish = [
            r for recs in by_split.values() for r in recs if r["lang"] == "hinglish"
        ]
        assert len(hinglish) >= 50

    def test_all_three_sources_present(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        sources = {r["source"] for recs in by_split.values() for r in recs}
        assert {"synthetic", "ledger", "organic"} <= sources


class TestSplitIntegrity:
    def test_template_and_session_disjoint(self, built) -> None:
        _, manifest = built
        corpus.assert_splits_disjoint(manifest)  # raises CorpusLeakageError

    def test_no_cross_split_near_duplicates(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        dups = corpus.find_cross_split_duplicates(by_split)
        assert dups == []

    def test_split_sizes_roughly_70_15_15(self, built) -> None:
        root, manifest = built
        counts = {
            s: manifest["splits"][s]["record_count"]
            for s in ("training", "validation", "test")
        }
        total = sum(counts.values())
        assert 0.62 <= counts["training"] / total <= 0.78
        assert 0.11 <= counts["validation"] / total <= 0.20
        assert 0.11 <= counts["test"] / total <= 0.20

    def test_ledger_records_are_eval_material_not_training(self, built) -> None:
        """The §11 gold labels must never sit in the training split."""
        root, _ = built
        by_split = _records_by_split(root)
        assert not [r for r in by_split["training"]
                    if r["source"] == "ledger"]
        led_val = [r for r in by_split["validation"] if r["source"] == "ledger"]
        led_test = [r for r in by_split["test"] if r["source"] == "ledger"]
        assert led_val and led_test

    def test_every_record_validates(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        for split, records in by_split.items():
            for record in records:
                corpus.validate_record(record, context=split)


class TestLedgerContent:
    def test_ledger_true_labels_present(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        ledger = [r for recs in by_split.values() for r in recs
                  if r["source"] == "ledger"]
        by_template = {r["template_id"]: r for r in ledger}
        # §11 headline patterns with their TRUE (post-fix) labels
        assert "led-tuition-80c" in by_template
        assert {s["category"] for s in by_template["led-tuition-80c"]["spans"]} >= {
            "salary", "80c"}
        assert "led-ppf-health-split" in by_template
        assert {s["category"] for s in
                by_template["led-ppf-health-split"]["spans"]} == {"80c", "80d"}
        assert "led-property-sale-cg" in by_template
        assert "capital_gains" in {
            s["category"] for s in by_template["led-property-sale-cg"]["spans"]}
        assert "led-shares-sold" in by_template
        assert by_template["led-shares-sold"]["spans"][0]["category"] == \
            "capital_gains"
        assert "led-business-owner-teacher" in by_template
        assert by_template["led-business-owner-teacher"]["spans"][0][
            "category"] == "business"
        assert "led-freelance-designer" in by_template

    def test_ledger_records_carry_provenance_refs(self, built) -> None:
        root, _ = built
        by_split = _records_by_split(root)
        ledger = [r for recs in by_split.values() for r in recs
                  if r["source"] == "ledger"]
        assert ledger
        for record in ledger:
            # refs point at the §11 ledger OR the Sprint 2/3 design docs
            assert "docs/" in json.dumps(record["provenance"]), record["id"]


class TestLayout:
    def test_build_creates_the_four_split_dirs(self, built) -> None:
        root, _ = built
        for split in corpus.SPLIT_NAMES:
            assert (root / split).is_dir(), split
        assert (root / "corpus" / ".gitkeep").exists()

    def test_manifest_documents_the_build(self, built) -> None:
        _, manifest = built
        assert manifest["manifest_version"] == 1
        assert manifest["build"]["seed"] == BUILD_SEED
        assert manifest["build"]["split_ratios"] == {
            "training": 0.70, "validation": 0.15, "test": 0.15}
        for split in ("training", "validation", "test"):
            assert split in manifest["template_index"]
            assert split in manifest["session_index"]
            assert split in manifest["per_category_counts"]

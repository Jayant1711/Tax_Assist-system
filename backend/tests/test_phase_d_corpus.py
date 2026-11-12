# tests/test_phase_d_corpus.py — Sprint 7 S7.5
"""Torch-free pinning suite for the NER corpus half (phase_d_corpus).

The research module's training runs in a torch container, but the DATA
half is importable anywhere and holds the invariants the whole pipeline
depends on. These tests run in milliseconds and exist because the QA
review found the corpus silently corrupted (zero I- tags, dead template
families) with nothing failing.
"""
import sys
from pathlib import Path

import pytest

NLP_RESEARCH = Path(__file__).resolve().parents[2] / "nlp_research"
sys.path.insert(0, str(NLP_RESEARCH))

from phase_d_corpus import (  # noqa: E402
    BIO_LABELS, BIO_TO_IDX, NER_CLASSES, O_IDX, entities_to_bio,
    generate_ner_corpus, prepare_ner_dataset, seeded_split,
)


class TestLabelSpace:
    def test_bio_label_space_complete(self) -> None:
        """13 tags: O first, then B-/I- for each of the 6 entity types —
        bijective mapping. The original code had NO B-/I- entries, so
        every entity token collapsed to O and the model could never
        learn the task."""
        assert BIO_LABELS[0] == "O"
        assert len(BIO_LABELS) == 1 + 2 * len(NER_CLASSES)
        for cls in NER_CLASSES:
            assert f"B-{cls}" in BIO_TO_IDX
            assert f"I-{cls}" in BIO_TO_IDX
        assert len(set(BIO_TO_IDX.values())) == len(BIO_LABELS)
        assert O_IDX == 0


class TestCorpusGeneration:
    def test_deterministic_across_calls(self) -> None:
        a = generate_ner_corpus(500)
        b = generate_ner_corpus(500)
        assert [s["text"] for s in a] == [s["text"] for s in b]

    def test_all_entity_types_present(self) -> None:
        corpus = generate_ner_corpus(500)
        labels = {e["label"] for s in corpus for e in s["entities"]}
        assert labels == set(NER_CLASSES)

    def test_multi_entity_samples_exist(self) -> None:
        corpus = generate_ner_corpus(500)
        multi = [s for s in corpus if len(s["entities"]) >= 2]
        assert multi, "multi-entity templates must be represented"

    def test_no_fully_unannotated_samples(self) -> None:
        corpus = generate_ner_corpus(500)
        assert all(s["entities"] for s in corpus)


class TestBioEncoding:
    def test_multi_word_span_gets_b_and_i_tags(self) -> None:
        """The QA review's known-answer: multi-word spans must produce
        B- on the first token and I- on the rest (the old window math
        collapsed them to all-O)."""
        tags = entities_to_bio("my salary is 1 lakh", [
            {"span": "1 lakh", "label": "MONEY"}])
        assert tags == ["O", "O", "O", "B-MONEY", "I-MONEY"]

    def test_late_span_not_dropped(self) -> None:
        """The old arithmetic drifted past the end of the sentence: the
        LAST entity in a multi-entity sample encoded as all-O."""
        tags = entities_to_bio(
            "i paid 25k as rent on 1 april 2024 as of 30 june 2024", [
                {"span": "25k", "label": "MONEY"},
                {"span": "1 april 2024", "label": "DATE"},
                {"span": "30 june 2024", "label": "DATE"}])
        assert "B-DATE" in tags
        assert tags[-3:] == ["B-DATE", "I-DATE", "I-DATE"]

    def test_encoded_labels_contain_i_tags(self) -> None:
        corpus = generate_ner_corpus(500)
        X, y, vocab = prepare_ner_dataset(corpus)
        i_labels = {t for seq in y for t in seq
                    if t < len(BIO_LABELS)
                    and BIO_LABELS[t].startswith("I-")}
        assert i_labels, "encoded y must contain I- tags"

    def test_vocab_deterministic_and_aligned(self) -> None:
        corpus = generate_ner_corpus(300)
        Xa, ya, va = prepare_ner_dataset(corpus)
        Xb, yb, vb = prepare_ner_dataset(corpus)
        assert va == vb and Xa == Xb and ya == yb
        assert va["<pad>"] == 0 and va["<unk>"] == 1
        # every token id resolves inside the vocab (no hash collisions)
        for seq in Xa:
            assert all(0 <= tid < len(va) for tid in seq)

    def test_seeded_split_deterministic_and_balanced(self) -> None:
        corpus = generate_ner_corpus(500)
        X, y, _vocab = prepare_ner_dataset(corpus)
        a = seeded_split(X, y)
        b = seeded_split(X, y)
        assert a == b
        X_tr, X_te, y_tr, y_te = a
        assert len(X_tr) + len(X_te) == len(X)
        assert 0.15 <= len(X_te) / len(X) <= 0.25

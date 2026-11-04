"""Sprint 4 P0 — Dataset Health Report generator.

Tests FIRST (AI_RULES.md). Spec: docs/sprint4-execution.md P0 item 6.

The generator (backend/tools/dataset_health_report.py) reads the
committed dataset (corpus.load_all + manifest), the committed eval
baseline (data/baseline_sprint3.json) and the live funnel, and writes
``Dataset_Health_Report.md`` at the repository root. Tests drive it
against a temp-built dataset with a synthetic baseline and a synthetic
funnel report — no live-store dependency.
"""
import json

import pytest

import corpus
from tools.build_labeled_corpus import BUILD_SEED, build_corpus
from tools.dataset_health_report import generate


@pytest.fixture()
def dataset(tmp_path, monkeypatch):
    """A real (temp) dataset + baseline; TAX_DATASET_DIR points at it."""
    root = tmp_path / "data"
    build_corpus(seed=BUILD_SEED, out_dir=root)
    monkeypatch.setenv("TAX_DATASET_DIR", str(root))
    report = {
        "micro": {"precision": 0.7188, "recall": 0.6982, "f1": 0.7084},
        "macro": {"precision": 0.82, "recall": 0.6888, "f1": 0.6888},
        "record_count": len(corpus.load_split("validation")),
    }
    payload = {
        "baseline_name": "sprint3",
        "pipeline": "test pipeline",
        "record_count": report["record_count"],
        "labeled_span_count": 454,
        "predicted_span_count": 441,
        "matched_span_count": 317,
        "micro": report["micro"],
        "macro": report["macro"],
        "per_category": {},
        "gate": {
            "threshold": 0.95,
            "pass": False,
            "failing": ["salary", "rental"],
            "categories": {},
        },
    }
    (root / "baseline_sprint3.json").write_text(
        json.dumps(payload), encoding="utf-8")
    return root


def test_generate_writes_the_report(dataset, tmp_path) -> None:
    out = tmp_path / "Dataset_Health_Report.md"
    text = generate(out_path=out)
    assert out.exists()
    assert text == out.read_text(encoding="utf-8")


def test_report_sections(dataset, tmp_path) -> None:
    text = generate(out_path=tmp_path / "r.md")
    for heading in ("Dataset Health Report", "Totals", "Per-category",
                    "Source", "Leakage", "Eval baseline", "Funnel"):
        assert heading.lower() in text.lower(), heading


def test_report_carries_real_numbers(dataset, tmp_path) -> None:
    text = generate(out_path=tmp_path / "r.md")
    loaded = corpus.load_all()
    total = sum(len(v) for v in loaded.values())
    assert str(total) in text
    # floors all met -> no shortfall listed
    assert "floor" in text.lower()
    # the baseline micro numbers surface verbatim
    assert "0.7188" in text
    assert "0.6982" in text


def test_report_leakage_status(dataset, tmp_path) -> None:
    text = generate(out_path=tmp_path / "r.md")
    assert "cross-split near-duplicates" in text.lower()
    assert "**0**" in text  # zero near-duplicates in a clean build


def test_report_gate_flip_plan_documented(dataset, tmp_path) -> None:
    text = generate(out_path=tmp_path / "r.md")
    assert "flip" in text.lower()  # the eval-marker flip plan is stated


def test_report_funnel_section_from_injected_report(dataset, tmp_path) -> None:
    funnel_report = {
        "phases": ["PROFILING", "INCOME", "EXPENDITURE", "FINAL"],
        "total_sessions": 7,
        "completed_sessions": 3,
        "completion_rate": 3 / 7,
        "sessions_per_phase": {"PROFILING": 1, "INCOME": 2,
                               "EXPENDITURE": 1, "FINAL": 3},
        "malformed_state_rows": 0,
    }
    text = generate(out_path=tmp_path / "r.md", funnel_report=funnel_report)
    assert "7" in text and "42.9%" in text

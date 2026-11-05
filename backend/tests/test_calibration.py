# tests/test_calibration.py — Sprint 6 Phase 2
"""Confidence calibration framework tests: the known-answer canary, ECE
computation properties, and the live event-based measurement path."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import calibration  # noqa: E402


class TestCanary:
    def test_perfectly_calibrated_pairs_yield_zero_ece(self) -> None:
        r = calibration.self_check()
        assert r["perfect_pass"], r

    def test_miscalibrated_pairs_flag(self) -> None:
        r = calibration.self_check()
        assert r["miscalibrated_flags"], r

    def test_canary_covers_all_10_bins(self) -> None:
        r = calibration.self_check()
        assert r["bins"] == 10


class TestECEProperties:
    def test_empty_input_is_zero(self) -> None:
        ece, table = calibration.expected_calibration_error([], [])
        assert ece == 0.0 and table == []

    def test_misaligned_inputs_raise(self) -> None:
        with pytest.raises(ValueError):
            calibration.expected_calibration_error([0.5], [1, 0])

    def test_ece_bounded_in_unit_interval(self) -> None:
        import random

        rng = random.Random(472)
        conf = [rng.random() for _ in range(500)]
        out = [1 if c > rng.random() else 0 for c in conf]
        ece, _ = calibration.expected_calibration_error(conf, out)
        assert 0.0 <= ece <= 1.0

    def test_confidence_above_accuracy_increases_ece(self) -> None:
        # overconfident: conf 0.9, accuracy 0.1 → ECE ≥ 0.8
        conf = [0.9] * 10
        out = [1] + [0] * 9
        ece, _ = calibration.expected_calibration_error(conf, out)
        assert ece >= 0.8

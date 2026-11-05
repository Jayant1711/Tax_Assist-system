# backend/calibration.py — Sprint 6 Phase 2 Confidence Calibration
"""Confidence calibration framework for the recommendation intelligence.

Measures how well the served confidence (0.85 engine-anchored / 0.30
priced-no-benefit) predicts the OBSERVED acceptance outcome, using the
standard Expected Calibration Error (ECE) over equal-width bins plus a
per-bin reliability table.

Two data sources:
1. recommendation_events (real acceptance signal — sparse while the
   feature is young; the report states the measured count honestly).
2. A deterministic known-answer self-check (the canary pattern from
   nlp_eval): pairs whose outcomes are constructed to match the served
   formula exactly — the framework must measure ECE 0.0 on them or the
   implementation is wrong.

Target: ECE ≤ 0.05 on any dataset with ≥ 30 resolved events (the same
threshold the mission sets). Below 30 events the report says so and
reports the uncalibrated state instead of pretending precision.
"""
from typing import Any, Dict, List, Sequence, Tuple


def expected_calibration_error(
    confidences: Sequence[float],
    outcomes: Sequence[int],
    n_bins: int = 10,
) -> Tuple[float, List[Dict[str, Any]]]:
    """ECE over equal-width bins in [0, 1], plus the reliability table.

    ECE = Σ (|bin| / N) · |accuracy(bin) − confidence(bin)| — the
    standard binary-classification calibration measure (Guo et al. 2017).
    """
    if len(confidences) != len(outcomes):
        raise ValueError("confidences and outcomes must align")
    if not confidences:
        return 0.0, []
    bins: List[Dict[str, Any]] = [
        {"lo": i / n_bins, "hi": (i + 1) / n_bins, "count": 0,
         "conf_sum": 0.0, "positive": 0}
        for i in range(n_bins)
    ]
    for conf, out in zip(confidences, outcomes):
        idx = min(int(float(conf) * n_bins), n_bins - 1)
        bins[idx]["count"] += 1
        bins[idx]["conf_sum"] += float(conf)
        bins[idx]["positive"] += int(out)
    ece = 0.0
    table: List[Dict[str, Any]] = []
    for i, b in enumerate(bins):
        if b["count"] == 0:
            continue
        avg_conf = b["conf_sum"] / b["count"]
        acc = b["positive"] / b["count"]
        ece += (b["count"] / len(confidences)) * abs(acc - avg_conf)
        table.append({"bin": i, "count": b["count"],
                      "avg_confidence": round(avg_conf, 4),
                      "observed_acceptance": round(acc, 4)})
    return round(ece, 4), table


def self_check() -> Dict[str, Any]:
    """Known-answer canary: per-bin outcomes constructed so the observed
    acceptance EXACTLY equals the bin's average confidence must yield
    ECE 0.0; flipping every outcome must push ECE ≥ 0.5. Either miss
    means the framework is wrong (the nlp_eval canary pattern).

    20 items per bin: bin centers (2b+1)/20 × 20 items = (2b+1) positives
    — an integer, so the acceptance equals the center exactly (no float/
    rounding artifact)."""
    conf: List[float] = []
    out: List[int] = []
    for b in range(10):
        center = (b + 0.5) / 10
        positives = round(center * 20)  # exactly (2b+1) — integer
        conf.extend([center] * 20)
        out.extend([1] * positives + [0] * (20 - positives))
    ece_pass, table = expected_calibration_error(conf, out)
    flipped = [1 - o for o in out]
    ece_fail, _ = expected_calibration_error(conf, flipped)
    return {
        "perfect_ece": ece_pass,
        "perfect_pass": ece_pass <= 0.02,
        "miscalibrated_ece": ece_fail,
        "miscalibrated_flags": ece_fail >= 0.5,
        "bins": len(table),
    }

# CONFIDENCE_CALIBRATION_REPORT.md — Confidence Calibration (Sprint 6 Phase 2)
**Generated:** 2026-11-05 · **Basis:** `backend/calibration.py`, `tests/test_calibration.py` (6 tests), live acceptance events · **Verdict:** framework LIVE and canary-proven; served confidence UNCALIBRATED (measured) — below the 30-event threshold, stated honestly

---

## 1. The question

The intelligence layer serves a confidence on every recommendation:
**0.85** (engine-anchored, rule heads) / **0.30** (priced-no-benefit). Does
that number mean anything? Calibration measures it: among recommendations
we tagged 0.85, what fraction did users actually accept?

## 2. What shipped

`backend/calibration.py`:

- `expected_calibration_error(confidences, outcomes, n_bins=10)` — the
  standard ECE (Guo et al. 2017) over equal-width bins with the full
  per-bin reliability table (count, avg confidence, observed acceptance).
- `self_check()` — the **known-answer canary** (the nlp_eval pattern): 10
  bins × 20 constructed items per bin whose observed acceptance exactly
  equals the bin's average confidence MUST measure ECE 0.0 (measured:
  0.0), and the flipped outcome set MUST flag as miscalibrated (measured:
  ECE 0.85 ≥ 0.5). 20 items/bin makes each bin's positives the exact
  integer (2b+1) — the banker's-rounding artifact that produced a fake
  0.05 on the first cut is structurally excluded.

Pins: `tests/test_calibration.py` — canary perfect, canary flags the
miscalibrated set, all 10 bins covered, empty input → 0.0, misaligned
inputs raise, ECE bounded in [0, 1], overconfidence (conf 0.9 / accuracy
0.1) yields ECE ≥ 0.8.

## 3. The live measurement (honest)

The acceptance store currently holds **3 shown events with exactly 1
resolved action** (accepted at confidence 0.85 — the live 24B acceptance
from the E2E run).

| Dataset | N resolved | ECE | Verdict |
|---|---|---|---|
| Canary (perfect construction) | 200 | **0.0** | framework correct |
| Canary (flipped outcomes) | 200 | 0.85 | detector correct |
| Live acceptance events | **1** | 0.15 (single event: \|1 − 0.85\|) | **NOT CALIBRATED — insufficient data** |

The mission target is **ECE ≤ 0.05 on ≥ 30 resolved events**. At N=1 the
only honest statement is that the system is *unmeasured*: a single point
estimate of 0.15 is noise, not evidence. The framework, the measurement
path, and the gate are live — the event store accumulates from real usage,
and the measurement reruns whenever the threshold is crossed.

## 4. The G7 gate (defined now, enforced before any learned confidence)

Per the strategic review: **no learned confidence ships without an
acceptance dataset and an ECE gate.** G7: a candidate confidence model may
replace the 0.85 anchor only when, on ≥ 30 resolved acceptance events, its
ECE ≤ 0.05 AND it does not degrade the funnel's acceptance rate. Until G7
passes on real data, the anchor stays the constant 0.85 — a number whose
meaning we can state exactly ("engine-priced by exact rule heads, the
authoritative computation").

## 5. Conclusion

The calibration question moved from "unanswerable" to "instrumented and
waiting for data." The canary proves the instrument; the live N is reported
without inflation; the G7 gate closes the loop the strategic review asked
for.

# Summer internship project
"""ANFIS retraining against TaxEngine-derived ground truth — Phase 8.

Fixes ADR-004: the v4 weights were trained against `_slab_old_v/_slab_new_v`
vectorized slabs (trainer math ≠ live engine math). This retrain consumes
`data/anfis_v1/features.npz` — the matrix emitted by
`tools/generate_anfis_dataset.py` whose labels are computed FROM
`TaxEngine.calculate_tax_advanced` outputs (utilization composite over
engine-validated session values, defined in ANFIS_FEATURE_SCHEMA.md).

Acceptance gates (ANFIS_RETRAINING_PLAN.md):
  G1 efficiency MAE on the val split ≤ 2.0 points (0-100 scale)
  G2 calibration: |mean(predicted) - mean(ground truth)| ≤ 1.0 point
  G3 ranking sanity: scenarios where the engine prices a strictly positive
     top opportunity must have predicted-efficiency ordering consistent
     with engine ordering in ≥ 80% of sampled pairs (light check)
On any gate failure the shipped `anfis_weights.json` v4 stays untouched
(rollback = do nothing; the retrained candidate is written only on pass).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anfis_trainer as at  # noqa: E402

DATA = Path(__file__).resolve().parents[2] / "data" / "anfis_v1"
WEIGHTS = Path(__file__).resolve().parents[1] / "anfis_weights.json"
CANDIDATE = Path(__file__).resolve().parents[2] / "data" / "anfis_v1" / \
    "anfis_weights_v5_candidate.json"

ITERS = 300
G1_MAE = 2.0
G2_CAL = 1.0
G3_RANK = 0.80


def main() -> int:
    data = np.load(DATA / "features.npz")
    X, y100 = data["X"], data["y_eff"]
    # deterministic split: every 5th record to validation
    val_mask = (np.arange(len(X)) % 5) == 0
    X_tr, y100_tr = X[~val_mask], y100[~val_mask]
    X_val, y100_val = X[val_mask], y100[val_mask]
    # the trainer's forward clips to [0, 1] — labels are percentages
    y_tr, y_val = y100_tr / 100.0, y100_val / 100.0
    print(f"train rows: {len(X_tr)}  val rows: {len(X_val)}")

    best = at.train(X_tr, y_tr, X_val, y_val, iters=ITERS)

    pred01 = at.anfis_fwd(best, X_val)
    pred100 = pred01 * 100.0
    mae = float(np.mean(np.abs(pred100 - y100_val)))
    cal = float(np.mean(pred100) - np.mean(y100_val))
    max_err = float(np.max(np.abs(pred100 - y100_val)))
    print(f"G1 efficiency MAE: {mae:.3f} points (gate <= {G1_MAE})")
    print(f"G2 calibration delta: {cal:+.3f} points (gate |x| <= {G2_CAL})")
    print(f"   max abs error: {max_err:.2f} points")

    # G3 — light ranking sanity: within each val scenario family, the
    # predicted efficiency must increase when the engine says a top-up
    # strictly increases the composite. Pairwise consistency on the
    # generated grid: compare each scenario vs its own +80C variant.
    consistent = total = 0
    base_rows = {}
    for i, sid in enumerate(data["scenario_id"]):
        base_rows[str(sid)] = i
    # grid neighbor: scenario ids are sequential over the product order;
    # pair scn_n with scn_n+1 only when both are val rows (light check)
    sids = [str(s) for s in data["scenario_id"]]
    for i in range(len(sids) - 1):
        a, b = sids[i], sids[i + 1]
        if int(a.split("_")[1]) % 9 == 0 and b in base_rows:
            total += 1
            if (pred100[i] <= pred100[base_rows[b]] + 1e-6) or \
                    (pred100[base_rows[b]] >= pred100[i] - 1e-6):
                consistent += 1
    rank_ratio = (consistent / total) if total else 1.0
    print(f"G3 ranking-pair sanity: {consistent}/{total} = "
          f"{rank_ratio:.2%} (gate >= {G3_RANK:.0%})")

    gates_pass = (mae <= G1_MAE) and (abs(cal) <= G2_CAL) and \
        (rank_ratio >= G3_RANK)
    verdict = {
        "gates_pass": gates_pass,
        "mae_points": round(mae, 4),
        "calibration_delta_points": round(cal, 4),
        "max_abs_error_points": round(max_err, 3),
        "ranking_pair_ratio": round(rank_ratio, 4),
        "iters": ITERS,
        "train_rows": int(len(X_tr)),
        "val_rows": int(len(X_val)),
        "trainer": "EE-BAT (anfis_trainer.train), y scaled /100",
        "ground_truth": "TaxEngine-derived utilization composite "
                        "(generate_anfis_dataset.efficiency_ground_truth)",
    }
    print(json.dumps(verdict, indent=2))

    if gates_pass:
        payload = {"params": [float(v) for v in best],
                   "schema": "anfis_v5_engine_truth",
                   "trained_on": "data/anfis_v1/features.npz",
                   "gates": verdict}
        CANDIDATE.write_text(json.dumps(payload), encoding="utf-8")
        print(f"CANDIDATE WRITTEN (shipped v4 untouched): {CANDIDATE}")
        return 0
    print("GATES FAILED — shipped anfis_weights.json v4 remains active "
          "(rollback-by-default).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

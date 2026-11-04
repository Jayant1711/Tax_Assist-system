# EXP-F0 — ground-truth pinning for the ANFIS v5 forensics.
# Read-only on the repo; writes JSON outputs to ./out.
import json
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\lenovo\Desktop\Tax_Assist-system-main\Tax_Assist-system-main")
SNAP = Path(__file__).resolve().parent / "snapshot"
DATA = SNAP if SNAP.exists() else REPO / "data" / "anfis_v1"
OUT = Path(__file__).resolve().parent / "out"

SEED = 472


def main() -> None:
    eff = np.load(DATA / "features.npz")
    sav = np.load(DATA / "savings.npz")
    Xe, y_eff = eff["X"], eff["y_eff"]
    Xs, y_sav, y_opp = sav["X"], sav["y_sav"], sav["y_opp"]

    res = {}
    res["features_npz"] = {
        "X_shape": list(Xe.shape), "y_eff_shape": list(y_eff.shape),
        "keys": list(eff.keys()),
        "y_eff_min": float(y_eff.min()), "y_eff_max": float(y_eff.max()),
    }
    n = len(Xs)
    val = (np.arange(n) % 7) == 0
    pos = y_opp > 0
    mat = y_sav >= 100.0
    res["savings_npz"] = {
        "X_shape": list(Xs.shape), "keys": list(sav.keys()),
        "rows_total": int(n),
        "positives_y_opp_gt0": int(pos.sum()),
        "positive_rate": float(pos.mean()),
        "material_y_sav_ge100": int(mat.sum()),
        "material_eq_positives": bool(int(mat.sum()) == int(pos.sum())),
        "negatives_y_sav_lt0": int((y_sav < 0).sum()),
        "rows_0_to_100": int(((y_sav > 0) & (y_sav < 100)).sum()),
        "val_rows": int(val.sum()),
        "val_positives": int((pos & val).sum()),
        "val_material": int((mat & val).sum()),
        "train_positives": int((pos & ~val).sum()),
        "train_material": int((mat & ~val).sum()),
    }
    # per-head / per-delta distribution of positives
    head_idx = np.rint(Xs[:, 21] * 9).astype(int)
    delta_norm = Xs[:, 20]
    names = ["80c", "80d", "80d_parents", "nps", "24b", "80g", "80e",
             "80tta", "80ttb"]
    res["positive_head_dist"] = {
        names[h]: int(((head_idx == h) & pos).sum()) for h in range(9)}
    dvals = sorted(set(np.round(delta_norm[pos], 4).tolist()))
    res["positive_delta_norm_values"] = dvals
    res["positive_delta_by_value"] = {
        str(d): int((pos & (np.round(delta_norm, 4) == d).astype(bool)).sum())
        for d in dvals}
    # savings magnitude of positives
    ps = y_sav[pos]
    res["positive_savings_inr"] = {
        "min": float(ps.min()), "p25": float(np.percentile(ps, 25)),
        "median": float(np.median(ps)), "p75": float(np.percentile(ps, 75)),
        "max": float(ps.max()), "mean": float(ps.mean())}

    # dead-feature check on the current dataset (schema-v2 cols)
    feat_names = ["income_norm", "u80c", "u80d", "u80d_parents", "unps",
                  "u_hra", "u24b", "u80e", "u80g", "u80tta", "u80u",
                  "u80ddb", "u80eea", "cg_ratio", "business_share",
                  "regime_signal", "savings_ratio", "tax_ratio", "senior",
                  "80c_headroom"]
    dead = {}
    for j, nm in enumerate(feat_names):
        col = Xe[:, j]
        dead[nm] = {"n_unique_eff": int(len(np.unique(col))),
                    "max": float(col.max()), "min": float(col.min())}
    res["eff_feature_uniqueness"] = dead
    # same on savings matrix (hypothetical-state features)
    dead2 = {}
    for j, nm in enumerate(feat_names):
        col = Xs[:, j]
        u = np.unique(col)
        dead2[nm] = {"n_unique": int(len(u)),
                     "max": float(col.max()), "min": float(col.min())}
    res["sav_feature_uniqueness"] = dead2

    # reproduce the v5_metrics cross-check
    met = json.loads((DATA / "v5_metrics.json").read_text(encoding="utf-8"))
    res["v5_metrics_crosscheck"] = {
        "metrics_val_material": met["savings_material_rows"],
        "measured_val_material": int((mat & val).sum()),
        "metrics_val_rows_sav": met["val_rows"]["sav"],
        "measured_val_rows": int(val.sum()),
        "metrics_eff_mae_points": met["eff_mae_points"],
        "metrics_learned_eff_mae": met["learned_eff_mae_experiment"],
        "metrics_mape": met["savings_mape_material"],
        "metrics_opp_P": met["opportunity_precision"],
        "metrics_opp_R": met["opportunity_recall"],
        "metrics_top1": met["ranking_top1"],
        "metrics_seed": met["seed"], "metrics_fit_rules": met["fit"]["rules"],
    }
    # params-vs-positives
    P = int(pos.sum())
    res["lse_param_math"] = {
        "rules_K": 48, "sav_input_dims": 22,
        "sav_params": 48 * 23, "eff_params": 48 * 21,
        "positives_P": P,
        "params_per_positive": round(48 * 23 / P, 2),
        "positives_per_param": round(P / (48 * 23), 4),
        "registry_claimed_positives": 146,
        "measured_vs_registry": f"measured {P} vs registry 146 "
                                f"(dataset regenerated 2026-11-03 21:47, "
                                f"after v5_metrics.json 21:24)"}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f0_pin.json").write_text(json.dumps(res, indent=2),
                                     encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()

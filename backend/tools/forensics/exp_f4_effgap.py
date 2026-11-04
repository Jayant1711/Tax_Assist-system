# EXP-F4 — efficiency learned-head gap forensics:
# (a) plain ridge on the 20 schema features (closed form, no rules)
# (b) repo K=48 quantile TSK replication (registry: learned MAE 12.772)
# (c) sweep K x placement x dims on a 900-row train subsample, val MAE
# (d) sigma-search on/off isolation
# In-memory only; no repo writes.
import json
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\lenovo\Desktop\Tax_Assist-system-main\Tax_Assist-system-main")
SNAP = Path(__file__).resolve().parent / "snapshot"
DATA = SNAP if SNAP.exists() else REPO / "data" / "anfis_v1"
OUT = Path(__file__).resolve().parent / "out"

import sys
sys.path.insert(0, str(REPO / "backend"))
import tax_intelligence as tmod  # noqa: E402

SEED = 472
SUB = 900
KS = [4, 8, 16, 32, 48, 64, 128]
PLACEMENTS = ["quantile", "kmeans"]
DIMS = {"all20": list(range(20)),
        "signal8": [1, 2, 3, 4, 6, 7, 8, 9],
        "signal9_plus_income": [0, 1, 2, 3, 4, 6, 7, 8, 9]}


def kmeans_means(X, k, rng, iters=25):
    """Deterministic Lloyd: init = per-feature quantile means (repo-style)."""
    d = X.shape[1]
    qs = (np.arange(k) + 0.5) / k
    C = np.stack([np.quantile(X[:, j], qs) for j in range(d)], axis=1)
    for _ in range(iters):
        dist = ((X[:, None, :] - C[None]) ** 2).sum(axis=2)
        lab = dist.argmin(axis=1)
        newC = C.copy()
        for r in range(k):
            pts = X[lab == r]
            if len(pts):
                newC[r] = pts.mean(axis=0)
        if np.allclose(newC, C):
            break
        C = newC
    return C


def fit_config(Xtr, ytr, K, placement, rng, sigma_search=True):
    d = Xtr.shape[1]
    if placement == "quantile":
        means, sigmas = tmod._init_memberships(Xtr, K, rng)
    else:
        means = kmeans_means(Xtr, K, rng)
        spans = np.maximum(Xtr.max(axis=0) - Xtr.min(axis=0), 1e-6)
        sigmas = np.maximum(spans[None, :] / 6.0, 1e-3) * np.ones((K, d))
    best = (sigmas.copy(), None, 1e18)
    scales = ([1.0] + list(rng.uniform(0.4, 2.5, 40))) if sigma_search \
        else [1.0]
    for scale in scales:
        sig_try = sigmas * scale
        wb = tmod._membership(Xtr, means, sig_try)
        cons = tmod._lse(wb, Xtr, ytr)
        pred = tmod._predict_head(wb, cons, Xtr)
        loss = float(np.mean((pred - ytr) ** 2))
        if loss < best[2]:
            best = (sig_try.copy(), cons, loss)
    if sigma_search:
        sig, cons, loss = best
        for _ in range(6):
            j = rng.randint(d)
            if j >= K:
                continue
            cand = sig.copy()
            cand[j] *= rng.uniform(0.7, 1.4)
            wb = tmod._membership(Xtr, means, cand)
            c2 = tmod._lse(wb, Xtr, ytr)
            l2 = float(np.mean((tmod._predict_head(wb, c2, Xtr) - ytr) ** 2))
            if l2 < loss:
                sig, cons, loss = cand, c2, l2
        best = (sig, cons, loss)
    return {"means": means, "sigmas": best[0], "consequents": best[1]}


def eval_pack(pack, Xva, yva):
    wb = tmod._membership(Xva, pack["means"], pack["sigmas"])
    pred = np.clip(tmod._predict_head(wb, pack["consequents"], Xva),
                   0.0, 100.0)
    mae = float(np.mean(np.abs(pred - yva)))
    eff_rules = float(np.mean(1.0 / np.sum(wb ** 2, axis=1)))
    return mae, eff_rules


def main() -> None:
    eff = np.load(DATA / "features.npz")
    Xe, y_eff = eff["X"].astype(np.float64), eff["y_eff"].astype(np.float64)
    n = len(Xe)
    val = (np.arange(n) % 7) == 0
    Xtr, ytr = Xe[~val], y_eff[~val]
    Xva, yva = Xe[val], y_eff[val]
    res = {"rows_train": len(Xtr), "rows_val": len(Xva)}

    # composite-closure check: is y_eff an exact function of the features?
    w = np.zeros(20)
    w[[1, 2, 3, 4, 6, 7, 8, 9]] = [0.40, 0.12, 0.08, 0.15, 0.10, 0.05,
                                   0.05, 0.025]
    comp = np.clip(30.0 + 68.5 * (Xe @ w), 30.0, 98.5)
    res["composite_closure_max_abs_diff"] = float(
        np.abs(comp - y_eff).max())
    print("max |composite - y_eff| =", res["composite_closure_max_abs_diff"])

    # (a) plain ridge, closed form (no rules)
    A = Xtr.T @ Xtr + 1e-8 * np.eye(20)
    coef = np.linalg.solve(A, Xtr.T @ ytr)
    pred_va = Xva @ coef
    res["plain_ridge"] = {
        "val_MAE": round(float(np.mean(np.abs(pred_va - yva))), 6),
        "val_max_abs_err": round(float(np.abs(pred_va - yva).max()), 6),
        "coef_nonzero": int((np.abs(coef) > 1e-6).sum()),
    }
    print("plain ridge:", res["plain_ridge"])

    # (b) repo K=48 quantile replication (fresh SEED-472 rng)
    pack = fit_config(Xtr, ytr, 48, "quantile", np.random.RandomState(SEED))
    mae, eff_rules = eval_pack(pack, Xva, yva)
    res["repo_replication_K48_quantile"] = {
        "val_MAE": round(mae, 4), "mean_effective_rules": round(eff_rules, 2),
        "note": "registry RUN-003 (previous dataset gen) measured 12.7722"}
    print("repo K48 quantile:", res["repo_replication_K48_quantile"])

    # (c) sweep on 900-row subsample
    rng_sub = np.random.RandomState(SEED)
    sub = rng_sub.choice(len(Xtr), min(SUB, len(Xtr)), replace=False)
    Xs, ys = Xtr[sub], ytr[sub]
    sweep = []
    for dname, dims in DIMS.items():
        Xs_d, Xva_d = Xs[:, dims], Xva[:, dims]
        for K in KS:
            for plc in PLACEMENTS:
                pack_c = fit_config(Xs_d, ys, K, plc,
                                    np.random.RandomState(SEED))
                m, er = eval_pack(pack_c, Xva_d, yva)
                row = {"dims": dname, "K": K, "placement": plc,
                       "val_MAE": round(m, 4),
                       "mean_effective_rules": round(er, 2)}
                sweep.append(row)
                print(row)
    res["sweep"] = sweep
    best_row = min(sweep, key=lambda r: r["val_MAE"])
    res["sweep_best"] = best_row
    print("BEST:", best_row)

    # (d) sigma-search isolation at K=48 quantile all20 (900 rows)
    pack_ns = fit_config(Xs, ys, 48, "quantile",
                         np.random.RandomState(SEED), sigma_search=False)
    m_ns, er_ns = eval_pack(pack_ns, Xva, yva)
    res["no_search_K48"] = {"val_MAE": round(m_ns, 4),
                            "mean_effective_rules": round(er_ns, 2)}
    print("no-search K48:", res["no_search_K48"])

    # winner at full train size
    bd = DIMS[best_row["dims"]]
    pack_f = fit_config(Xtr[:, bd], ytr, best_row["K"], best_row["placement"],
                        np.random.RandomState(SEED))
    m_f, er_f = eval_pack(pack_f, Xva[:, bd], yva)
    res["winner_full_train"] = {**best_row, "val_MAE_full_train":
                                round(m_f, 4),
                                "mean_effective_rules": round(er_f, 2)}
    print("winner full-train:", res["winner_full_train"])

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f4_effgap.json").write_text(json.dumps(res, indent=2),
                                        encoding="utf-8")
    print("F4 DONE")


if __name__ == "__main__":
    main()

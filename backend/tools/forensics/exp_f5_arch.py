# EXP-F5 — architecture isolation: minimal TSK variants vs the 48-rule
# repo protocol on the SAME rows, measuring whether rule placement on the
# 1-2 signal dims (regime_signal f15-col15, savings_ratio f16-col16)
# recovers G5/G4. In-memory only.
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
from tax_engine import TaxEngine  # noqa: E402

SEED = 472


def fit_head(X, y, rng, K, sigma_evals=40, iters=6, subsample=6000,
             weights=None):
    means, sigmas = tmod._init_memberships(X, K, rng)
    best = (sigmas.copy(), None, 1e18)
    idx = rng.choice(len(X), min(subsample, len(X)), replace=False)
    Xs, ys = X[idx], y[idx]
    ws = weights[idx] if weights is not None else None
    for scale in [1.0] + list(rng.uniform(0.4, 2.5, sigma_evals)):
        sig_try = sigmas * scale
        wb = tmod._membership(Xs, means, sig_try)
        cons = tmod._lse(wb, Xs, ys, weights=ws)
        pred = tmod._predict_head(wb, cons, Xs)
        loss = float(np.mean((pred - ys) ** 2))
        if loss < best[2]:
            best = (sig_try.copy(), cons, loss)
    sig, cons, loss = best
    for _ in range(iters):
        j = rng.randint(X.shape[1])
        cand = sig.copy()
        cand[j] *= rng.uniform(0.7, 1.4)
        wb = tmod._membership(Xs, means, cand)
        c2 = tmod._lse(wb, Xs, ys, weights=ws)
        l2 = float(np.mean((tmod._predict_head(wb, c2, Xs) - ys) ** 2))
        if l2 < loss:
            sig, cons, loss = cand, c2, l2
    wb_full = tmod._membership(X, means, sig)
    cons_full = tmod._lse(wb_full, X, y, weights=weights)
    return {"means": means, "sigmas": sig, "consequents": cons_full}


def tsk_predict(pack, X):
    wb = tmod._membership(X, pack["means"], pack["sigmas"])
    return tmod._predict_head(wb, pack["consequents"], X)


def sweep_pr(y, s):
    thrs = np.arange(0.01, 0.96, 0.01)
    best = {"thr": None, "P": None, "R": None, "F1": 0.0}
    for t in thrs:
        flag = s >= t
        tp = float(np.sum(flag & (y > 0)))
        fp = float(np.sum(flag & (y == 0)))
        fn = float(np.sum(~flag & (y > 0)))
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        if f1 > best["F1"]:
            best = {"thr": float(t), "P": round(p, 4), "R": round(r, 4),
                    "F1": round(f1, 4)}
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s))
    sp = s[order]
    i = 0
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    npos, nneg = float((y > 0).sum()), float((y == 0).sum())
    auc = (ranks[y > 0].sum() - npos * (npos + 1) / 2) / (npos * nneg)
    return best, round(float(auc), 4)


def mape(pred, truth):
    nz = (truth >= 100.0) & (pred > 0)
    return float(np.mean(np.abs((pred[nz] - truth[nz]) / truth[nz])))


def main() -> None:
    sav = np.load(DATA / "savings.npz")
    X, y_sav, y_opp = sav["X"].astype(np.float64), sav["y_sav"], sav["y_opp"]
    n = len(X)
    val = (np.arange(n) % 7) == 0
    res = {}

    # ---- opportunity head: minimal rule bases on signal dims ----
    Xtr, yo_tr = X[~val], y_opp[~val]
    Xva, yo_va = X[val], y_opp[val]
    pos_tr = np.where(yo_tr > 0)[0]
    neg_tr = np.where(yo_tr == 0)[0]
    rng_b = np.random.RandomState(SEED)
    neg_take = rng_b.choice(neg_tr, size=min(len(neg_tr),
                                             20 * len(pos_tr)),
                            replace=False)
    bal = np.concatenate([pos_tr, neg_take])
    w_bal = np.where(yo_tr[bal] > 0, 5.0, 1.0)
    y_bal = yo_tr[bal]

    for name, dims, K in (
            ("opp_TSK_K2_dims[regime_sig]", [15], 2),
            ("opp_TSK_K8_dims[regime_sig+sav_ratio]", [15, 16], 8),
            ("opp_TSK_K48_dims[regime_sig+sav_ratio]", [15, 16], 48),
            ("opp_TSK_K48_dims[sav_ratio+delta+head]", [16, 20, 21], 48),
    ):
        pack = fit_head(Xtr[bal][:, dims], y_bal, np.random.RandomState(SEED),
                        K, weights=w_bal)
        s = np.clip(tsk_predict(pack, Xva[:, dims]), 0.0, 1.0)
        best, auc = sweep_pr(yo_va, s)
        res[name] = {"gate_sweep_best": best, "auc": auc}
        print(name, "->", best, "AUC", auc)

    # ---- savings head: minimal rule bases ----
    ys_tr, ys_va = y_sav[~val], y_sav[val]
    material = ys_tr >= 100.0
    rng_c = np.random.RandomState(SEED + 1)
    zidx = np.where(~material)[0]
    cond = rng_c.choice(zidx, size=min(len(zidx), 2500), replace=False)
    rows = np.concatenate([np.where(material)[0], cond])
    w_c = np.where(material[rows], 20.0, 0.05)
    y_c = np.log1p(np.maximum(ys_tr[rows], 0.0))

    for name, dims, K in (
            ("sav_TSK_K8_dims[sig+ratio+delta+head]", [15, 16, 20, 21], 8),
            ("sav_TSK_K16_dims[sig+ratio+delta+head]", [15, 16, 20, 21], 16),
            ("sav_TSK_K48_dims[sig+ratio+delta+head]", [15, 16, 20, 21], 48),
    ):
        pack = fit_head(Xtr[rows][:, dims], y_c,
                        np.random.RandomState(SEED), K, weights=w_c)
        pred = np.expm1(np.clip(tsk_predict(pack, Xva[:, dims]), 0.0, 18.0))
        m = mape(pred, ys_va)
        mae = float(np.mean(np.abs(pred[ys_va >= 100] - ys_va[ys_va >= 100])))
        res[name] = {"val_material_mape": round(m, 4),
                     "val_material_mae_inr": round(mae, 2)}
        print(name, "-> MAPE", round(m, 4), "MAE", round(mae, 2))

    # ---- linear ridge with engineered interaction f17*(1-sig) ----
    def inter(Xm):
        sig = Xm[:, 15]
        f17 = Xm[:, 16]
        onehot = np.zeros((len(Xm), 9))
        onehot[np.arange(len(Xm)),
               np.rint(Xm[:, 21] * 9).astype(int)] = 1.0
        return np.hstack([onehot, f17[:, None], sig[:, None],
                          (f17 * (1.0 - sig))[:, None], Xm[:, 20:22]])

    Ai, yc = inter(Xtr[rows]), y_c
    A = (Ai * w_c[:, None]).T @ Ai + 1e-3 * np.eye(Ai.shape[1])
    cons = np.linalg.solve(A, Ai.T @ (w_c * yc))
    pred = np.expm1(np.clip(inter(Xva) @ cons, 0.0, 18.0))
    m = mape(pred, ys_va)
    res["sav_linear_ridge_engineered_interaction"] = {
        "val_material_mape": round(m, 4),
        "val_material_mae_inr": round(float(np.mean(np.abs(
            pred[ys_va >= 100] - ys_va[ys_va >= 100]))), 2)}
    print("sav linear engineered ->", res["sav_linear_ridge_engineered_interaction"])

    # opportunity via the same engineered linear form (logit-free LSE)
    Ai_o = np.hstack([Xva[:, 15:17], (Xva[:, 16] * (1 - Xva[:, 15]))[:,
                                                               None]])
    Atr = np.hstack([Xtr[bal][:, 15:17],
                     (Xtr[bal][:, 16] * (1 - Xtr[bal][:, 15]))[:, None]])
    wb1 = np.ones((len(Atr), 1))
    cons_o = tmod._lse(wb1, Atr, y_bal, weights=w_bal)
    s_o = np.clip(tmod._predict_head(np.ones((len(Ai_o), 1)), cons_o,
                                     Ai_o), 0.0, 1.0)
    best, auc = sweep_pr(yo_va, s_o)
    res["opp_linear_engineered_interaction"] = {"gate_sweep_best": best,
                                                "auc": auc}
    print("opp linear engineered ->", best, "AUC", auc)

    # ---- f21/f23 engine-feature test for savings magnitude ----
    pos_all = np.where(y_opp > 0)[0]
    rng = np.random.RandomState(SEED)
    neg_all = np.where(y_opp == 0)[0]
    idx = np.concatenate([pos_all, rng.choice(neg_all,
                                              size=20 * len(pos_all),
                                              replace=False)])
    idx.sort()
    need = set(idx.tolist())
    sess_map, head_map, delta_map = {}, {}, {}
    with (DATA / "optimization.jsonl").open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i in need:
                r = json.loads(line)
                sess_map[i] = r["session"]
                head_map[i] = r["head"]
                delta_map[i] = r["delta"]
    engine = TaxEngine()
    f21 = np.zeros(len(idx))
    f23 = np.zeros(len(idx))
    for j, i in enumerate(idx):
        sess = sess_map[i]
        rb = engine.calculate_tax_advanced(dict(sess),
                                           tax_year="fy_2025_26")
        old_b = float(rb["old_regime"].total_tax)
        new_b = float(rb["new_regime"].total_tax)
        inc = (float(sess.get("salary") or 0)
               + float(sess.get("business") or 0)
               + float(sess.get("other_income") or 0) + 1e-9)
        f21[j] = old_b / (inc * 0.3 + 1)
        f23[j] = (old_b - new_b) / (inc * 0.3 + 1)
    ptr = np.array([k for k, i in enumerate(idx)
                    if y_opp[i] > 0 and not val[i]])
    pva = np.array([k for k, i in enumerate(idx)
                    if y_opp[i] > 0 and val[i]])
    Xmat = X[idx]
    ymat = y_sav[idx]

    def ridge_fit(Am, ym, wm):
        A = (Am * wm[:, None]).T @ Am + 1e-3 * np.eye(Am.shape[1])
        return np.linalg.solve(A, Am.T @ (wm * ym))

    for tag, eng in (("base_f22_style", None), ("plus_f21_f23", "eng")):
        def build(krows, use_eng):
            f17u = (Xmat[krows, 16]
                    * (Xmat[krows, 0] * 10_000_000 * 0.1 + 1))
            sig = Xmat[krows, 15]
            base = np.hstack([f17u[:, None], sig[:, None],
                              (f17u * (1 - sig))[:, None],
                              Xmat[krows, 20:22]])
            if use_eng == "eng":
                base = np.hstack([base, f21[krows][:, None],
                                  f23[krows][:, None]])
            return base
        Atr2 = build(ptr, eng)
        Ava2 = build(pva, eng)
        wm = np.ones(len(ptr))
        cons2 = ridge_fit(Atr2, np.log1p(np.maximum(ymat[ptr], 0.0)), wm)
        pred2 = np.expm1(np.clip(Ava2 @ cons2, 0.0, 18.0))
        m = mape(pred2, ymat[pva])
        res[f"sav_linear_{tag}"] = {"val_material_mape": round(m, 4)}
        print(f"sav linear {tag} -> MAPE {m:.4f}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f5_arch.json").write_text(json.dumps(res, indent=2),
                                      encoding="utf-8")
    print("F5 DONE")


if __name__ == "__main__":
    main()

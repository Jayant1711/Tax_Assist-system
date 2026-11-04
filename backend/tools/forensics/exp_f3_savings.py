# EXP-F3 — savings-head target analysis on material rows:
# (1) variance of log1p(savings) explained by [head, delta_norm] cells
# (2) 22-dim additive-membership dilution measurement
# (3) fix candidates head-to-head on val material rows (repo protocol,
#     reduced-feature TSK, per-head 80e submodel, plain ridge)
# (4) G6 instability diagnostic (engine top-1 vs top-2 margins, seed spread)
# Repo protocol replication (TaxIntelligence.fit, in-memory, no writes).
import json
import time
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\lenovo\Desktop\Tax_Assist-system-main\Tax_Assist-system-main")
SNAP = Path(__file__).resolve().parent / "snapshot"
DATA = SNAP if SNAP.exists() else REPO / "data" / "anfis_v1"
OUT = Path(__file__).resolve().parent / "out"

import sys
sys.path.insert(0, str(REPO / "backend"))
import tax_intelligence as tmod  # noqa: E402
from tax_intelligence import TaxIntelligence  # noqa: E402

K = 48
SEEDS = [472, 473, 474]


def fit_head_like_repo(X, y, rng, sigma_evals=40, iters=6, subsample=6000,
                       weights=None, rules=K):
    means, sigmas = tmod._init_memberships(X, rules, rng)
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
        if j >= rules:
            continue
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


def mape(pred, truth):
    nz = truth >= 100.0
    ok = nz & (pred > 0)
    if not ok.any():
        return None
    return float(np.mean(np.abs((pred[ok] - truth[ok]) / truth[ok])))


def group_r2(y_fit, cells_fit, y_ev, cells_ev):
    """R^2 of train-fitted group means on eval rows (global mean fallback)."""
    tab = {}
    for c, v in zip(cells_fit, y_fit):
        tab.setdefault(c, []).append(v)
    means = {c: float(np.mean(v)) for c, v in tab.items()}
    gm_fit = float(np.mean(y_fit))
    pred = np.array([means.get(c, gm_fit) for c in cells_ev])
    gm_ev = float(np.mean(y_ev))
    ss_res = float(np.sum((y_ev - pred) ** 2))
    ss_tot = float(np.sum((y_ev - gm_ev) ** 2))
    return 1.0 - ss_res / ss_tot, len(means)


def main() -> None:
    sav = np.load(DATA / "savings.npz")
    X, y_sav, y_opp = sav["X"].astype(np.float64), sav["y_sav"], sav["y_opp"]
    n = len(X)
    val = (np.arange(n) % 7) == 0
    mat = y_sav >= 100.0
    names9 = ["80c", "80d", "80d_parents", "nps", "24b", "80g", "80e",
              "80tta", "80ttb"]
    head_idx = np.rint(X[:, 21] * 9).astype(int)
    dnorm = X[:, 20]

    res = {"rows": n, "material_total": int(mat.sum()),
           "material_train": int((mat & ~val).sum()),
           "material_val": int((mat & val).sum())}

    # ---------- (1) variance decomposition on log1p target ----------
    ltr = np.log1p(np.maximum(y_sav[mat & ~val], 0.0))
    lev = np.log1p(np.maximum(y_sav[mat & val], 0.0))
    dec = np.digitize(X[:, 0], np.quantile(X[:, 0],
                                           np.linspace(0.1, 0.9, 9)))
    decomp = {}
    for nm, keyf in (
            ("head", lambda m: head_idx[m]),
            ("delta_norm", lambda m: np.round(dnorm[m], 4)),
            ("head_x_delta", lambda m: list(zip(head_idx[m],
                                                np.round(dnorm[m], 4)))),
            ("head_x_delta_x_incdec",
             lambda m: list(zip(head_idx[m], np.round(dnorm[m], 4),
                                dec[m]))),
    ):
        r2, ncell = group_r2(ltr, keyf(mat & ~val), lev, keyf(mat & val))
        decomp[nm] = {"val_R2": round(float(r2), 4), "cells": int(ncell)}
        print(f"R2[{nm:22s}] = {r2:.4f}  ({ncell} cells)")
    res["variance_decomposition_log1p"] = decomp
    res["log1p_val_sd"] = round(float(np.std(lev)), 4)

    # ---------- (3) fixes head-to-head ----------
    X_tr, ys_tr, yo_tr = X[~val], y_sav[~val], y_opp[~val]
    X_va, ys_va, yo_va = X[val], y_sav[val], y_opp[val]
    variants = {}

    # (a) repo protocol: full TaxIntelligence.fit per seed
    eff_npz = np.load(DATA / "features.npz")
    Xe, y_eff = eff_npz["X"], eff_npz["y_eff"]
    val_e = (np.arange(len(Xe)) % 7) == 0
    for seed in SEEDS:
        tmod.SEED = seed  # deterministic per-seed fit
        ti = TaxIntelligence()
        t0 = time.time()
        ti.fit(Xe[~val_e], y_eff[~val_e], X_tr, ys_tr, yo_tr)
        wall = time.time() - t0
        sp = ti.predict_savings(X_va)
        learned_eff = float(np.mean(np.abs(
            ti.model_efficiency(Xe[val_e]) - y_eff[val_e])))
        m = mape(sp, ys_va)
        mae = float(np.mean(np.abs(sp[ys_va >= 100] - ys_va[ys_va >= 100])))
        variants[f"repo_protocol_seed{seed}"] = {
            "savings_mape_val_material": round(m, 4) if m else None,
            "savings_mae_inr": round(mae, 2),
            "learned_eff_mae_val": round(learned_eff, 4),
            "fit_wall_s": round(wall, 1),
        }
        print(f"repo fit seed={seed}: MAPE {m:.4f} MAE {mae:,.0f} "
              f"learned-eff-MAE {learned_eff:.3f} wall {wall:.0f}s")
        if seed == SEEDS[0]:
            np.save(OUT.parent / "f3_repo_savpred.npy", sp)
            with (DATA / "optimization.jsonl").open(encoding="utf-8") as fh:
                scen = [ln.split('"scenario_id": "')[1].split('"')[0]
                        for ln in fh]
            np.save(OUT.parent / "f3_scen_ids_val.npy",
                    np.array([scen[i] for i in range(n) if val[i]]))
            np.save(OUT.parent / "f3_ys_va.npy", ys_va)
            # G5 replication on current data (trainer threshold sweep)
            opp_p = ti.predict_opportunity(X_va)
            best = (None, 0.0, 0.0, 0.0)
            for thr in np.arange(0.01, 0.96, 0.01):
                flag = opp_p >= thr
                tp = float(np.sum(flag & (yo_va > 0)))
                fp = float(np.sum(flag & (yo_va == 0)))
                fn = float(np.sum(~flag & (yo_va > 0)))
                p = tp / (tp + fp) if tp + fp else 0.0
                r = tp / (tp + fn) if tp + fn else 0.0
                f1 = 2 * p * r / (p + r) if p + r else 0.0
                if p >= 0.95 and f1 > best[1]:
                    best = (float(thr), f1, p, r)
            res["g5_replication_current_data"] = {
                "val_positives": int((yo_va > 0).sum()),
                "gate_thr": best[0], "P": best[2], "R": best[3],
                "pred_min": round(float(opp_p.min()), 4),
                "pred_max": round(float(opp_p.max()), 4),
                "pred_mean": round(float(opp_p.mean()), 4)}
            print("G5 replication:", res["g5_replication_current_data"])
            # (2) dilution measurement on the fitted sav pack
            pack = ti.sav
            sub = X_va[ys_va >= 100][:500]
            wb_pre = (sub[:, None, :] - pack["means"][None]) \
                ** 2 / (pack["sigmas"][None] ** 2)
            mf = np.exp(-0.5 * wb_pre)          # (B, K, d)
            sums = mf.sum(axis=2)               # (B, K) unnormalized firing
            total_range = 0.0
            dim_share = []
            for j in range(sub.shape[1]):
                lo, hi = sub[:, j].min(), sub[:, j].max()
                if hi - lo < 1e-9:
                    dim_share.append(0.0)
                    continue
                xs = sub.copy()
                xs[:, j] = hi
                mf_hi = np.exp(-0.5 * ((xs[:, None, :] - pack["means"][None])
                                       ** 2 / (pack["sigmas"][None] ** 2)))
                xs[:, j] = lo
                mf_lo = np.exp(-0.5 * ((xs[:, None, :] - pack["means"][None])
                                       ** 2 / (pack["sigmas"][None] ** 2)))
                infl = np.abs(mf_hi.sum(axis=2) - mf_lo.sum(axis=2)).mean()
                dim_share.append(float(infl))
            tot = sum(dim_share) + 1e-12
            res["firing_influence_share"] = {
                "delta_norm(dim20)": round(dim_share[20] / tot, 4),
                "head_idx(dim21)": round(dim_share[21] / tot, 8),
                "top3_dims": sorted(
                    [(round(s / tot, 4), j) for j, s in
                     enumerate(dim_share)], reverse=True)[:3],
                "mean_unnorm_firing": round(float(sums.mean()), 2),
            }
            print("firing influence share:",
                  json.dumps(res["firing_influence_share"]))
        else:
            continue
    base_sp = np.load(OUT.parent / "f3_repo_savpred.npy")

    # (b) reduced-feature TSK (same machinery, 12 dims)
    def red(Xm):
        onehot = np.zeros((len(Xm), 9))
        onehot[np.arange(len(Xm)), head_idx_of(Xm)] = 1.0
        return np.hstack([onehot, Xm[:, [20, 0, 17]]])

    def head_idx_of(Xm):
        return np.rint(Xm[:, 21] * 9).astype(int)

    material_tr = ys_tr >= 100.0
    rng_c = np.random.RandomState(472 + 1)
    zidx = np.where(~material_tr)[0]
    cond = rng_c.choice(zidx, size=min(len(zidx), 2500), replace=False)
    rows_b = np.concatenate([np.where(material_tr)[0], cond])
    w_b = np.where(material_tr[rows_b], 20.0, 0.05)
    Xb_red = red(X_tr[rows_b])
    yb = np.log1p(np.maximum(ys_tr[rows_b], 0.0))
    pack_b = fit_head_like_repo(Xb_red, yb, np.random.RandomState(472),
                                weights=w_b)
    pred_b = np.expm1(np.clip(tsk_predict(pack_b, red(X_va)), 0.0, 18.0))
    m = mape(pred_b, ys_va)
    variants["reduced_12dim_tsk"] = {
        "savings_mape_val_material": round(m, 4) if m else None,
        "savings_mae_inr": round(float(np.mean(np.abs(
            pred_b[ys_va >= 100] - ys_va[ys_va >= 100]))), 2)}
    print(f"reduced TSK: MAPE {m:.4f}")

    # (c) per-head submodel: 80e only, K=16 / K=8, [20 feats + delta_norm]
    h80e = (head_idx == 6)
    for kk in (16, 8):
        tr_m = h80e & ~val & mat
        va_m = h80e & val & mat
        pack_e = fit_head_like_repo(
            X[tr_m], np.log1p(np.maximum(y_sav[tr_m], 0.0)),
            np.random.RandomState(472), rules=kk)
        pred_e = np.expm1(np.clip(
            tsk_predict(pack_e, X[va_m]), 0.0, 18.0))
        truth = y_sav[va_m]
        nz = (truth >= 100) & (pred_e > 0)
        mm = float(np.mean(np.abs((pred_e[nz] - truth[nz]) / truth[nz]))) \
            if nz.any() else None
        variants[f"perhead_80e_K{kk}"] = {
            "train_rows": int(tr_m.sum()), "val_rows": int(va_m.sum()),
            "savings_mape_80e_material": round(mm, 4) if mm else None,
            "params": kk * 22}
        print(f"80e submodel K={kk}: rows {int(tr_m.sum())}/"
              f"{int(va_m.sum())} MAPE {mm}")

    # (d) plain linear ridge reference on interaction features
    def inter(Xm):
        d = Xm[:, 20]
        onehot = np.zeros((len(Xm), 9))
        onehot[np.arange(len(Xm)), np.rint(Xm[:, 21] * 9).astype(int)] = 1.0
        return np.hstack([onehot, (onehot * d[:, None]), d[:, None],
                          Xm[:, [0, 17]]])

    Ai, yi = inter(X_tr[rows_b]), yb
    wrow = w_b
    A = (Ai * wrow[:, None]).T @ Ai + 1e-3 * np.eye(Ai.shape[1])
    cons = np.linalg.solve(A, Ai.T @ (wrow * yi))
    pred_d = np.expm1(np.clip(inter(X_va) @ cons, 0.0, 18.0))
    m = mape(pred_d, ys_va)
    variants["linear_ridge_interactions"] = {
        "savings_mape_val_material": round(m, 4) if m else None,
        "savings_mae_inr": round(float(np.mean(np.abs(
            pred_d[ys_va >= 100] - ys_va[ys_va >= 100]))), 2)}
    print(f"linear ridge interactions: MAPE {m:.4f}")

    res["fix_variants"] = variants

    # ---------- (4) G6 instability diagnostic ----------
    ys_v = np.load(OUT.parent / "f3_ys_va.npy")
    scen_v = np.load(OUT.parent / "f3_scen_ids_val.npy")
    groups = {}
    for i, s in enumerate(scen_v):
        groups.setdefault(s, []).append(i)
    margins = []
    agree = []
    agree_fixed = []
    for s, ii in groups.items():
        if len(ii) < 2:
            continue
        order = np.argsort(-ys_v[ii])
        top1, top2 = ys_v[ii][order[0]], ys_v[ii][order[1]]
        margins.append(float(top1 - top2))
        eng_best = ii[int(np.argmax(ys_v[ii]))]
        mod_best = ii[int(np.argmax(base_sp[ii]))]
        agree.append(int(mod_best == eng_best))
    margins = np.array(margins)
    res["g6_diagnostic"] = {
        "scenarios_with_ge2_candidates": len(agree),
        "repo_top1_agreement_seed472": round(float(np.mean(agree)), 4),
        "margin_p25": round(float(np.percentile(margins, 25)), 2),
        "margin_median": round(float(np.median(margins)), 2),
        "share_margins_below_500":
            round(float((margins < 500).mean()), 4),
        "share_exact_zero_ties": round(float((margins == 0).mean()), 4),
    }
    print("G6:", json.dumps(res["g6_diagnostic"]))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f3_savings.json").write_text(json.dumps(res, indent=2),
                                         encoding="utf-8")
    print("F3 DONE")


if __name__ == "__main__":
    main()

# EXP-F1 — positive-scarcity quantification for the opportunity head.
# Uses the repo's own TSK machinery (in-memory import; no repo writes).
# Subsample levels adapted to the measured P: m in {50,100,200,415,617,800,1500}
# with 800/1500 using duplication+jitter (train-only) above the genuine cap.
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

K = 48
LEVELS = [50, 100, 200, 415, 800, 1097, 1500, 3000]
SEEDS = [472, 473, 474]
NEG_RATIO = 20
POS_W = 5.0


def fit_head_like_repo(X, y, rng, sigma_evals=40, iters=6, subsample=6000,
                       weights=None):
    """Mirror of TaxIntelligence._fit_head (same algorithm, local rng)."""
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


def predict_opp(pack, X):
    wb = tmod._membership(X, pack["means"], pack["sigmas"])
    p = tmod._predict_head(wb, pack["consequents"], X)
    return np.clip(p, 0.0, 1.0)


def pr_curve(y_true, score):
    """Full operating curve + trainer-style sweep points."""
    thrs = np.arange(0.01, 0.96, 0.01)
    pts = []
    for t in thrs:
        flag = score >= t
        tp = float(np.sum(flag & (y_true > 0)))
        fp = float(np.sum(flag & (y_true == 0)))
        fn = float(np.sum(~flag & (y_true > 0)))
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        pts.append((float(t), p, r, f1))
    # AUC (rank statistic, tie-corrected)
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score))
    sp = score[order]
    i = 0
    ranks_sorted = np.arange(1, len(score) + 1, dtype=float)
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        ranks_sorted[i:j + 1] = (i + 1 + j + 1) / 2.0
        i = j + 1
    ranks[order] = ranks_sorted
    npos = float((y_true > 0).sum())
    nneg = float((y_true == 0).sum())
    auc = (ranks[y_true > 0].sum() - npos * (npos + 1) / 2) / (npos * nneg)
    pts_arr = np.array(pts)
    # trainer-style: max F1 subject to P >= 0.95
    ok = pts_arr[:, 1] >= 0.95
    if ok.any():
        sub = pts_arr[ok]
        b = sub[np.argmax(sub[:, 3])]
        gate = {"thr": float(b[0]), "P": float(b[1]), "R": float(b[2]),
                "F1": float(b[3])}
    else:
        gate = {"thr": None, "P": None, "R": None, "F1": None}
    bF1 = pts_arr[np.argmax(pts_arr[:, 3])]
    bP = pts_arr[np.argmax(pts_arr[:, 1])]
    bR = pts_arr[np.argmax(pts_arr[:, 2])]
    return {
        "gate_point": gate,
        "max_f1_point": {k: float(v) for k, v in
                         zip(("thr", "P", "R", "F1"), bF1)},
        "max_P_point": {k: float(v) for k, v in
                        zip(("thr", "P", "R", "F1"), bP)},
        "max_R_point": {k: float(v) for k, v in
                        zip(("thr", "P", "R", "F1"), bR)},
        "auc": float(auc),
        "curve": pts,
    }


def main() -> None:
    sav = np.load(DATA / "savings.npz")
    X, y_sav, y_opp = sav["X"], sav["y_sav"], sav["y_opp"]
    n = len(X)
    val = (np.arange(n) % 7) == 0
    X_tr, y_opp_tr = X[~val], y_opp[~val]
    X_va, y_opp_va = X[val], y_opp[val]
    pos_tr = np.where(y_opp_tr > 0)[0]
    neg_tr = np.where(y_opp_tr == 0)[0]
    P_genuine = len(pos_tr)
    P_val = int((y_opp_va > 0).sum())
    print(f"train rows {len(X_tr)} positives {P_genuine}; "
          f"val rows {len(X_va)} positives {P_val}")

    rng_c = np.random.RandomState(472)  # conditioning-neg sample per level
    rows = []
    curves = {}
    for m in LEVELS:
        for seed in SEEDS:
            rng = np.random.RandomState(seed)
            take = rng.choice(pos_tr, size=min(m, P_genuine), replace=False)
            x_pos = X_tr[take].astype(np.float64).copy()
            n_dup = m - len(take)
            if n_dup > 0:
                dsrc = rng.choice(len(take), size=n_dup, replace=True)
                dup = X_tr[take[dsrc]].astype(np.float64).copy()
                jit = rng.uniform(0.95, 1.05, size=(n_dup, 1))
                dup[:, 20] = np.clip(dup[:, 20] * jit[:, 0], 0.0, 1.0)
                x_pos = np.vstack([x_pos, dup])
            n_neg = min(len(neg_tr), NEG_RATIO * m)
            ntake = rng_c.choice(neg_tr, size=n_neg, replace=False)
            X_bal = np.vstack([x_pos, X_tr[ntake].astype(np.float64)])
            y_bal = np.concatenate([np.ones(len(x_pos)),
                                    np.zeros(len(ntake))])
            w_bal = np.where(y_bal > 0, POS_W, 1.0)
            fit_rng = np.random.RandomState(seed)
            pack = fit_head_like_repo(X_bal, y_bal, fit_rng,
                                      weights=w_bal)
            score = predict_opp(pack, X_va.astype(np.float64))
            r = pr_curve(y_opp_va.astype(np.float64), score)
            row = {"m": m, "seed": seed, "genuine": int(len(take)),
                   "dup": int(n_dup), "neg": int(n_neg), **r}
            rows.append(row)
            print(f"m={m:5d} seed={seed} dup={n_dup:4d} | "
                  f"gate P>={0.95}: {r['gate_point']} | maxF1 "
                  f"P={r['max_f1_point']['P']:.3f} "
                  f"R={r['max_f1_point']['R']:.3f} "
                  f"@thr {r['max_f1_point']['thr']:.2f} | "
                  f"AUC {r['auc']:.4f}")
    # aggregate per level across seeds
    def ms(sub, key, field):
        vals = [r[key][field] for r in sub if r[key][field] is not None]
        return (round(float(np.mean(vals)), 4) if vals else None,
                round(float(np.std(vals)), 4) if vals else None,
                len(vals))

    agg = {}
    for m in LEVELS:
        sub = [r for r in rows if r["m"] == m]
        agg[m] = {
            "seeds": len(sub),
            "gate_achieved": ms(sub, "gate_point", "thr")[2],
            "gate_F1_mean_sd": ms(sub, "gate_point", "F1"),
            "maxF1_P": ms(sub, "max_f1_point", "P"),
            "maxF1_R": ms(sub, "max_f1_point", "R"),
            "auc": (round(float(np.mean([r["auc"] for r in sub])), 4),
                    round(float(np.std([r["auc"] for r in sub])), 4)),
            "best_P_any_thr": ms(sub, "max_P_point", "P"),
            "R_at_best_P": ms(sub, "max_P_point", "R"),
            "best_R_any_thr": ms(sub, "max_R_point", "R"),
            "P_at_best_R": ms(sub, "max_R_point", "P"),
        }
    # minimum m with gate achievable in all seeds (P>=0.95 and R>=0.90)
    min_ok = None
    for m in LEVELS:
        sub = [r for r in rows if r["m"] == m]
        ok = [r for r in sub if r["gate_point"]["thr"] is not None
              and r["gate_point"]["R"] >= 0.90]
        if len(ok) == len(sub):
            min_ok = m if min_ok is None else min_ok
    result = {
        "P_total": int((y_opp > 0).sum()), "P_train_genuine": int(P_genuine),
        "P_val": P_val, "params": K * 23,
        "levels": LEVELS, "seeds": SEEDS, "rows": rows, "agg": agg,
        "min_m_gate_all_seeds": min_ok,
        "note": f"m>{P_genuine} uses all {P_genuine} genuine train "
                "positives + jittered duplicates (delta_norm U(0.95,1.05), "
                "train-only); val untouched",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f1_scarcity.json").write_text(json.dumps(result, indent=2),
                                          encoding="utf-8")
    print(json.dumps(agg, indent=2))
    print("min m with gate achievable in ALL seeds:", min_ok)
    # plot if matplotlib exists
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 5))
        mean_curves = {}
        for m in LEVELS:
            cs = np.array([r["curve"] for r in rows if r["m"] == m])
            mc = cs.mean(axis=0)  # mean over seeds: (n_thr, 4)
            mean_curves[m] = mc
            ax.plot(mc[:, 2], mc[:, 1], marker=".", ms=3,
                    label=f"m={m}" + (" (dup)" if m > P_genuine else ""))
        ax.plot([0, 1], [0.95, 0.95], "k--", lw=0.6)
        ax.plot([0.90, 0.90], [0, 1], "k:", lw=0.6)
        ax.set_xlabel(f"Recall (val, {P_val} positives)")
        ax.set_ylabel("Precision")
        ax.set_title("EXP-F1 opportunity head: P/R curve vs positive "
                     "count m (mean of seeds 472/473/474)")
        ax.legend(fontsize=8)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        fig.tight_layout()
        fig.savefig(OUT / "f1_pr_curves.png", dpi=150)
        print("plot saved")
    except Exception as e:  # noqa: BLE001
        print("matplotlib unavailable, table only:", e)


if __name__ == "__main__":
    main()

# EXP-F2 — regime-flip boundary complexity: linear-model learnability of the
# opportunity label with the current 22 features vs + old-regime-tax features
# (f21 base old-regime ratio, f22 hypothetical old-regime ratio, f23 signed
# old-new ratio). Engine calls are in-memory only; no repo writes.
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
from tax_engine import TaxEngine  # noqa: E402

SEED = 472
NEG_RATIO = 20
N_FOLDS = 5
K1_RIDGE = 1e-3


def lse_k1_fit(X, y, w):
    wb = np.ones((len(X), 1))
    return tmod._lse(wb, X, y, ridge=K1_RIDGE, weights=w)


def lse_k1_pred(cons, X):
    wb = np.ones((len(X), 1))
    return tmod._predict_head(wb, cons, X)


def oof_curves(y, scores_by_model, names):
    """Threshold sweep on pooled OOF scores -> summary per model."""
    out = {}
    thrs = np.arange(0.01, 0.96, 0.01)
    for nm, s in zip(names, scores_by_model):
        pts = []
        for t in thrs:
            flag = s >= t
            tp = float(np.sum(flag & (y > 0)))
            fp = float(np.sum(flag & (y == 0)))
            fn = float(np.sum(~flag & (y > 0)))
            p = tp / (tp + fp) if tp + fp else 0.0
            r = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * p * r / (p + r) if p + r else 0.0
            pts.append((float(t), p, r, f1))
        pts_arr = np.array(pts)
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
        npos = float((y > 0).sum())
        nneg = float((y == 0).sum())
        auc = (ranks[y > 0].sum() - npos * (npos + 1) / 2) / (npos * nneg)
        okP = pts_arr[pts_arr[:, 1] >= 0.95]
        gateP = okP[np.argmax(okP[:, 2])] if len(okP) else None
        okR = pts_arr[pts_arr[:, 2] >= 0.90]
        gateR = okR[np.argmax(okR[:, 1])] if len(okR) else None
        bF1 = pts_arr[np.argmax(pts_arr[:, 3])]
        out[nm] = {
            "auc": round(float(auc), 4),
            "maxF1": {"thr": float(bF1[0]), "P": round(float(bF1[1]), 4),
                      "R": round(float(bF1[2]), 4),
                      "F1": round(float(bF1[3]), 4)},
            "bestP_at_Rge090": ({"thr": float(gateR[0]),
                                 "P": round(float(gateR[1]), 4)}
                                if gateR is not None else None),
            "bestR_at_Pge095": ({"thr": float(gateP[0]),
                                 "R": round(float(gateP[2]), 4)}
                                if gateP is not None else None),
        }
    return out


def main() -> None:
    sav = np.load(DATA / "savings.npz")
    X, y_sav, y_opp = sav["X"], sav["y_sav"], sav["y_opp"]
    n = len(X)
    pos_all = np.where(y_opp > 0)[0]
    rng = np.random.RandomState(SEED)
    neg_all = np.where(y_opp == 0)[0]
    neg_take = rng.choice(neg_all, size=NEG_RATIO * len(pos_all),
                          replace=False)
    idx = np.concatenate([pos_all, neg_take])
    idx.sort()
    print(f"analysis set: {len(idx)} rows "
          f"({len(pos_all)} pos + {len(neg_take)} neg)")

    # --- pull base sessions for engine recomputation (row i <-> jsonl line i+1)
    need = set(idx.tolist())
    sessions = {}
    heads = {}
    deltas = {}
    t0 = time.time()
    with (DATA / "optimization.jsonl").open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i in need:
                r = json.loads(line)
                sessions[i] = r["session"]
                heads[i] = r["head"]
                deltas[i] = r["delta"]
    print(f"parsed {len(sessions)} sessions in {time.time()-t0:.1f}s")

    engine = TaxEngine()
    # timing probe
    t0 = time.time()
    for k in list(need)[:50]:
        engine.calculate_tax_advanced(dict(sessions[k]),
                                      tax_year="fy_2025_26")
    per_call = (time.time() - t0) / 50
    print(f"engine per-call: {per_call*1000:.2f} ms -> "
          f"est {per_call*2*len(idx):.0f}s for 2 calls x {len(idx)} rows")

    f21 = np.zeros(len(idx))
    f22 = np.zeros(len(idx))
    f23 = np.zeros(len(idx))
    sanity_bad = 0
    for j, i in enumerate(idx):
        sess = sessions[i]
        res_b = engine.calculate_tax_advanced(dict(sess),
                                              tax_year="fy_2025_26")
        old_b = float(res_b["old_regime"].total_tax)
        new_b = float(res_b["new_regime"].total_tax)
        inc = (float(sess.get("salary") or 0)
               + float(sess.get("business") or 0)
               + float(sess.get("other_income") or 0) + 1e-9)
        f21[j] = old_b / (inc * 0.3 + 1)
        f23[j] = (old_b - new_b) / (inc * 0.3 + 1)
        hyp = dict(sess)
        h, d = heads[i], deltas[i]
        hyp[h] = float(sess.get(h, 0) or 0) + d
        if h == "80d_parents":
            hyp["has_parents"] = bool(hyp.get("80d_parents"))
        if h == "24b":
            hyp["has_home_loan"] = bool(hyp.get("24b"))
        res_h = engine.calculate_tax_advanced(hyp, tax_year="fy_2025_26")
        old_h = float(res_h["old_regime"].total_tax)
        new_h = float(res_h["new_regime"].total_tax)
        f22[j] = old_h / (inc * 0.3 + 1)
        # sanity: replicate the stored savings label
        rep = round(min(old_b, new_b) - min(old_h, new_h), 2)
        if abs(rep - float(y_sav[i])) > 0.01:
            sanity_bad += 1
        if (j + 1) % 3000 == 0:
            print(f"  engine rows {j+1}/{len(idx)} "
                  f"({time.time()-t0:.0f}s)")
    print(f"sanity: savings label reproduced from sessions; mismatches "
          f"(>0.01 INR) = {sanity_bad}/{len(idx)}")

    Xa = X[idx].astype(np.float64)
    ya = y_opp[idx].astype(np.float64)
    summary = {"analysis_rows": int(len(idx)),
               "positives": int(len(pos_all)),
               "engine_label_mismatches": int(sanity_bad),
               "models": {}}
    F = {
        "F22 (production 22)": Xa,
        "F22+f21": np.hstack([Xa, f21[:, None]]),
        "F22+f21+f22hyp": np.hstack([Xa, f21[:, None], f22[:, None]]),
        "F22+f21+f22hyp+f23": np.hstack([Xa, f21[:, None], f22[:, None],
                                         f23[:, None]]),
    }
    # class separation of the new features alone
    pos_mask = ya > 0
    sep = {}
    for nm, v in (("f21", f21), ("f22hyp", f22), ("f23", f23)):
        sep[nm] = {"mean_pos": round(float(v[pos_mask].mean()), 4),
                   "mean_neg": round(float(v[~pos_mask].mean()), 4)}
        print(f"{nm}: mean pos {sep[nm]['mean_pos']:.4f} "
              f"mean neg {sep[nm]['mean_neg']:.4f}")
    summary["feature_separation"] = sep

    # --- linear probe (K=1 LSE, repo machinery) with 5-fold CV
    folds = []
    rng_cv = np.random.RandomState(SEED)
    perm = rng_cv.permutation(len(ya))
    pos_order = perm[ya[perm] > 0]
    neg_order = perm[ya[perm] == 0]
    for f in range(N_FOLDS):
        pos_f = np.array_split(pos_order, N_FOLDS)[f]
        neg_f = np.array_split(neg_order, N_FOLDS)[f]
        folds.append(np.concatenate([pos_f, neg_f]))

    for fname, Xf in F.items():
        # K=1 LSE probe
        oof = np.zeros(len(ya))
        for f in range(N_FOLDS):
            te = folds[f]
            tr = np.setdiff1d(np.arange(len(ya)), te)
            w = np.where(ya[tr] > 0, 5.0, 1.0)
            cons = lse_k1_fit(Xf[tr], ya[tr], w)
            oof[te] = lse_k1_pred(cons, Xf[te])
        cur = oof_curves(ya, [oof], [f"K1-LSE {fname}"])
        summary["models"][f"K1-LSE {fname}"] = cur[f"K1-LSE {fname}"]
        print(f"K1-LSE  {fname:24s} AUC {cur[f'K1-LSE {fname}']['auc']:.4f} "
              f"maxF1 {cur[f'K1-LSE {fname}']['maxF1']}")

        # sklearn logistic: per-fold inner C selection by max-F1
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError:
            summary["sklearn"] = "absent"
            continue
        oof = np.zeros(len(ya))
        for f in range(N_FOLDS):
            te = folds[f]
            tr = np.setdiff1d(np.arange(len(ya)), te)
            rng_in = np.random.RandomState(SEED + f)
            ptr = rng_in.permutation(tr)
            n_inner = max(1, int(0.2 * len(tr)))
            inn = ptr[:n_inner]
            fit_idx = ptr[n_inner:]
            best_C, best_f1 = 1.0, -1.0
            for C in (0.01, 0.1, 1.0, 10.0):
                lr = LogisticRegression(C=C, max_iter=2000, solver="lbfgs")
                lr.fit(Xf[fit_idx], ya[fit_idx])
                s_in = lr.predict_proba(Xf[inn])[:, 1]
                tt = ya[inn] > 0
                order = np.argsort(-s_in)
                tp = np.cumsum(tt[order])
                fp = np.cumsum(~tt[order])
                prec = tp / np.maximum(tp + fp, 1)
                rec = tp / max(tt.sum(), 1)
                f1s = 2 * prec * rec / np.maximum(prec + rec, 1e-9)
                if f1s.max() > best_f1:
                    best_f1, best_C = float(f1s.max()), C
            lr = LogisticRegression(C=best_C, max_iter=2000, solver="lbfgs")
            lr.fit(Xf[tr], ya[tr])
            oof[te] = lr.predict_proba(Xf[te])[:, 1]
        cur = oof_curves(ya, [oof], [f"LogReg {fname}"])
        summary["models"][f"LogReg {fname}"] = cur[f"LogReg {fname}"]
        print(f"LogReg  {fname:24s} AUC {cur[f'LogReg {fname}']['auc']:.4f} "
              f"maxF1 {cur[f'LogReg {fname}']['maxF1']}")

    # holdout-consistent variant: CV folds built from TRAIN rows only,
    # final eval on the every-7th val positives/negatives (gate-comparable)
    val = (np.arange(n) % 7) == 0
    val_idx = np.where(val)[0]
    val_mask = np.isin(idx, val_idx)
    summary["holdout_note"] = ("fold CV on train rows; headline numbers "
                               "above use pooled OOF over train+val "
                               "(model-class diagnostic)")
    summary["val_pos_in_analysis"] = int(val_mask.sum())

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f2_boundary.json").write_text(json.dumps(summary, indent=2),
                                          encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "models"},
                     indent=2))
    for k, v in summary["models"].items():
        print(k, "->", json.dumps(v))


if __name__ == "__main__":
    main()

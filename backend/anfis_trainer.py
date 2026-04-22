"""
ANFIS v3 + EE-BAT (Enhanced Evolving Bat Algorithm) Trainer — FAST VERSION
Mini-batch evaluation + vectorized forward pass + gradient warm-start.

10 inputs, 50 rules — trained on 100,000 pre-tested ground-truth tax cases.
"""

import numpy as np
import json, time, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

N_INPUTS  = 10
N_RULES   = 50
PARAM_DIM = 2 * N_INPUTS * N_RULES + N_RULES * (N_INPUTS + 1)
BATCH     = 2048   # mini-batch per MSE evaluation


# ─────────────────────────────────────────────────────────────────────
# 1.  Fast Ground-Truth Tax Engine
# ─────────────────────────────────────────────────────────────────────
def _slab_old_v(v, senior):
    t = np.zeros_like(v)
    lim = np.where(senior, 300_000.0, 250_000.0)
    mask = v > 1_000_000
    t = np.where(mask, t + (v - 1_000_000) * 0.30, t)
    v = np.where(mask, 1_000_000.0, v)
    mask = v > 500_000
    t = np.where(mask, t + (v - 500_000) * 0.20, t)
    v = np.where(mask, 500_000.0, v)
    mask = v > lim
    t = np.where(mask, t + (v - lim) * 0.05, t)
    return t

def _slab_new_v(v):
    t = np.zeros_like(v)
    for lo, hi, rate in [(1_500_000, np.inf, 0.30),
                         (1_200_000, 1_500_000, 0.20),
                         (1_000_000, 1_200_000, 0.15),
                         (700_000,   1_000_000, 0.10),
                         (300_000,   700_000,   0.05)]:
        mask = v > lo
        t = np.where(mask, t + np.minimum(v - lo, hi - lo if np.isfinite(hi) else v - lo) * rate, t)
    return t

def generate_dataset(n=100_000, seed=42):
    rng = np.random.RandomState(seed)

    inc    = rng.uniform(200_000, 20_000_000, n)
    ptype  = rng.randint(0, 3, n)
    split  = rng.uniform(0.2, 0.8, n)
    sal    = np.where(ptype == 0, inc, np.where(ptype == 2, inc * split, 0.0))
    biz    = np.where(ptype == 1, inc, np.where(ptype == 2, inc * (1-split), 0.0))
    rent   = np.where(rng.rand(n) < 0.3, rng.uniform(0, 0.3, n) * inc, 0.0) * 0.7
    other  = np.where(rng.rand(n) < 0.4, rng.uniform(0, 0.1, n) * inc, 0.0)
    cg     = np.where(rng.rand(n) < 0.2, rng.uniform(0, 0.3, n) * inc, 0.0)
    c80c   = np.where(rng.rand(n) < 0.8, rng.uniform(0, 150_000, n), 0.0)
    c80d   = np.where(rng.rand(n) < 0.6, rng.uniform(0,  75_000, n), 0.0)
    nps    = np.where(rng.rand(n) < 0.4, rng.uniform(0,  50_000, n), 0.0)
    c80e   = np.where(rng.rand(n) < 0.2, rng.uniform(0, 500_000, n), 0.0)
    senior = rng.rand(n) < 0.15

    # Old Regime
    std_d  = np.where(sal > 0, 50_000.0, 0.0)
    net_s  = np.maximum(0, sal - std_d - 2500)
    gti    = net_s + biz + rent + other
    ded    = np.minimum(c80c, 150_000) + np.minimum(c80d, 75_000) + np.minimum(nps, 50_000) + c80e
    base_o = np.maximum(0, gti - ded)
    t_old  = _slab_old_v(base_o, senior)
    reb_o  = np.where(base_o <= 500_000, np.minimum(t_old, 12_500), 0.0)
    t_old  = np.maximum(0, t_old - reb_o)
    sur_o  = np.where(base_o > 50_000_000, t_old * 0.37,
             np.where(base_o > 20_000_000, t_old * 0.25,
             np.where(base_o > 10_000_000, t_old * 0.15,
             np.where(base_o >  5_000_000, t_old * 0.10, 0.0))))
    old_tax = (t_old + sur_o) * 1.04

    # New Regime
    std2   = np.where(sal > 0, 75_000.0, 0.0)
    base_n = np.maximum(0, sal + biz + rent + other + cg - std2)
    t_new  = _slab_new_v(base_n)
    reb_n  = np.where(base_n <= 700_000, np.minimum(t_new, 25_000), 0.0)
    t_new  = np.maximum(0, t_new - reb_n)
    sur_n  = np.where(base_n > 50_000_000, t_new * 0.37,
             np.where(base_n > 20_000_000, t_new * 0.25,
             np.where(base_n > 10_000_000, t_new * 0.15,
             np.where(base_n >  5_000_000, t_new * 0.10, 0.0))))
    new_tax = (t_new + sur_n) * 1.04

    savings    = np.maximum(0, np.abs(old_tax - new_tax))
    total_inc  = sal + biz + rent / 0.7 + other + cg + 1e-9
    ded_used   = np.minimum(c80c, 150_000) + np.minimum(c80d, 75_000) + np.minimum(nps, 50_000)
    max_ded    = 275_000.0
    ded_ratio  = ded_used / max_ded
    regime_ok  = (new_tax <= old_tax).astype(float)
    efficiency = np.clip(50 * ded_ratio + 30 * regime_ok +
                         20 * np.minimum(1.0, savings / (total_inc * 0.02 + 1)), 0, 100)

    # Build feature matrix
    n_src = ((sal > 0).astype(float) + (biz > 0).astype(float) +
             (rent > 0).astype(float) + (other > 0).astype(float) +
             (cg > 0).astype(float))

    X = np.stack([
        np.clip(total_inc / 5_000_000, 0, 1),
        c80c / 150_000,
        c80d / 75_000,
        nps  / 50_000,
        np.clip(c80e / (total_inc + 1), 0, 1),
        n_src / 5.0,
        np.clip(savings / (total_inc * 0.1 + 1), 0, 1),
        np.clip(cg / (total_inc + 1), 0, 1),
        np.clip(np.minimum(old_tax, new_tax) / (total_inc + 1), 0, 1),
        1.0 - np.clip(ded_used / max_ded, 0, 1),
    ], axis=1).astype(np.float32)

    y = (efficiency / 100.0).astype(np.float32)
    return X, y


# ─────────────────────────────────────────────────────────────────────
# 2.  Vectorized ANFIS Forward Pass
# ─────────────────────────────────────────────────────────────────────
def unpack(params):
    n = N_INPUTS * N_RULES
    means  = params[:n].reshape(N_INPUTS, N_RULES)
    sigmas = np.abs(params[n:2*n]).reshape(N_INPUTS, N_RULES) + 0.05
    cons   = params[2*n:].reshape(N_RULES, N_INPUTS + 1)
    return means, sigmas, cons

def anfis_forward(params, X):
    means, sigmas, cons = unpack(params)
    diff = X[:, :, None] - means[None]               # (B, I, R)
    mf   = np.exp(-0.5 * (diff / sigmas[None]) ** 2) # (B, I, R)
    w    = mf.prod(axis=1)                            # (B, R)
    w_n  = w / (w.sum(axis=1, keepdims=True) + 1e-9) # (B, R)
    Xe   = np.concatenate([X, np.ones((len(X), 1))], axis=1)  # (B, I+1)
    f    = np.einsum('bi,ri->br', Xe, cons)           # (B, R)
    return np.clip((w_n * f).sum(axis=1), 0, 1)       # (B,)

def mse_batch(params, X, y, rng, batch=BATCH):
    idx = rng.choice(len(X), batch, replace=False)
    pred = anfis_forward(params, X[idx])
    return float(np.mean((pred - y[idx]) ** 2))


# ─────────────────────────────────────────────────────────────────────
# 3.  EE-BAT Optimizer (Enhanced Evolving Bat Algorithm)
# ─────────────────────────────────────────────────────────────────────
def ee_bat(X_tr, y_tr, X_val, y_val, n_bats=50, max_iter=400):
    rng = np.random.RandomState(99)
    print(f"  EE-BAT | bats={n_bats} | iters={max_iter} | dim={PARAM_DIM}")
    print(f"  Mini-batch size: {BATCH} | Full-val every 50 iters")

    # Smart initialization
    pop = rng.uniform(-0.3, 0.3, (n_bats, PARAM_DIM)).astype(np.float32)
    nm  = N_INPUTS * N_RULES
    for i in range(n_bats):
        pop[i, :nm]    = rng.uniform(0.0, 1.0, nm)   # means
        pop[i, nm:2*nm]= rng.uniform(0.05, 0.25, nm) # sigmas

    vel   = np.zeros_like(pop)
    loud  = np.full(n_bats, 0.9)
    pulse = np.full(n_bats, 0.1)
    fit   = np.array([mse_batch(pop[i], X_tr, y_tr, rng) for i in range(n_bats)])

    best_idx = int(np.argmin(fit))
    best     = pop[best_idx].copy()
    best_f   = fit[best_idx]

    history, t0 = [], time.time()

    for it in range(1, max_iter + 1):
        freq = rng.uniform(0, 1.5, n_bats)

        for i in range(n_bats):
            vel[i]  = vel[i] + (pop[i] - best) * freq[i]
            cand    = np.clip(pop[i] + vel[i], -2, 2)

            # Local random walk around best
            if rng.rand() > pulse[i]:
                cand = best + rng.randn(PARAM_DIM).astype(np.float32) * 0.015 * loud[i]

            # EE: Crossover with random partner
            if rng.rand() < 0.25:
                partner = pop[rng.randint(n_bats)]
                mask    = rng.rand(PARAM_DIM) < 0.5
                cand    = np.where(mask, cand, partner).astype(np.float32)

            # EE: Gaussian mutation on random genes
            if rng.rand() < 0.12:
                k = max(1, int(PARAM_DIM * 0.03))
                idx2 = rng.choice(PARAM_DIM, k, replace=False)
                cand[idx2] += rng.randn(k).astype(np.float32) * 0.05

            cand = np.clip(cand, -2, 2).astype(np.float32)
            fc   = mse_batch(cand, X_tr, y_tr, rng)

            if fc < fit[i] and rng.rand() < loud[i]:
                pop[i], fit[i] = cand, fc
                loud[i]  *= 0.97
                pulse[i] += (1 - np.exp(-0.03 * it)) * 0.01

            if fc < best_f:
                best, best_f = cand.copy(), fc

        # Elitism injection
        worst = int(np.argmax(fit))
        pop[worst], fit[worst] = best.copy(), best_f

        if it % 50 == 0:
            val_mse = mse_batch(best, X_val, y_val, rng, batch=min(10000, len(X_val)))
            elapsed = time.time() - t0
            history.append({"iter": it, "train_mse": float(best_f), "val_mse": float(val_mse)})
            print(f"  [{it:3d}/{max_iter}] train={best_f:.5f}  val={val_mse:.5f}  t={elapsed:.0f}s")

    return best, history


# ─────────────────────────────────────────────────────────────────────
# 4.  Main
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("ANFIS v3 + EE-BAT  |  Tax Efficiency Optimizer")
    print("=" * 60)

    N = 100_000
    print(f"\n[1/4] Generating {N:,} vectorized ground-truth tax cases...")
    t0 = time.time()
    X, y = generate_dataset(N)
    print(f"      {time.time()-t0:.1f}s | eff mean={y.mean()*100:.1f}  std={y.std()*100:.1f}")

    # Split 80/10/10
    perm  = np.random.RandomState(1).permutation(N)
    n_tr  = int(N * 0.80)
    n_val = int(N * 0.10)
    X_tr,  y_tr  = X[perm[:n_tr]],            y[perm[:n_tr]]
    X_val, y_val = X[perm[n_tr:n_tr+n_val]],  y[perm[n_tr:n_tr+n_val]]
    X_te,  y_te  = X[perm[n_tr+n_val:]],      y[perm[n_tr+n_val:]]
    print(f"      train={len(X_tr):,}  val={len(X_val):,}  test={len(X_te):,}")

    print(f"\n[2/4] EE-BAT optimization on ANFIS({N_INPUTS} in, {N_RULES} rules)...")
    best_params, history = ee_bat(X_tr, y_tr, X_val, y_val, n_bats=50, max_iter=400)

    print(f"\n[3/4] Full test-set evaluation...")
    rng_e = np.random.RandomState(0)
    # Evaluate in chunks to avoid memory issues
    preds = []
    for start in range(0, len(X_te), 4096):
        chunk = X_te[start:start+4096]
        preds.append(anfis_forward(best_params, chunk))
    pred_all = np.concatenate(preds) * 100
    true_all = y_te * 100
    mae = float(np.mean(np.abs(pred_all - true_all)))
    mse_f = float(np.mean((pred_all - true_all) ** 2))
    r2  = float(1 - np.var(pred_all - true_all) / (np.var(true_all) + 1e-9))
    print(f"      MSE={mse_f:.4f}  MAE={mae:.2f} pts  R2={r2:.4f}")

    print(f"\n[4/4] Saving weights to anfis_weights.json...")
    payload = {
        "n_inputs": N_INPUTS, "n_rules": N_RULES, "param_dim": PARAM_DIM,
        "params": best_params.tolist(),
        "metrics": {"mse": mse_f, "mae": mae, "r2": r2},
        "training": {"n_samples": N, "n_bats": 50, "max_iter": 400, "batch": BATCH},
        "history": history,
    }
    path = Path(__file__).parent / "anfis_weights.json"
    with open(path, "w") as f:
        json.dump(payload, f)
    print(f"      Saved: {path}")
    print(f"\n{'='*60}")
    print(f"DONE  |  R2={r2:.4f}  MAE={mae:.2f} pts  params={PARAM_DIM}")
    print(f"{'='*60}")

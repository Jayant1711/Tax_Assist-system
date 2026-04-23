"""
ANFIS v4 Industrial — The "Gold Standard" Tax Intelligence Trainer
FY 2024-25 (AY 2025-26) | 20-D Feature Vector | 1,000,000 Ground Truth Cases
"""

import numpy as np
import json, time, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

N_INPUTS  = 20
N_RULES   = 64  # Increased rules for more granular resolution
PARAM_DIM = 2 * N_INPUTS * N_RULES + N_RULES * (N_INPUTS + 1)
BATCH     = 4096 

# ─────────────────────────────────────────────────────────────────────
# 1.  Industrial Ground-Truth Tax Engine (Vectorized)
# ─────────────────────────────────────────────────────────────────────
def _slab_old_v(v, senior, vsr):
    t = np.zeros_like(v)
    ex = np.where(vsr, 500_000.0, np.where(senior, 300_000.0, 250_000.0))
    # 30% bucket
    m = v > 1_000_000
    t = np.where(m, t + (v - 1_000_000) * 0.30, t); v = np.where(m, 1_000_000.0, v)
    # 20% bucket
    m = v > 500_000
    t = np.where(m, t + (v - 500_000) * 0.20, t); v = np.where(m, 500_000.0, v)
    # 5% bucket
    m = v > ex
    t = np.where(m, t + (v - ex) * 0.05, t)
    return t

def _slab_new_v(v):
    t = np.zeros_like(v)
    for lo, hi, rate in [(1_500_000, np.inf, 0.30),(1_200_000, 1_500_000, 0.20),
                         (1_000_000, 1_200_000, 0.15),(700_000, 1_000_000, 0.10),(300_000, 700_000, 0.05)]:
        m = v > lo
        t = np.where(m, t + np.minimum(v - lo, hi - lo if np.isfinite(hi) else v - lo) * rate, t)
    return t

def generate_dataset(n=1_000_000, seed=42):
    rng = np.random.RandomState(seed)
    print(f"Generating 1,000,000 industrial tax scenarios...")

    # Income components
    inc = rng.uniform(200_000, 100_000_000, n) # Up to 10 Cr
    age = rng.randint(20, 90, n)
    senior, vsr = age >= 60, age >= 80
    
    sal   = np.where(rng.rand(n) < 0.6, inc * rng.uniform(0.5, 1.0, n), 0.0)
    biz   = np.where(rng.rand(n) < 0.3, inc * rng.uniform(0.3, 0.8, n), 0.0)
    rent  = np.where(rng.rand(n) < 0.2, rng.uniform(10_000, 200_000, n) * 12, 0.0)
    cg    = np.where(rng.rand(n) < 0.15, rng.uniform(0, 0.4, n) * inc, 0.0)
    agri  = np.where(rng.rand(n) < 0.05, rng.uniform(50_000, 1_000_000, n), 0.0)
    other = rng.uniform(0, 0.05, n) * inc

    # Deduction profiles
    c80c  = np.where(rng.rand(n) < 0.85, rng.uniform(0, 200_000, n), 0.0)
    c80d  = np.where(rng.rand(n) < 0.60, rng.uniform(0, 40_000, n), 0.0)
    c80dp = np.where(rng.rand(n) < 0.40, rng.uniform(0, 60_000, n), 0.0)
    nps   = np.where(rng.rand(n) < 0.35, rng.uniform(0, 60_000, n), 0.0)
    c80e  = np.where(rng.rand(n) < 0.10, rng.uniform(0, 800_000, n), 0.0)
    c80g  = np.where(rng.rand(n) < 0.15, rng.uniform(0, 0.2 * inc, n), 0.0)
    c24b  = np.where(rng.rand(n) < 0.25, rng.uniform(0, 300_000, n), 0.0)
    c80u  = np.where(rng.rand(n) < 0.05, rng.choice([75000, 125000], n), 0.0)
    c80ddb= np.where(rng.rand(n) < 0.03, rng.uniform(0, 100_000, n), 0.0)
    c80eea= np.where(rng.rand(n) < 0.08, 150_000.0, 0.0)
    tt    = np.where(senior, rng.uniform(0, 60000, n), rng.uniform(0, 15000, n))

    # Calculate Old Tax
    hra_ex = np.where(sal > 0, np.minimum(0.2*sal, np.maximum(0, rng.uniform(0, 0.3, n)*sal - 0.05*sal)), 0.0)
    std_o  = np.where(sal > 0, 50000.0, 0.0)
    nsal_o = np.maximum(0, sal - std_o - hra_ex)
    nrent  = np.maximum(-200_000, (rent * 0.7) - np.minimum(c24b, 200000))
    gti    = nsal_o + biz + nrent + other
    via    = (np.minimum(c80c, 150000) + np.minimum(c80d, 25000) + np.minimum(c80dp, 50000) +
              c80e + np.minimum(c80g, 0.1*gti) + np.minimum(nps, 50000) +
              np.where(senior, np.minimum(tt, 50000), np.minimum(tt, 10000)) +
              c80u + np.minimum(c80ddb, 100000) + c80eea)
    base_o = np.maximum(0, gti - via)
    t_o    = _slab_old_v(base_o, senior, vsr)
    reb_o  = np.where(base_o <= 500000, np.minimum(t_o, 12500), 0.0)
    t_o    = np.maximum(0, t_o - reb_o)
    total_inc_full = base_o + cg
    sur_o  = np.where(total_inc_full > 50_000_000, t_o * 0.37, np.where(total_inc_full > 20_000_000, t_o * 0.25, 0.0))
    tax_o  = (t_o + sur_o) * 1.04

    # New Regime
    std_n  = np.where(sal > 0, 75000.0, 0.0)
    base_n = np.maximum(0, sal + biz + (rent*0.7) + other - std_n)
    t_n    = _slab_new_v(base_n)
    reb_n  = np.where(base_n <= 700000, np.minimum(t_n, 25000), 0.0)
    t_n    = np.maximum(0, t_n - reb_n)
    sur_n  = np.where(base_n > 50_000_000, t_n * 0.25, 0.0)
    tax_n  = (t_n + sur_n) * 1.04

    # Efficiency Logic
    savings = np.abs(tax_o - tax_n)
    best_tax = np.minimum(tax_o, tax_n)
    total_gti = inc + 1e-9
    ded_cap = 275_000
    ded_util = np.minimum(c80c + c80d + nps, ded_cap)
    eff = (40 * (ded_util/ded_cap) + 20 * (savings/(inc*0.05 + 1)) + 40 * (1 - best_tax/total_gti))
    y = np.clip(eff/100.0, 0, 1).astype(np.float32)

    # Features (20D)
    X = np.stack([
        np.clip(inc/10_000_000, 0, 1), # 0
        np.clip(c80c/150000, 0, 1),    # 1
        np.clip(c80d/25000, 0, 1),     # 2
        np.clip(c80dp/50000, 0, 1),    # 3
        np.clip(nps/50000, 0, 1),      # 4
        np.clip(hra_ex/200000, 0, 1),  # 5
        np.clip(c24b/200000, 0, 1),    # 6
        np.clip(c80e/500000, 0, 1),    # 7
        np.clip(c80g/(inc*0.1+1), 0, 1),# 8
        np.clip(tt/50000, 0, 1),       # 9
        np.clip(c80u/125000, 0, 1),    # 10
        np.clip(c80ddb/100000, 0, 1),  # 11
        np.clip(c80eea/150000, 0, 1),  # 12
        np.clip(cg/(inc+1), 0, 1),     # 13
        np.clip(biz/(inc+1), 0, 1),    # 14
        np.clip(age/100, 0, 1),        # 15
        np.clip(savings/(inc*0.1+1), 0, 1),# 16
        np.clip(best_tax/(inc*0.3+1), 0, 1),# 17
        np.where(senior, 1.0, 0.0),    # 18
        1.0 - (ded_util/ded_cap)       # 19
    ], axis=1).astype(np.float32)

    return X, y

# ─────────────────────────────────────────────────────────────────────
# 2.  Optimized Trainer (EE-BAT + Mini-Batch)
# ─────────────────────────────────────────────────────────────────────
def unpack(p):
    n = N_INPUTS * N_RULES
    m = p[:n].reshape(N_INPUTS, N_RULES)
    s = np.abs(p[n:2*n]).reshape(N_INPUTS, N_RULES) + 0.05
    c = p[2*n:].reshape(N_RULES, N_INPUTS + 1)
    return m, s, c

def anfis_fwd(p, X):
    m, s, c = unpack(p)
    diff = X[:, :, None] - m[None]
    mf = np.exp(-0.5 * (diff/s[None])**2)
    w = mf.prod(axis=1)
    wn = w / (w.sum(axis=1, keepdims=True) + 1e-9)
    Xe = np.concatenate([X, np.ones((len(X), 1))], axis=1)
    f = np.einsum('bi,ri->br', Xe, c)
    return np.clip((wn * f).sum(axis=1), 0, 1)

def train(X_tr, y_tr, X_val, y_val, iters=500):
    rng = np.random.RandomState(42)
    pop = rng.uniform(-0.1, 0.1, (30, PARAM_DIM)).astype(np.float32)
    # Calibrate means/sigmas
    pop[:, :N_INPUTS*N_RULES] = rng.uniform(0, 1, (30, N_INPUTS*N_RULES))
    pop[:, N_INPUTS*N_RULES:2*N_INPUTS*N_RULES] = 0.2
    
    best = pop[0]; best_f = 1e9
    print(f"Starting EE-BAT training on {PARAM_DIM} parameters...")
    
    for it in range(1, iters+1):
        idx = rng.choice(len(X_tr), BATCH)
        Xb, yb = X_tr[idx], y_tr[idx]
        
        for i in range(len(pop)):
            cand = pop[i] + rng.randn(PARAM_DIM) * 0.01
            f = np.mean((anfis_fwd(cand, Xb) - yb)**2)
            if f < best_f:
                best = cand.copy(); best_f = f
                pop[i] = cand
        
        if it % 50 == 0:
            v_idx = rng.choice(len(X_val), 10000)
            vf = np.mean((anfis_fwd(best, X_val[v_idx]) - y_val[v_idx])**2)
            print(f"  [{it:4d}] Loss: {best_f:.6f} | Val Loss: {vf:.6f}")
            
    return best

if __name__ == "__main__":
    X, y = generate_dataset(200_000)
    n = len(X)
    p = np.random.permutation(n)
    X_tr, y_tr = X[p[:int(n*0.8)]], y[p[:int(n*0.8)]]
    X_val, y_val = X[p[int(n*0.8):]], y[p[int(n*0.8):]]
    
    best_params = train(X_tr, y_tr, X_val, y_val)
    
    # Final evaluation
    pred = anfis_fwd(best_params, X_val[:10000])
    r2 = 1 - np.var(pred - y_val[:10000]) / np.var(y_val[:10000])
    
    payload = {
        "n_inputs": N_INPUTS, "n_rules": N_RULES, "params": best_params.tolist(),
        "metrics": {"r2": float(r2), "mse": float(np.mean((pred - y_val[:10000])**2))}
    }
    with open("anfis_weights.json", "w") as f:
        json.dump(payload, f)
    print(f"Training Complete. R2 Score: {r2:.4f}")

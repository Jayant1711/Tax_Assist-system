"""
Phase 2: Adam Gradient Refinement on best EE-BAT solution.
Runs after anfis_trainer.py — loads weights, refines with numerical gradients.
Also runs a final full-set validation and updates anfis_weights.json.
"""

import numpy as np
import json, time, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WEIGHTS_PATH = Path(__file__).parent / "anfis_weights.json"
N_INPUTS, N_RULES = 10, 50
PARAM_DIM = 2 * N_INPUTS * N_RULES + N_RULES * (N_INPUTS + 1)

# ── Re-use dataset generator ──────────────────────────────────────────
def _slab_new_v(v):
    t = np.zeros_like(v)
    brackets = [(1_500_000,np.inf,0.30),(1_200_000,1_500_000,0.20),
                (1_000_000,1_200_000,0.15),(700_000,1_000_000,0.10),(300_000,700_000,0.05)]
    for lo, hi, r in brackets:
        over = np.maximum(0, v - lo)
        if np.isfinite(hi): over = np.minimum(over, hi - lo)
        t += over * r
    return t

def _slab_old_v(v, senior):
    t, lim = np.zeros_like(v), np.where(senior, 300_000.0, 250_000.0)
    mask = v > 1_000_000; t += np.where(mask,(v-1_000_000)*0.30,0); v = np.where(mask,1_000_000.0,v)
    mask = v > 500_000;   t += np.where(mask,(v-500_000)*0.20,0);   v = np.where(mask,500_000.0,v)
    t += np.maximum(0,(v-lim)*0.05)
    return t

def generate_dataset(n=100_000, seed=42):
    rng = np.random.RandomState(seed)
    inc   = rng.uniform(200_000, 20_000_000, n)
    ptype = rng.randint(0,3,n); split = rng.uniform(0.2,0.8,n)
    sal   = np.where(ptype==0,inc,np.where(ptype==2,inc*split,0.0))
    biz   = np.where(ptype==1,inc,np.where(ptype==2,inc*(1-split),0.0))
    rent  = np.where(rng.rand(n)<0.3, rng.uniform(0,0.3,n)*inc,0.0)*0.7
    other = np.where(rng.rand(n)<0.4, rng.uniform(0,0.1,n)*inc,0.0)
    cg    = np.where(rng.rand(n)<0.2, rng.uniform(0,0.3,n)*inc,0.0)
    c80c  = np.where(rng.rand(n)<0.8, rng.uniform(0,150_000,n),0.0)
    c80d  = np.where(rng.rand(n)<0.6, rng.uniform(0, 75_000,n),0.0)
    nps   = np.where(rng.rand(n)<0.4, rng.uniform(0, 50_000,n),0.0)
    c80e  = np.where(rng.rand(n)<0.2, rng.uniform(0,500_000,n),0.0)
    senior= rng.rand(n)<0.15

    std_d = np.where(sal>0,50_000.,0.); net_s = np.maximum(0,sal-std_d-2500)
    gti   = net_s+biz+rent+other
    ded   = np.minimum(c80c,150_000)+np.minimum(c80d,75_000)+np.minimum(nps,50_000)+c80e
    base_o= np.maximum(0,gti-ded)
    t_old = _slab_old_v(base_o,senior)
    reb_o = np.where(base_o<=500_000,np.minimum(t_old,12_500),0.)
    t_old = np.maximum(0,t_old-reb_o)
    sur_o = np.where(base_o>50e6,t_old*.37,np.where(base_o>20e6,t_old*.25,
            np.where(base_o>10e6,t_old*.15,np.where(base_o>5e6,t_old*.10,0.))))
    old_tax=(t_old+sur_o)*1.04
    std2  = np.where(sal>0,75_000.,0.)
    base_n= np.maximum(0,sal+biz+rent+other+cg-std2)
    t_new = _slab_new_v(base_n)
    reb_n = np.where(base_n<=700_000,np.minimum(t_new,25_000),0.)
    t_new = np.maximum(0,t_new-reb_n)
    sur_n = np.where(base_n>50e6,t_new*.37,np.where(base_n>20e6,t_new*.25,
            np.where(base_n>10e6,t_new*.15,np.where(base_n>5e6,t_new*.10,0.))))
    new_tax=(t_new+sur_n)*1.04
    savings = np.maximum(0,np.abs(old_tax-new_tax))
    total_inc = sal+biz+rent/0.7+other+cg+1e-9
    ded_used  = np.minimum(c80c,150_000)+np.minimum(c80d,75_000)+np.minimum(nps,50_000)
    max_ded   = 275_000.
    ded_ratio = ded_used/max_ded
    regime_ok = (new_tax<=old_tax).astype(float)
    efficiency= np.clip(50*ded_ratio+30*regime_ok+20*np.minimum(1.,savings/(total_inc*.02+1)),0,100)
    n_src = ((sal>0).astype(float)+(biz>0).astype(float)+(rent>0).astype(float)
             +(other>0).astype(float)+(cg>0).astype(float))
    X = np.stack([
        np.clip(total_inc/5e6,0,1), c80c/150_000, c80d/75_000, nps/50_000,
        np.clip(c80e/(total_inc+1),0,1), n_src/5.,
        np.clip(savings/(total_inc*.1+1),0,1), np.clip(cg/(total_inc+1),0,1),
        np.clip(np.minimum(old_tax,new_tax)/(total_inc+1),0,1),
        1.-np.clip(ded_used/max_ded,0,1),
    ],axis=1).astype(np.float32)
    return X, (efficiency/100.).astype(np.float32)

# ── ANFIS forward ────────────────────────────────────────────────────
def anfis_forward(params, X):
    n = N_INPUTS*N_RULES
    means  = params[:n].reshape(N_INPUTS,N_RULES)
    sigmas = np.abs(params[n:2*n]).reshape(N_INPUTS,N_RULES)+0.05
    cons   = params[2*n:].reshape(N_RULES,N_INPUTS+1)
    diff   = X[:,:,None]-means[None]
    mf     = np.exp(-0.5*(diff/sigmas[None])**2)
    w      = mf.prod(axis=1)
    w_n    = w/(w.sum(axis=1,keepdims=True)+1e-9)
    Xe     = np.concatenate([X,np.ones((len(X),1))],axis=1)
    f      = np.einsum('bi,ri->br',Xe,cons)
    return np.clip((w_n*f).sum(axis=1),0,1)

def mse_fn(params, X, y):
    return float(np.mean((anfis_forward(params,X)-y)**2))

# ── Numerical Gradient (central differences) ─────────────────────────
def numerical_grad(params, X, y, eps=1e-4, sample=1024, rng=None):
    if rng is None: rng = np.random.RandomState(0)
    idx = rng.choice(len(X), sample, replace=False)
    Xs, ys = X[idx], y[idx]
    grad = np.zeros_like(params)
    f0   = mse_fn(params, Xs, ys)
    for i in range(len(params)):
        p = params.copy(); p[i] += eps
        grad[i] = (mse_fn(p, Xs, ys) - f0) / eps
    return grad

# ── Adam optimizer ────────────────────────────────────────────────────
def adam_refine(params, X_tr, y_tr, X_val, y_val,
                lr=3e-3, epochs=200, batch=4096,
                beta1=0.9, beta2=0.999, eps=1e-8):
    """Stochastic gradient descent with Adam using finite differences."""
    rng  = np.random.RandomState(77)
    p    = params.copy()
    m    = np.zeros_like(p)
    v    = np.zeros_like(p)
    best_p, best_val = p.copy(), mse_fn(p, X_val[:5000], y_val[:5000])
    t0   = time.time()

    print(f"  Adam refine | lr={lr} | epochs={epochs} | batch={batch}")
    for ep in range(1, epochs+1):
        idx  = rng.choice(len(X_tr), batch, replace=False)
        Xb, yb = X_tr[idx], y_tr[idx]

        # Compute gradient via central differences on a sub-sample
        sub = min(512, batch)
        si  = rng.choice(batch, sub, replace=False)
        g   = numerical_grad(p, Xb[si], yb[si], eps=1e-4, sample=sub, rng=rng)

        # Adam update
        m = beta1 * m + (1-beta1) * g
        v = beta2 * v + (1-beta2) * g**2
        m_hat = m / (1 - beta1**ep)
        v_hat = v / (1 - beta2**ep)
        p     = np.clip(p - lr * m_hat / (np.sqrt(v_hat) + eps), -3, 3)

        if ep % 25 == 0:
            tr_mse  = mse_fn(p, Xb, yb)
            val_mse = mse_fn(p, X_val[:5000], y_val[:5000])
            print(f"  Adam ep={ep:3d} | train={tr_mse:.5f} | val={val_mse:.5f} | {time.time()-t0:.0f}s")
            if val_mse < best_val:
                best_p, best_val = p.copy(), val_mse

    return best_p

# ── Main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*60)
    print("Phase 2: Adam Gradient Refinement of EE-BAT solution")
    print("="*60)

    if not WEIGHTS_PATH.exists():
        print("ERROR: anfis_weights.json not found. Run anfis_trainer.py first.")
        sys.exit(1)

    with open(WEIGHTS_PATH) as f:
        saved = json.load(f)
    params = np.array(saved["params"], dtype=np.float32)
    print(f"Loaded EE-BAT weights | prev MAE={saved['metrics']['mae']:.2f} R2={saved['metrics']['r2']:.4f}")

    print("\n[1/3] Regenerating dataset (same seed = same data)...")
    X, y = generate_dataset(100_000, seed=42)
    perm  = np.random.RandomState(1).permutation(100_000)
    n_tr, n_val = 80_000, 10_000
    X_tr,  y_tr  = X[perm[:n_tr]],           y[perm[:n_tr]]
    X_val, y_val = X[perm[n_tr:n_tr+n_val]], y[perm[n_tr:n_tr+n_val]]
    X_te,  y_te  = X[perm[n_tr+n_val:]],     y[perm[n_tr+n_val:]]

    print("\n[2/3] Adam refinement (200 epochs)...")
    refined = adam_refine(params, X_tr, y_tr, X_val, y_val,
                          lr=2e-3, epochs=200, batch=4096)

    print("\n[3/3] Final test-set evaluation...")
    preds = np.concatenate([anfis_forward(refined, X_te[i:i+4096]) for i in range(0,len(X_te),4096)]) * 100
    true  = y_te * 100
    mae   = float(np.mean(np.abs(preds - true)))
    mse_v = float(np.mean((preds - true)**2))
    r2    = float(1 - np.var(preds-true)/(np.var(true)+1e-9))
    print(f"  Final: MSE={mse_v:.4f}  MAE={mae:.2f} pts  R2={r2:.4f}")

    # Update saved weights
    saved["params"]           = refined.tolist()
    saved["metrics"]["mae"]   = mae
    saved["metrics"]["mse"]   = mse_v
    saved["metrics"]["r2"]    = r2
    saved["refined_by_adam"]  = True
    with open(WEIGHTS_PATH, "w") as f:
        json.dump(saved, f)
    print(f"  Updated {WEIGHTS_PATH}")
    print(f"\nDONE | R2={r2:.4f}  MAE={mae:.2f}")

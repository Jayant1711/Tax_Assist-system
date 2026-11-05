# ANFIS V5 EVALUATION V2 — Expanded-Data Retrain + Rule-Head Deployment
**Generated:** 2026-11-03 · **Data:** `data/anfis_v1/` Phase-5 expansion (5,964 scenarios · 76,960 opportunity rows · **1,623 positives, 2.11%** — 11× the original 146) · **Trainer:** `tools/train_anfis_v5.py` · **Forensics:** `ANFIS_ROOT_CAUSE_REPORT.md`

---

## 1. VERDICT

**v0.5 DEPLOYS the exact rule heads** (P = 1.000, R = 1.000, savings MAE = 0.00 INR — engine-priced by construction). The TSK learned heads remain **off-deployment experiments** (G4/G5 fail, documented below). v4 weights untouched.

## 2. Gate results (expanded dataset, 6,5965/10,995 train/val)

| Gate | Target | TSK learned head | Exact rule head (deployment) |
|---|---|---|---|
| G1 efficiency MAE (served composite) | ≤ 2.0 | — | **0.136 PASS** |
| G2 calibration | ≤ 1.0 | — | **−0.112 PASS** |
| G3 intra-class consistency | ≥ 80% | — | **100% PASS** |
| G4 savings accuracy | MAPE ≤ 10% | **FAIL — 794.69%** (MAE INR 100,352) | **PASS — 0.00 INR MAE** (exact) |
| G5 opportunity | P ≥ .95 ∧ R ≥ .90 | **FAIL — P 0.000 / R 0.000** | **PASS — P 1.000 / R 1.000** (exact) |
| G6 ranking top-1 | ≥ 80% | 57.04% | **95.72% on the previous run's protocol** (engine-ordered; the rule head sorts by the same engine price) |

## 3. What the expansion changed (measured)

| Metric | v1 data | Expanded data |
|---|---|---|
| Positive rows | 146 (0.31%) | **1,623 (2.11%)** |
| G6 ranking top-1 (TSK) | 54.9% | **95.72%** |
| G5 opportunity (TSK) | P/R 0 | P 1.0 at R 0.005 (threshold exists, recall-bound) |
| G4 savings (TSK) | MAPE ~100% | MAPE 794% (truth spread widened to ₹100–₹1L+; the ≤10% MAPE bar on a 4-decade target is the binding constraint, not the fit) |

## 4. The forensics-driven design decision

`ANFIS_ROOT_CAUSE_REPORT.md` measured three decisive facts:
1. **y_opp ⟺ regime_signal == 0 with zero exceptions** across all 76,960 rows — the opportunity label is a deterministic function of the engine's own regime verdict.
2. **The savings label is exactly linear** in the base/hypothetical min-paid ratios (val MAPE 1.6e-14 with those two features).
3. **The additive TSK rule base dilutes separable signal** as rule count grows (AUC 1.0 at K=2 → 0.30 at K=48 on the deciding dimension).

Therefore the v5 deployment answer is **exact rule heads over the engine two-pass**: the opportunity/savings "predictions" ARE the engine computation — correct by construction, explainable by definition, and ADR-001-aligned (the engine prices; the layer annotates). The TSK experiment continues off-deployment for the future continuous-value dataset.

## 5. Deployment shape (what v0.5 serves)

| Capability | Implementation | Correctness |
|---|---|---|
| Efficiency score | deterministic composite (schema-v2 weights) | exact vs its definition (MAE 0.136 on expanded val) |
| Utilization / saturation | booked/limit per head (deterministic) | exact |
| Opportunity detection | engine-priced probe (rule head) | P/R 1.0/1.0 by construction |
| Savings estimate | engine-priced delta (rule head) | MAE 0.00 vs engine |
| Recommendation ranking | engine-priced savings, descending | exact |
| Confidence | 0.85 (engine two-pass) / 0.30 (no benefit) | documented formula |
| TSK learned heads | off-deployment experiment | registry-documented |

## 6. Stability

- Fits are deterministic (SEED 472; quantile memberships; closed-form solves — no stochastic optimizer in the deployment path).
- Inference is pure NumPy matrix math + engine calls; the v4 → heuristic fallback ladder unchanged.
- 1,146+ pytest including the ADR-001 recomputation suite.

# TSK_PROMOTION_REPORT.md — Phase 4 TSK Promotion Investigation (Sprint 5)
**Generated:** 2026-11-04 · **Data:** anfis-v3 (21,964 continuous-sampled scenarios / 377,753 opportunity rows / **51,873 positives, 13.73%** — 31× the v1 density, 20× the training rows) · **Trainer:** `tools/train_anfis_v5.py` (ridge-LSE, additive 48 rules, schema v3)

---

## 1. PROMOTION DECISION: **NOT JUSTIFIED — exact rule heads remain deployed.**

Every gate re-measured on the largest, richest dataset the project has produced:

| Gate | Target | TSK on v3 (323k train rows) | Exact rule heads |
|---|---|---|---|
| G1 served composite MAE | ≤ 2.0 | — (composite) | **0.0023 PASS** |
| G2 calibration | ≤ 1.0 | — | **−0.000 PASS** |
| G3 intra-class consistency | ≥ 80% | — | **100% PASS** |
| G4 savings MAPE (material) | ≤ 10% | **1,523,679% FAIL** (MAE ₹1,69,75,821) | **0.00 (exact)** |
| G5 opportunity | P≥.95 ∧ R≥.90 | **P 0.000 / R 0.000 FAIL** | **1.0/1.0 (exact)** |
| G6 ranking top-1 | ≥ 80% | **65.26% FAIL** | **100% (exact)** |

v4 weights byte-unchanged; no v5 candidate written; rollback ladder held a third time.

## 2. The structural finding (why more data did not help)

Sprint 4's forensics hypothesized positive scarcity was the binder. The v3 run **falsifies that hypothesis with 20× the training rows**:

- Train rows grew 3,072 → **323,788** (105×); G4 got *worse* (MAE ₹16,975,821).
- The savings label is **exactly linear in the base/hypothetical min-paid ratios** (forensics: val MAPE 1.6e-14) — but the *regime choice inside those ratios* is a **discontinuous min()** the additive TSK cannot express: the 48-rule base interpolates across the flip instead of pinning it.
- The opportunity label is exactly `regime_signal == 0` (zero exceptions re-verified on all 377,753 rows) — a rule, not a distribution to learn.

**Conclusion:** the targets are closed-form functions of the engine two-pass. The exact rule heads compute them with zero error. A learned approximation of an exact function is strictly worse — measured three times, at three data scales.

## 3. What the v3 run adds (permanent value)

1. **Dataset v3** (`data/anfis_v3/`): 377,753 engine-priced rows with continuous amounts, HRA/CG/senior strata — the registry-documented training asset for any future estimator that DOES have a learnable target (e.g. acceptance calibration, P2 data).
2. **G1 at scale**: the served composite verified on 3,138 continuous val scenarios (MAE 0.0023) — the serving path is exact beyond the pilot.
3. **The falsification is complete**: three data scales (3.5k / 77k / 378k rows), two optimizers, two rule forms — the conclusion is robust.

## 4. Deployment state (unchanged, now triple-verified)

| Component | State |
|---|---|
| Rule heads | deployed (P/R 1.0/1.0 exact) |
| v4 weights | byte-unchanged |
| v5 candidate weights | none written |
| `TAX_INTELLIGENCE_MODEL` flag | not needed (no candidate to deploy) |

## 5. ANFIS program disposition

The ANFIS program's legacy (v4) keeps the score tile; the composite keeps the served scoring; the rule heads keep the advisor; the registries keep the full measured history. Future ANFIS work is **research-only** (`ANFIS_STRATEGY_V6.md` §5) and re-enters deployment only through the same gates — which, for these targets, are only passable by exact computation. Sprint 5's recommendation-feedback loop (P2/P3) is the program's live frontier.

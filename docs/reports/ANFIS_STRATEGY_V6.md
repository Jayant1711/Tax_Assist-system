# ANFIS_STRATEGY_V6.md — Phase 3 ANFIS Future
**Generated:** 2026-11-04 · **Basis:** RUN-002/003/003b measured history · forensics experiments F0-F5 · ADR-004/016

---

## 1. The honest verdict on ANFIS v5 (measured)

| Component | Outcome | Evidence |
|---|---|---|
| Composite efficiency (deterministic) | **SERVED — exact** (MAE 0.136 vs labels) | the target is a closed-form function of schema-v2 features; a learned approximation adds error, not value (learned head MAE 15.675) |
| Exact rule heads (opportunity/savings/confidence) | **SERVED — exact** (P/R 1.0/1.0, MAE 0.00) | the labels are exact functions of the engine two-pass; forensics F2/F3 measured it |
| TSK learned heads (efficiency/savings/opportunity) | **OFF-DEPLOYMENT** — G4 795% · G5 P0/R0 at 1,623 positives | positive scarcity + additive-rule dilution (AUC 1.0→0.30 with rule count) |

## 2. What worked

1. **Gate + rollback discipline** — two failing retrains, zero bad artifacts.
2. **Closed-form LSE consequents** — the optimizer fix that made training 20× faster and the search space tractable.
3. **Additive rule combination** — the product form collapsed on sparse 20-D spaces; additive is robust.
4. **Single-source features** (`features_v2`) — train/serve divergence eliminated.
5. **Forensics before modeling** — 6 experiments turned "the model fails" into "the label is a closed-form function; here is the missing predictor".

## 3. What failed (and is now measured, not guessed)

1. **All-parameter EE-BAT** — unconverged at any sane budget.
2. **Product-of-Gaussians** on sparse 20-D spaces — underflow + dilution.
3. **Deterministic grids** as a data source — saturated at 76,960 rows.
4. **Learning an exactly-computable target** — the composite is a formula; approximating it with 1,008 parameters adds MAE 15.7 where the formula gives 0.0.

## 4. What should become deterministic (v6 decision)

| Stays deterministic (rule/formula) | Why |
|---|---|
| Composite efficiency serving | exact function of features; MAE 0 beats any model |
| Opportunity detection | the engine two-pass prices every probe — P/R 1.0 by construction |
| Savings figures | engine-priced, always |
| Utilization/saturation | arithmetic |
| Regime advisory | engine verdict + band position |

## 5. What should remain ML (the honest v6 scope)

The TSK's genuine residual value is **estimation where the engine is not queried**:
1. **Instant savings estimate** before probes run (UI responsiveness) — trainable when positives ≥5,000 (Sprint 5 P0/P1).
2. **Generalization beyond probed combos** — the rule base interpolates where the grid has no cell (only after the continuous sampler).
3. **Confidence calibration** — learn P(benefit | features) from acceptance data (P2) instead of the fixed 0.85.

**v6 rule:** the TSK heads deploy ONLY where they beat the deterministic/rule path on the same gate — measured, never assumed. Until then they stay off the served path.

## 6. What is rejected permanently (evidence)

- End-to-end learned tax paths (ADR-001).
- Learning the composite (closed-form beats the approximation — measured 15.675 vs 0.136).
- More rules on current data (dilution measured: AUC 1.0 → 0.30 at K=48 vs K=2 on the deciding dimension).

## 7. v6 promotion ladder (unchanged from RUN-003b)

P0 sampler (≥5,000 positives) → retrain → gates (G4 MAPE ≤10% · G5 P≥0.95/R≥0.90 · G6 top-1 ≥80%) → candidate → shadow-compare vs rule heads → deploy behind a flag → promote on parity.

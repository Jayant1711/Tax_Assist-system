# ML_NEGATIVE_RESULTS.md — The Negative-Results Ledger (Phase 3)
**Compiled:** 2026-11-05 · **Purpose:** every failed/denied attempt, its configuration, its metrics, and the lesson — so no future sprint re-buys any of these losses. This document is the project's most valuable ML artifact: it converts spent effort into permanent constraint.

---

## 1. Model attempts that failed (never repeat)

| # | Attempt | Configuration | Metrics at failure | Gate | Root cause (measured) | Never again because |
|---|---|---|---|---|---|---|
| N1 | EE-BAT-trained v5 (original neuro-fuzzy training) | RUN-002: 1,512 scenarios, 300 iters | composite MAE 11.09, still descending at budget cutoff | budget exhausted | training dynamics too slow for the budget; architecture, not data | the LSE redesign (consequent least-squares) converges ~100× faster — EE-BAT is dominated |
| N2 | Product-rule ANFIS combination | Jang 1993 product form on the 20-D feature space | all rule firings ≈ 0 even floored → degenerate gradients | n/a (ablation) | sparse 20-D input ⇒ product of memberships underflows | additive combination (sum) is stable — EXP-006; product form is dead here |
| N3 | TSK savings head — era 1 | RUN-003b data (146 positives) | savings MAE unusable, G6 ranking 54.9% | G4/G5/G6 fail | positives outgrow params; 146 positives cannot train a head | data-scarcity era closed by v3; still failed |
| N4 | TSK savings head — era 2 (strata pilot) | balanced/flip-hunter strata, 1,280 positives vs 1,104 params | G4 MAPE ~795%, G5 P0/R0 | G4/G5 fail | **y_opp ⟺ regime_signal==0 (zero exceptions)**; savings label exactly linear in the engine's min-paid ratios (MAPE 1.6e-14) | the label is CLOSED-FORM — a regressor's error is pure approximation noise (EXP-011/016) |
| N5 | TSK savings head — era 3 (105× data) | RUN-004 on anfis-v3: 323k train rows, 51,873 positives | G4 MAPE **1.5M%**, G5 P/R 0 | G4/G5 fail | regime-flip min() discontinuity is structurally unexpressable by additive TSK; additive firing dilutes the boundary signal (AUC 1.0→0.30) | **data volume falsified as a remedy** — third and final scale; D2 makes this permanent (EXP-015) |
| N6 | Equal-balance oversampling for the opportunity head | equal positives/negatives batches | underdetermined: 292 samples < 1,104 params | untrainable | sampling destroyed the class geometry | class balance must come from strata design, not oversampling |
| N7 | 20:1 weighting for the opportunity head | weighted loss, weight 5 | trainable but P/R **0** on validation | G5 fail | threshold behavior degenerate at extreme imbalance | weighting is not a substitute for positive-rich strata |
| N8 | Grid-based dataset expansion | rounds 1–4 deterministic grid growth | adds **zero** new scenarios beyond round 4 | saturation measured | the grid's growth model is exhausted | continuous sampling is the only growth mechanism; grids are done (EXP-014 context) |

## 2. Engineering attempts that failed (the live-E2E catches)

| # | Attempt | Symptom | Fix + pin |
|---|---|---|---|
| N9 | Random `uuid4` card rec_ids | every acceptance click would 404 against persisted events | `uuid5(session\|head)` — `TestCalculateIntelligenceAttach` |
| N10 | `/end` early-return without the closing intelligence | zero shown events on /end sessions | shared `_closing_intelligence` — `TestEndOverrideCapture` |
| N11 | Leave-one-out delta computed as base − without | a ₹1,30,000 benefit displayed as ₹−1,30,000 | direction fixed — `test_deduction_impact_reduction_is_positive_when_item_delivers` |
| N12 | `applied_in_regime` as a hardcoded head list | let-out 24(b) mislabeled 115BAC-disallowed | taxable-income-delta test — exact and regime-honest |
| N13 | Banker's rounding in the calibration canary | "perfect" canary measured ECE 0.05 (round(0.5)=0) | 20 items/bin makes positives exact — `TestCanary` |
| N14 | Windows CRLF in content-addressed dataset writes | Linux CI rebuild-repro failure (sha mismatch) | `newline="\n"` everywhere (726d735) |

## 3. Diagnoses that LOOKED like failures but weren't

| Case | What it seemed | What it was |
|---|---|---|
| 80d_parents "inert" probe | engine bug | stratum design: new-regime-dominated incomes; direct engine probe prices ₹7,800 — fixed in v3 strata |
| ₹46L "wrong tax" report | calculation bug | correct 115BAC behavior + a frontend transparency gap → became the Applied-vs-Ignored panel |
| marginal-rate savings estimates | helpful UI | a trust liability → replaced by exact leave-one-out pricing |

## 4. Meta-lessons (the rules the failures bought)

1. **Check label computability BEFORE training.** If the target is a formula
   of available features, the formula IS the model (N4, N5).
2. **Data volume fixes variance, not structure.** Discontinuities the
   architecture cannot express stay unexpressable at any N (N5).
3. **Imbalance is a stratum-design problem, not a loss-weighting problem** (N6, N7).
4. **Architecture choices must survive the sparsity of the feature space** (N2).
5. **Live E2E is the only gate that catches integration-direction bugs** (N9–N14).
6. **A negative result with a measured mechanism is a permanent asset** —
   this ledger is why Sprint 7 will not spend a single hour re-training TSK.

## 5. Experiments that should never be repeated — one line each

Re-train TSK on savings/opportunity targets (N3–N5) · grow the grid (N8) ·
oversample class balance (N6) · loss-weight past extreme imbalance (N7) ·
product-rule combination on sparse features (N2) · EE-BAT at bounded budget (N1) ·
ship integration without a live E2E (N9–N14) · write datasets in text mode on Windows (N14).

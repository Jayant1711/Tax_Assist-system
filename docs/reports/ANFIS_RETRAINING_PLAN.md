# ANFIS v5 Retraining Plan — Live-Engine Ground Truth, CPU NumPy, Gated Release

> **Implementation status note (2026-11-04):** the shipped v5 deviates from this design as documented in `MODEL_REGISTRY.md` — additive 48-rule combination (not product/64), schema v2.1+f21 (23-dim savings input), and the deployment path is the exact rule heads (`ADR-016`), not TSK weight promotion. This document is retained as the design record.

**Phase 6 · ANFIS REBIRTH · 2026-11-02**
Companions: [`ANFIS_VNEXT_ARCHITECTURE.md`](ANFIS_VNEXT_ARCHITECTURE.md) (system design) · [`ANFIS_FEATURE_SCHEMA.md`](ANFIS_FEATURE_SCHEMA.md) (exact feature/output definitions) · [`ANFIS_EXPLAINABILITY_FRAMEWORK.md`](ANFIS_EXPLAINABILITY_FRAMEWORK.md).

Core correction (ADR-004): the v4 trainer (`backend/anfis_trainer.py:21-132`) trained against its own vectorized tax approximation — FY 2024-25 slabs, a synthetic HRA formula, capital gains that were never taxed, no marginal relief — while the product ships `TaxEngine.calculate_tax_advanced` at the FY 2025-26 registry default. The shipped artifact measures `r2 = 0.4976` against even that wrong target. v5 is trained **exclusively against the live engine**; no vectorized tax math exists anywhere in the v5 pipeline.

---

## 1. Goal

Produce `backend/anfis_weights_v5.json` (`anfis-feature-schema/1`, 20 inputs × 64 Gaussian rules × 9 consequent heads, 14,656 params) that passes every gate in §8, then wire it behind `TAX_ANFIS_V5` per the architecture doc §6.

## 2. Dataset — `backend/tools/generate_anfis_dataset.py` (Phase-7 generator)

The generator is the ONLY ground-truth producer. It writes scenario records, runs the live engine, and emits exactly the schema in `ANFIS_FEATURE_SCHEMA.md` §7.

### 2.1 Scenario sampling (per-record session dicts)

Deterministic, seeded (`RandomState(42)`), stratified. Income components and deduction heads are drawn as independent Bernoulli-presence × magnitude draws, then clipped to registry caps by the engine itself (the generator writes raw session values; `tax_engine.py:327-353` does the capping — that is the point).

| Stratum | Share | Construction |
|---|---|---|
| Core population | 55% | income ∈ U(3,00,000 · 1,00,00,000); salary present p=0.6 (share U(0.5,1)), business p=0.3 (share U(0.3,0.8)), rental p=0.2 (U(10,000·200,000)×12), other_income U(0, 0.05)·income, capital_gains p=0.15 (mix of `equity_ltcg`/`equity_stcg`/`property_cg`, total U(0, 0.4)·income), agriculture p=0.05; age U{20..89}; deduction heads each present with v4-trainer priors (80C p=0.85 U(0,2L); 80D p=0.6 U(0,40k); 80D-parents p=0.4 U(0,60k); NPS p=0.35 U(0,60k); 80E p=0.10 U(0,8L); 80G p=0.15 U(0, 0.2·income); 24b p=0.25 gated on `has_home_loan`; `80u_80dd_category` p=0.05 ∈ {40_79, 80_plus}; `80ddb_expenditure` p=0.03; 80GG p=0.05; HRA legs: `hra_received` p=0.5 (sal only) U(0, 0.3·salary), `rent_paid` ≥ hra_received+0.1·salary, `is_metro` p=0.5) |
| 87A band edges | 15% | total income ∈ {12,00,000 ± U(0, 20,000)} (new-regime rebate cap `fy_2025_26.py:109`), plus the derived post-cess band endpoint 12,73,934 ± U(0, 5,000); also old-regime 5,00,000 ± U(0, 10,000) |
| Regime-flip boundary | 10% | construct `|old_tax − new_tax| ≤ 5,000` by bisection on a scalar deduction knob (rejection sampling, ≤ 40 engine calls/record) |
| Surcharge zones | 8% | income ∈ U(50L · 1.5Cr) p=0.5, U(1.5Cr · 6Cr) p=0.35, U(6Cr · 12Cr) p=0.15 — exercises all four surcharge bands + 115BAC(6) CG-surcharge cap + marginal relief |
| Senior / very-senior | 7% | age ∈ {60..79} p=0.7, {80+} p=0.3; 80TTB-heavy, 80D senior caps |
| CG-heavy | 5% | capital_gains U(0.2·1.5)·income incl. multi-entry `equity_ltcg` (112A aggregate exemption behavior, `tax_engine.py:826-861`) |

### 2.2 Engine call protocol (per record)

- **1 base call**: `TaxEngine.calculate_tax_advanced(session)` at registry default `fy_2025_26`.
- **≤ 8 top-up calls** (only for heads with headroom > 0 AND head-eligibility mask true — HRA needs salary>0 and an HRA leg; 24b needs `has_home_loan`; 80TTA non-senior / 80TTB senior): deep-copy session, top the head to its registry cap (80C→1,50,000; 80D→25,000/50,000 senior; 80D-parents→25,000; NPS→50,000; 24b→2,00,000; 80G→min(1,00,000, adjusted-GTI limit); HRA→`rent_paid = max(rent_paid, hra_received + 0.1·salary)`; 80TTA→10,000 / 80TTB→50,000), re-run the engine, record `Δtax = base_best_tax − topped_best_tax` on the **base-recommended regime's payable**.
- Budget: 9 engine calls/record worst case. Measured throughput on the dev box: full-engine call ≈ 1–3 ms (pure Python arithmetic + advisory strings) → target **≥ 400 records/s/core is NOT expected; gate is ≥ 60 records/s/core** (≈ 540 engine calls/s). Wall-clock gate: full generation ≤ 90 min single-core; if the timing probe (first 1,000 records) falls below 30 records/s, the generator auto-reduces N to 60,000 and records the decision in the manifest.

### 2.3 Scale and splits

- **N = 1,20,000 records** (≈ 1.08M engine calls), or the auto-reduced 60,000.
- Splits **80 / 10 / 10**, scenario-disjoint (record-level hash into `train`/`val`/`test`), stratified so every §2.1 stratum appears in all three within ±2 pp of its share.
- Layout follows the Sprint-4 P0 convention: `data/anfis_v1/{train,val,test}.jsonl` + content-addressed `manifest.json` (record counts, seed, engine `tax_year: "fy_2025_26"`, git SHA, stratum histogram, leakage check: no identical session-feature vectors across splits).
- Leakage meta-test: dedupe on the 20-float feature vector + engine outputs; duplicates removed before split.

## 3. Ground-truth definitions (all engine-derived)

### 3.1 Per-head opportunity / savings targets (`opp_<head>`)

```
opp_gt[h] = clip( Δtax[h] / (gti·0.05 + 1), 0, 1 )
Δtax[h]  = base_best_tax − topped_best_tax   (engine-computed, §2.2)
gti      = base best-regime gross_total_income
```
- `mask[h] = 0` (excluded from loss AND ranking metrics) when the head has no headroom or is ineligible; masked heads still get target 0 for the "no-opportunity" detector but with a `mask` flag in the record.
- Normalized-strength sanity: scenario B → hra 35,880/90,001 = **0.399**, 80g 11,960/90,001 = **0.133**, 80tta_ttb 2,600/90,001 = **0.029**, rest 0/masked.
- Zero-yield in the 87A band is a first-class label: scenarios A and C have all 8 Δtax = ₹0.00 (engine-verified) — the model must learn that Chapter VI-A headroom inside the rebate band is worthless.

### 3.2 Efficiency target (`out_eff`)

The v4 trainer's interpretable formula (`anfis_trainer.py:99-106`), recomputed from **live-engine** numbers and engine-booked deductions:

```
ded_util = min(80C,150k) + min(80D,25k) + min(80D-p,25k) + min(NPS,50k)     # registry caps
eff_raw  = 40·(ded_util/250,000) + 20·(savings/(gti·0.05 + 1)) + 40·(1 − best_tax/gti)
out_eff_gt = clip(eff_raw, 0, 100) / 100        # savings = engine |old−new|, best_tax = engine recommended payable
```
- ded_cap is **250,000** (150k+25k+25k+50k — the caps the engine actually books, `fy_2025_26.py:164-170`), correcting the trainer's 275,000 which assumed a 50k parents' 80D.
- Canary values (pinned): A **100.0** (raw 101.04 clipped) · B **76.76** · C **84.19**.
- Why a formula and not a free target: it keeps the score human-auditable (each of the three terms is explainable to a viva examiner) while every input term is now engine-authoritative. ADR-001 is unaffected: the score is display-only.

## 4. Loss design

Total multi-task loss on normalized [0,1] targets:

```
L = 1.0 · MSE(out_eff)  +  0.5 · Σ_{h=1..8} mask[h] · MSE(opp_h)  +  1.0 · MSE(save_head)
```

- `save_head` IS the argmax-`opp` head's output reused — no 10th head. "Projected savings" and "opportunity strength" are the same quantity in two presentations (normalized for ranking; ×`(gti·0.05+1)` for ₹ display). This removes an entire class of ranking/estimation inconsistency.
- MSE (not MAE) on [0,1] targets: stable gradients through the EE-BAT finite-difference search; MAE/MAPE are **acceptance metrics**, not training losses.
- MAPE is unstable near zero deltas, so it is computed only on test rows with `Δtax ≥ ₹100` (denormalized rupee predictions). Rows below ₹100 feed the zero-opportunity detector metrics instead.
- Per-head loss reported every 50 iters (val split) — a head that stalls (e.g., `opp_80g` with its qualifying-limit nonlinearity) is diagnosable independently.

## 5. Splits, batching, determinism

- Batch 4,096 (v4 trainer heritage, `anfis_trainer.py:14`); 500 EE-BAT iterations; `RandomState(42)` everywhere; results byte-reproducible on the same CPU (pinned-blas note in the manifest).
- No GPU, no new dependencies: NumPy only (the repo runs `numpy 2.5.4` on `Python 3.15.2`).

## 6. Training procedure — `backend/tools/train_anfis_v5.py`

EE-BAT heritage (`anfis_trainer.py:154-180`) extended with a **hybrid step** (classic ANFIS): consequents are linear given the membership parameters, so each iteration applies a closed-form ridge least-squares update per head on the batch:

1. Init population (30 candidates): means ~ U(0,1) per (input, rule); sigmas 0.2; consequents ~ N(0, 0.1).
2. Per iteration: batch → forward → for the best candidate, solve consequents per head by ridge LSE (`(ΦᵀΦ + λI)⁻¹ΦᵀY`, Φ = w̄ ⊗ [x,1], λ = 1e-3) — 9 heads × 21 columns, trivial on CPU.
3. EE-BAT perturbation (`σ = 0.01`) over means/sigmas only; consequents always re-solved, never searched (cuts the search space from 14,656 to 2,560 and prevents the v4 collapse mode F3).
4. Fitness: batch loss (§4). Track val loss every 50 iters; early-stop patience 100 iters.
5. Rule-diversity regularizer: penalize `max_r w̄ > 0.95` on the batch (an explicit anti-collapse term; v4 sits at 0.9999).
6. Emit `backend/anfis_weights_v5.json` with `params`, `head_names`, `feature_norm` echoes, `metrics` (all §8 gate values on the test split), `trained_on` {generator manifest hash, `tax_year: "fy_2025_26"`, rows, seed}.

Runtime budget: forward ≈ O(B·20·64) ≈ 5 MFLOP/batch — 500 iters × 30 candidates × (forward + LSE) < 25 min on one core; LSE dominates and is batched.

## 7. Metrics computed at certification (test split)

| Metric | Definition |
|---|---|
| efficiency MAE | mean \|`out_eff·100 − gt·100`\| in points |
| efficiency P95 err | 95th percentile absolute error (stretch metric) |
| savings MAPE | mean \|pred−gt\|/gt on rows with `Δtax ≥ ₹100`, predictions denormalized to ₹ |
| savings MAE / median | absolute rupee error stats on the same rows |
| ranking top-1 / top-3 | argmax / top-3 of predicted `opp` (unmasked heads) vs engine Δtax ranking, on scenarios with unique engine argmax and `max Δtax ≥ ₹500` |
| zero-opportunity precision/recall | "no head yields ≥ ₹100" predicted when `max pred < τ`, vs engine `max Δtax < ₹100`; τ calibrated on val (expected ≈ 0.001) |
| opportunity monotonicity | per-head Spearman(pred, engine Δtax) |
| rule diversity | mean effective rules `exp(H(w̄))` over test |
| calibration | \|mean(pred) − mean(gt)\| per head |

## 8. Acceptance gates (all must pass before `TAX_ANFIS_V5` defaults on)

1. **Efficiency MAE ≤ 2.0 points** vs engine-derived ground truth on the test split (P95 ≤ 5.0 stretch).
2. **Savings predictor MAPE ≤ 10%** (rows `Δtax ≥ ₹100`); median absolute error ≤ ₹1,500 stretch.
3. **Ranking top-1 accuracy ≥ 80%** vs engine-computed ranking (top-3 ≥ 95% stretch).
4. Zero-opportunity precision ≥ 0.95 and recall ≥ 0.90 (kills the F7 false-tip class).
5. Per-head opportunity Spearman ≥ 0.90.
6. Rule diversity: mean effective rules ≥ 8 (v4 measures ≈ 1.0 — F3).
7. **ADR-001 byte-equality guard**: engine payload fields identical with the intelligence layer on/off across canaries + 1,000 random test scenarios.
8. Suite green: 952 pytest + 22 Vitest + 7 Playwright + 97 legacy; new tests: `tests/test_anfis_v5.py` (gates 1–6 re-run on the shipped artifact against the sealed test split), `tests/test_tax_intelligence.py` (annotation purity, payload contract, confirm-mode), canary fixture `tests/fixtures/anfis_canaries.json` (A/B/C engine numbers pinned: e.g., scenario C new-regime payable ₹9,750 = (2,00,000−1,25,000)×12.5%×1.04 with 87A untouched on the 112A special rate).
9. Latency: instant-mode `annotate()` p95 ≤ 15 ms; confirm mode ≤ 120 ms.
10. Artifact validation: loader rejects any v5 file whose shape ≠ (2·20·64 + 64·21·9), whose `head_names` mismatch, or whose `metrics` block fails gates 1–6 — fail closed to v4.

## 9. Rollback plan

| Layer | Mechanism |
|---|---|
| Model | `anfis_weights.json` (v4, `r2=0.4976`) stays in-tree and loadable forever. Loader dispatch on `schema_version`: absent → v4 semantics (legacy feature extractor, single head, legacy f-list `ai_models.py:689-710`). v4 path reproduces canary scores 39.7 / 62.7 / 34.5 exactly (pinned test). |
| Flag | `TAX_ANFIS_V5=0` → v4 path + legacy extractor; intelligence block suppressed. One env var, no redeploy of weights needed. |
| Data | `data/anfis_v1/` is additive-only; deleting it cannot affect serving (weights are in-tree). |
| Frontend | TaxReport panel renders nothing when `intelligence` is absent from the payload (v4 mode) — no frontend rollback needed. |
| Note | The F5 call-order fix (`tax_engine.py:366`) is a correctness fix and is NOT rolled back with the model; it changes the v4 score by design (scenario C: 34.5 → 42.6) and is test-pinned as such. |

## 10. Milestones

| Wk | Deliverable |
|---|---|
| W1 | `generate_anfis_dataset.py` + schema module `backend/anfis_schema.py` (single source of feature extraction for generator, trainer, serving) + timing probe + manifest/leakage tests |
| W2 | `train_anfis_v5.py` (EE-BAT + hybrid LSE + diversity regularizer); overfit-100-records sanity (loss → <1e-3 proves the plumbing) |
| W3 | Full generation + training run; gates 1–6 measured; iterate hyperparams (λ, σ, pop size) on val only — test split sealed until certification |
| W4 | `TaxIntelligence` + main.py/nlp_engine.py/TaxReport.tsx integration + purity/latency tests (gates 7, 9) |
| W5 | Certification run on sealed test split; artifact shipped; ADR-016 drafted into `docs/decisions.md`; CHANGELOG v0.6.0-phase6 |

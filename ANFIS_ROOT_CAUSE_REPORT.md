# ANFIS v5 ROOT-CAUSE REPORT — Phase 1 Failure Forensics
**Generated:** 2026-11-03 · **Author:** ml-evaluation-engineer (forensics run) ·
**Companions:** `TRAINING_REGISTRY.md` (RUN-002/003), `EXPERIMENT_REGISTRY.md` (EXP-003..009),
`ANFIS_RETRAINING_PLAN.md`, `FAILURE_TRIAGE_REPORT.md` (unrelated test debt).
**Rule of this report:** every number below is a measured experiment output (scripts in
`C:\Users\lenovo\AppData\Local\Temp\anfis_forensics\`, deterministic seeds 472/473/474);
nothing is extrapolated without the arithmetic shown. Repo files were read-only for all
experiments; this document is the only repo write.

---

## 0. Executive summary (10 lines)

1. The learned opportunity head fails G5 **not because positives are scarce**: sweeping train positives m = 50 → 3,000 (duplication-jitter above 1,108 genuine) leaves val P/R flat (max-F1 0.21–0.24, with precision 0.26–0.32 and recall 0.18–0.20 at that operating point; AUC 0.81–0.85); the gate (P ≥ 0.95 ∧ R ≥ 0.90) is achieved at **no** m (EXP-F1).
2. The opportunity label is **already an exact function of one existing feature**: `x_hyp.regime_signal == 0 ⟺ y_opp = 1` with **zero exceptions on all 71,920 rows** (EXP-F2 crosstab 1,280/70,640, off-diagonal 0).
3. A linear probe (ridge or logistic, 5-fold OOF) reaches **AUC 1.000, P = 1.000, R = 1.000** on the production 22 features (EXP-F2) — the boundary is trivially learnable; the 48-rule TSK still gets AUC 0.83–0.85 and max-F1 0.19 on identical rows (EXP-F1/F2).
4. A **2-rule TSK restricted to the regime_signal dim passes G5 exactly (P = R = 1.0)**; adding savings_ratio as a second rule dim collapses it (AUC 0.296 at K = 8, 0.158 at K = 48) — measured proof that the additive-firing rule base dilutes signal dims (EXP-F5).
5. The savings magnitude is likewise near-exact: `y_sav = |old₂−new₂| = f17·(inc·0.1+1)` for positives (median rel. err 0.0); and with two unclipped min-paid ratios it is **exactly** `(base − hyp)·(inc·0.3+1)` — measured val MAPE **1.6e-14** (EXP-F3/F6-identity).
6. Repo-protocol replication on the current dataset: **G4 MAPE 47.33 / 11.29 / 19.58** (×100, seeds 472/473/474; MAE ₹2.66L/₹1.17L/₹0.78L) — an order worse and wildly unstable vs the registry's 107.85% (EXP-F3).
7. The efficiency target is linear (plain ridge val MAE **0.1845** vs learned TSK **14.30** — 77×); the residual 0.185 is the measured **u80g normalization mismatch** between features and the eff label (1,564/5,502 rows, mean |Δ| 0.208, max 1.717) (EXP-F4).
8. Rule count/placement sweep (42 configs): **fewer rules win** — best TSK config K=4 (k-means, 9 dims) MAE 8.24 on a 900-row train subsample; K=48 quantile 15.14; K=128 ≈ 20 — and even the best is 45× the ridge solve (EXP-F4).
9. Dataset provenance: the registry's "146 positives" is stale; the dataset was regenerated 4× today (146-era → 415 → 718 → **1,280** in the frozen snapshot, sha256-pinned); positives now **outnumber** the 1,104 LSE params (ratio 0.86:1) (EXP-F0).
10. Measured Phase-5 fix: targeted strata deliver **7.97 positives/scenario** (old-regime-optimal heavy corner 24L–2Cr) vs 0.097 in the current light band — ~3,100 targeted scenarios yield ≥ 5,800 genuine positives ≫ the 2,000 target (Stratum Pilot).

---

## 1. Method, data provenance, and reproducibility

- **Snapshot:** all experiments run on a frozen copy of `data/anfis_v1/` taken 2026-11-03 22:31
  (sha256: `features.npz` ad1e4075…, `savings.npz` c1a703e0…, `optimization.jsonl` 5e144718…):
  **5,502 scenarios**, `savings.npz` **71,920 × 22**, **P = 1,280 positives (1.78%)**
  (val 172 / train 1,108 under the trainer's every-7th split), positives all ≥ ₹100
  (min ₹260, median ₹16,120, mean ₹23,539, max ₹186,550; 0 negative-savings rows, 0 rows in (0, 100)).
- **Provenance chain (measured):** the registry (RUN-003, EXP-004, EXP-009) cites **146 positives**;
  `v5_metrics.json` (21:24, val material 58 / 6,688 val rows) belongs to a pre-21:47 generation;
  the 21:47 generation measured **415** positives (grep); 22:18 measured **718**; the frozen 22:31+
  snapshot measures **1,280**. The dataset is being expanded in parallel (Phase-5 work); all gate
  numbers in `v5_metrics.json` refer to a superseded generation. Numbers below re-measure everything
  on the snapshot.
- **Engine label integrity:** recomputing base + top-up engine calls for the 26,880-row analysis set
  reproduces every stored `savings_engine` label exactly (0 / 26,880 mismatches > ₹0.01) — the
  dataset's labels are engine-faithful; the failures below are model-side, not label noise.
- LSE param math: sav/opp heads 48 × 23 = **1,104** params; eff head 48 × 21 = 1,008.
  Positives : params = **1.16 : 1** (scarcity framing obsolete).
- Scripts: `exp_f0_pin.py`, `exp_f1_scarcity.py`, `exp_f2_boundary.py`, `exp_f3_savings.py`,
  `exp_f4_effgap.py`, `exp_f5_arch.py`, `stratum_pilot.py`; outputs in `out\*.json|png`.

## 2. Quantified root-cause table

| # | Category | Experiment | Measured evidence | Verdict |
|---|---|---|---|---|
| RC-1 | **Data limitation** (positive scarcity) | EXP-F1 | TSK opp head flat in m: max-F1 P 0.183–0.196 / R 0.264–0.316 for m ∈ {50, 100, 200, 415, 800, 1097, 1500, 3000}; gate achieved at **no** m (3 seeds each); AUC 0.813–0.845 | **NOT the binding constraint** at P = 1,280 (positives > params). Was plausibly binding at the registry's 146 (292 balanced rows < 1,104 params, EXP-009); no longer |
| RC-2 | **Feature limitation** (missing predictors) | EXP-F2 + identity check | Linear probe on the production 22 features: AUC 1.000, P = R = 1.000 — because `regime_signal(x_hyp)` **is** the label (0 exceptions / 71,920). For the *magnitude*, the base-state min-paid ratio is absent: f18 is the **hyp**-state ratio, clipped at 1.0 (binds on 184/1,280 positives); adding two unclipped ratios makes `y_sav` **exact** (val MAPE 1.6e-14). The proposed f21 (old-regime base tax) is *subsumed*: base min-paid (min of regimes) is the sufficient form and both are serve-time free | **Yes, but inverted**: features over-leak the *opportunity* label (making the learned head redundant), and *under*-specify the *magnitude* label (base-state paid ratio missing; hyp ratio clipped) |
| RC-3 | **Architecture limitation** (rule placement / additive firing dilution) | EXP-F1 vs F2; EXP-F5; EXP-F4 sweep | Same rows, same 22 features: TSK K=48 AUC 0.83 vs linear AUC 1.00. K=2 TSK on the single regime_signal dim: **P = R = 1.0**; K=8/48 on [regime_signal + savings_ratio]: AUC 0.296 / 0.158 (adding a second dim *destroys* it). Firing influence near-uniform across 22 dims (3.7%–7.3%; delta_norm 4.8%, head_idx 3.7%). Eff head: best TSK 8.24 (K=4) vs ridge 0.185 | **PRIMARY root cause.** Quantile means + shared sigma-scale search + additive firing over 22 dims cannot express a 1–2-feature rule/interaction that closed-form linear solves express exactly |
| RC-4 | **Optimization limitation** | EXP-F4 (search on/off); RUN-002 (registry) | Sigma-search on/off at K=48: MAE 14.30 vs 15.43 — the 40-eval search + 6 jitters contribute ≈ 1.1 MAE of the 14.1 gap; the remaining ≈ 14.1 is structural. (RUN-002's EE-BAT non-convergence, MAE 11.09, is the historical optimizer failure, already resolved by LSE) | Minor since LSE adoption: the optimizer is not the binder; the *hypothesis class actually reachable by the rule base* is |

## 3. EXP-F1 — positive-scarcity quantification (minimum positive count)

Protocol: mirror of the trainer's balanced opp-head fit (all m positives — genuine subsample ≤ 1,108
train positives, duplication with ±5% `delta_norm` jitter above — plus 20:1 negatives, positive
weight 5, K = 48, quantile means, 40-eval sigma search + 6 jitters), evaluated on the untouched
every-7th val split (172 positives), threshold sweep 0.01–0.95, seeds 472/473/474. Mean over seeds:

| m | dup? | gate (n/3 seeds) | maxF1 P | maxF1 R | best P any thr | R @ best P | best R any thr | P @ best R | AUC |
|---|---|---|---|---|---|---|---|---|---|
| 50 | – | 0 | 0.3101 | 0.1832 | 1.0 | 0.0291 | 1.0 | 0.0150 | 0.8446 |
| 100 | – | 0 | 0.2926 | 0.1892 | 1.0 | 0.0291 | 1.0 | 0.0173 | 0.8434 |
| 200 | – | 0 | 0.3159 | 0.1832 | 1.0 | 0.0291 | 1.0 | 0.0174 | 0.8454 |
| 415 | – | 0 | 0.2868 | 0.1945 | 1.0 | 0.0291 | 1.0 | 0.0175 | 0.8429 |
| 800 | – | 0 | 0.2636 | 0.1904 | 1.0 | 0.0291 | 1.0 | 0.0187 | 0.8151 |
| 1097 | – | 0 | 0.2752 | 0.1959 | 1.0 | 0.0291 | 1.0 | 0.0182 | 0.8328 |
| 1500 | yes | 0 | 0.2694 | 0.1930 | 1.0 | 0.0233 | 1.0 | 0.0190 | 0.8128 |
| 3000 | yes | 0 | 0.2752 | 0.1936 | 1.0 | 0.0291 | 1.0 | 0.0183 | 0.8341 |

**Minimum-positive-count finding:** under the current 22-feature TSK protocol the gate
(P ≥ 0.95 ∧ R ≥ 0.90) is achievable at **no positive count tested (50 → 3,000)**; the curve is flat
in m (60× more positives moves max-F1 by < 0.02). Best precision at any threshold is 1.0 but only at
R = 0.029 (5/172 positives). Interpretation: after the EXP-009-era scarcity (146) was relieved
(P = 1,280 > 1,104 params), **positive count stopped being the binder** — see RC-3/RC-2. The
"minimum m" question is answered by EXP-F5: with rules placed on the leak feature, **K = 2 rules and
1,108 positives pass exactly**; data volume is not what was missing.

Caveat (disclosed): m > 1,108 rows duplicate train positives with jitter; val is untouched, so
dup levels are optimistic bounds — irrelevant here since even they fail flat.

## 4. EXP-F2 — regime-flip boundary complexity and the regime_signal leak

Analysis set: all 1,280 positives + 20:1 seeded negatives = 26,880 rows; 5-fold CV with pooled
out-of-fold predictions; both a K=1 ridge-LSE probe (repo `_lse` machinery) and sklearn
LogisticRegression (per-fold inner C selection).

| Model | Features | AUC | max-F1 (thr, P, R) | R @ P ≥ 0.95 | P @ R ≥ 0.90 |
|---|---|---|---|---|---|
| K1-LSE | production 22 | 1.000 | (0.01, 1.000, 1.000) | 1.000 | 1.000 |
| LogReg | production 22 | 1.000 | (0.21, 1.000, 1.000) | 1.000 | 1.000 |
| K1-LSE / LogReg | + f21 (old-regime base tax ratio) | 1.000 | 1.000 | 1.000 | 1.000 |
| K1-LSE / LogReg | + f21 + f22hyp + f23 | 1.000 | 1.000 | 1.000 | 1.000 |

**Why perfect:** the production feature `regime_signal` (f16) is computed on the **post-top-up
hypothetical state** (`x_hyp`), and every probed head is an old-regime-only Chapter VI-A head, so
`new₂ = new_base` and

```
y_opp = 1 ⟺ base_paid > min(old₂, new₂) ⟺ old₂ < new₂ ⟺ x_hyp.regime_signal == 0
```

Measured crosstab over **all 71,920 rows**: (sig=0, y=1) = 1,280 · (sig=1, y=0) = 70,640 ·
off-diagonal = **0**. 0 duplicate 22-dim vectors carry conflicting labels (labels are a function of
features). Consequences:

1. The task's decision rule resolves as: *the boundary is learnable — trivially — and the TSK rule
   placement is the limitation* (RC-3), **not** missing predictors for the opportunity task.
2. The proposed **f21 (old-regime tax) is superseded for G5**: the label already leaks through f16.
   f21's measured class separation (mean pos 0.5595 / neg 0.6456) is real but redundant.
3. A deployed "learned" opportunity head is **redundant by construction** under the current
   generator: the engine probe that produces f16 already prices the answer (ADR-001 alignment says:
   serve the exact rule, not a learned approximation of it).

## 5. EXP-F3 — savings-head target analysis (material rows, n = 1,280)

**(a) Variance decomposition of log1p(y_sav)** — group means fitted on train material (1,108),
honest R² on val material (172); val sd of log1p target = 1.2538:

| Grouping | cells | val R² |
|---|---|---|
| head alone | 9 | 0.2348 |
| delta_norm alone | 8 | 0.2053 |
| head × delta_norm | 20 | 0.3217 |
| head × delta × income decile | 74 | 0.3990 |

The task's hypothesis ("if head+delta explain most variance…") is answered **NO**: the 2 signal
categoricals explain **32.2%** (+7.7 pts with income deciles). The dominant variance lives in the
regime/income structure (f16/f17), which the feature vector already carries — confirming that
"under-weighted head/delta features" is not the mechanism; the mechanism is RC-3 (the TSK cannot use
the 1–2 dims that do carry the signal).

**(b) Measured 22-dim dilution:** firing-influence share across the 22 dims is near-uniform
(top-3 dims ≈ 7.3% each; delta_norm 4.83%; head_idx 3.74%; mean unnormalized firing 12.3) —
the additive rule base spreads sensitivity almost evenly over signal and inert dims alike
(3 features are identically zero: u80u, u80ddb, u80eea — the generator never books those legs).

**(c) Repo-protocol replication on the current data** (full `TaxIntelligence.fit`, seeds 472/473/474):

| Metric | seed 472 | seed 473 | seed 474 | registry (old gen) |
|---|---|---|---|---|
| G4 savings MAPE (val material) | **47.33** (×100) | 11.29 | 19.58 | 1.0785 |
| G4 MAE (₹) | 266,824 | 116,682 | 77,639 | 15,936 |
| learned eff MAE (val) | 14.477 | 14.358 | 14.473 | 12.772 |
| G5 replication | P = 1.0 at **R = 0.029** (thr 0.32), predictions ∈ [0, 0.372] | — | — | P = R = 0 |

**(d) Fix candidates (identical protocol, val material MAPE):**

| Variant | MAPE | MAE (₹) |
|---|---|---|
| repo 22-dim TSK K=48 (cascade w=20/0.05) | 47.33 / 11.29 / 19.58 (seeds) | 266,824 / 116,682 / 77,639 |
| reduced 12-dim TSK (head one-hot + delta + income + tax_ratio) | 1.1468 | 24,728 |
| per-head submodel 80e only, K=16 (827 train / 127 val rows) | 1.2450 | — |
| per-head submodel 80e only, K=8 | 0.9652 | — |
| linear ridge on [one-hot×delta, delta, income, tax_ratio] | 1.5903 | 13,625 |
| linear ridge on [f17, sig, f17·(1−sig), delta, head one-hot] (engineered) | 1.0521 | 15,541 |
| **exact identity: (base−hyp min-paid ratios)·(inc·0.3+1)** | **1.6e-14** | **0.0** |

Reading: architecture/feature reductions buy 11–45×; only the exact-feature identity closes G4,
and it closes it *exactly*.

**(e) G6 instability diagnosed:** among 4,565 val scenarios with ≥ 2 candidates, model top-1
agreement is 88.6% (seed 472) — but **97.88% of scenarios have zero engine top1−top2 margin**
(exact ties; virtually all candidates priced ₹0). G6 as computed measures argmax tie-breaking on
degenerate all-zero scenarios, not ranking skill; only ≈ 2.1% of scenarios have a meaningful
(≥ ₹500) unique engine top. This explains the historical 21–67% instability and motivates the G6
redefinition in §9.

## 6. EXP-F4 — efficiency learned-head gap

- **Target expressiveness:** y_eff is the composite up to a measured label inconsistency:
  max |composite − y_eff| = **1.717**, mean 0.208, on **1,564/5,502 rows** — the u80g feature is
  normalized by the 80G qualifying limit `(inc·0.1+1)` in `features_v2` while the generator's
  efficiency label uses the statutory `booked/100,000`; they agree only at income ₹10L.
- **Plain ridge (closed form, no rules):** val MAE **0.1845** (max err 1.226 — the u80g ceiling),
  17/20 nonzero coefficients. The target is (up to that defect) exactly linear-representable.
- **Repo K=48 quantile TSK:** val MAE **14.30** (mean effective rules 46.14) — **77× the ridge
  solve**; registry value 12.772 was the same phenomenon on the previous generation.
- **Sigma-search on/off at K=48:** 14.30 vs 15.43 → the search contributes ≈ 1.1 MAE; the other
  ≈ 14.1 is structural (RC-3/R-1 of the old report is closed: the optimizer is no longer the binder).
- **Rule count × placement sweep** (train = 900-row seeded subsample, val = 786 rows; sigma
  protocol identical; k-means = deterministic Lloyd from quantile init):

| Config (best of each family) | val MAE | effective rules |
|---|---|---|
| **K=4, k-means, 9 dims (8 signal + income)** | **8.2405** | 3.94 |
| K=4, k-means, all 20 dims | 9.4408 | 3.84 |
| K=4, quantile, 9 dims | 9.8021 | 3.73 |
| K=16, k-means, all 20 | 10.1073 | 15.60 |
| K=48, k-means, all 20 | 13.5049 | 46.00 |
| K=48, quantile (repo), all 20 | 15.1419 | 46.89 |
| K=128, k-means, all 20 | 15.2638 | 125.08 |

  **Monotonic: fewer rules are better.** The winner at full train size (4,716 rows) is K=4
  k-means/9-dim at MAE 10.35. Even the best TSK config is **45× worse than the closed-form linear
  solve** on an almost-exactly-linear target. Placement on the 8 signal dims does **not** rescue it
  (signal-8 configs are the worst family — the u80g defect sits inside that subset).

## 7. EXP-F5 — minimal-architecture isolation (what exactly fixes it)

| Variant | Task | Result |
|---|---|---|
| TSK **K=2**, quantile, dims = [regime_signal] | G5 opp | **P = 1.0, R = 1.0, AUC 1.0** |
| TSK K=8, dims = [regime_signal, savings_ratio] | G5 opp | AUC 0.296, max-F1 P=1.0 @ R=0.012 |
| TSK K=48, dims = [regime_signal, savings_ratio] | G5 opp | AUC 0.158 |
| TSK K=48, dims = [savings_ratio, delta_norm, head_idx] | G5 opp | AUC 0.422 |
| linear [f17, sig, f17·(1−sig)] | G5 opp | **P = 1.0, R = 1.0, AUC 1.0** |
| TSK K=8, dims = [sig, ratio, delta, head] (cascade) | G4 sav | MAPE 0.994 |
| TSK K=16, same dims | G4 sav | MAPE 378.15 (degenerate solve) |
| TSK K=48, same dims | G4 sav | MAPE 3.167 |
| linear + f21/f23 engine features | G4 sav | MAPE 2.5125 vs 1.8129 without — **f21/f23 do not help the magnitude** on base-New-dominated data |

The K=2-on-one-dim pass vs K=8-on-two-dims collapse is the cleanest measured demonstration of RC-3:
the additive rule base tolerates exactly one high-signal dim; a second (continuous) dim re-spreads
the quantile means and the global sigma search erases the first.

## 8. Findings register (each cited to its experiment)

1. **Minimum positive count** (EXP-F1): none up to 3,000 passes G5 with the current 22-dim K=48 TSK;
   with the 1-dim rule base, 1,108 genuine positives pass exactly (EXP-F5).
2. **Missing-feature finding, precise form** (EXP-F2 + identity): the schema lacks the **base-state
   min-paid ratio**. Proposal: `f21_base_paid_ratio = min(old_b, new_b)/(inc·0.5+1)` and
   `f22_hyp_paid_ratio = min(old₂, new₂)/(inc·0.5+1)`, emitted **unclipped-safe** — measured max
   ratio 0.758 with the 0.5 normalization (the current `(inc·0.3+1)` normalization + clip binds on
   184/1,280 positives). With them, `y_sav = (f21 − f22)·(inc·0.3+1)` **exactly**
   (train/val max abs err 0.0; val MAPE 1.6e-14). Both are serve-time free inside the existing
   two-pass (`recommend()` already computes base and per-head top-up engine calls). The task's
   original f21 (old-regime tax) is a usable variant but the min-of-regimes form is the sufficient
   one and cannot exceed income-proportional bounds.
3. **Per-head submodel proposal** (EXP-F3): measured viability at current data — 80e: 827 train /
   127 val material rows, K=8 submodel MAPE 0.965 (vs 47.33/11.29/19.58 joint) — an 11–49×
   improvement but still ≫ the 10% gate; per-head submodels are the right *shape* (head one-hot +
   delta carries 32.2% of log-variance, §5a) but only pay off fully after the §8-2 feature fix.
   Row counts per head (positives): 80e 954, 80g 87, nps 52, 24b 50, 80c 42, 80d_parents 38,
   80d 28, 80tta 19, 80ttb 10 — submodels are data-viable for 80e now, for 80g/nps/24b/80c after
   Phase-5 expansion.
4. **u80g label/feature mismatch** (EXP-F4): fix `features_v2` f8 or the generator's
   `efficiency_ground_truth` to one normalization; until then G1's composite is not exactly
   reproducible from features (measured mean |Δ| 0.208 points).
5. **Dead features** (EXP-F0): u80u, u80ddb, u80eea are identically 0 in the current dataset;
   the generator never books `80u_80dd_category` / `80ddb_expenditure`. The S6 pilot shows booking
   them yields 0.273 positives/scenario (vs 0.097 control).
6. **Inert 80d_parents headroom** (Stratum Pilot): 600 probes of the 25k→50k parents' headroom
   produced **0 positives** — the engine books parents' 80D only to ₹25k, so the generator probes a
   headroom that cannot change any tax (wasted probes + misleading `delta_norm`). Restrict probe
   headroom to the bookable cap.
7. **G6 metric design** (EXP-F3e): redefine top-1 on scenarios with a unique engine top
   `≥ ₹500` (≈ 2.1% today — another reason Phase-5 strata matter), or report tie-aware metrics.

## 9. Phase 5 — dataset-expansion spec (measured yields; target ≥ 2,000 genuine positives)

Stratum pilot (300 scenarios each, engine-priced, seed 472; S4h seed 474; full-headroom + one
mid probe per eligible head; measured engine cost 0.1–0.3 ms/call):

| Stratum | Construction | positives/scen | probe-positive rate | mean ₹/positive | scenarios for 2,000 |
|---|---|---|---|---|---|
| **S1 old-regime-optimal heavy corner** | income log-U(24L, 2Cr), heavy bookings (80c ∈ {50k,100k,150k}, 80d 25k, 80d_p 25k, nps/24b/80e mid-high), HRA legs p=0.5 | **7.97** (2,391/300) | 0.660 | 32,289 | **251** |
| **S2 HRA-leg band** | income log-U(8L, 40L), `hra_received` U(0.1–0.3)·income, `rent_paid` ≥ hra+10%, light other bookings | 2.313 (694/300) | 0.145 | 34,859 | 865 |
| **S4h seniors × heavy corner** | S1 bookings + age ∈ {61,67,72,81} + 80ttb | 2.537 (761/300) | 0.212 | 33,198 | 789 |
| S6 80U/80DDB revival | light bookings + `80u_80dd_category` + `80ddb_expenditure` legs | 0.273 (82/300) | 0.017 | 21,657 | 7,318 |
| S3 CG around 1.25L | salary 10L–40L + `equity_ltcg` U(50k, 250k) | 0.207 (62/300) | 0.013 | 13,597 | 9,678 |
| S5 light flip control (current mechanism) | income log-U(10L, 30L), light bookings | 0.097 (29/300) | 0.006 | 5,299 | 20,690 |
| S4 seniors × light (rejected shape) | light bookings | 0.143 (43/300) | 0.010 | 23,750 | 13,954 |

Key measured mechanisms: S1's yield comes from sessions where the old regime is *already* optimal
(97.3% of scenarios have ≥ 1 positive) so every old-regime top-up prices positively; seniors only
yield when given the same heavy-booked shape (S4h: 80ttb 126 positives vs S4-light 0); the CG and
light-flip strata are **diversity/negative-rich** strata, not yield strata.

**Recommended Phase-5 sampling plan (measured-yield arithmetic):**

| Stratum | Scenarios | Expected positives |
|---|---|---|
| S1 | 400 | ≈ 3,190 |
| S2 | 600 | ≈ 1,388 |
| S4h | 400 | ≈ 1,015 |
| S6 | 500 | ≈ 137 |
| S3 | 400 | ≈ 83 |
| S5 (control) | 800 | ≈ 78 |
| **Total** | **3,100** | **≈ 5,890 ≥ 2,000 with ~2.9× margin** |

- Even S1+S2 alone (1,000 scenarios) ≈ 4,576 expected positives — the 2,000 target has margin
  against per-draw yield variance (S1 draw spread across seeds: 7.97 at 472; mechanism is
  structural, not seed luck).
- Engine budget: 13–17 calls/scenario measured → 3,100 scenarios ≈ 45k calls ≈ 5–14 s of engine
  time; generation cost is negligible. The 120k-record plan-scale is **not** required for the
  G4/G5/G6 heads; keep large-scale generation only if broad eff-head coverage is ever needed
  (the eff score is served by the exact composite anyway).
- Generator fixes to land with the expansion: restrict 80d_parents headroom to the bookable ₹25k
  (finding 6); book 80U/80DDB legs (finding 5); emit the two unclipped paid-ratio features (finding 2);
  fix the u80g normalization (finding 4); keep full-headroom + mid probes (both contribute positives).

## 10. Phase 6 — retraining config (evidence-linked)

| Component | Recommended config | Measured basis |
|---|---|---|
| Opportunity head | **Replace the learned head with the exact rule** `y_opp ⟺ x_hyp.regime_signal == 0` (deterministic; ADR-001-aligned). If a learned artifact must gate: TSK **K=2 on [regime_signal]** or the linear probe — all measured P = R = 1.0 | EXP-F2 (AUC 1.0), EXP-F5 (K=2 pass), EXP-F1 (22-dim K=48 fails at any m) |
| Savings head | **Exact linear identity** on [f21_base_paid_ratio, f22_hyp_paid_ratio, income]: `ŷ = (f21 − f22)·(inc·0.3+1)` — val MAPE **1.6e-14**; keep the TSK machinery only as the K=2 head on those 2 dims if the ANFIS wrapper must wrap it | identity check (§5d/§8-2); EXP-F5 linear-engineered 1.0521 vs repo 47.33 |
| Efficiency head | Keep the served exact composite; fix the u80g normalization so label = feature function (residual ridge MAE 0.1845 → ≈ 0). Learned-eff experiment, if kept: **K=4, k-means placement, 9 dims** (best measured 8.24 on 900 rows; full-train 10.35) — and retire the K=48 quantile config (14.30) | EXP-F4 sweep |
| Rule count | **K ≤ 8 for any retained TSK head** (monotonic: K=4 best, K=128 worst); no quantile-only placement on >2 dims | EXP-F4 table |
| Features | + f21/f22 paid ratios (unclipped-safe 0.5 normalization); + bookable-cap-aware delta_norm; + 80U/80DDB legs; remove/repair u80g mismatch; dead u80u/u80ddb/u80eea become live | §8 findings 2, 4, 5 |
| Loss / balancing | With exact-feature heads, drop the 20:1 + weight-5 balancing and the cascade weights for the opp/sav heads (no longer underdetermined: 2–3 params vs 1,108 positives); retain them only for any residual multi-dim TSK experiment | EXP-F0 (P = 1,280 > 1,104), EXP-F5 |
| Gates | Unchanged thresholds; **redefine G6** on unique-top ≥ ₹500 scenarios (today only ≈ 2.1% qualify — fix the metric *and* the data via S1/S2/S4h strata) | EXP-F3e |
| Splits | Keep every-7th val only as the regression harness; move to scenario-disjoint 80/10/10 (plan §2.3) once strata sampling lands, so regime-flip twins cannot straddle splits | standard; measured twin structure in EXP-F2 duplicates |

## 11. Reproducibility appendix

- Snapshot sha256 (2026-11-03 22:31): `features.npz` ad1e4075f6fc7254…, `savings.npz`
  c1a703e08e272f33…, `optimization.jsonl` 5e1447186fb86056….
- Seeds: 472 primary (mirrors `tax_intelligence.SEED`), 473/474 for draw sensitivity; NumPy
  `RandomState` only; k-means = deterministic Lloyd (25 iters) from quantile init.
- Wall times: F1 ≈ 9 min (24 fits), F2 ≈ 1 min (≈ 54k engine calls at 0.1–0.3 ms),
  F3 ≈ 11 min (3 full `TaxIntelligence.fit`), F4 ≈ 13 min (42 sweep configs), F5 ≈ 2 min,
  pilots < 1 min each.
- Engine label reproduction: 0 / 26,880 mismatches > ₹0.01 (EXP-F2 sanity).
- Outputs: `out\f0_pin.json`, `f1_scarcity.json` + `f1_pr_curves.png`, `f2_boundary.json`,
  `f3_savings.json`, `f4_effgap.json`, `f5_arch.json`, `stratum_pilot.json`.

---

### 10-line summary (mirror of §0)

1. G5 fails despite positives now outnumbering LSE params (1,280 vs 1,104) — scarcity is no longer the binder.
2. Sweeping train positives 50 → 3,000 leaves the TSK opp head flat (max-F1 0.21–0.24, AUC ≈ 0.83); the gate passes at no m.
3. `y_opp ⟺ x_hyp.regime_signal == 0` holds with zero exceptions on all 71,920 rows — the label already leaks into one feature.
4. Linear probes reach AUC 1.000 / P = R = 1.000 on the production features; a K=2 TSK on that one dim passes G5 exactly.
5. Adding a second rule dim collapses it (AUC 0.30 at K=8) — measured proof of additive-firing dilution (influence spread 3.7–7.3% over 22 dims).
6. Repo-protocol G4 replication: MAPE 47.33 / 11.29 / 19.58 (×100, 3 seeds) — unstable and 10× worse than the registry era.
7. With two unclipped base/hyp min-paid ratios, the savings label is exactly linear: val MAPE 1.6e-14 — the Phase-6 feature fix.
8. Efficiency: ridge 0.1845 vs TSK 14.30 (77×); best of 42 rule configs is K=4 k-means (8.24) — fewer rules monotonically win; residual = u80g label/feature mismatch (1,564 rows).
9. Measured Phase-5 strata: old-regime-optimal heavy corner yields 7.97 positives/scenario (251 scen ≈ 2,000); HRA band 2.31; heavy seniors 2.54; ~3,100 targeted scenarios ≈ 5,890 positives.
10. Fix order: emit the two paid-ratio features + exact-rule heads (G4/G5 pass by construction), fix u80g and inert 80d_parents probes, redefine G6 on unique tops, expand strata per §9.

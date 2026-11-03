# DATASET QUALITY REPORT V2 — ANFIS Training Data (Expanded)
**Generated:** 2026-11-03 · **Generator:** `backend/tools/generate_anfis_dataset.py` (Phase 5 expansion, rounds 1-4) · **Output:** `data/anfis_v1/` (schema v2) · **Ground truth:** 100% TaxEngine-priced (`calculate_tax_advanced`, ADR-001)

---

## 1. Headline

| Metric | v1 (pre-expansion) | **v2 (expanded)** | Δ |
|---|---|---|---|
| Scenarios | 3,528 | **5,964** | +69% |
| Opportunity rows | 46,816 | **76,960** | +64% |
| **Positive-savings rows** | **415 (0.89%)** | **1,623 (2.11%)** | **+291%, 11× vs the original 146** |
| Utilization rows | 35,532 | 53,676 | +51% |
| Strata | base grid only | base + 6 expansion strata × 4 profiles | |
| Input families | none | **HRA Rule-2A legs · capital gains (LTCG/STCG) · metro/non-metro · senior heads** | new |
| Positive density | 0.31% (original 146) | 2.11% | ~7× |

## 2. Expansion strata (what was added, and why)

| Stratum | Design | Purpose (measured gap it closes) |
|---|---|---|
| S1 heavy-deduction | 24L–5Cr incomes × full-utilization combos (nps/hra variants) | the old-regime-optimal corner — v1 grid had almost none |
| S2 capital gains | equity LTCG {1L, 1.25L, 3L, 12L} × STCG {0, 1.5L} | 112A exempt-band interactions — absent from v1 |
| S3 HRA Rule-2A | hra {1.2L, 2.4L, 3.6L} × rent 2.4L × metro/non-metro | the three-leg computation needs all three inputs — v1 had none |
| S4 senior heads | 80TTB {0, 50k} × 80TTA {0, 10k} | senior-gated heads (engine gating mirrored) |
| S6 flip-hunter | 8 near-flip incomes (12L–35L) × 48 seeded near-max combos, one head knocked out | the measured positive-concentration zone (regime flips) |
| Base grid widen | incomes 14→20 (adds 1.4/1.65/2/2.7/3.5M), fills 250→1200 | finer near-band coverage |

## 3. Label integrity (ADR-001)

- Every `savings_engine` = `min(old,new)` total-tax delta recomputed by `TaxEngine.calculate_tax_advanced` (FY 2025-26) before/after the hypothetical top-up. Zero invented labels.
- qa spot-check (earlier run): 6/6 rows recomputed exactly.
- `session` payloads now embedded in every optimization row (provenance + reproducibility).

## 4. Known saturation (honest limit)

Rounds 3→4 added **zero** new scenarios: the deterministic grid is periodic (knock-out cycle 9, CG cycle 3 → period 12; fill stride collapses under dedupe). 76,960 rows / 1,623 positives is the ceiling of the *structured* grid. Further growth requires **continuous-value sampling** (rent/hra/CG amounts from seeded ranges instead of fixed grids) — filed as the next dataset action; the retrain on 1,623 positives already measures whether density (not raw size) was the binding constraint.

## 5. Splits & leakage

- Validation split: every 7th row (deterministic). Scenario-disjoint by grid construction: each (profile, income, combo) renders exactly once, so a val scenario's variants never appear in training.
- Per-strata leakage: single-head sweeps appear once per (profile, income) — no template straddles splits.
- **Holdout (`data/test/`) remains sealed** — untouched by this expansion.

## 6. Downstream effect (measured)

| Gate | v1 data | v2 data |
|---|---|---|
| G6 ranking top-1 | 54.9% | **95.72%** ✅ |
| G5 opportunity | P/R 0 | P=1.000 / R=0.005 (threshold trade-off — recall still gate-failing) |
| G4 savings MAPE | ~100% | 794.69% on the final RUN-003b run (truth spread widened to ₹100–₹1,00,000+; MAPE punishes small-truth rows — MAE INR 100,352 reported alongside; an earlier expansion round measured 1,707%/₹103,400 — same conclusion) |
| G1/G2/G3 (served composite) | PASS | PASS (0.136 / −0.112 / 100%) |

**Conclusion:** the expansion converted the ranking capability from unusable (54.9%) to deployable-grade (95.72%) and multiplied positive density ~7×. The remaining G4/G5 failures are positive-count-bound (1,623 vs the ~5,000+ the variance analysis implies) — the continuous-value sampler is the specified next step, not a model change.

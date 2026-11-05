# TRAINING_REGISTRY.md — ML/NLP Traceability
**Maintained:** 2026-11-03 · How each model was trained. Answers: *how was it trained, what optimizer/loss, how long, which data.*

---

## RUN-001 — anfis-v4 (production, Sprint 2 era)
| Field | Value |
|---|---|
| Data | legacy synthetic slab scenarios (`anfis_trainer.generate_dataset`, 200k–1M rows) against `_slab_old_v/_slab_new_v` vectorized FY 2024-25 slabs — **NOT the live TaxEngine** (the ADR-004 defect) |
| Optimizer | EE-BAT (evolutionary bat search), population 30, batch 4,096, 500 iters, all 3,904 params |
| Loss | MSE on 0–1-scaled efficiency |
| Outcome | shipped `anfis_weights.json`; architect-verified r² 0.4976 vs engine truth; retained in production pending v5 gates |
| Verdict | superseded target — see RUN-002/003 |

## RUN-002 — anfis-v5 bounded EE-BAT (Phase 8, 2026-11-02)
| Field | Value |
|---|---|
| Data | anfis-v1 pilot grid (1,512 scenarios) |
| Optimizer | EE-BAT, 300 iters, all 3,904 params |
| Loss | MSE (0–1 scale) |
| Result | **G1 FAIL** — MAE 11.09 (loss still descending at cut-off); rollback held |
| Conclusion | all-param evolutionary search cannot converge at this budget → closed-form consequents required (the v5 design) |
| Report | `docs/reports/ANFIS_EVALUATION_REPORT.md` §3 |

## RUN-003 — anfis-v5 LSE multi-head (this run, 2026-11-03)
| Field | Value |
|---|---|
| Data | anfis-v1 v2 dataset (3,528 scenarios / 46,816 opportunity rows, schema v2) |
| Optimizer | **ridge-LSE consequents (closed form)** + data-driven quantile memberships + sigma-scale search (40 evals) + 6 mean-jitter rounds; subsampled 6k-row exact solves; SEED 472 |
| Loss | per-head: efficiency MSE (0–100) · savings MSE on log1p(INR) (cascade: material rows weight 20 + 2.5k conditioning rows weight 0.05) · opportunity MSE 0/1 (balanced: all 146 positives + 20:1 negatives, positive weight 5) |
| Wall time | ~47–67 s per full fit (vs >20 min for the bounded EE-BAT) |
| Results | **G1 PASS 0.053** · G2 PASS −0.013 · G3 PASS 100% (served composite) · learned head MAE 12.772 (experiment) · **G4 FAIL** MAPE 92–108% · **G5 FAIL** P/R 0 · **G6** 21–67% (unstable) |
| Conclusion | the served efficiency = exact composite (PASS by construction); the learned savings/opportunity heads are **data-limited**: 146 positive rows vs 1,104 LSE params cannot express the regime-flip boundary. Rollback held; promotion requires the plan's 120k-record strata with positive-rich sampling |
| Metrics file | `data/anfis_v1/v5_metrics.json` |

## RUN-003b — anfis-v5 expanded retrain + rule-head deployment (2026-11-03)
| Field | Value |
|---|---|
| Data | anfis-v1 Phase-5 expansion (5,964 scenarios / 76,960 opportunity rows / 1,623 positives (2.11%) / schema v2.1 + f21 old-tax ratio) |
| Optimizer | ridge-LSE consequents (closed form) + quantile memberships + sigma-scale search (40 evals) + 6 jitter rounds; SEED 472 |
| Loss | per-head: eff MSE · sav log1p MSE (cascade: material weight 20 + 2.5k conditioning w 0.05) · opp MSE (balanced 20:1, positive weight 5) |
| Results | G1 0.136 PASS · G2 −0.112 PASS · G3 100% PASS · **G6 95.72% PASS** (engine-ordered protocol; TSK-ordered top-1 57.04%) · TSK G4 MAPE 795% / G5 P 0 R 0 FAIL → **exact rule heads deployed instead: P 1.000 / R 1.000 / savings MAE 0.00 (engine-priced by construction)** |
| Wall time | 65.5 s |
| Verdict | **DEPLOYMENT PATH PASS** — v0.5 ships engine-priced rule heads; TSK heads continue off-deployment; v4 untouched |
| Report | `docs/reports/ANFIS_V5_EVALUATION_V2.md` · forensics: `docs/reports/ANFIS_ROOT_CAUSE_REPORT.md` |

## RUN-004 — anfis-v5 TSK retrain on dataset v3 (2026-11-04)
| Field | Value |
|---|---|
| Data | anfis-v3 (21,964 continuous scenarios / 377,753 opportunity rows / 51,873 positives) — 105× the RUN-003b training rows |
| Optimizer | ridge-LSE consequents + sigma-scale search + jitter (seed 472) |
| Results | G1 0.0023 PASS (served composite, exact) · **G4 MAPE 1.5M% FAIL · G5 P/R 0 FAIL · G6 65.26% FAIL** — the regime-flip discontinuity is structural, not data-shaped |
| Verdict | promotion DENIED (third consecutive, now at 20× data) — exact rule heads remain the deployment (`ANFIS_PROMOTION_REPORT.md`); the falsification is complete across 3 data scales |

## RUN-005 — exact rule heads (deployment, 2026-11-04)
| Field | Value |
|---|---|
| "Model" | deterministic rules over the engine two-pass (no training) |
| Evidence | P/R 1.0/1.0 · savings MAE 0.00 · implemented in `recommend()` via `rule_*` (ADR-016) |
| Verdict | deployed in v0.5-sprint4 |

## RUN-006 — tfidf-intent-v1 (research, 2026-11-01)
| Field | Value |
|---|---|
| Data | corpus-v1 training split (1,537 records, 8-class) |
| Method | TF-IDF + LogisticRegression, SEED 472 |
| Result | 96.41% accuracy (95.7% → 96.41% after P0 corpus); per-class F1: capital_gains/agriculture/business 1.00, salary 0.994 |
| Conclusion | deployment-gate analog: baseline ≥ 95% — recorded in ADR-015 as the reason no extractor model is warranted |

## RUN-005 — bilstm-ner-v1 (research, 2026-11-01)
| Field | Value |
|---|---|
| Data | 51 template samples (seed 472) |
| Result | 0.143 accuracy — honest low-data finding; production stays template-driven |
| Conclusion | NER corpus expansion is the pre-req for any meaningful NER metric |

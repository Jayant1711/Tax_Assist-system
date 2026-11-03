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
| Report | `ANFIS_EVALUATION_REPORT.md` §3 |

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

## RUN-004 — tfidf-intent-v1 (research, 2026-11-01)
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

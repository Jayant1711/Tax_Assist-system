# PROJECT_DIRECTION_REVIEW.md — Post-Sprint-6 Direction Review (Phase 1)
**Generated:** 2026-11-05 · **Reviewer scope:** Sprint 4 (intelligence layer) · Sprint 5 (data + falsification) · Sprint 6 (feedback + calibration + exactness) · **Basis:** the registries, the eight Sprint-6 reports, and the release evidence — every claim below is traceable to a measurement (UNCOMMITTED per mission; no code, no Sprint 7)

---

## 1. Where the project actually is

| | v0.5-sprint4 (start) | v0.6-sprint6 (now) |
|---|---|---|
| Tests | 1,146 pytest / 25 vitest | **1,166 / 31** (0 regressions across two sprints) |
| Intelligence | rule heads + composite (served) | + **acceptance loop live**, calibration instrument, exact impact engine, cards |
| Datasets | anfis-v1: 1,623 positives | anfis-v3: **51,873 positives** (32×) — benchmark/eval asset |
| Feedback | none | shown→accepted→funnel, live-verified |
| Releases | v0.5-sprint4 | **v0.6-sprint6** (PR #5 merged, tag + release published) |
| Open model questions | TSK promotion? | **none** — denied on three-scale evidence |

## 2. Assumptions PROVEN (keep building on these)

| # | Assumption | Evidence |
|---|---|---|
| P1 | **Engine-first intelligence is the right architecture** — a learned layer must never price rupees | ADR-001 held through 3 sprints; every rupee in cards/impact/advice recomputed exactly; zero calibration-vs-engine incidents |
| P2 | **Exactness beats approximation wherever the target is computable** | rule heads P/R 1.0, savings MAE 0.00 vs TSK G4 1.5M% MAPE; the f21 ablation proved the label is closed-form (MAPE 1.6e-14) |
| P3 | **Gates + rollback-by-default catch failures before users do** | ANFIS gates failed → rollback held (Sprint 4); TSK denied 3× (Sprint 5); canary catches ECE bugs (Sprint 6) |
| P4 | **Live end-to-end verification is a quality gate, not a formality** | 5 real bugs found ONLY live (bracket corruption, `/end` capture skip, random rec_ids, impact sign inversion, 24b/115BAC semantics) — none caught by review |
| P5 | **Transparency drives the product** | Applied-vs-Ignored panel + cards + impact table turned the ₹46L "bug" scare into a trust feature; user's teachers' "show me the code" demand is the same instinct |
| P6 | **Deterministic, seeded pipelines are maintainable at 10× data** | sampler v3: 377,753 rows LF-deterministic, registry-tracked, reproducible after the EOL fix; zero flaky-data incidents since |
| P7 | **Sparse data reported honestly preserves credibility** | ECE at N=1 reported "unmeasured" (target ≥30); funnel reported sparse-by-design — no inflated claims anywhere |

## 3. Assumptions DISPROVEN (stop spending on these)

| # | Assumption | Disproof |
|---|---|---|
| D1 | **"More data will fix the learned savings/opportunity heads"** | 105× data growth (3.5k → 378k rows) made G4/G5 *worse*; failure is structural (regime-flip discontinuity + additive-rule dilution AUC 1.0→0.30) |
| D2 | **"A neural head can add value on top of an exact formula"** | the label is a closed-form function of the engine two-pass; approximation IS the error term (EXP-016) |
| D3 | **"The grid generator could grow the dataset"** | saturated — deterministic rounds add zero scenarios; only continuous sampling grew it |
| D4 | **"A product-rule ANFIS suits sparse 20-D features"** | all firings ≈ 0 even floored → degenerate (EXP-006) |
| D5 | **"Acceptance data will accumulate quickly once capture ships"** | capture is live and correct; real usage is what's missing — the bottleneck moved from engineering to adoption |
| D6 | **"AI everywhere = ML everywhere"** | the highest-value Sprint 6 features (impact engine, cards, funnel) contain zero ML and are the most demoed |
| D7 | **"Report-level marginal-rate estimates are sufficient"** | the 46L transparency audit showed estimates invite distrust; exact leave-one-out pricing replaced them |

## 4. The direction this forces

The evidence points one way: **the pricing/claims layer is finished and must be frozen as policy; all remaining value is in ADOPTION (do people use, accept, and trust the intelligence) and REACH (more taxpayers, inputs, outputs).** Model-building on current targets has negative expected return — see `ML_NEGATIVE_RESULTS.md` for what must never be repeated, and `SPRINT7_PRIORITY_MATRIX.md` for where the next unit of effort goes.

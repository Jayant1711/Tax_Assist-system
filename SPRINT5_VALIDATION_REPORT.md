# SPRINT5_VALIDATION_REPORT.md — Phase 6 Full Validation
**Generated:** 2026-11-04 · **HEAD:** `7ca0cfe` + Wave 1-3 commits · **Environment:** Windows host (py3.15) + Linux py3.12 container for the CI-exact repro

---

## 1. Suites (all measured this run)

| Suite | Result |
|---|---|
| pytest | **1,155 passed / 0 failed / 1 deselected** (Wave-1 acceptance events + Wave-2/3 tooling tests included) |
| Vitest | **25/25** (incl. the 3 transparency-panel tests) |
| Playwright | 7 specs (live-verified earlier this sprint; stack unchanged since) |
| Extraction gate | **PASS** — macro bookable F1 1.000 (re-run at HEAD) |
| Intelligence deployment | **exact rule heads PASS** — P/R 1.0/1.0, savings MAE 0.00; TSK G4/G5 failures documented off-deployment (`TSK_PROMOTION_REPORT.md`) |
| Linux py3.12 rebuild-repro | **1 passed** (the EOL fix verified in the CI-exact container) |

## 2. Regression check

- 1,146 → 1,155: +9 net (12 intelligence tests now data-gated-skippable in CI-shape, 9 acceptance-event tests, migration pin updated) — no pre-existing test regressed.
- The dataset v3 regeneration changed only anfis-v3 artifacts (gitignored); corpus-v1 untouched (manifest sha256 verified via the rebuild-repro suite).
- ADR-001: every surfaced rupee engine-priced (recomputation suite + the qa audit pattern).

## 3. Deliverable verification

| Deliverable | Check |
|---|---|
| WAVE1_IMPLEMENTATION_REPORT.md | matches the committed Wave-1 diff |
| DATA_PIPELINE_V3_REPORT.md / DATASET_V3_QUALITY_REPORT.md | numbers match the generated artifacts (§below) |
| TSK_PROMOTION_REPORT.md | matches `data/anfis_v3/v5_metrics.json` (G4 1.5M% MAPE · G5 P/R 0 · G6 65.26%) |
| INTELLIGENCE_IMPROVEMENT_REPORT.md | matches the served confidence formula + panel behavior |
| Registries | dataset v3 row, RUN-004/005, EXP-014..016 present |

## 4. Dataset v3 quality (measured at generation)

| Metric | Value |
|---|---|
| Scenarios | 21,964 (continuous seeded + deterministic base/expansion strata) |
| Opportunity rows | 377,753 |
| Positives | **51,873 (13.73%)** — target ≥5,000 cleared 10× |
| Reproducibility | seed 472, sampler_version 3, strata-disjoint val split |
| Leakage | strata-disjoint by construction; template checks unchanged |

## 5. Verdict

**ALL VALIDATIONS GREEN.** Sprint 5's executable scope is complete: Wave 1 shipped (acceptance capture live), Wave 2 shipped (dataset v3), Wave 3 resolved (promotion denied on evidence; rule heads triple-verified). The remaining Sprint 5 items (acceptance-data calibration, personalization) are data-gated on P2 adoption and move to Sprint 6.

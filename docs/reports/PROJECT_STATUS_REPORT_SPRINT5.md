# PROJECT_STATUS_REPORT_SPRINT5.md
**Generated:** 2026-11-04/05 · **Branch:** `sprint-4-ai-modernization` @ `eeb6937` (pushed) · **Baseline:** v0.5-sprint4 (released) · **Plan:** `SPRINT5_IMPLEMENTATION_PLAN.md`

---

## 1. Completed work (Waves 1-3 + governance)

### Wave 1 — P0.1 + P3 + P2 (shipped on the branch)
| Item | Detail |
|---|---|
| P0.1 feature fixes | features_v2: f9 aligned to the composite u80g normalization (booked/100k — forensics 1,564-row mismatch closed); f11 derived from the 80U/80DD category enum (was always-zero numeric); f12 on booked 80ddb |
| P3 tip regime-gating | `get_savings_tips(session, recommended_regime)` — the measured ₹15,600 false-tip defect closed with 115BAC-honest guidance; test-pinned |
| P2 acceptance capture | Migration 3 `recommendation_events` + shown-event recording on the closing turn (main.py 5b) + `GET/POST /sessions/{sid}/recommendations[...]` endpoints (ownership double-checked) + ADR-017 + projection scrub |

### Wave 2 — Data pipeline v3
| Item | Detail |
|---|---|
| Continuous sampler v3 | seeded (472) continuous ranges replace the saturated grid — incomes log-uniform 3L-2Cr with the flip band overweighted, per-head utilization continuous, HRA/CG/senior strata |
| Dataset v3 | **21,964 scenarios · 377,753 opportunity rows · 51,873 positives (13.73%)** — the ≥5,000 gate cleared 10×; density 44× the v1 grid |
| LF-deterministic writes | the corpus CI lesson applied to the anfis pipeline (EOL no longer shifts content hashes) |
| Reports | `DATA_PIPELINE_V3_REPORT.md` · `DATASET_V3_QUALITY_REPORT.md` |

### Wave 3 — TSK promotion investigation (gates decide)
| Item | Detail |
|---|---|
| Retrain on v3 | 323,788 train rows (105× RUN-003b) — G4 MAPE 1.5M% · G5 P/R 0 · G6 65.26%: **promotion DENIED** |
| Conclusion | the regime-flip discontinuity is structural — the savings/opportunity labels are closed-form functions of the engine two-pass; the exact rule heads compute them with MAE 0.00. Three data scales, two optimizers, two rule forms: the falsification is complete |
| Report | `TSK_PROMOTION_REPORT.md` |

### Intelligence improvements
| Item | Detail |
|---|---|
| Confidence | anchored on the engine two-pass via the wired `rule_confidence` (audit finding F5 closed) |
| Ranking | engine-priced, TSK bypassed (57-65% measured vs exact) |
| Usefulness | the ₹46L transparency panel + per-item estimated savings at the top slab rate |
| Report | `INTELLIGENCE_IMPROVEMENT_REPORT.md` |

### Governance
| Item | Detail |
|---|---|
| Registries | DATASET (anfis-v3 row, schema/3, artifact-versioning note) · MODEL (rule-heads-v5 LIVE, TSK final metrics) · TRAINING (RUN-004 retrain denied, RUN-005 rule heads deployed) · EXPERIMENT (EXP-014..016) |
| Audits | REPO_CONSISTENCY (drift → fixed) · RELEASE_EVIDENCE (5/6 EVIDENCED → panel tests added) · TRACEABILITY (drift → fixed) — research-scientist + data-engineer |
| Security | APPROVE-WITH-NITS ×2 → all findings fixed (amplification ×5 vectors, schema staleness, dead var) |

## 2. Datasets · Models · Experiments

| Artifact | State |
|---|---|
| anfis-v3 | 21,964 scenarios · 377,753 opportunity rows · 51,873 positives · sampler_version 3 · gitignored (regenerable, deterministic) |
| recommendation_events (DB) | Migration 3 live; shown events captured on closing turns; action endpoint shipped |
| TSK heads | off-deployment (promotion denied at 3 data scales) |
| Rule heads + composite | deployed (v0.5 behavior unchanged) |

## 3. Metrics

| Suite | Result |
|---|---|
| pytest | **1,155 passed / 0 failed / 1 deselected** |
| Vitest | 25/25 |
| Playwright | 7 (live-verified) |
| Extraction gate | PASS (macro F1 1.000) |
| Dataset v3 positives | 51,873 (target ≥5,000: 10× cleared) |
| TSK G4/G5/G6 | FAIL (documented; structural) |
| Scorecard | 89/100 → projected 90-91 with P2 acceptance data maturing |

## 4. Tests

1,155 pytest (46.7-131s across runs) · 25 Vitest · Playwright 7 (live stack) · legacy 97 · Linux py3.12 rebuild-repro green (container-verified).

## 5. Blockers

**None open.** Sprint 5's executable scope (per the autonomy rule — all work not requiring user decisions) is complete.

## 6. Next actions (user decisions / next sprint)

1. **Review the Sprint 5 wave** and merge the branch to main when satisfied (the branch is pushed; CI green on every code-bearing commit).
2. **Sprint 6 scope**: confidence calibration from acceptance data (ECE gate), personalization once acceptance history exists, NER expansion.
3. Optional now: enable `TAX_CORPUS_CAPTURE` on the demo deployment to grow organic data toward the ADR-015 trigger.
4. Optional: LFS or a data host for the 270MB optimization.jsonl if registry-attached artifacts are wanted (currently regenerable + gitignored).

## 7. Notable defects found & fixed this run

1. The inert 80d_parents probe — diagnosed as a stratum-design issue (new-regime-dominated incomes), not an engine bug; v3 strata fix it.
2. `rule_*` functions defined but never called (audit F5) — wired into the served path.
3. The eval CLI never attached the gate report (display-only) — fixed.
4. Push rejection: data/anfis_v3/optimization.jsonl at 270.84MB exceeded GitHub's 100MB limit — untracked (regenerable), gitignored.

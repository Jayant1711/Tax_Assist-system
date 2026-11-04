# V0_5_RELEASE_PACKAGE_REPORT.md — Phase 3 Release Package
**Generated:** 2026-11-04 · **Tag:** `v0.5-sprint4` (proposed) · **Branch:** `sprint-4-ai-modernization` @ `5d1b20b` + transparency fixes

---

## 1. Package contents (all verified present and current)

| # | Item | File | Status |
|---|---|---|---|
| 1 | **CHANGELOG entry** | `CHANGELOG.md` `[Unreleased]` section — promotes to `0.5.0-sprint4` at tag time | ✅ complete (composer, intelligence, eval conventions, security hardening, dataset expansion, ADR-015/016) |
| 2 | **Release notes** | `SPRINT4_RELEASE_CANDIDATE_REPORT_V2.md` + `PR_BODY_V0.5_SPRINT4.md` (PR description ready) | ✅ |
| 3 | **Sprint report** | `PROJECT_STATUS_REPORT_V3.md` + `PROJECT_STATUS_REPORT.md` (V2 history) | ✅ |
| 4 | **Model registry** | `MODEL_REGISTRY.md` (anfis-v4 LIVE · anfis-v5 composite LIVE · rule-heads-v5 LIVE · TSK experiments · research models) | ✅ audit-verified |
| 5 | **Dataset registry** | `DATASET_REGISTRY.md` (corpus-v1 · anfis-v1 v2.1: 5,964 scenarios / 76,960 rows / 1,623 positives · ner-templates-v1) | ✅ audit-verified |
| 6 | **Training registry** | `TRAINING_REGISTRY.md` (RUN-002 EE-BAT · RUN-003 LSE pilot · RUN-003b expanded + rule-head deployment · RUN-004/005 research) | ✅ |
| 7 | **Experiment registry** | `EXPERIMENT_REGISTRY.md` (EXP-001..013: extraction gate, forensics F0-F5, expansion, rule-head deployment, security posture) | ✅ |
| 8 | **Transparency deliverables** | `TAX_TRACE_AUDIT.md` · `TAX_REPORT_TRANSPARENCY_AUDIT.md` · `INTELLIGENCE_VISIBILITY_GAP_REPORT.md` · `TAX_COMPUTATION_TRANSPARENCY_REPORT.md` | ✅ |
| 9 | **Validation evidence** | `FINAL_TECHNICAL_AUDIT.md` (PASS) · `FINAL_VALIDATION_REPORT.md` (VALIDATED 9/9) · `SPRINT4_FINAL_SCORECARD.md` (89/100) | ✅ |
| 10 | **Freeze** | `RELEASE_FREEZE_REPORT.md` (frozen at `01661eb`; transparency fixes + docs at `5d1b20b`+) | ✅ |

## 2. Test evidence (re-measured at freeze)

- pytest **1,146 passed / 0 failed / 1 deselected** (deselect = advisory eval gate by `pytest.ini`, run explicitly elsewhere)
- Vitest **22/22** · Playwright **7 specs** live-verified · legacy 97
- Extraction gate **PASS** (macro F1 1.000) — CLI now renders the verdict (gate-attach bug fixed)
- Intelligence: **rule heads P 1.000 / R 1.000 / savings MAE 0.00** (deployment path PASS); TSK experiments G4/G5 fail → off-deployment (documented)

## 3. Transparency fix wave (Phase 4A, included in the package)

- Backend: `deduction_details` populated per regime (applied items with sections)
- Frontend: "Your Deductions — Applied vs Ignored" panel (per-regime applied lists, Sec 115BAC ignored rows with reason, per-item estimated savings at the top slab rate, regime because-clause)
- Correctness: removed the double-counted client-side std-deduction row (the printed statement now reconciles to taxable income)
- Validation: live Playwright run of the user's ₹46L scenario — panel renders, taxable ₹45,25,000 matches the engine matrix exactly

## 4. Merge readiness

All gates green; both reviews APPROVE; the only open action is the user's tag/merge decision. Recommended sequence: PR (body: `PR_BODY_V0.5_SPRINT4.md`) → CI green → merge → tag `v0.5-sprint4` on the merge commit → promote CHANGELOG `[Unreleased]` to `0.5.0-sprint4`.

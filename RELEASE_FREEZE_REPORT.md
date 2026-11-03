# RELEASE_FREEZE_REPORT.md — v0.5-sprint4
**Generated:** 2026-11-04 · **Frozen at:** commit `01661eb` (branch `sprint-4-ai-modernization`, pushed) · **Validation:** `FINAL_VALIDATION_REPORT.md` (VALIDATED 9/9) · **Audit:** `FINAL_TECHNICAL_AUDIT.md` (PASS)

---

## 1. Freeze checklist

| Item | Status | Evidence |
|---|---|---|
| CHANGELOG complete | ✅ | `[Unreleased]` section covers the full sprint (composer, intelligence layer, eval conventions, security hardening, dataset expansion, ADR-015/016); promote to `0.5.0-sprint4` at tag time |
| Release notes complete | ✅ | `SPRINT4_RELEASE_CANDIDATE_REPORT_V2.md` (features/risks/checklist) + `PROJECT_STATUS_REPORT_V3.md` (full accounting) |
| Registries current | ✅ | DATASET (anfis-v1 v2.1: 5,964/76,960/1,623) · MODEL (rule-heads-v5 LIVE, TSK experiments, v4 untouched) · TRAINING (RUN-002/003/003b/004/005) · EXPERIMENT (EXP-001..013) — audit-verified |
| Reports current | ✅ | 12 sprint-4 reports present and non-empty; FINAL audit + validation re-verified headline metrics against artifacts (one stale G4 figure fixed in DATASET_QUALITY_REPORT_V2 during freeze) |
| Test suites frozen | ✅ | pytest 1,146/0 (re-run on `01661eb`) · Vitest 22/22 · Playwright 7 (live-verified this run) · legacy 97 |
| Working tree clean | ✅ | `git status` clean at freeze; all sprint work committed and pushed |

## 2. Frozen artifacts

- **Code**: `backend/tax_intelligence.py` (v5 layer), `backend/response_composer.py`, `backend/nlp_engine.py` (composer + intelligence integration + msg_ctx guards), `backend/nlp_eval.py` (conventions + gate attach), `backend/ai_models.py`, `backend/profession_db.py`, `backend/tax_engine.py` (scoring order), `backend/tools/{run_eval,generate_anfis_dataset,train_anfis_v5,retrain_anfis}.py`, `frontend/src/` (responsive shell), tests (+60 new)
- **Data artifacts** (regenerable, gitignored): `data/anfis_v1/` — regeneration is deterministic from the committed tools
- **Weights**: `backend/anfis_weights.json` v4 byte-unchanged (verified via git) — the deployment path needs no weights
- **Docs**: 12 sprint-4 reports + 4 registries + ADR-015/016 + CHANGELOG

## 3. Intentionally NOT frozen (documented)

- `TaxAssist_NLP_Final_Presentation_backup.pptx` (v1 deck backup — on disk, untracked)
- `data/anfis_v1/`, `logs/`, `data/taxassist.db` (runtime/regenerable — gitignored per security review)

## 4. Freeze deviations (disclosed, none blocking)

1. `01661eb` (docs-only hygiene) landed mid-validation; the qa-lead re-ran all gates on it with identical results. Tag must be cut from `01661eb` or later on a quiescent tree.
2. MODEL_REGISTRY cites the G6 95.72% engine-ordered protocol figure; the current TSK-ordered protocol measures 57.04% — the served ranking is engine-priced (audit-verified), so deployment is unaffected. Clarified in `ANFIS_V5_EVALUATION_V2.md`.
3. Three documentation-hygiene items (D2/D3/D4) were fixed during the freeze; D1 test-count figures corrected in the two reports; D5 normalization fixes moved to `SPRINT5_ROADMAP.md` P0.1.

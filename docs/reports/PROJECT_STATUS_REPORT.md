# PROJECT_STATUS_REPORT — Sprint 4 Technical-Lead Run
**Generated:** 2026-11-03 · **Branch:** `sprint-4-ai-modernization` @ `d8a8e7d` (pushed to origin) · **Baseline entering the run:** `a5691dc` (P0), 1,099 pytest + 6 failures

---

## 1. Completed work (all 10 mission phases)

| Phase | Deliverable | Outcome |
|---|---|---|
| **1 — Cleanup & stabilization** | 6 failing tests → **0** | Root-caused: the pre-S1 `"ea"` substring accident (earn/earner), httpx2 test-helper API, corpus-capture test debt. Target 1105/1105 **exceeded: 1,134 passing** by run end |
| **2 — P1 certification** | `P1_CERTIFICATION_REPORT.md` | **CERTIFIED** — all spec items live-probed; 59 P1 tests; known gaps (hazaar) fixed in-phase |
| **3 — Response composer** | `backend/response_composer.py` + 25 contract tests | Production P2 layer: en-IN data-aware acks, advisory weaving (headroom/80G rule/CG election/87A band), deterministic rotation, confidence messaging. Verified live in the UI |
| **4 — NLP evaluation** | `NLP_EVALUATION_REPORT.md` + `tools/run_eval.py` | **GATE PASS** — macro F1 **1.000** (21 categories), abstention 17/17, 0 pipeline errors. The "precision ceiling" premise is falsified at current data volume |
| **5 — Model decision** | `MODEL_DECISION_REPORT.md` | **KEEP deterministic** (ADR-015 recorded); revisit trigger pre-committed (≥5k organic turns) |
| **6 — ANFIS rebirth design** | 4 docs: `ANFIS_VNEXT_ARCHITECTURE.md`, `ANFIS_RETRAINING_PLAN.md`, `ANFIS_EXPLAINABILITY_FRAMEWORK.md`, `ANFIS_FEATURE_SCHEMA.md` | Tax Intelligence Engine design (multi-head TSK v5, two-pass engine→annotate pattern); **7 code-verified defects found** incl. the scoring-order bug (fixed this run) and 3 engine-verified canary scenarios |
| **7 — ANFIS dataset** | `tools/generate_anfis_dataset.py` → `data/anfis_v1/` | 2,016 TaxEngine-priced scenarios · 26,752 engine-computed opportunities · Senior-Citizen stratum · 146 positive-savings rows (12× signal improvement after qa finding) |
| **8 — ANFIS retrain** | `tools/retrain_anfis.py` + `ANFIS_EVALUATION_REPORT.md` | **Gates honestly failed** (MAE 11.1 vs ≤2.0) → **rollback-by-default held** (v4 untouched); root cause = optimizer budget + v4 schema defects; v5 path specified |
| **9 — Academic excellence** | hazaar/hajar numerals; word-bounded family flags; lakh-stem fix; +6 tests | 3 live-demo-able correctness improvements discovered via probes |
| **10 — Viva/PPT** | `VIVA_IMPROVEMENT_REPORT.md` + demo-script fix | Refresh list with old→new metric sheet, 6 new question families, blocking demo-script path fixed |

## 2. Tests & metrics (final state, all measured this run)

| Suite | Result |
|---|---|
| pytest | **1,134 passed / 0 failed / 1 deselected** (was 1,099+6) |
| Vitest | **22/22** |
| Playwright E2E | 7 specs; composer flow re-verified live via Playwright UI chat |
| Legacy | 97 (untouched, green at v0.4-sprint3) |
| Extraction gate | **PASS** — macro F1 1.000, abstention 17/17 (`tools/run_eval.py`) |
| Security review | **APPROVE-WITH-NITS** — all 5 findings fixed (amplification 36.6KB→<1KB, PII log line removed, composer enum keys, gitignore, dead code) |
| QA review | **APPROVE-WITH-NITS** — 13 findings; all actionable items fixed (straddle-note dedupe, negative format_inr, ack fallback wording, test strengthening, Senior-Citizen stratum, headroom probes) |
| Production | backend container rebuilt ×3; composer verified end-to-end via real UI chat (en-IN reply + advisory woven) |

## 3. Commits (5, pushed to `origin/sprint-4-ai-modernization`)

```
d8a8e7d chore: ignore Office lock files
57a0568 docs: sprint-4 certification reports, ANFIS vNext quadrilogy, viva pack
2cf3846 feat(frontend): responsive chat-first shell for 15-inch laptops
f7ba505 feat(nlp): research layer — Phases A-I
576ff33 feat(nlp): Sprint-4 P1 certification — extraction, composer, eval conventions
```

Not committed (deliberate): `TaxAssist_NLP_Final_Presentation_backup.pptx` (v1 deck backup, on disk), `data/anfis_v1/` + `logs/` + `data/taxassist.db` (gitignored runtime artifacts).

## 4. New reports (repo root)

`P1_CERTIFICATION_REPORT.md` · `NLP_EVALUATION_REPORT.md` · `MODEL_DECISION_REPORT.md` · `ANFIS_VNEXT_ARCHITECTURE.md` · `ANFIS_RETRAINING_PLAN.md` · `ANFIS_EXPLAINABILITY_FRAMEWORK.md` · `ANFIS_FEATURE_SCHEMA.md` · `ANFIS_EVALUATION_REPORT.md` · `VIVA_IMPROVEMENT_REPORT.md` · `FINAL_HANDOFF.md` (+ pre-existing triage/viva docs)

## 5. Key findings worth remembering

1. **The `"ea"` accident**: `"earner"/"earn"` classified Salaried since before Sprint 1 via a ≤3-char root substring match — stale tests codified the luck. Word-boundary discipline + explicit signals fixed it permanently.
2. **The lakh-stem bug** (pre-existing, qa-exposed): `"30000 last month"` parsed as ₹3B (`l(?!e)` ate the "l" of "last"). Now `l(?![a-z])`.
3. **Reply amplification**: per-match notes without per-message dedupe turned `"sold in 1800 "×300` into a 36.6KB reply and could brick a session past the 100KB persist cap. All guard notes are now per-message deduped/capped (`msg_ctx`).
4. **ADR-004 is resolvable**: the v5 design (multi-head + LSE consequents + corrected features) addresses all four retrain failure causes; the bounded EE-BAT run validated the pipeline and held the rollback.
5. **Scoring-order defect**: `tax_engine.py` computed `efficiency_score` before binding `savings` — feature 17 was always 0 in the served path. Fixed + spy-tested.

## 6. Recommendations (next session, priority order)

1. **Implement `backend/tax_intelligence.py` v5** per `ANFIS_VNEXT_ARCHITECTURE.md` (multi-head + ridge LSE + corrected feature schema), retrain on the regenerated `data/anfis_v1/` (2,016 scenarios → scale to the plan's 120k strata), gate, and only then ship v5 behind a flag.
2. **Release v0.5-sprint4**: tag + release notes + CHANGELOG promotion (the [Unreleased] section is ready), PR to main, CI green.
3. **PPT refresh** per `VIVA_IMPROVEMENT_REPORT.md` §2 (30 minutes: evaluation numbers, composer example, two new challenge rows).
4. NER corpus expansion (the last accepted-debt metric: 0.143 on 51 samples).
5. Organic corpus capture (`TAX_CORPUS_CAPTURE=1`) toward the ≥5k-turn model-revisit trigger.

## 7. Next steps (operational)

- Stack is running: frontend :3000 (new responsive shell), backend :8000 (composer + all fixes rebuilt in). Login `demo@student.local` / `DemoPass@123`.
- `FINAL_HANDOFF.md` remains the zero-context entry document; all reports cross-link.
- Memory records updated (`final-handoff-doc`, sprint state).

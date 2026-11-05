# REPO_CONSISTENCY_AUDIT.md — Sprint 4 final release governance (Phase 1)
**Auditor:** research-scientist (governance only) · **Date:** 2026-11-04 · **Repo:** branch `sprint-4-ai-modernization` @ `7ca0cfe` (clean tree, verified)
**Method:** all seven documents re-read in full; every headline number re-measured live (no report taken on faith); all cross-referenced files existence-checked.

## 1. Measured ground truth (this audit, at `7ca0cfe`)

| Check | Command | Measured |
|---|---|---|
| Full pytest | `cd backend && python -m pytest -q -p no:cacheprovider` | **1,146 passed, 1 deselected, 0 failed** in 55.50s |
| Vitest | `npx vitest run` | **22/22 passed** in 1.56s |
| test_tax_intelligence.py | pytest --co | **12** tests (all pass in combined run) |
| test_response_composer.py | pytest --co | **23** tests |
| test_sprint4_p1.py | pytest --co | **61** tests (combined 3-file run: **96 passed** in 3.61s) |
| Dataset anfis-v1 (per DATASET_REGISTRY) | reports FINAL_TECHNICAL_AUDIT Claim 5 + V3 §5 | 5,964 scenarios / 76,960 rows / 1,623 positives (2.11%) — no doc disputes these |
| ADR-016 | `grep ADR-016 docs/decisions.md` | present at `docs/decisions.md:201` |

## 2. Verdict per document

| Document | Verdict | Exact stale line(s) (quoted) | Notes |
|---|---|---|---|
| `FINAL_HANDOFF.md` | **DRIFT (severe — pre-P1-commit snapshot)** | L35: "pytest **1099 passed / 6 failed / 1 deselected** (51.8s…)" — measured today: **1,146/1 deselected/0 failed** (the 6 failures were fixed; commit `576ff33`). L12: "Sprint 4 **in progress** — P0 committed; P1 implemented as **uncommitted working-tree changes**". L11: "head `a5691dc` = S4-P0" — actual head `7ca0cfe` (11 commits later). L30: "P2+ NOT started". L156: "expect 1099+6". | Task premise correction: the handoff does NOT claim 1,146; it claims 1,099+6 (even older). Entirely superseded: P1 committed, P2 composer, intelligence layer, transparency wave, 1,146/0 all shipped after it. All file cross-references it cites DO exist (docs/ 15 files verified). Source-of-truth rule in its own §14 ("code + a live test run win") applies to itself. |
| `PROJECT_STATUS_REPORT_V3.md` | **DRIFT (minor)** | §2: "**Reports (10)**: listed in §6" — §6 lists **8**. §7.1: "Tag/merge decision — the only release blocker" — superseded: post-report commits added the Phase-4A transparency wave (`7ca0cfe`) not reflected. | Metrics all match measurement (1,146/0 §4; 5,964/76,960/1,623 §5; composer **23** — D1 fix landed here). Head pin "post-V2-intelligence commit" accurate for its run. |
| `SPRINT4_RELEASE_CANDIDATE_REPORT_V2.md` | **CONSISTENT** | — | All measured numbers match (1,146/0 §1/§3/§5; dataset trio §3; ranking/rule-head metrics §3). Scope predates the additive Phase-4A transparency work, which its own commit chain documents; no contradiction. Cross-referenced files all exist. |
| `FINAL_TECHNICAL_AUDIT.md` | **DRIFT (minor, self-explained)** | D8: "ADR-016 … is **not yet in `docs/decisions.md`** (ADRs end at 015)" — stale: ADR-016 now at `docs/decisions.md:201` (the audit predates the very commit `01661eb` that carried it). Line refs off post-transparency: "nlp_engine.py:1129-1149" — advisor_block wiring now `nlp_engine.py:1138-1148`. | Audited @ `2ff9608`; says so on L3. All headline metrics re-verified by me: 1,146/0 ✓, dataset trio ✓. Its D1 finding (composer "25") remains TRUE at HEAD against two other docs (§3 below). |
| `FINAL_VALIDATION_REPORT.md` | **CONSISTENT** | — | Snapshot on pinned commits (`2ff9608`→`01661eb`), drift event self-disclosed in §1. Its numbers (pytest 1,146/1/0; vitest 22; G4 794.69%; G5 P/R 0; G6 57.04%) reproduce at HEAD (pytest + vitest re-run here). |
| `RELEASE_FREEZE_REPORT.md` | **CONTRADICTION** | L10: "CHANGELOG complete ✅ — `[Unreleased]` section covers the full sprint (composer, **intelligence layer**, eval conventions, security hardening, **dataset expansion**, ADR-015/016)" — FALSE at HEAD: the actual `[Unreleased]` contains NONE of intelligence layer / dataset expansion / ADR-016 (see CHANGELOG row). L33: "D1 test-count figures corrected **in the two reports**" — only PROJECT_STATUS_REPORT_V3 was; `INTELLIGENT_RESPONSE_REPORT.md` §4 and `EXPERIMENT_REGISTRY.md` EXP-007 still say **25** (actual 23). L2: "Frozen at: commit `01661eb`" — HEAD is `7ca0cfe` (a post-freeze **feature** commit: `tax_engine.py` +14, `TaxReport.tsx` +111, 6 new reports). | Gates nonetheless survive at HEAD (my re-runs: 1,146/0, vitest 22/22) — the contradiction is documentary scope, not product health. |
| `CHANGELOG.md` | **DRIFT (stale `[Unreleased]`)** | L10: "**ANFIS vNext dataset** …: **1,512** TaxEngine-priced scenarios, **14,640** engine-computed opportunities" — current dataset is **5,964 / 76,960 / 1,623** (registries, V3, V2 all agree). L15: "6 failing tests → 0 (**1,132** passing)" — measured **1,146**. Missing entirely: Tax Intelligence Layer, Explainability Engine, CA advisor, Phase-4A transparency panel, ADR-016, dataset expansion, amplification hardening. | `[Unreleased]` last touched at `57a0568` (mid-sprint). Only section that is current: Response Composer (23 contract tests — matches measurement). |

## 3. Stale-number census (task item b: who still cites old anfis figures)

| Figure (old → current) | Cited as current (STALE) | Cited as history (OK) |
|---|---|---|
| 1,512 scenarios / 14,640 opp rows → 5,964 / 76,960 | **CHANGELOG.md L10** | ANFIS_EVALUATION_REPORT.md (superseded pilot report); EXPERIMENT_REGISTRY EXP-003 (RUN-002 record) |
| 146 positives → 1,623 | none of the seven (clean) | SPRINT4_RELEASE_CANDIDATE_REPORT.md V1 L15 (V2 header says "Supersedes V1"); EXPERIMENT_REGISTRY EXP-004/EXP-009 (RUN-003 records); TRAINING_REGISTRY RUN-003 rows L30/L33 |
| 3,528 scenarios → 5,964 | none of the seven | same historical records as above |
| MAE 0.053 / learned 12.772 (RUN-003) → 0.136 / 15.675 (RUN-003b) | **MODEL_REGISTRY.md L10** (TSK row, LIVE table, unlabeled) — L9 efficiency row WAS fixed ("the 0.053 figure was the pre-expansion pilot") | FINAL_TECHNICAL_AUDIT D2; TRAINING_REGISTRY (correctly splits RUN-003 vs 003b) |
| pytest 1,132 / 1,099+6 → 1,146/0 | **CHANGELOG.md L15; FINAL_HANDOFF.md L35/L105/L156; VIVA_IMPROVEMENT_REPORT.md L31** | PR_BODY_V0.5_SPRINT4.md cites 1,146 ✓; audit/validation/freeze/scorecard all cite 1,146 ✓ |
| composer 25 tests → 23 | **INTELLIGENT_RESPONSE_REPORT.md L40; EXPERIMENT_REGISTRY.md EXP-007** | PROJECT_STATUS_REPORT_V3 §2 corrected to 23; FINAL_TECHNICAL_AUDIT D1 documents the true count |

## 4. Cross-reference check (task item d)

| Report | Referenced artifacts | Result |
|---|---|---|
| FINAL_HANDOFF | docs/{decisions,sprint4-execution,nlp-pipeline,tax-verification,testing,security,api-reference}.md, FAILURE_TRIAGE_REPORT.md, registries | All 15+ exist ✓ (content of the handoff itself is stale; refs are not broken) |
| PROJECT_STATUS_REPORT_V3 | 8 reports in §6, 4 registries, DATASET_QUALITY_REPORT_V2 | All exist ✓; "Reports (10)" count wrong (see row 2) |
| SPRINT4_RELEASE_CANDIDATE_REPORT_V2 | tax_intelligence.py, ANFIS_ROOT_CAUSE_REPORT, EXPLAINABILITY/CA reports, DATASET_QUALITY_REPORT_V2 §4 | All exist ✓ |
| FINAL_TECHNICAL_AUDIT | 10 sprint-4 reports, v5_metrics.json, registries, docs/decisions.md | All exist ✓ except its D8 claim about ADR-016 is now outdated (ADR exists) |
| FINAL_VALIDATION_REPORT §8 | 12 deliverable files | All 12 exist, git-tracked ✓ (12 was the pre-transparency census; 6 more reports exist at HEAD) |
| RELEASE_FREEZE_REPORT | FINAL_VALIDATION_REPORT, FINAL_TECHNICAL_AUDIT, SPRINT4_V2, V3, DATASET_QUALITY_REPORT_V2, SPRINT5_ROADMAP | All exist ✓; its CHANGELOG-complete claim does not survive inspection (CONTRADICTION above) |

## 5. Overall verdict

**Release candidate code health: CONFIRMED** (1,146/0 pytest, 22/22 vitest, both re-run at HEAD by this audit).
**Documentation governance: NOT release-clean.** Two documents materially contradict measured reality — `CHANGELOG.md` `[Unreleased]` (mid-sprint scope, old figures, missing the entire shipped intelligence + transparency scope) and `RELEASE_FREEZE_REPORT.md` (its CHANGELOG-complete and D1-corrected claims are false; its freeze commit predates the transparency feature commit). `FINAL_HANDOFF.md` is a superseded snapshot and should carry a banner or be regenerated before tag. Required before tagging `v0.5-sprint4`: (1) rewrite CHANGELOG `[Unreleased]` to the shipped scope; (2) re-freeze at `7ca0cfe` or re-cut the freeze report; (3) fix INTELLIGENT_RESPONSE_REPORT L40 + EXP-007 test counts; (4) MODEL_REGISTRY TSK-row stale metrics; (5) stamp FINAL_HANDOFF as superseded.

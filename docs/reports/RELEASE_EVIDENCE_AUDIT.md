# RELEASE_EVIDENCE_AUDIT.md — Sprint 4 claim verification (Phase 2)
**Auditor:** research-scientist (governance only) · **Date:** 2026-11-04 · **Repo:** `sprint-4-ai-modernization` @ `7ca0cfe` (clean tree)
**Method:** each claim checked for THREE legs — source file (line-verified at HEAD), test evidence (tests actually executed by this audit), report evidence (section-verified). No claim accepted from any report without its legs.

## 0. Test execution record (this audit, at HEAD)

| Run | Result |
|---|---|
| `python -m pytest tests/test_tax_intelligence.py tests/test_response_composer.py tests/test_sprint4_p1.py -q` | **96 passed in 3.61s** |
| Per-file collection | test_tax_intelligence **12** · test_response_composer **23** · test_sprint4_p1 **61** |
| Full suite `python -m pytest -q -p no:cacheprovider` | **1,146 passed, 1 deselected, 0 failed** in 55.50s |
| `npx vitest run` (transparency commit touched TaxReport.tsx) | **22/22 passed** in 1.56s |

## 1. Claim-by-claim evidence matrix

### Claim 1 — Tax Intelligence Layer exists and works — **EVIDENCED**

| Leg | Evidence |
|---|---|
| Source | `backend/tax_intelligence.py`: `composite_efficiency` :249, `predict_efficiency` :275 (served composite, exact); `recommend` :408 (two-pass advisor); `RULES = 48` :50; `SCHEMA "anfis-feature-schema/3"` :60; 661-line module |
| Tests | `tests/test_tax_intelligence.py` 12/12 pass — incl. `TestADRBoundary` (every recommendation re-priced through fresh `calculate_tax_advanced`, exact equality) and `no_amount_is_invented` (zero-benefit → ₹0 + NO BENEFIT) |
| Reports | `SPRINT4_RELEASE_CANDIDATE_REPORT_V2.md` §2 ("Tax Intelligence Layer"); `CA_RECOMMENDATION_ENGINE_REPORT.md` §2 (two-pass loop, cites `tax_intelligence.py:408-498`); `MODEL_REGISTRY.md` L9 (anfis-v5 composite LIVE); `FINAL_TECHNICAL_AUDIT.md` Claim 1 VERIFIED |

### Claim 2 — Explainability Engine — **EVIDENCED**

| Leg | Evidence |
|---|---|
| Source | `backend/tax_intelligence.py`: `explain_efficiency` :533 (statutory-weight decomposition), `explain_model_efficiency` :564 (μ → w̄ → consequents → top rules), `advisor_block` :602 (layer-3 renderer) |
| Tests | `tests/test_tax_intelligence.py` 12/12 pass — Layer-1 and Layer-2 decomposition contracts pinned on a real in-session fit (`FINAL_TECHNICAL_AUDIT.md` Claim 8 pins these at :28-47, :127-152) |
| Reports | `EXPLAINABILITY_ENGINE_REPORT.md` §1 (three layers mapped to the three functions), §2 (worked example 39.1 / 0.4103 / ₹1,300 — live-reproduced by FINAL_TECHNICAL_AUDIT Claim 3), §5 (test evidence table) |

### Claim 3 — CA Recommendation System — **EVIDENCED**

| Leg | Evidence |
|---|---|
| Source | `backend/tax_intelligence.py`: `recommend` two-pass :408-498 (baseline price → full-headroom probes → engine-priced ranking); exact rule heads `rule_opportunity`/`rule_savings`/`rule_confidence` :647-658; wiring `backend/nlp_engine.py:1141-1148` (import :1141, call :1144, closing assembly :1148, blanket containment :1138/:1147) |
| Tests | `tests/test_tax_intelligence.py` 12/12 pass (shape/ranking/regime-advisory/no-benefit-suppression/engine-only degradation contracts); CA report §9 documents the same 12 as its test evidence |
| Reports | `CA_RECOMMENDATION_ENGINE_REPORT.md` §2 (two-pass), §3.1-3.5 (five advisor modules), §5 (worked 8-head table), §6 (ADR-001 audit trail), §9 (12 tests); `FINAL_VALIDATION_REPORT.md` §4 (independent ADR-001 recompute: **15/15 rows exact**, zero-benefit contract holds) |

### Claim 4 — Transparency Fix (Applied-vs-Ignored panel + deduction_details) — **PARTIAL**

| Leg | Evidence |
|---|---|
| Source | `frontend/src/components/TaxReport.tsx:226-231` — "Sprint 4 Phase 4A" panel, card title "Your Deductions — Applied vs Ignored"; `backend/tax_engine.py:203` (`deduction_details` result field) + :377-384 (per-regime population from the authoritative Explanation list). Shipped in `7ca0cfe` (+111 lines TaxReport.tsx, +14 tax_engine.py) |
| Tests | **No committed automated test pins the panel or `deduction_details`** (repo-wide grep: only the source file matches). Test leg = live Playwright DOM verification on the real stack (`TAX_COMPUTATION_TRANSPARENCY_REPORT.md` §2: panel renders ✅, Sec-115BAC reason ✅, taxable ₹45,25,000 matches the engine matrix ✅, double-counted std-ded row removed ✅) + regression gates re-run green at HEAD by this audit (pytest 1,146/0; vitest 22/22 — no test was added, none broke) |
| Reports | `TAX_TRACE_AUDIT.md` (backend exonerated, matrix A-G), `TAX_REPORT_TRANSPARENCY_AUDIT.md` (258-line per-question verdicts, file:line), `TAX_COMPUTATION_TRANSPARENCY_REPORT.md` §1-4, commit `7ca0cfe` message |

**Why PARTIAL:** source and report legs are strong; the test leg is a documented one-time live validation, not a regression-pinned automated test. A future TaxReport.tsx edit could silently break the panel. (Mitigating: existing `__tests__/TaxReport.test.tsx:63-77` pins the /calculate wire contract the panel consumes.)

### Claim 5 — Response Composer — **EVIDENCED**

| Leg | Evidence |
|---|---|
| Source | `backend/response_composer.py` (dedicated module); integrated in `backend/nlp_engine.py`: import :15, composer construction :1068-1069, ack/advisory :1088, closing line :1148 |
| Tests | `tests/test_response_composer.py` **23/23 pass** (collected 23 — determinism, rotation, data-awareness, advisory contracts; the >95% contextual metric is pinned inside) |
| Reports | `CHANGELOG.md` `[Unreleased]` Added §1 ("23 contract tests" — the one current CHANGELOG line); `INTELLIGENT_RESPONSE_REPORT.md` §1 (integrated response contract), §4 (test coverage — cites **25**, stale count, actual 23); `FINAL_TECHNICAL_AUDIT.md` Claim 2 (composer contract verified: pure prose, deterministic rotation, ADR-001 boundary) |

### Claim 6 — ANFIS v5 findings (composite exact; TSK heads off-deployment with measured G4/G5 failures) — **EVIDENCED**

| Leg | Evidence |
|---|---|
| Source | Serving exact: `tax_intelligence.py:249-278` (composite evaluated directly from schema features — exact by construction). TSK off-deployment: `backend/anfis_v5_weights.json` **absent** (verified: file does not exist; trainer writes only on `gates_pass`); MODEL_REGISTRY L10 "**EXPERIMENT — not deployed**" |
| Tests | `tests/test_tax_intelligence.py` 12/12 pass (model fields optional; `ti=None` engine-only degradation; ADR boundary proves the model cannot alter served rupees); `tests/test_sprint4_p1.py` 61/61 incl. `TestEngineScoringOrder` |
| Reports | `ANFIS_V5_EVALUATION_V2.md` §1 VERDICT + §2 gates: G1 MAE 0.136 PASS · G2 −0.112 PASS · G3 100% PASS; TSK **G4 savings MAPE 794.69% FAIL** · **G5 opportunity P=0.000 R=0.000 FAIL** · G6 57.04% current-protocol (95.72% engine-ordered, reconciliation disclosed); independently reproduced live by `FINAL_VALIDATION_REPORT.md` §2 row 4 ("byte-for-byte same gate lines") and `RELEASE_FREEZE_REPORT.md` §4.2 |

## 2. Summary table

| # | Claim | Source | Tests (run here) | Report | Verdict |
|---|---|---|---|---|---|
| 1 | Tax Intelligence Layer | tax_intelligence.py:249/:275/:408/:50 | 12/12 (test_tax_intelligence.py) | SPRINT4_V2 §2; CA §2; MODEL_REGISTRY L9; audit Claim 1 | **EVIDENCED** |
| 2 | Explainability Engine | tax_intelligence.py:533/:564/:602 | 12/12 (decomposition contracts) | EXPLAINABILITY_ENGINE_REPORT §1/§2/§5 | **EVIDENCED** |
| 3 | CA Recommendation System | tax_intelligence.py:408-498/:647-658; nlp_engine.py:1141-1148 | 12/12 + ADR-001 recompute 15/15 | CA report §2/§3/§5/§6/§9; FINAL_VALIDATION §4 | **EVIDENCED** |
| 4 | Transparency Fix | TaxReport.tsx:226-231; tax_engine.py:203/:377-384 | none committed (live Playwright validation only); gates green at HEAD | TAX_TRACE_AUDIT; TAX_REPORT_TRANSPARENCY_AUDIT; TAX_COMPUTATION_TRANSPARENCY_REPORT §2 | **PARTIAL** |
| 5 | Response Composer | response_composer.py; nlp_engine.py:15/:1068/:1148 | 23/23 (test_response_composer.py) | CHANGELOG Added; INTELLIGENT_RESPONSE §1/§4; audit Claim 2 | **EVIDENCED** |
| 6 | ANFIS v5 findings | tax_intelligence.py:249-278 exact; weights file absent | 12/12 + 61/61 regression | ANFIS_V5_EVALUATION_V2 §1-2; FINAL_VALIDATION §2.4; FREEZE §4.2 | **EVIDENCED** |

## 3. Overall verdict

**5 of 6 claims EVIDENCED with all three legs; 1 PARTIAL (Claim 4).** No claim is UNSUPPORTED. The single gap is governance-relevant for the tag decision: the Phase-4A transparency feature (the most user-visible Sprint-4 fix, born from a user-reported ₹46L issue) has zero committed automated coverage — recommend one Vitest test on the TaxReport panel render plus one pytest test asserting `deduction_details` population before tagging `v0.5-sprint4`. All other Sprint-4 claims are pinned by passing tests at HEAD and documented in dedicated report sections whose figures this audit reproduced live.

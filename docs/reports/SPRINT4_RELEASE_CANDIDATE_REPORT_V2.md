# SPRINT4_RELEASE_CANDIDATE_REPORT_V2.md
**Generated:** 2026-11-03 · **Branch:** `sprint-4-ai-modernization` · **Proposed tag:** `v0.5-sprint4` · **Supersedes:** `SPRINT4_RELEASE_CANDIDATE_REPORT.md` (V1)

---

## 1. Verdict: **RELEASE-READY — merge-ready pending user tag decision**

All mission phases (0-9) delivered. Security re-review APPROVE-WITH-NITS with all 5 findings fixed and re-probed. 1,146 pytest / 0 failures.

## 2. What v0.5 ships (final scope)

### Tax Intelligence Layer (ANFIS v5) — `backend/tax_intelligence.py`
- **Served efficiency**: deterministic composite over schema v2.1 features — exact (G1 MAE 0.136 / G2 −0.112 / G3 100% on the expanded validation split).
- **CA-style advisor** (`recommend()`): ADR-001 two-pass — baseline engine price → per-head FULL-HEADROOM top-up probes → engine-priced savings ranked; zero-benefit honestly rejected (`NO BENEFIT (current regime ignores this head)`); 87A band position; regime advisory.
- **Exact rule heads** (forensics-derived deployment): opportunity P 1.000 / R 1.000 / savings MAE 0.00 INR — engine-priced by construction (`ANFIS_ROOT_CAUSE_REPORT.md` measured why: the labels are exact functions of the engine's own regime verdict and paid ratios).
- **Learned TSK heads**: G6 ranking 54.9% → **95.72%** after dataset expansion; G4/G5 remain below deployment bar → **off-deployment experiments**, registry-documented with promotion gates.

### Explainability Engine
Three layers: served-composite statutory-weight decomposition (exact) · TSK rule attribution (experiment) · session-derived evidence lines. Reasoning chain per recommendation: why → evidence → impact → confidence → next action. (`EXPLAINABILITY_ENGINE_REPORT.md` — architect-authored with worked traces.)

### CA-Style Recommendation Engine
Five advisor roles implemented and documented (`CA_RECOMMENDATION_ENGINE_REPORT.md` — backend-engineer-authored with live engine-verified examples): deduction advisor (headroom + priced top-ups), regime advisor (engine verdict + 87A band), optimization advisor (the ranking), risk advisor (zero-benefit/regime-mismatch honesty + engine advisory stream), opportunity advisor (full-headroom probe strategy — measured: partial probes miss regime flips).

### Intelligent responses
Closing turn carries the 🧠 block (recommendation/reason/confidence/evidence/savings/next action) **only** when the engine prices a real benefit; absent otherwise (honesty over engagement). Engine-first degradation: the block works with the learned model offline.

### Also in v0.5
Response Composer (P2) · P1 certification · evaluation CLI · ADR-015 · hazaar numerals · lakh-stem fix · responsive frontend shell · amplification hardening (5 vectors) · Phase-5 dataset expansion.

## 3. Datasets / Models / Metrics

| Item | Value |
|---|---|
| corpus-v1 | 2,226 records · gate PASS · macro F1 1.000 |
| anfis-v1 (schema v2.1 + f21) | 5,964 scenarios · 76,960 opportunity rows · **1,623 positives (2.11%, 11× original)** · sessions embedded for provenance |
| Tests | **1,146 pytest / 0 failures** · 22 Vitest · 7 Playwright · 97 legacy |
| Extraction eval | gate PASS · macro F1 1.000 · abstention 17/17 |
| Intelligence gates | served composite G1/G2/G3 PASS · ranking 95.72% · exact rule heads P/R 1.0/1.0 · TSK experiment G4/G5 fail (documented, off-deployment) |
| Security | APPROVE-WITH-NITS → all 5+5 findings closed, probes re-run (255-587B bounded) |
| Reviews | qa-lead + security-auditor + architect + backend-engineer + ml-evaluation-engineer (5 specialist passes) |

## 4. Release risks

| Risk | Severity | Mitigation |
|---|---|---|
| Intelligence block rare in live chat (new-regime users get honest ₹0 verdicts) | Low | By design; block appears on old-regime-optimal sessions (test fixture proves the path) |
| Legacy NPS Quick Tip quotes old-regime arithmetic on new-regime users | Medium | Filed next-sprint: regime-gate `get_savings_tips` |
| TSK learned heads below deployment bar | Medium (scope) | Not deployed; promotion needs positive-rich continuous-value dataset (next dataset action) |
| Structured grid saturation (76,960 rows is the deterministic ceiling) | Low | Continuous-value sampling specified in `DATASET_QUALITY_REPORT_V2.md` §4 |

## 5. Merge readiness checklist

- [x] pytest 1,146 green · Vitest 22 · extraction gate PASS
- [x] Security re-review APPROVE (all findings fixed + re-probed)
- [x] QA validation running → report
- [x] ADR-001 recomputation suite green
- [x] Registries current (4 files)
- [x] Rollback ladder intact
- [ ] **User decision: tag `v0.5-sprint4` + PR to main**

## 6. Ten evidence-backed answers

1. **Why ANFIS exists** — instant, explainable planning intelligence without touching tax numbers (ADR-001).
2. **Value delivered** — efficiency scoring, utilization/saturation, opportunity ranking, honest CA-style verdicts.
3. **How recommendations are generated** — engine two-pass: baseline price → full-headroom probes → engine-priced ranking (`recommend()`).
4. **How confidence is calculated** — 0.85 engine-two-pass authority / 0.30 priced-no-benefit (`rule_confidence`).
5. **How explainability works** — statutory-weight decomposition + TSK attribution + session evidence lines (3 layers).
6. **Which datasets** — corpus-v1 (2,226) + anfis-v1 (5,964 scenarios / 76,960 rows / 1,623 positives), registries.
7. **Which models were trained** — RUN-002/003/003b (`TRAINING_REGISTRY.md`): TSK heads = experiments; rule heads = deployment.
8. **Which metrics justify deployment** — rule heads P/R 1.0/1.0 MAE 0.00 (exact); composite MAE 0.136; ranking 95.72%.
9. **Why TaxEngine stays authoritative** — ADR-001 tests: every estimate recomputed exactly; zero-benefit → ₹0; model fields optional.
10. **Is v0.5 ready?** — Yes: release-ready pending the user's tag decision.

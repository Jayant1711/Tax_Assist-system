# PR_BODY_V0.5_SPRINT4.md
**Use:** paste as the GitHub PR description for `sprint-4-ai-modernization` → `main` (squash-merge or merge-commit both fine; tag `v0.5-sprint4` on the merge commit).

---

## v0.5-sprint4 — Tax Intelligence Layer, ANFIS v5, and the Certification Wave

### Summary

Sprint 4 transforms Tax Assist from a scripted tax bot into a **measured, intelligent, and honestly self-limiting** consultant — without moving a single rupee out of the deterministic TaxEngine (ADR-001):

- **Tax Intelligence Layer (ANFIS v5)** — `backend/tax_intelligence.py`: exact composite efficiency scoring (schema v2.1, MAE 0.136 vs its own definition), per-head utilization/saturation, **CA-style recommendations** priced by a two-pass TaxEngine loop (baseline → full-headroom probes → engine-priced savings, ranked; zero-benefit honestly rejected).
- **Explainability Engine** — three layers: statutory-weight decomposition (served), TSK rule attribution (experiment), session-derived evidence lines. Every recommendation carries why/evidence/impact/confidence/next action.
- **Exact rule heads (deployment)** — forensics (`ANFIS_ROOT_CAUSE_REPORT.md`) measured that the opportunity label *is* the engine's regime verdict and the savings label is exactly linear in the paid ratios — so v0.5 deploys deterministic rule heads (P/R 1.0/1.0, MAE 0.00) instead of a failing neural approximation. The TSK learned heads remain registry-documented experiments with promotion gates (`ANFIS_V5_EVALUATION_V2.md`).
- **Response Composer (P2)** — data-aware acks (en-IN amounts), advisory weaving (headroom/80G rule/CG election/87A band), deterministic rotation, confidence messaging; 23 contract tests.
- **Extraction certification (P1)** — Indian comma grouping, Hinglish numerals (hazaar/hajar), lakh-stem fix, earn/earner signals, NGO donee/employer disambiguation, transfer-year handling — **macro F1 1.000 on the eval split, gate PASS**.
- **Security hardening** — 5 reply-amplification/PII vectors closed (probes 28–64KB → ≤587B); two independent reviews APPROVE.
- **Frontend** — responsive chat-first shell for 15″ laptops (chat column 460→614-700px, breakpoints, readability pass).

### Evidence

| Area | Result |
|---|---|
| pytest | **1,146 passed / 0 failed** (was 1,099+6) |
| Vitest / Playwright / legacy | 22/22 · 7 · 97 |
| Extraction eval | macro F1 **1.000** · gate PASS · abstention 17/17 (`tools/run_eval.py`) |
| Intelligence | rule heads P/R 1.0/1.0 · composite MAE 0.136 · ranking 95.72% (engine-ordered) |
| Datasets | corpus-v1 (2,226) · anfis-v1 v2.1 (5,964 scenarios / 76,960 rows / 1,623 engine-priced positives) |
| Reviews | qa-lead RELEASE-READY · security APPROVE · architect audit PASS · ADR-001 recomputation 15/15 exact |

Full evidence chain: `ANFIS_ROOT_CAUSE_REPORT.md` · `ANFIS_V5_EVALUATION_V2.md` · `DATASET_QUALITY_REPORT_V2.md` · `EXPLAINABILITY_ENGINE_REPORT.md` · `CA_RECOMMENDATION_ENGINE_REPORT.md` · `INTELLIGENT_RESPONSE_REPORT.md` · `FINAL_TECHNICAL_AUDIT.md` · `FINAL_VALIDATION_REPORT.md` · `SPRINT4_FINAL_SCORECARD.md` · `RELEASE_FREEZE_REPORT.md` · the four `*_REGISTRY.md` files.

### ADRs

- **ADR-015** — deterministic extraction retained (gate PASS; learned extractor not warranted at current corpus volume).
- **ADR-016** — intelligence deploys exact rule heads; TSK heads off-deployment with promotion gates.

### Release notes summary

New: intelligence block on the closing turn, eval CLI, ANFIS v5 dataset/training tools, Hinglish numerals, responsive shell. Fixed: 6 stale-failing tests, phantom-8/earn/earner/NGO/lakh-stem extraction bugs, 5 amplification vectors, PII log line. Documented: TSK heads off-deployment (data-limited), grid saturation, regime-gating of legacy tips (next sprint).

### Risks

- Intelligence block rare for new-regime users (honest ₹0 verdicts) — by design.
- Learned heads below deployment bar — not served; promotion gated on a positive-rich dataset (`SPRINT5_ROADMAP.md` P0/P1).
- Legacy NPS tip regime-gating — filed next sprint.

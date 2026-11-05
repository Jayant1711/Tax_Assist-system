# SPRINT4_RELEASE_CANDIDATE_REPORT.md
**Generated:** 2026-11-03 · **Branch:** `sprint-4-ai-modernization` · **Proposed tag:** `v0.5-sprint4` · **Baseline:** `v0.4-sprint3`

---

## 1. Verdict: **RELEASE-READY (with one documented scope decision)**

All six mission phases delivered; 1,146 tests passing (0 failures); ADR-001/003 intact; security review APPROVE; the Tax Intelligence Layer ships **engine-first** with the learned heads as registry-documented experiments.

## 2. What ships in v0.5

### Tax Intelligence Layer (ANFIS v5) — `backend/tax_intelligence.py`
- **Served efficiency**: the documented composite over schema-v2 features — exact (G1 MAE 0.053 pts vs labels; G2 calibration −0.013; G3 consistency 100%).
- **CA-style recommendations** (`recommend()`): two-pass engine pricing — baseline → per-head full-headroom top-up probes → engine-priced savings, ranked. Zero-benefit opportunities honestly labeled `NO BENEFIT (current regime ignores this head)`.
- **Learned heads** (savings estimate, opportunity probability): implemented (ridge-LSE TSK, 48 rules, cascade/balanced training) but **not deployed** — gates failed at current data volume (146 positive rows vs 1,104 params; regime-flip boundary needs the plan's 120k-row positive-rich strata). Registry-documented; promotion gates pre-committed.
- **Composer integration** (`nlp_engine.py` closing turn): the 🧠 "Best opportunity" block cites only engine-priced savings + confidence 0.85; absent (reply unchanged) when the engine prices no benefit. Live-verified.

### Explainability Engine
- `explain_efficiency` — served-composite decomposition: statutory weight × utilization per head, top contributors named.
- `explain_model_efficiency` — the learned TSK decomposition (μ → w̄ → contributions → top rules + effective-rule count) as the research path.

### Traceability (mission requirement)
- `DATASET_REGISTRY.md` · `MODEL_REGISTRY.md` · `TRAINING_REGISTRY.md` · `EXPERIMENT_REGISTRY.md` — location/version/schema/counts/labels/splits/generation for every dataset; architecture/params/loss/time/metrics/deployment for every model; goal/config/outcome/conclusion for every experiment.

### Also in v0.5 (from the previous run, already on the branch)
- Response Composer (P2), P1 certification, evaluation framework CLI, ADR-015, hazaar numerals, lakh-stem fix, security hardening, responsive frontend shell.

## 3. Datasets / Models / Metrics (summary — full detail in the registries)

| Item | Value |
|---|---|
| corpus-v1 | 2,226 records · template-disjoint 70/15/15 · sha256-pinned |
| anfis-v1 (schema v2) | 3,528 TaxEngine-priced scenarios · 46,816 engine-computed opportunities |
| Extraction eval | macro F1 1.000 · gate PASS · abstention 17/17 |
| Tests | **1,146 pytest / 0 failures** · 22 Vitest · 7 Playwright · 97 legacy |
| Served efficiency accuracy | MAE 0.053 pts vs its own documented definition |
| Learned savings head | MAPE ~92–108% on 58 material val rows — NOT deployed |
| Security | APPROVE-WITH-NITS → all findings closed |

## 4. Release risks

| Risk | Severity | Mitigation |
|---|---|---|
| Intelligence block appears only when the engine prices a real saving — users on the new regime see few recommendations | Low (by design — honesty over engagement) | The block text states the engine-verified basis; future positive-rich dataset may unlock more |
| Learned savings/opportunity heads below gates | Medium (scope, not correctness) | Not deployed; rollback ladder intact; promotion = retrain on 120k strata + gates |
| `v0.5` changes the closing-turn reply format (adds 🧠 block when material) | Low | Frontend renders plain text; no frontend change required |
| FY 2025-26 80CCD(1B) self-contribution non-deductible under 115BAC — the legacy Quick Tip's "₹15,600 NPS savings" can mislead on the new regime | Medium (pre-existing, out of scope this sprint) | Filed for the next sprint: gate `get_savings_tips` by the engine's recommended regime |

## 5. Merge readiness checklist

- [x] Full pytest green (1,146)
- [x] Vitest green (22)
- [x] Security review APPROVE (all findings closed)
- [x] QA review APPROVE (all actionable findings closed)
- [x] ADR-001/003 verified intact (two-pass tests + spy tests)
- [x] Registries complete (4 files)
- [x] Rollback ladder documented (v5 candidate absent → v4 active → numpy-less heuristic)
- [ ] User decision: tag `v0.5-sprint4` + PR to main
- [ ] Optional pre-merge: Playwright re-run against the rebuilt stack

## 6. Answers to the ten success questions

1. **Why does ANFIS exist?** To give users an instant, explainable read on how tax-efficient their planning is and which opportunities matter — without ever touching the tax numbers (ADR-001).
2. **What value does ANFIS provide?** Efficiency scoring, per-head utilization, opportunity ranking, confidence-tagged recommendations — annotated on engine output.
3. **How is it trained?** Ridge-LSE consequents (closed form) over data-driven Gaussian memberships; sigma-scale search; class-balanced/material-cascade heads (RUN-003, `TRAINING_REGISTRY.md`).
4. **Which dataset?** `data/anfis_v1/` (schema v2): 3,528 TaxEngine-priced scenarios, 46,816 opportunities — `DATASET_REGISTRY.md`.
5. **Which features?** The 20 schema-v2 features (`tax_intelligence.features_v2` — the single source; `ANFIS_FEATURE_SCHEMA.md`).
6. **How are recommendations generated?** Two-pass: TaxEngine prices baseline and per-head top-ups; ranking is by engine-priced savings; zero-benefit heads are honestly rejected (`recommend()`).
7. **Why is v5 better than v4?** v4's trainer optimized against the wrong ground truth (ADR-004, r² 0.4976); v5 defines the target exactly (composite MAE 0.053), fixes 4 schema defects, replaces the failing optimizer with closed-form LSE, and adds savings/opportunity/explainability heads — with gates that honestly held back what failed.
8. **How is explainability achieved?** Composite weight decomposition (served) + TSK rule-firing/contribution decomposition (experiment) + per-recommendation evidence lines from session utilization (`ANFIS_EXPLAINABILITY_FRAMEWORK.md`).
9. **How is correctness preserved?** ADR-001 two-pass tests: every estimate recomputed via `calculate_tax_advanced` (exact match asserted); zero-benefit → ₹0; the learned heads cannot alter amounts.
10. **Is v0.5-sprint4 ready?** **Yes** — pending only the user's tag/merge decision (§5 checklist).

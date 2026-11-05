# SPRINT5_ARCHITECTURE_PLAN.md — Phase 6
**Generated:** 2026-11-04 · **Baseline:** v0.5-sprint4 · **Scope:** the Sprint 5 architecture as it will be built (planning artifact — nothing implemented yet)

---

## 1. Objectives

1. **Close the learning loop**: acceptance capture → weak labels → calibrated intelligence (the only missing signal chain).
2. **Unblock the TSK heads**: continuous-value sampler → ≥5,000 positives → gate-driven promotion attempt.
3. **Fix label/feature correctness**: P0.1 normalization (u80g, 80d_parents probe, 80U/80DDB legs) before any retraining.
4. **Trust**: regime-gate the legacy tips; keep every rupee engine-priced.

## 2. Architecture deltas (v0.5 → v0.6)

| Delta | Design | ADR impact |
|---|---|---|
| **Acceptance events** | new `recommendation_events` table (session_id, rec_id, head, delta, shown_ms, action: accepted/rejected/ignored, confidence_at_show) — written through the existing session/audit path; PII-minimized (no free text) | **ADR-017 (new)**: recommendation event capture — event-sourced acceptance, opt-out by not interacting, DPDP-minimized |
| **Intelligence read surface** | `GET /sessions/{id}/recommendations` — serves `recommend()`'s full ranked list (engine-priced) for the frontend cards | extends the existing session ownership model (404 on foreign ids) |
| **Continuous sampler** | `tools/generate_anfis_dataset.py` v3: seeded continuous ranges replace grids; sampler-version in the manifest; strata quotas | dataset versioning discipline (existing registry rules) |
| **TSK promotion path** | `TAX_INTELLIGENCE_MODEL=tsk\|rules` env flag (default rules); tsk loads `anfis_v5_weights.json` only on gate pass | ADR-016 unchanged; adds the deployment flag the promotion ladder specified |
| **Tip regime-gating** | `get_savings_tips(session, recommended_regime)` — tips recomputed/rejected against the served regime | bug fix, no ADR |

**Non-delta (explicitly unchanged):** TaxEngine calculation path (ADR-001) · NLP extraction · auth/session/edge stack · the exact rule heads as default intelligence.

## 3. Implementation phases

| Phase | Content | Gates |
|---|---|---|
| A | P0.1 fixes + tip regime-gating + tests | full suite green; no tip contradicts the served regime |
| B | Acceptance events (schema + endpoint + capture) + P2 tests | event written per shown recommendation; 404/ownership enforced; audit rows minimized |
| C | Continuous sampler v3 + dataset v3 + quality report | ≥5,000 positives; leakage checker green; rebuild-repro green |
| D | TSK retrain + gates → deploy-on-pass behind the flag | G4 ≤10% · G5 P/R · G6 top-1 on the v3 data; rollback = flag default |
| E | Frontend intelligence cards (P6) + docs/registries | vitest + Playwright panel/cards green |

## 4. Expected metrics (end of Sprint 5)

| Metric | v0.5 | Target |
|---|---|---|
| anfis-v3 positives | 1,623 | **≥5,000** |
| TSK savings MAPE | 795% (off-deployment) | **≤10%** (material rows) on v3 val |
| TSK opportunity | P0/R0 | **P≥0.95 ∧ R≥0.90** |
| Rule-head confidence | fixed 0.85 | acceptance-calibrated (ECE ≤ 0.05 on holdout) — or documented non-promotion |
| Tip correctness | unregimed | 100% regime-consistent |
| Tests | 1,146 + 25 vitest | ≥1,160 pytest · ≥28 vitest (new contracts) |

## 5. Risks & rollback plans

| Risk | Rollback |
|---|---|
| TSK fails gates again (like RUN-003b) | flag stays `rules`; the dataset remains (compounding asset); document |
| Acceptance events bloat sessions | event table separate from app_sessions payload; size-capped; purge policy |
| Cards confuse users | feature-hidden behind the existing report tab; revert = one component commit |
| Sampler leakage | strata-disjoint validation enforced by the leakage checker (extended) |
| Any regression | full 1,146-test suite + CI as the merge gate — unchanged |

## 6. What is NOT in this architecture (evidence-based rejections)

- Learned models in the tax path (ADR-001) · streaming classification (no latency evidence) · multi-worker redesign (single-worker documented) · personalization before acceptance data exists (rejected in the priority matrix).

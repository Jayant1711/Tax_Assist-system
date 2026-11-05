# SPRINT5_EXECUTION_READY.md — Phase 5 Sprint 5 Preparation
**Generated:** 2026-11-04 · **Baseline:** v0.5-sprint4 · **Status:** execution-ready (objectives, dependencies, datasets, models, blockers, risks)

---

## Sprint 5 objective

**"Close the learning loop."** Turn the deployed intelligence layer from static rules into a feedback-driven system: capture acceptance, grow the dataset continuously, promote the TSK heads on gates, and extend coverage — ADR-001/003 unchanged.

## P0.1 — Feature/label normalization fixes (quick wins, first)

| Fix | Detail | Acceptance |
|---|---|---|
| u80g mismatch | align `features_v2` f9 with `efficiency_ground_truth` (1,564 rows mismatched, max 1.717) | mismatch count 0 |
| 80d_parents probe | probe prices ₹0 in 600/600 (cap gating) — verify the probe head list | probe produces non-zero where headroom exists |
| 80U/80DDB legs | features all-zero — wire the enum features or drop from the composite | no all-zero feature columns in the emitted npz |

## P0 — Continuous-value dataset sampler

- Seed-range sampling for rent/hra/80g/80e/24b amounts; log-uniform incomes 3L–2Cr; CG amounts bracketing the 1.25L 112A band.
- Target **≥5,000 genuine positives** (the measured requirement for TSK G4/G5 — forensics §min-positive-count), ~120k opportunity rows.
- Dependencies: TaxEngine (stable ✓); P0.1 first (labels must be feature-expressible).
- Acceptance: DATASET_QUALITY_REPORT_V3 with positive density, strata coverage, leakage check green.

## P1 — TSK head promotion attempt (conditional)

- Retrain on the P0 dataset (LSE consequents, additive combination — the proven config).
- Gates unchanged (G4 MAPE ≤10% material · G5 P≥0.95/R≥0.90 · G6 top-1 ≥80%).
- Deploy behind `TAX_INTELLIGENCE_MODEL=tsk|rules` (default rules) only on all-pass; otherwise document and continue with rule heads (v0.5 behavior unchanged).

## P2 — Recommendation acceptance tracking

- New session event: recommendation shown → accepted/rejected/ignored (PII-minimized, audit-streamed).
- `funnel.py` extension: acceptance rate per head × confidence band.
- Feeds P1 retraining (accepted recommendations are the strongest weak labels) and ADR-015's organic trigger.

## P3 — Regime-gate the legacy savings tips (quick win, co-first with P2)

- `ReasoningAgent.get_savings_tips`: gate each tip by the engine's recommended regime; recompute tip savings via the two-pass (the measured defect: NPS "₹15,600" tip shown to a new-regime user where the engine prices ₹0).
- Acceptance: no tip contradicts the served regime; tests pin it.

## P4 — NER corpus expansion (research)

- Templates 51 → ≥500 samples across the 6 entity types + Hinglish families; re-measure BiLSTM.
- Target ≥0.60 accuracy before claiming capability; else keep the honest-finding framing.

## P5 — Organic corpus capture

- `TAX_CORPUS_CAPTURE=1` on the demo deployment; monitor `data/corpus/` growth toward the ADR-015 ≥5k-organic-turns trigger; acceptance-derived weak labels (P2) reviewed before eval use.

## P6 — Frontend intelligence cards

- Render the full ranked recommendation list (from `recommend()`) in the TaxReport panel: reason/evidence/confidence/savings per card + acceptance buttons (wired to P2). Frontend + one read surface.

## Datasets & models (Sprint 5 start state)

- Datasets: anfis-v1 v2.1 (5,964 scenarios / 76,960 rows / 1,623 positives — sampler grows this) · corpus-v1 (2,226) · ner-templates-v1 (51 → grows in P4).
- Models: anfis-v4 (production scorer, untouched) · rule-heads-v5 (deployed intelligence) · TSK heads (experiment, promotion path P1) · research models (phase_c–g, unchanged).

## Blockers

- None open. (Sprint 4's blockers — positive scarcity, evaluator conventions, security findings — were all resolved this run.)

## Risks

| Risk | Mitigation |
|---|---|
| Continuous sampler produces near-duplicate positives (label leakage) | seeded diversity + dedupe on (session, head, delta) triples + leakage checker (P0 acceptance) |
| TSK heads fail gates again at 5k positives | documented outcome; rule heads remain the deployment; the dataset keeps growing toward the threshold |
| Acceptance capture PII exposure | DPDP-minimized event fields; audit-stream review before enabling |
| Multi-worker deployment vs per-process rate limiter/limiter assumptions | unchanged from v0.5 (single-worker documented deployment) |

## Definition of done (Sprint 5)

P0.1+P0 accepted → P1 gates decided (deploy or documented continuation) → P2/P3 shipped with tests → P4/P5 measured → registries + reports updated → v0.6 release candidate.

# SPRINT5_ROADMAP.md — Post-v0.5 Plan (Design Only, Not Implemented)
**Generated:** 2026-11-04 · **Baseline:** v0.5-sprint4 RC · **Owner:** next sprint

---

## Theme
From "honest intelligence" to "learning intelligence": close the loop between what the advisor recommends, what users accept, and what the models learn — without ever moving a tax number out of the TaxEngine (ADR-001 stands).

## P0.1 — Feature/label normalization fixes (forensics D5, quick win)
- u80g composite/feature normalization mismatch (measured 1,564 rows, max 1.717) — align `features_v2` f9 with `efficiency_ground_truth`.
- 80d_parents probe prices ₹0 in 600/600 probes (cap gating) — verify the probe head list.
- 80U/80DDB legs still all-zero features — either wire the enum features or drop them from the composite.

## P0 — Continuous-value dataset sampler (the binding constraint)
The deterministic scenario grid is saturated at 76,960 rows / 1,623 positives (grid periodicity — `DATASET_QUALITY_REPORT_V2.md` §4). Replace fixed value grids with seeded continuous sampling:
- `rent_paid`, `hra_received`, `80g`, `80e`, `24b` amounts drawn from seeded ranges (e.g. `rng.uniform` over [0, limit×1.2]); incomes log-uniform over 3L–2Cr.
- Target: ~120k opportunity rows with **≥5,000 positives** (the measured requirement for the TSK heads' G4/G5 — `ANFIS_ROOT_CAUSE_REPORT.md` §min-positive-count).
- Keep template-disjoint validation: stratify by seeded bucket, hold out 10%.
- Acceptance: positives ≥5,000; no duplicate (session, head, delta) triples; leakage checker green.

## P1 — Deploy the TSK learned heads (conditional)
With P0 data: retrain savings + opportunity heads (`train_anfis_v5.py`), gates unchanged (G4 MAPE ≤10% material, G5 P≥0.95/R≥0.90, G6 top-1 ≥80%). Deploy behind `TAX_INTELLIGENCE_MODEL=tsk|rules` (default rules) only on all-pass; keep the exact rule heads as the always-on fallback (the two-pass engine pricing is unchanged either way).

## P2 — Recommendation acceptance tracking (feedback loop)
- Capture accepted/rejected/ignored per recommendation in the session + audit stream (new session event, PII-minimized).
- Funnel analytics extension (`backend/funnel.py`): recommendation acceptance rate per head/confidence band.
- Feeds P3 retraining and the ADR-015 revisit trigger (organic corpus growth).

## P3 — Regime-gate the legacy savings tips
`ReasoningAgent.get_savings_tips` quotes old-regime arithmetic on new-regime users (measured: NPS "₹15,600" tip on a new-regime session where the engine prices ₹0). Gate each tip by the engine's recommended regime; recompute tip savings via the two-pass. Low effort, high user-trust payoff.

## P4 — NER corpus expansion
The last accepted-debt metric (BiLSTM 0.143 on 51 samples). Expand `nlp_research/phase_d_ner.py` templates to ≥500 samples across the 6 entity types with Hinglish families; re-measure; target ≥0.60 before claiming sequence-labeling capability.

## P5 — Corpus capture to organic eval
Enable `TAX_CORPUS_CAPTURE` on the demo deployment; grow organic turns toward the ADR-015 ≥5k trigger; convert accepted recommendations into additional labeled spans (acceptance = weak label, human-confirmable).

## P6 — Frontend intelligence surfacing
Render the advisor's full recommendation list (currently top-1 in the closing turn) in the TaxReport panel: reason/evidence/confidence per card; acceptance buttons wired to P2 capture. Frontend-only + one read endpoint.

## Explicitly out of scope for Sprint 5
- Any model in the tax computation path (ADR-001).
- External LLM APIs in the request path (ADR-003; the LLM integration plan remains opt-in/polisher only).
- NER production deployment (remains research until P4 clears a real bar).

## Suggested sequencing
P0 → P1 (data-first, gates decide) → P2+P3 (quick wins) → P4/P5 (research growth) → P6 (UX last, once the data loop exists).

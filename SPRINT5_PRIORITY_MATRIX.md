# SPRINT5_PRIORITY_MATRIX.md — Phase 2
**Generated:** 2026-11-04 · **Method:** every carried item scored on User Value (UV), Engineering Value (EV), Academic Value (AV), Risk, Effort (S/M/L) — scores 1-5, evidence-cited

---

## The matrix

| Item | UV | EV | AV | Risk | Effort | Weighted | Verdict |
|---|---|---|---|---|---|---|---|
| **P0.1 normalization fixes** (u80g, 80d_parents probe, 80U/80DDB legs) | 3 | 5 | 4 | Low | S | **4.2** | ✅ DO FIRST — unblocks verifiable labels; measured mismatches (1,564 rows) |
| **P3 regime-gate the legacy NPS tip** | 5 | 4 | 3 | Low | S | **4.4** | ✅ DO FIRST — measured ₹15,600 false tip on new-regime users; trust fix |
| **P2 acceptance tracking** | 4 | 5 | 5 | Low-Med | M | **4.4** | ✅ DO — creates the only missing training/eval signal; cheap event capture |
| **P0 continuous-value sampler** | 4 | 5 | 5 | Medium | M | **4.3** | ✅ DO — the binding constraint (≥5,000 positives); proven strata pattern generalizes |
| **P1 TSK promotion attempt** (gates on P0 data) | 3 | 4 | 5 | Medium | M | **3.6** | ⏳ CONDITIONAL — attempt only after P0; deploy on gates, else document |
| **P5 organic corpus capture** | 3 | 4 | 5 | Low | S | **3.8** | ✅ ENABLE (background, opt-in) — feeds the ADR-015 trigger |
| **P4 NER expansion** | 2 | 3 | 5 | Medium | M-L | **3.2** | ⏳ DEFER to mid-sprint or Sprint 6 — research track, no user path yet |
| **P6 frontend intelligence cards** | 4 | 3 | 3 | Low | M | **3.6** | ⏳ AFTER P2 — cards need acceptance wiring to matter |
| Personalization (profile-aware confidence) | 2 | 3 | 3 | Medium | L | **2.6** | ❌ REJECT for Sprint 5 — no data yet (needs P2 history); revisit Sprint 6 |
| Behavioral intelligence | 2 | 2 | 4 | High | L | **2.4** | ❌ REJECT — unjustified without acceptance data (this run's evidence standard) |
| Multi-worker deployment design | 2 | 3 | 1 | Medium | L | **2.4** | ❌ REJECT — single-worker is the documented deployment |

## The recommended Sprint 5 cut

**Wave 1 (day 1-2):** P0.1 + P3 — two quick wins, immediate trust/label correctness.
**Wave 2 (day 2-6):** P0 sampler → dataset v3 (≥5,000 positives) → P1 retrain + gates (deploy on pass, else document).
**Wave 3 (day 6-9):** P2 acceptance capture + P5 organic enable + P6 cards on the captured signal.
**Deferred:** P4 NER (mid-sprint stretch goal), personalization/behavioral (Sprint 6, data-gated).

## Rejected ideas (with the evidence that rejects them)

| Idea | Why rejected |
|---|---|
| End-to-end learned tax path | ADR-001; zero error budget on tax numbers |
| Bigger TSK rule count on current data | forensics: dilution worsens with rules (AUC 1.0→0.30); data is the constraint |
| 120k-row grid extension | grid is saturated (rounds 3→4 = zero new scenarios); only continuous sampling grows it |
| Real-time streaming classification | no latency evidence of need; ADR-003 determinism preferred |
| Multi-tenant scaling redesign | single-worker is the documented deployment; no load evidence |

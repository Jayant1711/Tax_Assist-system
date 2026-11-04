# SPRINT5_READINESS_REPORT.md — Phase 4 Roadmap Validation
**Generated:** 2026-11-04 · **Reviewed:** `SPRINT5_ROADMAP.md` (incl. the P0.1 additions from the final audit) · **Basis:** this run's measured evidence

---

## Verdict: **ROADMAP VALIDATED — priorities confirmed, two amendments adopted, one re-order**

## Priority validation (against measured evidence)

| Roadmap item | Evidence it addresses | Priority verdict |
|---|---|---|
| **P0.1 normalization fixes** (u80g mismatch 1,564 rows; 80d_parents probe ₹0 in 600 probes; 80U/80DDB all-zero features) | Forensics EXP-F4/F5 + audit D5 — measured label/feature mismatches | ✅ CONFIRMED — promoted to first (quick wins before the sampler) |
| **P0 continuous-value sampler** (≥5,000 positives; grid saturated at 76,960 rows) | EXP-009: 146→1,623 positives moved G6 from 54.9→95.7% but G4/G5 remain positive-count-bound | ✅ CONFIRMED as the binding constraint (adopted amendment: target ≥5,000 positives, not raw 120k rows) |
| **P1 deploy TSK heads on gates** | RUN-003b: gates still fail on expanded data; rule heads deployed instead | ✅ CONFIRMED conditional — only after P0 + gates |
| **P2 acceptance tracking** | ADR-015 revisit trigger needs organic signal; zero capture today | ✅ CONFIRMED (cheap, unlocks the learning loop) |
| **P3 regime-gate the legacy NPS tip** | This run's CA-audit measured the tip quoting ₹15,600 old-regime arithmetic to a new-regime user | ✅ CONFIRMED — **promoted alongside P2** (user-trust, tiny effort; validated by this run's transparency work) |
| **P4 NER expansion** | RUN-005: 0.143 on 51 samples | ✅ CONFIRMED (research track, after the P0/P1 data work) |
| **P5 organic corpus → ADR-015 trigger** | capture stream empty | ✅ CONFIRMED (continuous, background) |
| **P6 frontend intelligence cards** | advisor returns top-1 only today; full list available in `recommend()` | ✅ CONFIRMED (after P2 wires acceptance) |

## Amendments adopted into the roadmap (this validation)

1. **P0.1 added** (see above) — the three normalization fixes precede the sampler so labels stay verifiable from inputs.
2. **P3 promoted** to co-first with P2 — smallest effort, direct user-trust impact, validated by the 4A transparency work.
3. **P0 target restated** as "≥5,000 positives" rather than a raw row count — density, not volume, was the measured constraint.

## Sequencing (final)

P0.1 → P3+P2 (quick wins) → P0 (sampler) → P1 (conditional TSK deployment on gates) → P4/P5 (research) → P6 (UX).

## Readiness

The roadmap is execution-ready: every item has a measured justification, an owner-shaped scope, and acceptance criteria inherited from this run's gate infrastructure (`train_anfis_v5.py` gates, `run_eval.py`, the ADR-001 recomputation suite).

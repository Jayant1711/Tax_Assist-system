# INTELLIGENCE_QUALITY_REPORT.md — Intelligence Quality (Sprint 6 Phase 6)
**Generated:** 2026-11-05 · **Basis:** the six quality gates below, each tied to code + tests + live verification · **Verdict:** the intelligence layer is honest by construction — every number engine-priced, every claim testable

---

## 1. The quality framework

Sprint 6's theme added a *feedback* dimension to intelligence quality: the
system now measures how its intelligence lands (acceptance) and what its
confidence means (calibration). The quality gates:

| # | Gate | Mechanism | Evidence |
|---|---|---|---|
| Q1 | Every rupee is engine-priced | ADR-001 two-pass; rule heads exact (P/R 1.0, MAE 0.00) | `TestADRBoundary`; EXP-013 |
| Q2 | No manufactured opportunities | zero-benefit heads render as "— no benefit", ₹0, muted | live: fully-booked 24L profile; card verdict logic |
| Q3 | Claims carry evidence | each card lists booked-vs-limit + the engine's own pricing line | card evidence bullets; `recommend()` evidence field |
| Q4 | Confidence means something | calibration instrument live (canary ECE 0.0); G7 gate blocks any learned confidence until ECE ≤ 0.05 on ≥ 30 resolved events | `CONFIDENCE_CALIBRATION_REPORT.md` |
| Q5 | The system learns what users teach | shown/accepted/rejected events persisted (ADR-017) and funneled per head | `ACCEPTANCE_ANALYTICS_V1.md`; live 3-shown/1-accepted |
| Q6 | Explanations are exact where exactness is possible | per-deduction impact via leave-one-out engine recomputation (no ML, no estimates) | `DEDUCTION_IMPACT_REPORT.md`; live ₹1,30,000 80E row |

## 2. What the feedback loop already taught us (first signals)

- The **first real acceptance** was recorded (24B top-up, engine-priced
  ₹32,500, confidence 0.85) — the loop works mechanically end-to-end.
- The live funnel is too sparse for quality *inference* (N=3 shown) — the
  honest state. The instruments (funnel, ECE, per-head split) are the
  deliverable; conclusions wait for volume.
- The `/end` capture gap and the impact sign inversion were both caught by
  live verification, not by review — the E2E discipline is itself a
  quality mechanism (both now regression-pinned).

## 3. What this phase did NOT do (and why)

- **No confidence tuning.** The 0.85 anchor stays until G7's data exists —
  tuning to N=1 would be overfitting to noise.
- **No personalization.** The strategic review defers behavioral ranking
  to Sprint 7, gated on accumulated acceptance history.
- **No TSK revival.** Three-scale falsification stands; the rule heads
  remain the deployment path (ADR-016).

## 4. Quality debts carried forward

1. `viewed`/`dismissed` actions are captured but not yet auto-fired by the
   UI (the funnel has slots; the producers come with the dashboard).
2. The cross-session (per-user lifetime) analytics view is Sprint 7 scope.
3. The impact table's 24(b) reason text still says "self-occupied" in the
   cap description even when the let-out case applied (the applied column
   is correct; the string could distinguish the two) — cosmetic, logged.

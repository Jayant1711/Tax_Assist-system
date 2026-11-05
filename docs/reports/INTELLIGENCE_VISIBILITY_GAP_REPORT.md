# INTELLIGENCE_VISIBILITY_GAP_REPORT.md — Phase 4A.5
**Generated:** 2026-11-04 · **Question:** the backend/explanations/examined data existed — why did the user never see it?

---

## What the backend KNEW (verified on the wire, pre-fix)

| Data | Where | Status before fix |
|---|---|---|
| Per-regime applied deductions (particular/section/amount) | `tax_report.old_regime.explanations` (6 items) / `new_regime.explanations` (2) | **On the wire, never rendered** |
| Per-regime taxable income + total deductions | `taxable_income`, `total_deductions` per regime | Rendered as aggregates only |
| Why 80G donations don't help the new regime | `old_regime.audit_observations[2]` | Rendered only in the Advice tab as a generic risk banner |
| 80D statutory cap (₹25k of the entered ₹50k) | visible implicitly (applied 25k) | Never called out |
| Regime choice rationale | `recommendation` + `savings` | Rendered as bare strings ("New Regime saves ₹X") without the because-clause |
| Regime-flip opportunities (e.g. 80E ₹5L → ₹1,300) | engine-priced via the two-pass probes | Surfaced only as the closing-turn 🧠 block, not in the report |
| Per-item `deduction_details` | **did not exist** | Backend fix F2 populated it from the Explanation list |
| Learned-model insights (TSK heads) | off-deployment (G4/G5 fail) | Correctly absent — no invented numbers |

## What the user SAW before the fix

Regime comparison bars, slab table, strategy tile, generic risk banner, savings tips — **numbers without the narrative**. The exact reason the booked deductions "did nothing" (Sec 115BAC disallowance in the recommended regime) existed in `audit_observations` but rendered only as an unrelated-feeling risk line, and the applied/ignored split was invisible.

## Root cause of the gap

The frontend consumed only `best` (the recommended regime) and its slab table — the per-item `explanations` of the non-recommended regime, the cross-regime applied/ignored comparison, and the because-clause tying `savings` to `115BAC` were never implemented (`TaxReport.tsx` pre-Phase-4A).

## Gap closure (this run)

| Closure | Where |
|---|---|
| Applied-per-regime rendering (both regimes) | `TaxReport.tsx` "Applied vs Ignored" panel (F1) |
| Ignored list + Sec 115BAC reason per booked head | same panel (F1) |
| Regime because-clause | panel subtitle: "the New Regime is cheaper by ₹X — your booked deductions apply in the Old regime" |
| `deduction_details` backend population | `tax_engine.py` (F2) |
| Statement double-count removal | `TaxReport.tsx` (F3) |
| 80D cap callout | panel shows applied 25,000 vs the booked 50,000 (user sees the cap effect) |

## Residual gaps (filed)

1. Per-deduction rupee impact is an estimate (top-slab rate × applied) — exact per-head re-pricing needs 9 extra engine calls per render (deferred; the two-pass advisor prices the material ones).
2. HRA/80U/80DDB/80EEA probes are not in the advisor's head list (deduction advisor coverage).
3. The legacy Quick Tip still lacks regime gating (next sprint, per `SPRINT4_RELEASE_CANDIDATE_REPORT_V2.md` §4).

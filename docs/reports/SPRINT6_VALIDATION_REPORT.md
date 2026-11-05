# SPRINT6_VALIDATION_REPORT.md — Sprint 6 Validation (Phase 7)
**Generated:** 2026-11-05 · **Scope:** full test matrix + live end-to-end verification · **Verdict: 0 REGRESSIONS — all suites green, all six phases live-verified**

---

## 1. Test matrix

| Suite | Result | Delta vs Sprint 5 close |
|---|---|---|
| Backend pytest | **1,166 passed**, 1 deselected (canary), 0 failures | +20 (Sprint 5 close: 1,146) |
| Frontend vitest | **31 passed** (4 files), 0 failures | +6 (was 25) |
| TypeScript `tsc --noEmit` | clean | — |
| Extraction gate | untouched this sprint (macro F1 1.000 stands) | — |
| Live Playwright E2E | PASS (below) | — |

New tests this sprint (all regression pins for bugs actually met):

| Pin | Catches |
|---|---|
| `TestEndOverrideCapture` | `/end` skipping shown-event capture |
| `TestCalculateIntelligenceAttach` | missing review/impact attach; non-deterministic rec_ids |
| `test_deduction_impact_reduction_is_positive_when_item_delivers` | impact sign inversion (₹-1,30,000 bug) |
| `test_deduction_impact_115bac_heads_price_zero_in_new_regime` | 115BAC zero-pricing + cross-regime counterfactual |
| `TestCanary` ×3, `TestECEProperties` ×4 (test_calibration.py) | ECE framework correctness (banker's-rounding canary trap) |
| vitest: cards render / action wire / omission / pre-FINAL gating / impact render / omission | frontend card contract |

## 2. Live end-to-end transcript (running Docker stack)

1. Login `demo@student.local` → consultation at PROFILING.
2. Profile message: salary ₹15L + 80E ₹5L + 24(b) ₹2L (let-out).
3. `/end` → phase FINAL; closing advisor text + regime-gated tip render.
4. **Intelligence cards**: 3 RECOMMEND (24B ₹32,500 / 80C ₹22,100 / 80G
   ₹1,300 — confidence 85%) with reasons, evidence bullets, buttons.
5. Click "✓ Apply this" (24B) → `POST .../recommendations/{id}/action` → 200.
6. Analytics readback: `total_shown 3, total_accepted 1, rate 0.3333`,
   per-head rows with engine savings.
7. **Impact table**: 80E ₹5,00,000 → applied ✓ → ₹1,30,000; 24B ₹2,00,000
   → applied ✓ → ₹41,600 (hand-checked against the slab bridge).
8. Negative-path live check (earlier run): fully-booked ₹24L profile →
   cards render "no benefit" honestly; 46L control pinned in pytest.
9. Control: pre-FINAL phases show the cards without action buttons
   ("Acceptance unlocks in the final report.").

Screenshots: `sprint6-intelligence-cards-live.png`,
`sprint6-deduction-impact-live.png` (repo root).

## 3. Determinism & ADR invariants re-checked

- ADR-001: every rupee in the new surfaces comes from
  `calculate_tax_advanced` recomputation (cards' `savings_engine`, impact
  rows) — no client-side or model-authored numbers.
- ADR-017: shown events persist server-side only; the frontend holds no
  acceptance state; the action endpoint double-checks ownership in SQL.
- ADR-003: the calibration instrument is deterministic (canary reproducible
  bit-for-bit; no network, no RNG beyond the seeded test).

## 4. Regression sweep

The sprint touched: `tax_intelligence.py` (rec_id), `tax_engine.py`
(impact), `main.py` (attach + endpoints), `nlp_engine.py` (shared closing
intelligence), `db.py` (analytics helper), `TaxReport.tsx` (+ impact table),
`api.ts` untouched, plus tests. The full suites above cover all of it; the
extraction/eval, composer, and governance surfaces report no deltas.

## 5. Verdict

**0 regressions.** Sprint 6's six phases are implemented, pinned, and
verified against the running system — not just against tests.

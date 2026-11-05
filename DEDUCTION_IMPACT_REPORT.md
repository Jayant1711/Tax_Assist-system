# DEDUCTION_IMPACT_REPORT.md — Per-Deduction Impact Engine (Sprint 6 Phase 5)
**Generated:** 2026-11-05 · **Basis:** `TaxEngine.deduction_impact()`, `/calculate` attach, report table, pytest pins · **Status:** LIVE — exact, engine-authoritative, no ML

---

## 1. What shipped

`TaxEngine.deduction_impact(data, tax_year)` — for every booked deduction
head, the **exact** answer to "what did this item actually do to my tax?":

```python
{"head": "80e", "entered": 500000.0, "applied_in_regime": True,
 "tax_reduction": 130000.0, "tax_reduction_other_regime": 0.0,
 "reason": "Section 80E — statutory limits apply"}
```

Method: **leave-one-out recomputation** — the engine prices the full
profile (base), then re-prices it with the single head zeroed, in BOTH
regimes. `tax_reduction` = (recommended-regime tax without the item) −
(with the item): positive means the item delivered that much tax relief.
No ML, no marginal-rate approximation — the TaxEngine is the sole
calculator (ADR-001).

The report renders this as the **"Per-Deduction Impact — Exact
(Engine-Priced)"** table (entered / applied / tax reduced / reason) at the
FINAL report, directly under the intelligence cards.

## 2. Regime-honest semantics (the bugs the live run caught)

1. **Sign inversion** — the first cut computed base − without (negative of
   the benefit): the live table showed **₹-1,30,000** for 80E's ₹1,30,000
   benefit. Fixed and pinned:
   `test_deduction_impact_reduction_is_positive_when_item_delivers`.
2. **`applied_in_regime` was a head list** — it hard-coded 24(b) as
   115BAC-disallowed, but let-out property interest IS allowed under the
   New Regime. Now derived from the recomputation itself: the item applied
   iff the recommended regime's **taxable income changed** without it.
   The cross-regime field prices the same item against the OTHER regime's
   own baseline.
3. **The 46L control holds** (pinned):
   `test_deduction_impact_115bac_heads_price_zero_in_new_regime` — a
   New-Regime-recommended profile shows 80C with ₹0 delivered, applied =
   False, reason "Not allowed under the New Regime (Sec 115BAC)…", and a
   positive `tax_reduction_other_regime` (the Old-Regime counterfactual).

## 3. Live verification (running stack)

Profile: salary ₹15,00,000 + 80E ₹5,00,000 + 24(b) ₹2,00,000 (Old Regime
recommended):

| Head | Entered | Applied | Tax reduced | Reason |
|---|---|---|---|---|
| 80E | ₹5,00,000 | ✓ | **₹1,30,000** | Sec 80E — statutory limits apply |
| 24B | ₹2,00,000 | ✓ | **₹41,600** | Sec 24(b) — capped at ₹2,00,000 (self-occupied) |

Cross-checked by hand: old-regime taxable ₹15L − ₹75k std − ₹5L 80E − ₹2L
24(b) = ₹7.25L → the two items move the taxpayer across slab boundaries;
₹1,30,000 + ₹41,600 is exactly the slab-bridged difference the engine
recomputed. Screenshot: `sprint6-deduction-impact-live.png`.

## 4. Relationship to the other intelligence surfaces

- The **Applied-vs-Ignored panel** (Sprint 4 Phase 4A) explains the regime
  split qualitatively (with a disclosed marginal-rate *estimate*).
- The **impact table** (this phase) prices each item *exactly* in the
  recommended regime — the two are consistent by construction (both read
  the same engine).
- The **intelligence cards** rank *future opportunities* (headroom top-ups);
  the impact table prices *current bookings*. Together they answer "what
  did I do" and "what should I do" from the same authoritative engine.

## 5. Tests

- `tests/test_tax_engine.py`: two new pins (positive-direction reduction +
  exact values; 115BAC zero-pricing with cross-regime counterfactual).
- `tests/test_recommendation_events.py::TestCalculateIntelligenceAttach`:
  `/calculate` at FINAL carries the impact rows.
- vitest: impact table render + omission (2 tests).
- Full suites: **1,166 pytest / 31 vitest green**.

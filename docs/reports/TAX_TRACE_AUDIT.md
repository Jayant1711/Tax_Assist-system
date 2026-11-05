# TAX_TRACE_AUDIT.md — Phase 4A.1 Full Trace (₹46L Scenario)
**Generated:** 2026-11-04 · **Scenario:** user-reported "deductions change nothing" · **Method:** every hop executed live and inspected (not inferred)

---

## The trace (message → frontend)

| # | Hop | Result | Verdict |
|---|---|---|---|
| 1 | **User messages** (6 conversational turns: "I am a software engineer earning 46 lakhs", "invested 1.5 lakhs in PPF", "health insurance 50k", "nps 50k", "paying rent 40k monthly, hra received 30k monthly, metro", "donated 50k to an NGO") | each booked on the turn | — |
| 2 | **NLP Extraction** | `SALARY: ₹4,600,000` · `80C: ₹150,000` · `80D: ₹50,000` · `NPS: ₹50,000` · `RENT PAID (ANNUALIZED): ₹480,000` · `HRA RECEIVED (ANNUALIZED): ₹360,000` · `80G: ₹50,000` | ✅ correct (monthly rent/hra annualized ×12) |
| 3 | **Session state** | salary 4,600,000 · 80c 150,000 · 80d 50,000 · nps 50,000 · rent_paid 480,000 · hra_received 360,000 · 80g 50,000 + 80g_category | ✅ correct |
| 4 | **TaxEngine input** | session passed verbatim (`main.py` L1244 serializes `tax_result` into the reply) | ✅ |
| 5 | **Old regime** | deductions **320,000** applied → taxable 42,80,000 → tax **11,40,360**. Breakdown exact: std 50,000 + 80C 150,000 + 80D **25,000 (statutory cap — user entered 50k)** + NPS 50,000 + HRA 20,000 (Rule 2A: min(hra 360k, rent−10% salary=20k, 50% salary)) + 80G 25,000 (50% of 50k) | ✅ correct incl. caps |
| 6 | **New regime** | deductions **75,000** (standard deduction only) → taxable 45,25,000 → tax **9,75,000** | ✅ correct (Sec 115BAC: 80C/80D/HRA/80G/self-NPS not allowed) |
| 7 | **Regime selection** | New Regime recommended — saves ₹1,65,360 vs old even WITH all deductions | ✅ correct |
| 8 | **API response** | `tax_report.{old_regime,new_regime}` each carrying `explanations` (old: 6 items with particular/reason/section/amount/status; new: 2), `audit_observations`, `slabs_breakdown`, `taxable_income`, `total_deductions`, `total_tax` | ✅ rich payload already on the wire |
| 9 | **Frontend rendering** | TaxReport renders regime comparison, slab table, strategy — but does **not** render the per-regime `explanations` (applied list) or any "your booked deductions are ignored by the New Regime (Sec 115BAC)" message | ❌ **THE GAP** |

## Root-cause determination for the user report

| Hypothesis | Finding |
|---|---|
| 1. Frontend reporting problem | **PARTIAL — confirmed**: explanation/applied-vs-ignored data is on the wire but not rendered |
| 2. TaxEngine issue | **RULED OUT** — matrix A–G: every deduction applied with statutory caps, arithmetic exact (80C 46,800 + 80D 7,800 (25k cap) + NPS 15,600 + HRA 6,240 + 80G 7,800 = 84,240 total old-regime reduction ✓) |
| 3. Regime-selection issue | **RULED OUT — expected logic**: New Regime saves ₹1,65,360 even with all deductions; recommendation correct |
| 4. Deduction-application issue | **RULED OUT** — 320,000 applied in old regime, item-exact |
| 5. Response Composer explanation issue | **PARTIAL** — the closing/composer text never states the regime-vs-deductions relationship |
| 6. Combination | **FINAL: Regime Logic Expected + User Explanation Gap (frontend render + composer narrative)** |

## Additional finding (backend, minor)

`deduction_details` per regime serializes as an empty list — the per-item breakdown exists only inside `explanations` (old regime). A backend nicety: populate `deduction_details` with {particular, booked, applied, status} so the frontend can render applied-vs-ignored without deriving it. Filed as fix F2.

## The one legitimate user surprise (not a bug)

Entering 80D ₹50,000 yields only ₹7,800 old-regime tax reduction — because Section 80D caps self/family at ₹25,000 for non-seniors. The engine caps correctly; the UI must say so ("₹25,000 of your ₹50,000 is deductible — the Section 80D cap").

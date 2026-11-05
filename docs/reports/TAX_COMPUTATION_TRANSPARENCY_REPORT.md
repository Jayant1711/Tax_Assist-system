# TAX_COMPUTATION_TRANSPARENCY_REPORT.md — Phase 4A.7 Live Validation
**Generated:** 2026-11-04 · **Method:** the user's exact ₹46L scenario executed through the LIVE stack (rebuilt frontend + backend) via Playwright, then DOM-verified against the Phase-4A.2 TaxEngine matrix

---

## 1. Live run (real UI, real backend)

| Turn | Message | Engine result |
|---|---|---|
| 1 | "I am a software engineer earning 46 lakhs" | SALARY: ₹46,00,000 booked |
| 2 | "1.5 lakhs in PPF, 50k health insurance, 50k nps, rent 40k monthly hra 30k monthly metro, donated 50k to NGO" | 80C 150k · 80D 50k · NPS 50k · RENT PAID (ANNUALIZED) 480k · HRA RECEIVED (ANNUALIZED) 360k · 80G 50k booked |
| 3 | "/end" | Override → report generated |

## 2. DOM verification (measured from the rendered page)

| Check | Result |
|---|---|
| "Your Deductions — Applied vs Ignored" panel renders | ✅ true |
| New-Regime ignored rows with the Sec 115BAC reason | ✅ true ("not allowed under Sec 115BAC") |
| Old-Regime applied list ("deductions apply") | ✅ true |
| Net Taxable Income shown (New Regime) | ✅ **₹45,25,000** — matches the Phase-4A.2 matrix exactly |
| Recommended regime | ✅ New Regime |
| Double-counted std-deduction row (the qa-found bug) | ✅ removed — statement now reconciles to the engine's taxable income |

## 3. The trace (unchanged, backend exonerated)

Extraction ✓ → session ✓ → engine input ✓ → old regime applies **₹3,20,000** deductions (item-exact incl. the 80D ₹25k cap and Rule-2A HRA ₹20k) → new regime applies **₹75,000** (std only, Sec 115BAC) → new recommended (₹9,75,000 vs ₹11,40,360) → wire payload carries per-regime `explanations` + `audit_observations` → **frontend now renders them**.

## 4. Fixes applied (exact files)

| Fix | File(s) | What |
|---|---|---|
| F1 | `frontend/src/components/TaxReport.tsx` | **"Your Deductions — Applied vs Ignored"** card: per-regime applied lists (with per-item estimated saving at the top old-regime slab rate), ignored rows with the Sec 115BAC reason, regime-context line ("the New Regime is cheaper by ₹X — your deductions apply in the Old regime") |
| F2 | `backend/tax_engine.py` | `deduction_details` populated per regime from the authoritative per-item Explanation list (was always empty) |
| F3 | `frontend/src/components/TaxReport.tsx` | removed the hardcoded client-side ₹75,000 std-deduction row — it double-counted the payload's own 16(ia) row and made the printed statement not reconcile |
| F4 | `backend/nlp_engine.py` (earlier this sprint) | msg_ctx amplification caps for every note/ask-back class (security-review findings 1-3) |

## 5. Final verdict

| Hypothesis | Verdict |
|---|---|
| Backend bug | ❌ Ruled out — matrix A-G arithmetic exact incl. caps |
| Frontend bug | ✅ **Confirmed and fixed** — applied/ignored/why never rendered |
| Regime-selection issue | ❌ Expected logic — New Regime correctly recommended (Sec 115BAC ignores the booked deductions) |
| User explanation gap | ✅ **Confirmed and fixed** — the report now answers why the tax is what it is, which deductions applied, which were ignored and why, and why the regime was chosen |

**One-line summary:** the TaxEngine was right all along; the product now shows its work.

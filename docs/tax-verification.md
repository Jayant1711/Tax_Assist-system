# Tax Constants Verification Record — FY 2025-26 (AY 2026-27)

> **Purpose:** satisfies AI_RULES "Always verify tax constants — no constants from memory" for Sprint 2 (Objective A).
> Every constant below was verified against authoritative/secondary-authoritative sources on **2026-10-31** via live web search, immediately before implementation on branch `sprint-2-tax-year`.
> Status key: ✅ verified · ⚠ partially verified (mechanics verified, exact statutory wording to re-check at merge)
> **Amended per tax-expert review 2026-10-31** — six corrections applied to the record below; each is marked *(amended per tax-expert review 2026-10-31)* inline.

## 1. New Regime slabs (Sec 115BAC(1A), Finance Act 2025) — ✅

| Taxable income | Rate |
|---|---|
| ₹0 – 4,00,000 | Nil |
| ₹4,00,001 – 8,00,000 | 5% |
| ₹8,00,001 – 12,00,000 | 10% |
| ₹12,00,001 – 16,00,000 | 15% |
| ₹16,00,001 – 20,00,000 | 20% |
| ₹20,00,001 – 24,00,000 | 25% |
| Above ₹24,00,000 | 30% |

Sources: incometax.gov.in; ClearTax; multiple concordant references (Finance Act 2025, effective 1-Apr-2025).

## 2. Section 87A rebate — ✅

- **New regime:** rebate up to **₹60,000** → zero tax for total income ≤ **₹12,00,000**.
- **Marginal relief (new regime)** *(amended per tax-expert review 2026-10-31 — the original slab-only formula `tax = min(slab_tax, income − 12,00,000)` understated the cap)*: for total income above ₹12,00,000, the **PAYABLE TOTAL** — income-tax after rebate + special-rate (111A/112A) tax + surcharge — is capped at **(income − ₹12,00,000)**, and **cess is applied AFTER the cap** (post-cess cap, per the FA-2025 Explanation to Sec 87A: tax payable for this purpose includes surcharge and cess). The band endpoint therefore **emerges** from `min(payable × 1.04, income − 12,00,000)` and is **derived, not stored**: **₹12,73,934** total income (FY 2025-26) and **₹7,23,214** (FY 2024-25 at the ₹7,00,000 threshold).
- **Eligibility basis** *(amended per tax-expert review 2026-10-31 — missing constant made explicit)*: eligibility is keyed on **TOTAL income including special-rate capital gains**, not the slab taxable alone; when eligible, the rebate applies to the **normal-rate tax only**.
- **Old regime:** unchanged — rebate ₹12,500 for total income ≤ ₹5,00,000 (no relief band).
- **Special-rate income:** 87A rebate is **NOT available** against 112A LTCG (**statutory**) or 111A STCG (**conservative practice — ⚠ re-verify ITR-utility behavior at merge**) *(amended per tax-expert review 2026-10-31)*.
- **Residency caveat** *(amended per tax-expert review 2026-10-31 — missing caveat)*: Sec 87A is available to **resident individuals only** (NRIs are excluded). The tool computes as resident — advisory, not an eligibility check.

## 3. Standard deduction & cess — ✅

- New regime: **₹75,000** (unchanged from FY 2024-25). Old regime: **₹50,000** (unchanged).
- **Cess: 4% Health & Education Cess**, applied multiplicatively AFTER surcharge — and OUTSIDE the 87A-band and surcharge-relief comparisons *(amended per tax-expert review 2026-10-31 — missing constant made explicit)*.

## 4. Surcharge — ✅ (⚠ mechanics)

- Thresholds/rates unchanged: 10% (>₹50L), 15% (>₹1Cr), 25% (>₹2Cr), 37% (>₹5Cr, old regime only).
- **New regime capped at 25%** for all income levels.
- **s.115BAC(6) special-rate cap: 15%** *(amended per tax-expert review 2026-10-31 — missing constant made explicit)*: in the new regime, the surcharge on the 111A/112A portion of tax is capped at 15% (`S = rate × T_normal + min(rate, 0.15) × T_special`); the old regime is uncapped.
- **Marginal relief at every threshold** *(amended per tax-expert review 2026-10-31 — mechanics corrected)*: surcharge payable = `min(S_band(x), max(0, T_r1(h_top) + (x − h_top) − T(x)))`, where **T_r1(h_top) carries the band rate CONTAINING h_top** (50L→0%, 1Cr→10%, 2Cr→15%, 5Cr→25% — at exactly h the LOWER band's rate applies, so there is **no relief at x = h**), and **cess is applied AFTER, OUTSIDE the comparison**. Relief applies only for x > h. ⚠ Exact statutory proviso wording to be quoted in the PR.

## 5. Capital gains — ✅

- **112A LTCG (listed equity/equity MF):** **12.5%** on gains above **₹1,25,000 aggregate per year** (unchanged for FY 2025-26; regime since 23-Jul-2024).
- **111A STCG (listed equity):** **20%** (unchanged).
- **Other assets (property etc.):** 12.5% without indexation as the default post-23-Jul-2024 route **in both regimes**; 20%-with-indexation exists only as the transitional election for resident individuals/HUF for acquisitions before 23-Jul-2024. Transfer-date matters; regime does not.
- **87A rebate excludes special-rate CG income** (verified — see §2 eligibility basis).

## 6. Deduction sections — ✅

| Section | Verified rule (old regime only) |
|---|---|
| 80U / 80DD | **Flat ₹75,000** (disability 40–79%) or **flat ₹1,25,000** (≥80%). Actual expenditure irrelevant. Input should be the *category*, not an amount. |
| 80DDB | *(amended per tax-expert review 2026-10-31)* **min(expenditure, tier-cap)** — ₹40,000 where the **PATIENT** is below 60, ₹1,00,000 where the patient is a senior citizen: the **patient's** age (not the assessee's) decides the tier; the tool defaults to the self's age and emits an advisory when the patient differs. Specialist prescription from a prescribed specialist required (nuance per Budget 2019: the prescription/audit requirements were relaxed that year, but the specialist requirement itself stands). |
| 80EEA | **DISCONTINUED** — only loans sanctioned 1-Apr-2019 → 31-Mar-2022 qualified. Not available in FY 2024-25 or FY 2025-26. → **REMOVE from collection + engine.** |
| 80G | Four categories: (1) 100% no limit — PM National Relief Fund, PM CARES, National Defence Fund etc.; (2) 50% no limit — approved charitable trusts/hospitals etc.; (3) 100% subject to qualifying limit — Government/local authority family planning & charitable donations; (4) 50% subject to qualifying limit — any other approved charitable/religious institution. **Qualifying limit = 10% of adjusted gross total income.** Cash donations deductible only up to ₹2,000. **New regime: most 80G donations not deductible** (PM CARES etc. remain). |
| 80C / 80D / 80TTA / 80TTB / 80E / 80GG / 24(b) | Unchanged from FY 2024-25 (80C ₹1.5L; 80D ₹25k/₹50k self + ₹50k parents subject to parent seniority; 80TTA ₹10k; 80TTB ₹50k seniors; 80E uncapped; 24(b) ₹2L). |
| Professional tax | State levy; no national change. *(amended per tax-expert review 2026-10-31)* The engine's FY 2025-26 default is **0** (no invented figure) with the advisory: **"enter your actual figure — commonly ₹200/month, capped ₹2,500/yr, some states none"**. FY 2024-25 keeps its 2,500 default + the same advisory. |

## 7. Old Regime structure — ✅

Unchanged for FY 2025-26: basic exemption ₹2.5L / ₹3L (60+) / ₹5L (80+); slabs 5% (to ₹5L), 20% (to ₹10L), 30% above; all Chapter VI-A deductions as above. *(amended per tax-expert review 2026-10-31)* FY 2025-26 old regime = **identical to FY 2024-25 EXCEPT professional_tax_default 0** (see the professional-tax row above; a state levy with no national rate).

## 8. HRA (Sec 10(13A) + Rule 2A) — ✅ (statutory method, unchanged)

Exemption = **least of**: (a) actual HRA received; (b) rent paid − 10% of salary; (c) 50% of salary (metro: Delhi, Mumbai, Kolkata, Chennai) or 40% (non-metro). Requires **three separate inputs** (HRA received, rent paid, metro status) — none derivable from the others.

## Sources

- Income Tax Department — incometax.gov.in (slabs, 87A, standard deduction)
- Income Tax India — [Tax on Long-Term Capital Gains](https://www.incometaxindia.gov.in/w/tax-on-long-term-capital-gains%E2%80%8B) (112A/111A, ₹1.25L aggregate, rebate exclusion)
- ClearTax / CA Club India — [Marginal Relief FY 2025-26](https://www.caclubindia.com/articles/marginal-relief-in-income-tax-for-fy-2025-26-55502.asp) (₹12L–₹12.75L band, FA-2025 Explanation incl. surcharge+cess)
- ClearTax / tax2win / incometaxindia.gov.in — 80G categories & qualifying limit; 80U/80DD/80DDB fixed amounts; 80EEA sunset (31-Mar-2022)
- DBS Bank India — [LTCG rules](https://www.dbs.bank.in/in/treasures/articles/learning-centre/long-term-capital-gains-tax-ltcg)

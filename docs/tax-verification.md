# Tax Constants Verification Record — FY 2025-26 (AY 2026-27)

> **Purpose:** satisfies AI_RULES "Always verify tax constants — no constants from memory" for Sprint 2 (Objective A).
> Every constant below was verified against authoritative/secondary-authoritative sources on **2026-10-31** via live web search, immediately before implementation on branch `sprint-2-tax-year`.
> Status key: ✅ verified · ⚠ partially verified (mechanics verified, exact statutory wording to re-check at merge)

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
- **Marginal relief (new regime):** for income in **(₹12,00,000, ~₹12,75,000]**, tax payable is capped at **(income − ₹12,00,000)**; relief phases out at ₹12,75,000 where slab tax exceeds the excess. Formula: `tax = min(slab_tax, income − 12,00,000)`. ⚠ Mechanism verified via CA Club India / ClearTax worked examples; the Finance Act 2025 Explanation confirms tax payable for this purpose **includes surcharge and cess**.
- **Old regime:** unchanged — rebate ₹12,500 for total income ≤ ₹5,00,000.
- **Special-rate income:** 87A rebate is **NOT available** against 112A LTCG or 111A STCG (verified).

## 3. Standard deduction — ✅

- New regime: **₹75,000** (unchanged from FY 2024-25). Old regime: **₹50,000** (unchanged).

## 4. Surcharge — ✅ (⚠ mechanics)

- Thresholds/rates unchanged: 10% (>₹50L), 15% (>₹1Cr), 25% (>₹2Cr), 37% (>₹5Cr, old regime only).
- **New regime capped at 25%** for all income levels.
- **Marginal relief at every threshold:** surcharge payable is capped so that the incremental total tax (incl. surcharge and cess per the FA-2025 Explanation to Sec 2) does not exceed the income excess over the threshold — i.e. compare total tax at income `x` with total tax at the threshold, per the threshold-comparison method. ⚠ Exact statutory proviso wording to be quoted in the PR.

## 5. Capital gains — ✅

- **112A LTCG (listed equity/equity MF):** **12.5%** on gains above **₹1,25,000 aggregate per year** (unchanged for FY 2025-26; regime since 23-Jul-2024).
- **111A STCG (listed equity):** **20%** (unchanged).
- **Other assets (property etc.):** 12.5% without indexation as the default post-23-Jul-2024 route; 20%-with-indexation exists only as the transitional election for resident individuals/HUF for acquisitions before 23-Jul-2024. Transfer-date matters; regime does not.
- **87A rebate excludes special-rate CG income** (verified).

## 6. Deduction sections — ✅

| Section | Verified rule (old regime only) |
|---|---|
| 80U / 80DD | **Flat ₹75,000** (disability 40–79%) or **flat ₹1,25,000** (≥80%). Actual expenditure irrelevant. Input should be the *category*, not an amount. |
| 80DDB | **Flat ₹40,000** (age < 60) or **₹1,00,000** (senior). Specialist prescription required. |
| 80EEA | **DISCONTINUED** — only loans sanctioned 1-Apr-2019 → 31-Mar-2022 qualified. Not available in FY 2024-25 or FY 2025-26. → **REMOVE from collection + engine.** |
| 80G | Four categories: (1) 100% no limit — PM National Relief Fund, PM CARES, National Defence Fund etc.; (2) 50% no limit — approved charitable trusts/hospitals etc.; (3) 100% subject to qualifying limit — Government/local authority family planning & charitable donations; (4) 50% subject to qualifying limit — any other approved charitable/religious institution. **Qualifying limit = 10% of adjusted gross total income.** Cash donations deductible only up to ₹2,000. **New regime: most 80G donations not deductible** (PM CARES etc. remain). |
| 80C / 80D / 80TTA / 80TTB / 80E / 80GG / 24(b) | Unchanged from FY 2024-25 (80C ₹1.5L; 80D ₹25k/₹50k self + ₹50k parents subject to parent seniority; 80TTA ₹10k; 80TTB ₹50k seniors; 80E uncapped; 24(b) ₹2L). |
| Professional tax | State levy; no national change. Default assumption of ₹2,500/yr is an *assumption*, not statute. |

## 7. Old Regime structure — ✅

Unchanged for FY 2025-26: basic exemption ₹2.5L / ₹3L (60+) / ₹5L (80+); slabs 5% (to ₹5L), 20% (to ₹10L), 30% above; all Chapter VI-A deductions as above.

## 8. HRA (Sec 10(13A) + Rule 2A) — ✅ (statutory method, unchanged)

Exemption = **least of**: (a) actual HRA received; (b) rent paid − 10% of salary; (c) 50% of salary (metro: Delhi, Mumbai, Kolkata, Chennai) or 40% (non-metro). Requires **three separate inputs** (HRA received, rent paid, metro status) — none derivable from the others.

## Sources

- Income Tax Department — incometax.gov.in (slabs, 87A, standard deduction)
- Income Tax India — [Tax on Long-Term Capital Gains](https://www.incometaxindia.gov.in/w/tax-on-long-term-capital-gains%E2%80%8B) (112A/111A, ₹1.25L aggregate, rebate exclusion)
- ClearTax / CA Club India — [Marginal Relief FY 2025-26](https://www.caclubindia.com/articles/marginal-relief-in-income-tax-for-fy-2025-26-55502.asp) (₹12L–₹12.75L band, FA-2025 Explanation incl. surcharge+cess)
- ClearTax / tax2win / incometaxindia.gov.in — 80G categories & qualifying limit; 80U/80DD/80DDB fixed amounts; 80EEA sunset (31-Mar-2022)
- DBS Bank India — [LTCG rules](https://www.dbs.bank.in/in/treasures/articles/learning-centre/long-term-capital-gains-tax-ltcg)

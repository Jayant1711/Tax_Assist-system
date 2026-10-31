# Tax Rules Reference — as implemented (FY 2024-25 / AY 2025-26)

> ⚠ **Scope warning:** this file documents what is *coded* in `backend/tax_engine.py` today. Since Sprint 2 Step A3 (October 2026) the per-year constants live in the versioned registry `backend/tax_rules/` (ADR-008) — see [§5](#5-fy-2025-26-ay-2026-27-gap) and [§6](#6-rule-change-checklist-where-fy-constants-live) — and the engine serves **both** FY 2024-25 (explicit pin / parity fixture) and FY 2025-26 (the registry default) through the same algorithms.
> Rules were transcribed from the codebase (path:line evidence), not assumed. Verify each figure against the Income Tax Act / relevant Finance Act before relying on it for an actual filing.

## 1. New Regime (Section 115BAC)

Slab computation: `_slab_new` (`backend/tax_engine.py:348-368`).

| Taxable income band | Rate |
|---|---|
| ₹0 – 3,00,000 | 0% |
| ₹3,00,001 – 7,00,000 | 5% |
| ₹7,00,001 – 10,00,000 | 10% |
| ₹10,00,001 – 12,00,000 | 15% |
| ₹12,00,001 – 15,00,000 | 20% |
| Above ₹15,00,000 | 30% |

- **Standard deduction:** ₹75,000 when `salary > 0` (`tax_engine.py:237`), else ₹0.
- **Other deductions:** none — no Chapter VI-A; house-property gets only the 30% standard deduction under 24(a) (`tax_engine.py:240`).
- **Section 87A rebate:** full rebate while TOTAL income (incl. special-rate CG) ≤ ₹7,00,000; above it the POST-CESS band cap applies — the payable total (incl. surcharge and cess) is capped at `TOTAL income − 7,00,000`, so the band endpoint is **derived** at 7,23,214 incl-cess (Step A2 retired the stored pre-cess 7,27,777 bound; constants in `tax_rules/fy_2024_25.py` `rebate["new"]`, mechanics in `_calc_new`).
- Senior-citizen age parameters are accepted but unused (new-regime slabs are age-independent).

## 2. Old Regime

Slab computation: `_slab_old` (`backend/tax_engine.py:323-346`).

| Taxable income band | Rate |
|---|---|
| ₹0 – basic exemption | 0% |
| Basic exemption – ₹5,00,000 | 5% |
| ₹5,00,001 – ₹10,00,000 | 20% |
| Above ₹10,00,000 | 30% |

- **Basic exemption:** ₹2,50,000; ₹3,00,000 (age ≥ 60); ₹5,00,000 (age ≥ 80) (`tax_engine.py:327`).
- **Standard deduction:** ₹50,000 when `salary > 0` (`tax_engine.py:146`).
- **Professional tax:** input, **defaults to ₹2,500** whenever salary > 0 (`tax_engine.py:87`) — many states levy ₹2,400/yr or less; the default flatters old-regime savings.
- **Section 87A rebate:** `min(tax, ₹12,500)` if taxable ≤ ₹5,00,000 (`tax_engine.py:183`).

### Deduction caps as coded (`tax_engine.py:70-86`)

| Input key | Section | Cap applied |
|---|---|---|
| `80c` | 80C | ₹1,50,000 |
| `80d` | 80D (self/family) | ₹25,000 (₹50,000 if 60+) |
| `80d_parents` | 80D (parents) | ₹50,000 |
| `nps` | 80CCD(1B) | ₹50,000 |
| `24b` | 24(b) home-loan interest | ₹2,00,000 |
| `80eea` | 80EEA | ₹1,50,000 — **parsed but never deducted** (see §4) |
| `80tta` | 80TTA | ₹10,000 (0 if senior) |
| `80ttb` | 80TTB | ₹50,000 (seniors only) |
| `80e`, `80g` | 80E / 80G | **No cap and no 80G qualification-rate logic** as coded |
| `80u_80dd`, `80ddb` | 80U / 80DD / 80DDB | **Parsed but never deducted** (see §4) |

- **HRA** (`_calc_hra`, `tax_engine.py:316-321`): `min(40% × salary, HRA input, HRA input − 10% × salary)`. No metro 50% option; the input conflates HRA-received with rent-paid.
- **80GG** (`_calc_80gg`, `tax_engine.py:310-314`): least of ₹60,000 / 25% of income / rent − 10% of income; zero if any HRA claimed. Correctly excluded from new regime.
- **Rental income:** 30% standard deduction under 24(a) in both regimes (`tax_engine.py:150,240`).

## 3. Capital gains, surcharge, cess

### Capital gains (`_calc_cg`, `tax_engine.py:294-308`)

| Type key | Treatment as coded |
|---|---|
| `equity_ltcg` | 12.5% on amount **above ₹1.25L exemption, applied per entry** (`:302`) — the statutory exemption is per assessee, so multiple entries understate tax |
| `equity_stcg` | flat 20% (`:305`) |
| `property_cg` | flat 20% (old) / 12.5% (new) (`:307`) — indexation is **not modeled**; the input amount is treated as post-indexation gain |

FY 2024-25 grandfathering (pre-23-Jul-2024 transactions at 10%/15%) is not modeled. Gains are taxed at flat rates and added to slab tax before surcharge; the 87A rebate is computed on slab tax only, which matches the post-2024 rule that rebate does not cover 112A LTCG.

### Surcharge (`_apply_marginal_relief`, `tax_engine.py:283-292`)

| Total income | Rate |
|---|---|
| > ₹50L – ₹1Cr | 10% |
| > ₹1Cr – ₹2Cr | 15% |
| > ₹2Cr | 25% if new regime, else… |
| > ₹5Cr (old only) | 37% |

"Marginal relief" as originally coded = `min(surcharge, income − 50,00,000)` — an **approximation**, wrong near ₹50L and for capital-gains-heavy incomes. **RESOLVED in Sprint 2 Step A2 (2026-10-31):** `_apply_marginal_relief` now implements the statutory band-based threshold comparison at ALL FOUR thresholds — `S_payable = min(S_band(x), max(0, T_r1(h_top) + (x − h_top) − T(x)))`, with T_r1(h_top) at the band rate CONTAINING h_top and cess applied after, outside the comparison (see `tax_engine.py`; constants in `tax_rules/fy_2024_25.py` `surcharge`).

### Cess
4% Health & Education Cess applied multiplicatively in both regimes (`tax_engine.py:187,262`).

## 4. Known deviations from statute (audit findings)

| ID | Deviation | Evidence | Severity |
|---|---|---|---|
| C2 | **Agricultural income added to old-regime gross income** (taxed) while labelled "Exempt" in the same output; new regime excludes it → regime comparison biased. Partial integration (10(1) rules) not implemented. | `tax_engine.py:152` vs `:241`, `:202-203` | Critical |
| C3 | **Monthly amounts double-annualized in the chat flow** (parser ×12 for "per month", then NLP ×12 again) | `nlp_engine.py:181-184` + parser unit map | Critical |
| C4 | **NLP misclassification** in real usage: education-loan interest → income; tuition fees → salary; property sale → other income; PPF → 80D | `backend/logs/session_audit.json` (2026-04-22/23 entries) | Critical |
| H1 | LTCG ₹1.25L exemption applied **per entry**, not per assessee | `tax_engine.py:300-302` | High |
| H2 | HRA formula: no metro 50% leg; rent/HRA conflation | `tax_engine.py:316-321` | High |
| H3 | ~~Surcharge marginal relief is an approximation~~ **RESOLVED (Step A2, 2026-10-31)** — statutory band-based threshold comparison implemented | `_apply_marginal_relief` in `tax_engine.py` | High → closed |
| H4 | 80EEA / 80U / 80DD / 80DDB collected but silently excluded from the deduction total | `tax_engine.py:78,83,84` vs `:159-172` | High |
| M1 | Professional-tax default ₹2,500 assumed at maximum | `tax_engine.py:87` | Medium |
| M2 | No grandfathering for pre-23-Jul-2024 equity transactions | `tax_engine.py:294-308` | Medium |

## 5. FY 2025-26 (AY 2026-27) gap

✅ **RESOLVED (Sprint 2 Step A3, 2026-10-31):** FY 2025-26 is implemented via the rules registry — `backend/tax_rules/fy_2025_26.py`, transcribed 1:1 from the frozen record [tax-verification.md](tax-verification.md) plus the six tax-expert corrections of that date, import-validated by `tax_rules.validate_rules`. The registry **default is now `fy_2025_26`** (ADR-008); `fy_2024_25` stays registered for the pinned legacy callers and the parity fixture (`tests/fixtures/parity_fy2425.json`). New regime per Finance Act 2025: basic exemption ₹4,00,000, slab edges every ₹4L up to ₹24L, 87A rebate ₹60,000 (zero tax up to ₹12,00,000 TOTAL income; post-cess band above, endpoint derived at ₹12,73,934); standard deduction stays ₹75,000; old regime unchanged except the professional-tax default (0 + advisory). Verified cell-by-cell by `backend/tests/test_fy2025_26_matrix.py`.

## 6. Rule-change checklist (where FY constants live)

When adding or changing a tax year, every location below must change together. Since Step A3 the constants have a **single source**:

1. `backend/tax_rules/` — **single source of truth (ADR-008)**: `schema.py` (validated dataclasses) plus one module per year (`fy_2024_25.py`, `fy_2025_26.py`); `DEFAULT_TAX_YEAR` in `__init__.py`. Every slab, deduction cap, rebate, surcharge, CG rate, cess and professional-tax constant is transcribed here (from `docs/tax-verification.md`) and import-validated.
2. `backend/tax_engine.py` — the generalized algorithms only (slab walk, 87A, surcharge relief, CG booking); **no per-year constants**. A new year must run through them unforked.
3. `backend/anfis_trainer.py` — its own copies of slab/HRA/surcharge math used as training ground truth (currently divergent).
4. `backend/test_suite.py` — Block 5 ground-truth expectations (pinned to `fy_2024_25` since Step A3; `backend/tests/` is the authoritative suite, ADR-011).
5. Frontend copy: `frontend/src/app/page.tsx` (sidebar "Quick Rules"), `frontend/src/components/TaxReport.tsx` (AY strings — now rendered from the response's `fy_label`), `frontend/src/app/layout.tsx` (metadata), `frontend/src/components/ChatInterface.tsx` (welcome message).
6. `README.md` badge + this file.

This scattered-constants problem is tracked as design debt in [architecture.md §5](architecture.md#5-known-architectural-weaknesses-audit-2026-10-31) and resolved by ADR-008.

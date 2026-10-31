# Sprint 2 Design — Consolidated (planning review 2026-10-31)

> Sources: 4-agent planning review (@architect registry design, @tax-expert rulings, @security-auditor constraints, @qa-lead test matrix) + docs/tax-verification.md (verified constants, amended per expert). This file is the implementation spec for Steps C, B, D, D2/G, F. Steps A1-A3 are landed.

## State
- Landed: `1036ed8` (A1 registry+parity), `07ff4d8` (A2/E surcharge+87A), `f72cf57` (A3 FY 2025-26 + default flip). 542 pytest green, legacy 97/97 pinned to fy_2024_25.
- Engine: `calculate_tax_advanced(data, tax_year="fy_2025_26")`; registry `backend/tax_rules/` (`get_rules`, `DEFAULT_TAX_YEAR`, `UnknownTaxYearError`); responses carry `tax_year`/`assessment_year`/`fy_label`.
- Default FY 2025-26: property 12.5% both regimes (via data); 87A post-cess band (TI-keyed); surcharge relief at 50L/1Cr/2Cr/5Cr (new: CG portion capped 15%).

## Expert rulings (binding; re-verify ⚠ items at compliance review)
- R-a: 87A band caps the POST-CESS total at (TI − threshold); endpoints derived (FY24-25 ₹7,23,214 / FY25-26 ₹12,73,934) — QA expectations only, never stored.
- R-c: 87A eligibility keyed on TOTAL income incl. special-rate CG; rebate applies to normal-rate tax only; 111A exclusion is conservative practice (⚠ ITR-utility check at merge). In-band literal cap covers special-rate tax too (⚠ merge-gate verify).
- R-d: Surcharge relief for x > h_top: `S_payable = min(S_band(x)·T_taxable(x), max(0, T_r1(h_top) + (x−h_top) − T_taxable(x)))`, T_r1(h_top) uses the band rate CONTAINING h_top (50L→0%, 1Cr→10%, 2Cr→15%, 5Cr→25%); cess OUTSIDE the comparison. Landed in A2.
- R-e: Property CG — default 12.5% both regimes post-23-Jul-2024 + prominent election advisory (20%-with-indexation NOT built; needs cost input). Holding-period assumption: treat property_cg as LTCG, state assumption + advisory.
- R-f: 112A ₹1.25L aggregate per year; STCG no share; fix per-entry application.
- R-g: 80G = one amount + category (4 options: 100-no-limit / 50-no-limit / 100-qualified / 50-qualified) + qualifying limit 10% of adjusted GTI = GTI(before Ch VI-A) − 112A LTCG − 112 LTCG (incl. property) − 111A STCG; cash cap ₹2,000 (needs a mode flag — if not collectible, advisory); default when category unknown = category 4 + advisory; new regime: generic 80G not deductible (advisory), PM-CARES-class stays.
- R-h: 80DDB = min(expenditure, tier) with tier by PATIENT age (tool: self age + advisory); prescription nuance per Budget 2019.
- R-i: 80D parents cap ₹50k gated on parent seniority → implement ₹25k parents default + advisory (parents_senior input optional this sprint).
- R-j: professional tax default: FY 2024-25 ₹2,500 (parity), FY 2025-26 ₹0 + advisory (landed A3).
- New-regime CG surcharge cap 15% (landed A2). Residency: 87A is resident-only — tool computes as resident; advisory (R10).
- Rounding: statutory outputs ROUND_HALF_UP to the rupee where fractional; encode in test expectations (landed cells already assert to the paisa).

## Step C — Capital gains (engine + API + tests)
1. `_calc_cg`: aggregate 112A entries → exemption ₹1.25L ONCE → 12.5% on excess; 111A 20% full; property per rules (FY 2025-26: 12.5% both regimes).
2. `CapitalGainItem.transfer_date: Optional[date]` (main.py + validation bounds); session key `cg_transfer_before_2024_07_23` (tri-state bool|null per security table). Behavior: flag False/absent → 12.5% (default) + advisory when property and flag is null; flag True → 12.5% + election advisory ("20%-with-indexation election may be available — consult a CA; this tool cannot evaluate it") — never fabricate indexation.
3. Tests `test_capital_gains.py`: aggregate [2L,2L] → 35,750.00 total-effective; [1L,50k] → 3,275 excess-math per verification §5; STCG no exemption share; property cross-regime identity (FY 2025-26); flag null advisory; 87A-exclusion cross-ref.

## Step B — HRA (engine + NLP + tests)
1. Engine `_calc_hra(rules, salary, hra_received, rent_paid, is_metro)`: least of (a) hra_received, (b) rent_paid − 10%·salary, (c) metro ? 50% : 40% · salary; 0 when salary ≤ 0 or rent_paid ≤ 0; 80GG guard switches to hra_received > 0.
2. Legacy compat: `hra` key maps to BOTH hra_received and rent_paid (reproduces legacy formula exactly — parity cell).
3. NLP: split attention category `hra` → `hra_received` (["hra","house rent allowance","hra received"]) + `rent_paid` (rent-paid family); OVERWRITE rule exempts the new keys (both bookable in one turn); `_get_asked_cat` extended; HRA question asks all three (received, paid, metro city).
4. `is_metro` bool strictly (validator table); metro city names → bool true.
5. Tests `test_hra.py`: full least-of matrix per qa-lead §4; legacy-compat parity cell; NLP dual-booking; metro utterances; new regime ignores all three.

## Step D — Deductions (engine + API + tests)
1. 80U/80DD: category-driven flat amounts (`80u_80dd_category`: "none"|"40_79"|"80_plus" → 0/75,000/1,25,000); legacy numeric key → advisory (never guessed).
2. 80DDB: `80ddb_expenditure` numeric (≤1e11) → min(expenditure, tier by age≥60 ? 1,00,000 : 40,000) + patient-age advisory.
3. 80G: `80g_category` enum + existing `80g` amount → category rate; categories 3/4 subject to 10% adjusted-GTI limit (GTI before Ch VI-A − 112A − 112 − 111A); cash mode not collected → advisory on the ₹2,000 cap; new regime → 0 + advisory (PM-CARES-class note).
4. 80EEA: removed from engine + `_SESSION_NUMERIC_KEYS` + CalculateRequest → key now 422 ("discontinued"); advisory path for chat mentions ("80eea" keyword → discontinued advisory).
5. Parents' 80D: ₹25,000 default + parent-seniority advisory.
6. Tests `test_deductions.py` per qa-lead §6 + no-silent-collection meta-test (static key→artifact table).

## Step D2/G — NLP inputs (nlp_engine + ai_models + validation + tests)
1. New attention categories: `rent_paid`, `hra_received`, `80u_category`, `80g_category`, `age` guard; metro city names.
2. Age: anchored extractor BEFORE clause parsing (cue words: age/aged/years old/umar) — integer 0-120 only; span consumed/neutralized so it never reaches the money parser (G-1: ages 100-120 currently book as income — confirmed); never touches `_last_val`/`_prev_salary`; no `age` attention category; last explicit age wins.
3. NLP write clamping (closes V-1): clamp NLP-written numerics to 0..1e11 at write time (post-annualization); CG `type` enum-validated at both boundaries (closes V-2).
4. Validation table (security-auditor): `tax_year` enum; `hra_received`/`rent_paid` numeric 0..1e11 non-finite-reject; `is_metro` bool-strict; `80u_80dd_category`/`80g_category` enum strings; `80ddb_expenditure` numeric; `cg_transfer_before_2024_07_23` tri-state bool; `age` int 0-120 (existing).
5. Tests `test_nlp_new_inputs.py` + validator rows in `test_validation.py`.

## Step F — Append-only audit (audit_logger + main + tests)
1. JSONL append-only: global `logs/audit/session_audit.jsonl` + per-session `logs/blackbox/<safe_sid>.jsonl`; `os.open(O_APPEND|O_CREAT|O_WRONLY)` + one `os.write` per line under a process-wide lock; serialization failure → minimal redacted record (never skip the audit line, never 500).
2. Never truncate on any read error; read = line-scan with corrupt-line skip + count.
3. Rotation: `TAX_AUDIT_MAX_BYTES` (default 10MB) → `session_audit.jsonl.N`, keep `TAX_AUDIT_MAX_FILES` (default 5); rotation best-effort after write under lock (Windows-reader defer OK). Retention: `TAX_AUDIT_RETENTION_DAYS` (default 30) sweep for rotated files only; active file never deleted; invalid env → defaults.
4. PII minimization at write: drop raw user_input, ai_response, history[], `_last_val`/`_prev_salary`/`_last_question`; keep structured extracted[], state snapshot minus dropped keys, tax totals, tax_year, rules_version, advisory codes, sha256[:16] correlation hash of dropped text. `TAX_AUDIT_STORE_TEXT` opt-in (default off, 512-char cap).
5. `/history`: gate unchanged (404 default); reads global JSONL line-by-line, filters by safe sid, paginates (limit 50, max 200), returns {entries, corrupt_lines_skipped, has_more}; never serves blackbox; legacy-file fallback read-only.
6. Migration: offline script `tools/migrate_audit_to_jsonl.py` (parity-checked, corrupt source archived whole); not in request path.
7. Tests `test_audit_logger.py`: concurrency (16×25 → 400 lines all valid), corrupt-line recovery, read immutability (hash before/after), rotation, retention, never-truncate (no w-mode), serialization-failure record, path safety via safe_session_id, /history pagination + gate.

## Gates (every step)
Tests-first red → implement → `python -m pytest tests/ -q` all green (542+ baseline grows) → legacy 97/97 (pinned) → parity fixture untouched → commit → push → CI green. Per-issue report: files changed, tests added, score impact, regression status.

## Final Sprint 2 certification
security-auditor re-verification (10-item Sprint 1 checklist + new-key table) → tax-expert compliance review (FY 2025-26 matrix incl. the 3 corrected cliff cells + 87A/111A ⚠ items + property advisory) → qa-lead certification (§9.2 checklist) → Mode 9 re-score.

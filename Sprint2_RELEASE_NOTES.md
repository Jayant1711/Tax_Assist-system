# Sprint 2 Release Notes — Tax Assist AI

**Tag:** `v0.3-sprint2` (to be applied at merge) · **Date:** 2026-10-31 · **Branch:** `sprint-2-tax-year` (9 commits, `d6a6609..597485e`) · **Baseline:** `v0.2-sprint1` (`e503306`)
**Scope:** Tax year modernization (FY 2025-26 / AY 2026-27), computation correctness, deduction completeness, audit infrastructure. **Sprint 3 (auth, server-side sessions, Docker) NOT included.**

---

## ⚠ Read this first — behavior changes

1. **The engine now computes FY 2025-26 (AY 2026-27) by default.** The Finance Act 2025 new-regime structure is implemented (nil to ₹4L; 5/10/15/20/25/30% bands to ₹24L; 87A rebate ₹60,000 making income to ₹12L tax-free with marginal relief to ≈₹12,73,934). Pass `tax_year: "fy_2024_25"` explicitly to reproduce prior-year figures. Every response reports `tax_year` / `assessment_year` / `fy_label`.
2. **Section 80EEA is discontinued** (statutory sunset 31-Mar-2022). Requests containing it now return **422** with the discontinuation message — it is no longer silently ignored.
3. **87A eligibility is keyed on total income** (including special-rate capital gains), and the marginal-relief band caps the **post-cess** total — outputs change near the ₹7L (FY 2024-25) and ₹12L (FY 2025-26) thresholds, and in every surcharge relief zone. These are statutory corrections (H3/R1-R4), not regressions.
4. **Property capital gains are 12.5% in both regimes** for FY 2025-26 (transfers on/after 23-Jul-2024). The old regime no longer applies 20% to property. The 20%-with-indexation election for pre-23-Jul-2024 acquisitions is disclosed via advisory, never computed.
5. `GET /history/{sid}` (when enabled) returns a **paginated envelope** `{entries, corrupt_lines_skipped, has_more}` instead of a bare array.
6. **The localhost-only rule remains in force**: no authentication yet (Sprint 3), CORS wildcard unchanged.

## Highlights

### A — Tax year modernization (C1 closed)
- Versioned registry `backend/tax_rules/` (`fy_2024_25.py`, `fy_2025_26.py`, schema with import-time validation). Algorithms live once in the engine; years are data.
- All FY 2024-25 constants transcribed from the previous engine and proven **byte-identical** through the refactor by a 300-scenario parity fixture.
- FY 2025-26 constants verified against authoritative sources before implementation ([Finance Act 2025 slabs/87A — incometax.gov.in](https://incometax.gov.in); [112A/111A — incometaxindia.gov.in](https://www.incometaxindia.gov.in/w/tax-on-long-term-capital-gains%E2%80%8B); [marginal relief — CA Club India](https://www.caclubindia.com/articles/marginal-relief-in-income-tax-for-fy-2025-26-55502.asp)); full record with citations in `docs/tax-verification.md`.
- Hardcoded constants removed from the engine (verified: zero hits), legacy harnesses pinned to `fy_2024_25`, frontend labels now render the engine-reported `fy_label`.

### E — Surcharge & rebate correctness
- **Statutory surcharge marginal relief at all four thresholds** (₹50L/₹1Cr/₹2Cr/₹5Cr) via the threshold-comparison method — previously only ₹50L was approximated, overstating tax by up to ₹17,48,050 at ₹5Cr+.
- **87A marginal relief caps the post-cess total** (Finance Act 2025 Explanation); band endpoints derived (₹7,23,214 FY 2024-25 / ₹12,73,934 FY 2025-26) — the stale ₹7,27,777 constant is gone.
- **87A eligibility keyed on total income** including special-rate capital gains; rebate applies to normal-rate tax only and excludes 112A/111A.

### C — Capital gains correctness
- **112A ₹1.25L exemption aggregated per assessee** (was per entry — understated multi-broker tax).
- Property CG routed by statute, not regime: 12.5% both regimes (FY 2025-26); transfer-date flag + holding-period assumption + election advisories.

### B — HRA correctness
- Rule 2A three-leg computation with **separate inputs**: `hra_received`, `rent_paid`, `is_metro` (50%/40%). The legacy single `hra` key is preserved with identical legacy behavior (parity-proven).
- Conversational collection: rent, HRA received, and metro city are asked; both legs book in one sentence ("I receive 3L HRA and pay 2L rent").

### D — Deduction correctness (no silent collection)
- **80U/80DD**: category-driven flat deductions (₹75,000 / ₹1,25,000) — amounts are never guessed from user figures.
- **80DDB**: min(expenditure, tier) with the senior tier (₹1,00,000) and patient-age advisory.
- **80G**: four statutory categories, rate × qualifying limit (10% of adjusted GTI), default-category advisory, cash-cap advisory, new-regime non-deductibility advisory.
- **80EEA removed** everywhere; professional tax no longer defaults to ₹2,500 for FY 2025-26 (state-specific advisory instead).

### G — Senior citizen flows
- Conversational age collection with an anchored extractor (ages 100–120 no longer booked as income — a confirmed pre-sprint defect); senior/very-senior slabs, 80TTB routing, and 80D tiers are now reachable end-to-end.

### F — Audit infrastructure (H6/ADR-009 closed)
- **Append-only JSONL** audit + per-session blackbox streams (O_APPEND, single-write, lock; no truncate path exists). Rotation (`TAX_AUDIT_MAX_BYTES`, default 10 MB), retention (`TAX_AUDIT_RETENTION_DAYS`, default 30), corrupt-line recovery, read-path immutability.
- **PII minimization at write**: raw transcripts dropped by default (correlation-hash + length kept); `TAX_AUDIT_STORE_TEXT` opt-in with 512-char cap.
- `/history`: paginated, corrupt-line-counted, legacy-file fallback, gate unchanged (404 default).

## Metrics

| Metric | v0.2-sprint1 | v0.3-sprint2 |
|---|---|---|
| pytest suite | 153 + 300-cell parity | **776** (incl. 300-cell parity + FY-versioned matrix) |
| Supported tax years | 1 (stale) | **2** (FY 2024-25 parity + FY 2025-26 current), versioned registry |
| Audit store | read-modify-write JSON, can self-destruct | **append-only JSONL**, rotation + retention + PII minimization |
| Open audit Criticals | C1 (stale FY) | **0** (C5 auth remains Sprint 3) |
| CI | green | **green on every push** (9/9 Sprint 2 runs) |

## Testing summary

- **776 pytest tests, all green** (0 failed, 0 skipped): 153 Sprint 1 tests preserved unchanged inside the suite; +311 parity/matrix/registry (Objective A); +34 surcharge/87A boundary (E); +22 capital gains (C); +63 HRA (B); +60 deductions (D); +58 NLP inputs/age/clamping (D2/G); +31 audit infrastructure (F).
- **Parity discipline**: a 300-scenario fixture frozen at pre-refactor outputs proves FY 2024-25 behavior byte-identical outside **183 deliberately changed cells** — every cell annotated with the statutory cause (64 surcharge/87A + 56 CG-aggregate + 63 80G-default).
- **FY 2025-26 ground truths**: hand-computed and independently re-derived by a tax-expert review (223/223 + 300/300 green); four-agent independent verification confirmed 9/9 implementation claims, 55/55 security probes, and zero hidden regressions.
- Legacy 97/97 harness pinned to FY 2024-25 and green.

## Migration notes

**API consumers**
- Default computation year is now FY 2025-26. Pass `"tax_year": "fy_2024_25"` to reproduce prior output; unknown values → 422 with the supported list.
- New optional request fields: `tax_year`, `hra_received`, `rent_paid`, `is_metro`, `80u_80dd_category`, `80g_category`, `80ddb_expenditure`, `cg_transfer_before_2024_07_23`, `transfer_date` (per CG entry). Validation table in `docs/sprint2-design.md`.
- `80eea` → **422** (discontinued). `CapitalGainItem.type` is now required and enum-validated.
- `/history` (when enabled) returns the paginated envelope; `limit` ≤ 200.
- Responses carry `tax_year` / `assessment_year` / `fy_label`; audit observations now include prof-tax, HRA-assumption, 80G-category, property-election, and holding-period advisories.

**Deployment / ops**
- New env vars: `TAX_AUDIT_MAX_BYTES` (10 MB), `TAX_AUDIT_MAX_FILES` (5), `TAX_AUDIT_RETENTION_DAYS` (30), `TAX_AUDIT_STORE_TEXT` (default **off**). Invalid values fall back to defaults.
- Audit streams move to `logs/audit/session_audit.jsonl` + `logs/blackbox/<sid>.jsonl`. Run `python backend/tests/tools/migrate_audit_to_jsonl.py --logs-dir backend/logs` once to migrate legacy files (parity-checked; corrupt sources archived, never rewritten). Legacy fallback is read-only.
- Single-writer process contract for the audit streams: do not scale to multiple Uvicorn workers without adding an OS file lock.

**Frontend**
- Labels render the engine-reported `fy_label`; quick-rules copy updated to FY 2025-26. `npm ci` unchanged; no new dependencies.

## Known remaining

Auth + server-side sessions (Sprint 3) · CORS wildcard (localhost-only rule in force) · hardcoded `localhost:8000` (Sprint 3) · 16 moderate npm advisories (eslint/minimatch chain) · docs punch-list (pre-sprint wording in architecture/api-reference/nlp-pipeline) · 5 statutory-wording ⚠ items quarantined in `docs/tax-verification.md` for merge-gate verification (111A rebate exclusion ITR-utility behavior; in-band literal cap over special-rate tax; 80G adjusted-GTI Explanation enumeration; CII notification if indexation is ever built; First Schedule surcharge proviso wording) · smoke/final scripts retain print-only sections (superseded by pytest).

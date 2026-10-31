# Changelog

All notable changes to Tax Assist AI are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/); versioning is sprint-tagged (`vX.Y-sprintN`).

## [0.2.0-sprint1] — 2026-10-31

Sprint 1: correctness, security hardening, testing foundation. Baseline `main @ 50d8eda`. Full details in [Sprint1_RELEASE_NOTES.md](Sprint1_RELEASE_NOTES.md).

### Security
- **Fixed (Critical C6):** client-controlled `session.id` joined into a filesystem path (arbitrary file write). Session IDs are now validated (`^[A-Za-z0-9_-]{4,64}$`) at the API boundary and deterministically aliased at the persistence layer (`backend/validation.py`, new). — Issue #1
- **Fixed (High H5/N1):** unvalidated input on `/chat` and `/calculate` caused 500s and unbounded CPU/memory use. Added typed request models with bounds, session payload validation (size ≤ 100 KB, numeric-only amounts, finite floats, typed `capital_gains[]`, age 0–120), and a sanitized global 500 handler. — Issue #2
- **Changed:** validation errors return a bounded, non-reflecting 422 body (`{detail, errors:[{loc,msg,type}]}`, max 20 entries) instead of echoing attacker input.
- **Changed (Critical C5, interim):** `GET /history/{sid}` returns 404 unless `TAX_ENABLE_HISTORY` is set. — Issue #5

### Fixed — tax calculation
- **Fixed (Critical C2):** agricultural income is no longer added to old-regime taxable income (Sec 10(1)); partial-integration advisory emitted instead. — Issue #4
- **Fixed (Critical C3):** monthly amounts are annualized exactly once ("₹80,000 per month" now yields ₹9,60,000, not ₹1,15,20,000); annualization is match-local, not sentence-global. — Issue #3
- **Changed:** capital-gains statements carry a gross-value-vs-gain advisory. — Issue #8

### Fixed — NLP extraction
- **Fixed (Critical C4a):** unmatched deduction phrases no longer overwrite declared income via the profile-default fall-through (tuition payment destroying a ₹45 L salary); unrecognized amounts are flagged for the user. — Issue #6
- **Fixed (Critical C4b):** values are bound to their clause; a negative keyword in one clause can no longer capture amounts from another ("PPF + health insurance" splits correctly to 80C/80D). — Issue #7
- **Fixed (Critical C4c):** property-sale noun forms ("property sale", "flat sale", "plot sale", "sale of property") book to capital gains instead of rental income. — Issue #8

### Added — testing
- pytest suite: 153 tests across parser, profession, attention, conversation, tax engine (exact-rupee ground truth), edge cases, API, session security, and request validation; conftest/pytest.ini; `requirements-dev.txt`. — Issue #16
- Golden-file regression corpus replaying the five production misclassification patterns recorded in the April 2026 audit logs. — Issue #17
- Removed the tautological C03b check and the ±₹2,000/±₹5,000 tax tolerances from the migrated tests.

### Added — CI & dependencies
- GitHub Actions pipeline (`ci.yml`): backend (pytest + pip-audit) and frontend (npm audit + build) on push/PR. — Issue #19
- Backend dependencies pinned exact (fastapi 0.162.0, uvicorn 0.54.0, pydantic 2.14.2, numpy 2.5.4). — Issue #27

### Removed
- Dead/broken modules: `nlp_engine_v2.py`, `anfis_refine.py`, `view_lab_logs.py`, `debug_run.py`; broken `session_lab.__main__` demo. — Issue #28
- Unused dependencies: `scikit-learn`, `pandas`, `python-multipart`. — Issue #27
- Non-standard marker keys from `package.json`, `tsconfig.json`, `anfis_weights.json`. — Issue #28

### Documentation (pre-sprint foundation, same release)
- `docs/` set (architecture, api-reference, nlp-pipeline, tax-rules, testing, security, deployment, roadmap, decisions ADR-001…011, index), `AI_RULES.md`, and a README documentation section.

### Known issues / deferred
- CORS wildcard remains; **backend must stay localhost-only** until Sprint 3 (auth).
- Tax constants target FY 2024-25 (AY 2025-26) only; FY 2025-26 update is Sprint 2.
- HRA formula and surcharge marginal relief remain approximations; LTCG ₹1.25L exemption is per-entry (Sprint 2).
- `smoke_test.py` / `final_test.py` still contain print-only sections (superseded by the pytest suite).

## [0.1.0] — 2026-07-29

Initial public baseline (`main @ 50d8eda`): dual-regime rule engine for FY 2024-25, regex/keyword NLP consultant, ANFIS efficiency scoring, Next.js dashboard, legacy 97-check harness.

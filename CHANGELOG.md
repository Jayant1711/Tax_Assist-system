# Changelog

All notable changes to Tax Assist AI are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/); versioning is sprint-tagged (`vX.Y-sprintN`).

## [0.3.0-sprint2] — 2026-10-31

Sprint 2: tax year modernization (FY 2025-26 / AY 2026-27), computation correctness, deduction completeness, audit infrastructure. Branch `sprint-2-tax-year`; baseline `v0.2-sprint1`. Full details in [Sprint2_RELEASE_NOTES.md](Sprint2_RELEASE_NOTES.md); verified constants in [docs/tax-verification.md](docs/tax-verification.md).

### Added — Tax year modernization (Objective A; C1 closed)
- Versioned tax-rules registry (`backend/tax_rules/`): `fy_2024_25.py` (byte-identical parity, 300-scenario fixture) and `fy_2025_26.py` (Finance Act 2025 constants, verified against authoritative sources before implementation — `docs/tax-verification.md`).
- `TaxEngine` accepts `tax_year`; unknown years raise/422; every response reports `tax_year` / `assessment_year` / `fy_label`; default year flipped to FY 2025-26.
- FY-versioned test matrix (slab edges 4L-24L, 87A band, surcharge thresholds) + 300-cell FY 2024-25 parity fixture with annotation-backed changes.

### Fixed — Computation correctness (Objectives B, C, D, E)
- **87A**: eligibility keyed on total income (incl. special-rate CG); marginal-relief band caps the **post-cess** total; stale ₹7,27,777 constant retired (derived endpoints ₹7,23,214 / ₹12,73,934).
- **Surcharge**: statutory marginal relief at all four thresholds (₹50L/₹1Cr/₹2Cr/₹5Cr) — previously approximated at ₹50L only, overstating tax by up to ₹17,48,050; new-regime surcharge on special-rate income capped at 15% (s.115BAC(6)).
- **HRA**: Rule 2A three-leg computation (HRA received / rent paid − 10% salary / metro 50% or non-metro 40%) with separate conversational inputs; legacy `hra` key preserved with identical behavior.
- **Capital gains**: 112A ₹1.25L exemption aggregated per assessee (was per entry); property CG 12.5% in both regimes for FY 2025-26 with transfer-date flag + election/holding-period advisories; 87A rebate excluded from special-rate income.
- **Deductions**: 80U/80DD category-driven flat amounts (₹75,000/₹1,25,000); 80DDB = min(expenditure, ₹40k/₹1L senior tier) with patient-age advisory; 80G four statutory categories with rate × 10%-adjusted-GTI qualifying limit + cash-cap advisory; parents' 80D capped ₹25,000 with seniority advisory; professional tax no longer defaults to ₹2,500 for FY 2025-26.
- **Agricultural income**: exemption + partial-integration parameters moved into the registry.

### Removed
- **80EEA** (statutory sunset 31-Mar-2022) — requests containing it now return 422 with the discontinuation message; chat mentions produce an advisory.

### Added — Audit infrastructure (Objective F; H6/ADR-009 closed)
- Append-only JSONL audit + per-session blackbox streams (O_APPEND, single-write, process-wide lock; no truncate path exists).
- Rotation (`TAX_AUDIT_MAX_BYTES`, default 10 MB), retention (`TAX_AUDIT_RETENTION_DAYS`, default 30), corrupt-line recovery, read-path immutability.
- PII minimization at write: raw transcripts dropped by default (correlation hash + length kept); `TAX_AUDIT_STORE_TEXT` opt-in (512-char cap).
- `/history`: paginated envelope `{entries, corrupt_lines_skipped, has_more}` behind the existing gate; legacy-file fallback; migration tool (`tests/tools/migrate_audit_to_jsonl.py`).

### Added — NLP input collection (Objectives D2, G)
- Conversational collection for rent paid, HRA received, metro status, disability category, donation category, and age — with senior/very-senior slabs, 80TTB routing, and 80D tiers now reachable end-to-end.
- Security closures: NLP write clamping to the validated range (V-1), capital-gains type enum at both boundaries (V-2), anchored age extractor with span masking (G-1 — ages 100-120 no longer booked as income).
- Fixed en route: the `" pm "` annualization keyword false-matched "to PM CARES" (₹1L donations ×12); a parser regex could truncate adjacent amounts.

### Security
- Sprint 1 controls re-verified intact (10/10 checklist): session-id sanitization, request validation, non-reflecting 422s, sanitized 500s, `/history` gate, session cap, path safety, pinned dependencies, CI gates.
- Independent verification: 4-agent review (architect 9/9 claims verified, tax-expert 12/12 statutory recomputations matched, security 55/55 probes, qa-lead zero vacuous tests / zero hidden regressions).

### Documentation
- `docs/tax-verification.md` (verified constants + sources + expert amendments), `docs/sprint2-design.md` (consolidated design + rulings + test matrix), `docs/tax-rules.md` refreshed, `docs/security.md` §3 audit item marked landed.

## [0.4.0-sprint3] — 2026-11-01

Sprint 3: authentication, server-side sessions, deployment platform, security hardening, frontend testing, observability. Branch `sprint-3-production`; baseline `v0.3-sprint2`. Full details in [Sprint3_RELEASE_NOTES.md](Sprint3_RELEASE_NOTES.md).

### Added — Authentication (Objective A; C5 closed; ADR-012)
- Email/password accounts with stdlib scrypt hashing (memory-hard, per-hash parameters, timing-equalized logins) — zero new runtime dependencies.
- Opaque 256-bit HttpOnly cookie sessions (sha256-at-rest, sliding 30-min + absolute 24-h TTL, row-level revocation, UA binding, lockout after 5 failures).
- `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/sessions` (list + owner-checked revoke); audit events for all auth actions.
- OAuth-ready schema (`auth_provider`/`oauth_subject` reserved).

### Added — Server-side sessions (Objective B; ADR-013 accepted, supersedes ADR-002)
- Conversation state moved to SQLite (`app_sessions`, WAL); the client sends only an opaque `session_id` and receives a read-only projection.
- Ownership enforced on `/chat`, `/calculate`, `/history`, `/sessions` (foreign ids → 404); sliding + absolute expiration and revocation.
- **Breaking:** `POST /chat` body `{message, session_id}`; `POST /calculate` body `{session_id}`; legacy session-dict bodies → 422.

### Added — Deployment (Objective C)
- backend/frontend Dockerfiles (non-root, pinned, healthchecks), docker-compose.yml (loopback ports, named volumes), `.env.example`, production startup, `GET /health` (db + audit checks, 503 degradation).

### Added — Security hardening (Objective D; ADR-014)
- CORS allowlist from environment (fail-closed in production; wildcard retired); rate limiting (auth 10/min/IP, chat 30/min, calculate 60/min, global 120/min; 429 + Retry-After); 1 MB body cap; security headers on every response; OpenAPI surface disabled in production; Origin-check CSRF middleware.

### Added — Frontend testing (Objective E)
- Vitest (22 component/contract tests) + Playwright (7 E2E: auth flow, session_id wire contract, protected routes) — executed locally and in CI (new e2e job).
- Frontend auth wiring: `/login` page, session bootstrap, logout, `lib/api.ts` (NEXT_PUBLIC_API_URL — ADR-010; hardcoded localhost removed).

### Added — Observability (Objective F)
- Structured JSON logging with request-ID correlation; app-log rotation (`TAX_APP_LOG_*`); engine-failure diagnostics with graceful degradation; `docs/backup-recovery.md` + `backend/tools/backup_db.py` (SQLite backup, JSONL stream copies, recovery runbook).

### Added — Planning
- `Sprint4_AI_Modernization.md`: dataset strategy, model candidates, evaluation framework, confidence scoring, explainability (planning only — no ANFIS/NLP changes).

### Fixed
- `/health` db probe reads the header (`PRAGMA schema_version`) instead of `SELECT 1` — a corrupt/non-sqlite `TAX_DB_PATH` returned 200 on Linux CI (platform bug caught by the pipeline).

### Security
- Sprint 1+2 controls re-verified intact (10/10 disposition table); threat model T1–T12 implemented; CSRF closed (SameSite=Lax + JSON-only + Origin middleware); CORS wildcard retired (fail-closed allowlist); independent certification: SECURITY-CERTIFIED (116/116 probes) after CI green.

## [0.2.0-sprint1] — 2026-10-31

Sprint 1: correctness, security hardening, testing foundation. Baseline `main @ 50d8eda`. Full details in [Sprint1_RELEASE_NOTES.md](Sprint1_RELEASE_NOTES.md).

### Security
- **Fixed (Critical C6):** client-controlled `session.id` joined into a filesystem path (arbitrary file write). Session IDs are now validated (`^[A-Za-z0-9_-]{4,64}$`) at the API boundary and deterministically aliased at the persistence layer (`backend/validation.py`, new). — Issue #1
- **Fixed (High H5/N1):** typed request models with bounds on `/chat` and `/calculate`; finite-float rejection; sanitized 500 handler; non-reflecting 422 body.
- **Changed (Critical C5, interim):** `GET /history/{sid}` returns 404 unless `TAX_ENABLE_HISTORY` is set.

### Fixed
- Agricultural income exempt (Sec 10(1)) — C2; monthly amounts annualized exactly once — C3; NLP misclassification cluster (tuition→salary overwrite, PPF→80D, property-sale→rental) — C4a/b/c.

### Added
- pytest suite (153 tests) with golden-file regression corpus from production logs; GitHub Actions CI; pinned dependencies.

### Removed
- Dead modules (`nlp_engine_v2.py`, `anfis_refine.py`, `view_lab_logs.py`, `debug_run.py`); unused dependencies (`scikit-learn`, `pandas`, `python-multipart`).

## [0.1.0] — 2026-07-29

Initial public baseline (`main @ 50d8eda`): dual-regime rule engine for FY 2024-25, regex/keyword NLP consultant, ANFIS efficiency scoring, Next.js dashboard, legacy 97-check harness.

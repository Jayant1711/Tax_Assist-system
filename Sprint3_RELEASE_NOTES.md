# Sprint 3 Release Notes — Tax Assist AI

**Tag:** `v0.4-sprint3` (applied at merge) · **Date:** 2026-11-01 · **Branch:** `sprint-3-production` (13 commits, `39e87c3..bfb5fbf` + CI fixes) · **Baseline:** `v0.3-sprint2` (`39e87c3`)
**Scope:** Authentication & authorization, server-side sessions, deployment platform, security hardening, frontend testing, observability, Sprint 4 AI plan. **The localhost-only restriction is lifted** — with the operational conditions below.

---

## ⚠ Read this first — breaking changes & operations

1. **The API contract changed (breaking).** `POST /chat` now takes `{message, session_id}`; `POST /calculate` takes `{session_id}`; conversation state is **server-side** (ADR-013). The old client-owned session dict is rejected with 422. The bundled frontend is migrated; direct API consumers must migrate (see Migration notes).
2. **All conversation/compute endpoints require authentication.** Register → login → receive an HttpOnly cookie session. Unauthenticated requests → 401. `GET /history/{sid}` is authenticated **and ownership-checked** (C5 closed properly).
3. **CORS is now an explicit allowlist** (`CORS_ORIGINS`); production startup **fails closed** if unset or wildcard. The `allow_origins=["*"]` era is over.
4. **New env vars** (see Migration notes): `APP_ENV`, `CORS_ORIGINS`, `TAX_DB_PATH`, `TAX_SESSION_TTL_MINUTES`/`TAX_SESSION_ABS_TTL_HOURS`, `TAX_COOKIE_SECURE`, `TAX_ENABLE_ANON_DEMO` (default off), `TAX_RATE_LIMIT_*`, `TAX_MAX_BODY_BYTES`, `TAX_LOG_LEVEL`, `TAX_APP_LOG_*`.
5. `/docs` + `/redoc` + `/openapi.json` are **disabled in production** (`APP_ENV=prod`); available in dev.
6. Deploy via `docker compose up` (single-origin topology; TLS terminates at your reverse proxy).

## Highlights

### A — Authentication & authorization (C5 closed)
- **Email/password accounts** with `hashlib.scrypt` hashing (memory-hard, per-hash parameters, timing-equalized unknown-email logins) — zero new runtime dependencies.
- **Opaque 256-bit session tokens**, stored only as SHA-256 hashes, delivered in **HttpOnly SameSite=Lax cookies** (`__Host-`-prefixed in production); sliding 30-minute TTL capped by a 24-hour absolute expiry.
- **Full revocation semantics**: logout, per-session revoke, and (future) password-change revoke-all are row operations checked on every request.
- Account lockout (5 failures → 15 minutes, oracle-resistant), rate-limited `/auth/*`, generic error messages.
- Session binding: user-agent hash checked (mismatch revokes), IP hash logged.
- **OAuth-ready schema** (`auth_provider`/`oauth_subject` reserved) — future providers are additive.
- Threat model T1–T12 implemented and probed (docs/sprint3-design.md).

### B — Server-side sessions (W1 closed; ADR-002 reversed by ADR-013)
- Conversation state lives in SQLite (`app_sessions`, WAL); the client holds only an **opaque server-issued session id** and a read-only projection.
- Ownership enforced on every operation: another user's session id → **404** (no existence oracle).
- Session payload validated on every server-side write (Sprint 2's validation table now defends server-authored state).
- `POST /calculate` takes `{session_id}` — the unbounded client payload is gone.

### C — Deployment platform
- `backend/Dockerfile` (python:3.12-slim, non-root uid 10001, pinned deps, stdlib HEALTHCHECK, single-worker correctness contract), `frontend/Dockerfile` (node:20-alpine multi-stage), `docker-compose.yml` (loopback-published ports, named volumes for SQLite + logs, healthcheck-gated startup), `.env.example`.
- **`GET /health`**: process/db/audit checks with 503 degradation semantics; `?verbose=1` dev-only.
- Production startup scripts + documented reverse-proxy/TLS topology.

### D — Security hardening
- **CORS**: explicit allowlist from `CORS_ORIGINS`, `allow_credentials=True` (wildcard now unrepresentable), prod fail-closed.
- **Rate limiting**: stdlib sliding-window limiter — `/auth/*` 10/min/IP, `/chat` 30/min/user, `/calculate` 60/min/user, global 120/min/IP; 429 + `Retry-After`.
- **Request size cap** (1 MB → 413) and **security headers** on every response (nosniff, DENY, referrer-policy, no-store, API CSP, permissions-policy).
- **CSRF**: SameSite=Lax + JSON-only bodies + Origin validation middleware.
- **OpenAPI surface disabled in production.**

### E — Frontend testing
- **Vitest** (22 component/contract tests): SavingsGraph math/format, TaxReport `{session_id}` contract + tiles/error banner, ChatInterface send/bootstrap/error paths, api.ts credentials/401 handling.
- **Playwright** (7 E2E tests, executed locally and in CI): register → login → chat → report → logout; `{session_id}` wire-contract assertion; protected-route 401s.

### F — Observability
- Structured JSON logging with request-ID correlation (contextvars), access records, app-log rotation (`TAX_APP_LOG_*`).
- Engine failures log with request-id + session-hash and degrade gracefully (`tax_report: null`).
- `docs/backup-recovery.md`: SQLite backup procedure, JSONL stream copies, retention interplay, 9-step recovery runbook. Backup tool: `backend/tools/backup_db.py`.

### G — Sprint 4 AI modernization plan
- `Sprint4_AI_Modernization.md`: dataset strategy (labeled corpus from audited streams + synthetic known-true augmentation), architecture candidates (in-paradigm → local classifier with deterministic guardrails → flag-gated LLM), evaluation framework (≥95% per-category targets, CI-gated corpus, drift replay), confidence scoring (abstain-and-ask), explainability (span attribution + rule-ID traceability). Planning only — no ANFIS/NLP changes.

## Metrics

| Metric | v0.3-sprint2 | v0.4-sprint3 |
|---|---|---|
| pytest suite | 776 | **947** (+171: auth, sessions, health, hardening, observability, backup) |
| Frontend tests | 0 | **22 Vitest + 7 Playwright E2E** (executed locally + in CI) |
| AuthN/AuthZ | none | **full** (scrypt accounts, cookie sessions, ownership, lockout) |
| Session state | client-owned (tamperable) | **server-side SQLite** (ADR-013) |
| Deployment | dev-only (hardcoded localhost) | **Docker Compose** + `/health` + env config |
| CI | 2 jobs | **3 jobs** (backend + frontend + Playwright e2e), all green |

## Independent verification

- Security re-certification: Sprint 1+2 checklist 10/10 intact-or-superseded-with-rationale; 116/116 probes (49 auth + 31 protected + 30 hardening + 6 residuals); timing-equalization measured (ratio 1.00); fail-closed CORS verified; certifiable once CI green → **CI now green**.
- QA certification: 947/947 + 97/97 legacy + 22/22 Vitest + 7/7 Playwright; parity fixture untouched all sprint; golden corpus untouched; zero deleted or weakened tests; both CI blockers root-caused and fixed.
- Known residuals (tracked): per-IP rate-limit keys (design said per-user — align or document); chunked-encoding body-cap bypass (secondary caps hold); register 409 enumeration signal (inherent); `TAX_AUDIT_STORE_TEXT` must stay off in production; 2 test-docstring arithmetic slips (Sprint 2 review, non-blocking).

## Migration notes

**API consumers**
- Obtain a session: `POST /auth/register` then `POST /auth/login` (cookie jar required), or migrate to the cookie flow. All conversation/compute calls need the cookie.
- `POST /chat` body: `{message, session_id}`; bootstrap with `POST /sessions`. `POST /calculate`: `{session_id}`.
- `80eea` still → 422. All Sprint 2 validation bounds apply unchanged.
- `/history/{sid}` is owned: foreign ids → 404; on by default (`TAX_ENABLE_HISTORY` kill-switch retained).

**Deployment**
- `cp .env.example .env` and set `CORS_ORIGINS` + `APP_ENV=prod` (startup fails closed otherwise). `docker compose up -d` → verify `GET /health` → create your account.
- Run `python backend/tools/backup_db.py` on a schedule; see `docs/backup-recovery.md`.
- TLS terminates at your reverse proxy (set `TAX_COOKIE_SECURE=true` via compose env).
- Legacy audit files: run `python backend/tests/tools/migrate_audit_to_jsonl.py --logs-dir backend/logs` once.

**Frontend**
- Set `NEXT_PUBLIC_API_URL` at build time (empty string for single-origin/reverse-proxy deployments).

## Verification

```text
cd backend && python -m pytest tests/ -q   →  947 passed
cd backend && python test_suite.py         →  97/97 (fy_2024_25 pinned)
cd frontend && npm run test                →  22 passed
cd frontend && npx playwright test         →  7 passed
CI (backend + frontend + e2e)              →  green
```

Independent verification: security re-certification (116/116 probes + 10/10 checklist, blockers resolved), QA certification (zero vacuous tests, zero regressions, scope-complete), CI green at HEAD.

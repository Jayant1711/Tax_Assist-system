# Sprint 3 Design — Production Platform (auth, server-side sessions, deployment, hardening, frontend tests, observability)

> Planning review 2026-10-31 (@architect). Binding for all Sprint 3 implementation. Branch `sprint-3-production` @ `39e87c3` (= v0.3-sprint2). Targets: Architecture >85, Security >85, Testing >90, Compliance ≥85, Production >88.

## 1. AuthN/AuthZ decision (ADR-012)

**DECISION: HttpOnly-cookie server-side sessions with opaque random tokens.** JWT rejected (no revocation without a store → Objective B fails; adds PyJWT + signing-secret lifecycle for zero benefit). Hybrid rejected (doubles theft surface + test matrix). Chosen because Objective B's revocation requirement and the stdlib-first policy point at the same primitive: a session row. Zero new runtime dependencies (`secrets`, `hashlib.scrypt`, `sqlite3`).

- **Passwords:** `hashlib.scrypt` — stored format `scrypt$N$r$p$salt_b64$hash_b64`, params n=2^15, r=8, p=1, dklen=64, 16-byte salt (~32 MiB, ~50-100 ms); verify via `hmac.compare_digest`; dummy-hash timing equalization for unknown emails; policy: length 12–1024 (NIST 800-63B style).
- **Tokens:** `secrets.token_urlsafe(32)` (256-bit); stored ONLY as `sha256(token)` hex; sliding TTL `TAX_SESSION_TTL_MINUTES` (30) capped by absolute `TAX_SESSION_ABS_TTL_HOURS` (24); revocation = row update (logout/current, per-session, all-on-password-change); UA-hash mismatch → invalidate; IP-hash log-only.
- **Cookie:** `__Host-ta_session` when Secure (prod) else `ta_session`; HttpOnly always; Secure = `COOKIE_SECURE` (APP_ENV=prod → true); SameSite=Lax; Path=/; Max-Age mirrors TTL.
- **CSRF (no token):** SameSite=Lax + JSON-only bodies + Origin/Referer validation middleware on state-changing routes (mismatch → 403) + CORS `allow_credentials=True` forcing explicit origins (wildcard becomes unrepresentable).
- **Endpoints:** POST /auth/register (409 duplicate) · POST /auth/login (uniform 401, dummy-scrypt timing, 5-failure/15-min lockout) · POST /auth/logout (204, revokes) · GET /auth/me · GET /auth/sessions · DELETE /auth/sessions/{id} (owner-checked).
- **Authorization:** `get_current_user` dependency (cookie → sha256 → row → revoked/expiry/is_active/UA checks → slide TTL); protected: /chat, /calculate, /sessions*, /history (ownership-checked); /auth/* public+rate-limited; /health public exempt.
- **Anonymous demo:** deny-by-default; `TAX_ENABLE_ANON_DEMO=1` opt-in permits /chat + /calculate only (app_sessions.user_id NULL); never /history.
- **OAuth future:** users.auth_provider/oauth_subject columns reserved (UNIQUE pair); OAuth login upserts + issues the same opaque cookie — additive only.
- **Threat model T1-T12:** credential stuffing (rate limit + lockout + scrypt), network theft (Secure + TLS at proxy), XSS theft (HttpOnly), fixation (server-issued rotate-on-auth), CSRF (three layers above), enumeration (uniform 401 + timing equalization), IDOR/cross-user (ownership check → 404, uuid4 ids), revocation bypass (row-checked every request), SQLite file access (0600, uid 10001, hashed tokens), secrets (none exist), DoS (rate limits + caps), audit tampering (Sprint 2 append-only unchanged; auth events appended as new event types).

## 2. Server-side sessions (ADR-013 accepted; supersedes ADR-002)

**SQLite** `TAX_DB_PATH` (default `data/taxassist.db`): WAL, foreign_keys ON, busy_timeout 5000, thread-local connections, idempotent `CREATE TABLE IF NOT EXISTS` migrations + `schema_migrations` table (no Alembic).

```sql
users(id TEXT PK, email TEXT UNIQUE COLLATE NOCASE, password_hash TEXT NULL,
      auth_provider TEXT DEFAULT 'password', oauth_subject TEXT, is_active INT 1,
      failed_logins INT 0, locked_until TEXT NULL, created_at TEXT,
      CHECK(password_hash IS NOT NULL OR auth_provider <> 'password'));
auth_sessions(token_hash TEXT PK, user_id TEXT REFERENCES users ON DELETE CASCADE,
      created_at, last_used_at, expires_at, absolute_expires_at, revoked_at,
      ua_hash TEXT, ip_hash TEXT);
app_sessions(id TEXT PK, user_id TEXT REFERENCES users ON DELETE CASCADE,
      state TEXT NOT NULL /* JSON <=100KB */, created_at, updated_at);
```

**Contract swap (breaking, documented):** `POST /chat` body `{message, session_id}` (was `{message, session}`); response keeps `session` as a **read-only projection** (state minus internal/`_last_*`/`history` keys — preserves every key the frontend reads: id, phase, profile, salary, business, rental, flags); `POST /calculate` body `{session_id}`; `POST /sessions` bootstraps a server-uuid session; `/history/{sid}` ownership-checked (foreign/unknown → 404), gate default flips to ON (C5 precondition closed by auth+ownership). Old clients → 422 with explanation (no dual contract — one frontend, one deploy unit). Breaking change recorded in CHANGELOG + ADR-013 + api-reference.

**Handler flow:** load owned row → json.loads → `nlp.process_message(message, state)` (same function — zero NLP/engine changes) → engine → `_validate_session_payload(state)` defense-in-depth → persist → audit/blackbox as today → respond with projection.

## 3. Deployment (Objective C)

- `backend/Dockerfile`: python:3.12-slim, pinned reqs, non-root uid 10001, 1 uvicorn worker (**documented correctness requirement**: audit lock + SQLite), HEALTHCHECK via stdlib urllib.
- `frontend/Dockerfile`: node:20-alpine multi-stage; `NEXT_PUBLIC_API_URL` is the **browser-reachable** URL ("" in single-origin prod with reverse proxy; `http://localhost:8000` in dev) — corrects the Sprint-1 sketch.
- `docker-compose.yml`: backend (127.0.0.1:8000, volumes db-data + logs-data, healthcheck) + frontend (127.0.0.1:3000, depends_on healthy). TLS/proxy documented, not in compose.
- **`GET /health`**: `200 {"status":"ok","checks":{"db":"ok","audit":"ok"},"app_env","version"}`; db = SELECT 1 + dir write-permission; audit = dir writable + AuditLogger.last_error_at < 5 min; degrade → 503 with the failing check; `?verbose=1` dev-only; unauthenticated, rate-limit-exempt. Tests: `test_health.py`.

## 4. Hardening (Objective D)

- **CORS:** `CORS_ORIGINS` comma-list; `allow_credentials=True`; methods GET/POST; headers Content-Type; dev default `http://localhost:3000`; **prod startup fails closed** if unset/`*`. Retires the wildcard permanently.
- **Rate limiting** (`backend/rate_limit.py`, stdlib sliding window, lock, LRU-capped keys): /auth/* 10/min/IP · /chat 30/min/user · /calculate 60/min/user · global 120/min/IP; /health exempt; 429 `{"detail","retry_after_seconds"}` + Retry-After header. Per-process only (one worker).
- **Body cap:** middleware 413 over `TAX_MAX_BODY_BYTES` (1 MB).
- **Security headers:** X-Content-Type-Options nosniff; X-Frame-Options DENY; Referrer-Policy strict-origin-when-cross-origin; Cache-Control no-store; CSP `default-src 'none'; frame-ancestors 'none'`; Permissions-Policy camera/microphone/geolocation=(). Uvicorn --no-server-header.
- **App factory:** `create_app(app_env)` — prod: docs/redoc/openapi = None; dev: enabled. Middleware order: size-cap → headers → origin-check → rate-limit → CORS.

## 5. Env inventory

APP_ENV (dev|prod) · CORS_ORIGINS · TAX_DB_PATH · TAX_HOST/TAX_PORT (dev 127.0.0.1) · TAX_SESSION_TTL_MINUTES/TAX_SESSION_ABS_TTL_HOURS · TAX_COOKIE_SECURE · TAX_ENABLE_ANON_DEMO (off) · TAX_ENABLE_HISTORY (**on** — C5 closed) · TAX_AUDIT_* (carried) · TAX_RATE_LIMIT_* (auth 10/chat 30/calc 60/global 120 per min) · TAX_MAX_BODY_BYTES (1MB) · TAX_LOG_LEVEL · NEXT_PUBLIC_API_URL. No signing secret exists.

## 6. Frontend (Objective E)

- `frontend/src/lib/api.ts` (ADR-010): `NEXT_PUBLIC_API_URL ?? ""` + `apiFetch` with `credentials:"include"` + 401 redirect; removes both hardcoded localhost fetches + URL-disclosing error copy.
- ChatInterface: GET /auth/me bootstrap → POST /sessions; sends `{message, session_id}`; projection applied; Reset re-bootstraps. TaxReport: `{session_id}` body. page.tsx holds {sessionId, projection}. New /login page (login+register toggle); unauthenticated → client redirect to /login.
- Vitest (dev deps pinned: vitest ^3, @vitejs/plugin-react ^5, jsdom ^26, @testing-library/react ^16, jest-dom ^6; `test: vitest run`): SavingsGraph math/format; TaxReport `{session_id}` body regression + tiles + error banner; ChatInterface send/bootstrap/error paths; api.ts credentials/401/URL resolution.
- Playwright (chromium-only, retries 1, trace retain-on-failure, cached browsers): auth.spec (register→login→chat→report→logout→redirect), session.spec (Sprint-2 journey via `{session_id}`), protected.spec (401s). CI: e2e job with cached browsers.
- Playwright-MCP acceptance protocol (this sprint): root→/login redirect; register; 1-click SDE demo; network payload has session_id and no session dict; logout redirect; /health ok; /docs absent in prod; screenshots into release notes.

## 7. Observability (Objective F)

Structured JSON logs (timestamp/level/logger/message/request_id/user_id/path/status/duration_ms; request-ID middleware + contextvars filter; never tokens/bodies); app logs `logs/app/app.jsonl` reusing audit rotation helpers (`TAX_APP_LOG_*`); /health detail levels; engine failure → logger.exception + graceful `tax_report: null` (replaces print); `docs/backup-recovery.md` (SQLite `VACUUM INTO` backup script `backend/tools/backup_db.py`; JSONL whole-file copies rotation-aware; retention interplay; recovery runbook).

## 8. Sprint 4 AI modernization (planning only)

`Sprint4_AI_Modernization.md`: dataset strategy (labeled corpus from blackbox JSONL + synthetic augmentation; template-based splits; DPDP constraints on stored text); model candidates (in-paradigm improvements; small local intent classifier as extractor with deterministic guardrail; LLM-assisted behind flag — ADR-001 stands); evaluation framework (per-category P/R ≥95% targets, corpus as CI eval, drift replay); confidence scoring (margin/entropy, abstain-and-ask below threshold); explainability (span attribution, rule-ID traceability). No ANFIS/NLP redesign this sprint.

## 9. Build order + gates (tests-first red → implement → full suite green → parity/corpus untouched → commit → CI)

| Step | Scope |
|---|---|
| A | create_app factory + env plumbing + api.ts (no contract change yet) + docs gating |
| B | CORS allowlist + rate_limit.py + body cap + headers + origin check + /health + test_health + test_hardening |
| C | db.py + auth.py + /auth/* + lockout + auth rate limits + test_auth |
| D | app_sessions + POST /sessions + contract swap + ownership + history flip + audit user_id + mechanical test adaptation (grep inventory first) |
| E | frontend wiring + /login + Vitest suite |
| F | Dockerfiles + compose + deployment/backup-recovery docs + ADR-012/013/014 |
| G | Playwright suite + CI e2e job |
| H | structured logs + request IDs + app-log rotation + backup tooling + test_observability |
| I | Sprint4_AI_Modernization.md |
| Cert | security checklist re-verification (survive/supersede-with-rationale) + regression guard + re-score |

## 10. Regression guard

Engine/NLP/parity/corpus/FY-matrix/HRA/CG/deduction/audit-internal tests are **unaffected by design** (they call functions, not the wire). Mechanical adaptation scope: test_api/test_validation/test_session_security (~40-70 tests) — authed_client + make_session fixtures, `{session_id}` bodies, projection assertions, ownership rows. Grep inventory (`"session":`, `"/calculate"`) committed at Step D start. Sprint 1+2 checklist disposition: survives unchanged (bounds, sanitization, append-only audit + rotation, handlers, pinning) or superseded-with-rationale (CORS wildcard → allowlist; history default on; 127.0.0.1 bind → container boundary).

## 11. Validation checklist

- Wire contains session_id, never a session dict (grep + Playwright network assertion) · unauth → 401, foreign history → 404, demo never unlocks history · cookie HttpOnly/Secure-prod/Lax/__Host-; token sha256-at-rest; revoke same-cycle; absolute cap · CSRF cross-site POST → 403 · scrypt params in stored strings; 12-1024 policy; timing smoke · **no new runtime dependency** · CORS fail-closed, no wildcard, credentials=True · 429 + Retry-After; /health exempt · 413 >1MB; headers on every response; /docs 404 in prod · /health 200/503 semantics; verbose dev-only · audit envs honored; user_id additive; concurrency/corrupt tests green; blackbox contract intact · compose up → register→chat→report E2E; volumes survive down/up · Vitest + Playwright green in CI; MCP acceptance protocol with screenshots · regression: 776 + 97/97 + parity + corpus after adaptation · ADR-012/013/014 + CHANGELOG breaking entry + docs updated + Sprint4_AI_Modernization.md drafted.

## 12. Top risks

D contract-swap regression surface (High → grep inventory + mechanical adaptation + projection preserves frontend keys) · SQLite contention (High → 1 worker, WAL, short txns) · scrypt DoS on /auth (Medium → strict rate limits + lockout) · CORS/credentials misconfig (Medium → fail-closed prod) · Playwright flakiness (Medium → chromium-only, retries, cache) · rate-limit NAT false positives (Low → per-user keys).

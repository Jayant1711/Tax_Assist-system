# API Reference

> Refreshed 2026-11-01 for the Sprint 3 contract (Waves C+D+H). Backend entry point: `backend/main.py` via `create_app(app_env)`; dev run: `cd backend && python main.py` (Uvicorn on `127.0.0.1:8000`, `/docs` enabled). Production: container CMD, `/docs` disabled (see [deployment.md](deployment.md)).
>
> **All data endpoints are authenticated** (HttpOnly cookie sessions, ADR-012) and operate on **server-side session state** (ADR-013): the client carries only a `session_id`, never a session dict. Hardening posture (CORS allowlist, rate limits, security headers): [decisions.md](decisions.md) ADR-014. Threat model: [security.md](security.md).

## Conventions

- **Session cookie** (`ta_session` / `__Host-ta_session` in prod): opaque 256-bit token, HttpOnly, SameSite=Lax, Secure in prod. Send with `credentials: "include"` (the frontend's `apiFetch` does). Send `Content-Type: application/json` for POSTs — JSON-only bodies on state-changing routes.
- **`X-Request-ID`** is on every response (Wave H): a fresh uuid4 hex per request, echoed in the structured logs — quote it when reporting server issues.
- **Auth errors:** a missing/expired/revoked/forged cookie on a protected endpoint → `401 {"detail": "Authentication required"}` (uniform; never a validity oracle — `/auth/logout` still 204s). A **foreign or unknown** app-session id → `404 {"detail": "Session not found"}` (no existence oracle).
- **Rate limits** (sliding windows): `/auth/*` 10/min/IP · `/chat` + `/sessions*` 30/min/user · `/calculate` 60/min/user · aggregate 120/min/IP. Exceeded → `429 {"detail", "retry_after_seconds"}` + `Retry-After` header. `/health` is exempt.
- **Bodies** over `TAX_MAX_BODY_BYTES` (1 MB) → `413`. Malformed/oversized fields → `422 {"detail": "Validation error", "errors": [...]}` (loc/msg/type only, input never echoed).
- **Cross-site browser POSTs** with a non-allowlisted `Origin` → `403 {"detail": "Origin not allowed"}` (CSRF posture; curl/same-origin without an Origin header pass).

## Endpoints at a glance

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/auth/register` | none | Create account (scrypt) — 201 `{user_id, email}`, 409 duplicate |
| `POST` | `/auth/login` | none | 200 `{user_id, email}` + session cookie; uniform 401; 423 locked |
| `POST` | `/auth/logout` | none required | 204 — revokes the presented session, clears cookie |
| `GET` | `/auth/me` | cookie | 200 `{user_id, email, expires_at}` / 401 |
| `GET` | `/auth/sessions` | cookie | The caller's active auth sessions |
| `DELETE` | `/auth/sessions/{row_id}` | cookie | Revoke one (owner-checked, 404 otherwise) |
| `POST` | `/sessions` | cookie (demo: opt-in) | Bootstrap one server-side app session |
| `GET` | `/sessions` | cookie | List the caller's app sessions |
| `GET` | `/sessions/{session_id}` | cookie + owner | Read-only projection of the state |
| `DELETE` | `/sessions/{session_id}` | cookie + owner | Delete one app session |
| `POST` | `/chat` | cookie (demo: opt-in) | Conversational turn `{message, session_id}` |
| `POST` | `/calculate` | cookie (demo: opt-in) | Full report `{session_id, tax_year?}` |
| `GET` | `/history/{sid}` | cookie + owner | Paginated audit entries for an OWNED session |
| `GET` | `/health` | none (exempt) | 200 ok / 503 degraded liveness probe |

`/docs`, `/redoc`, `/openapi.json` exist in dev only — 404 in prod.

---

## Auth endpoints (ADR-012)

### `POST /auth/register`

```json
{ "email": "user@example.com", "password": "correct horse battery staple" }
```

- `201 {"user_id": "<uuid>", "email": "..."}`; `409 {"detail": "Email already registered"}` (case-insensitive); `422` invalid email / password outside 12–1024 chars. Auth events are audited with sha256[:16] correlation hashes only (never raw emails/tokens/passwords).

### `POST /auth/login`

- `200 {"user_id", "email"}` + `Set-Cookie` on success.
- `401 {"detail": "Invalid email or password"}` — uniform for unknown email AND wrong password (dummy-scrypt timing equalization; no enumeration oracle).
- `423 {"detail": "Account temporarily locked"}` — shown only for a CORRECT password after 5 failures within 15 minutes.

### `POST /auth/logout`

`204`, idempotent: revokes the presented session row and clears the cookie. Deliberately NOT behind the auth dependency — a stale/garbage cookie still gets the clean 204 (never a session-validity oracle).

### `GET /auth/me` · `GET /auth/sessions` · `DELETE /auth/sessions/{row_id}`

`/auth/me` → `{user_id, email, expires_at}`. `/auth/sessions` → rows identified by a 12-hex prefix of the hashed token (`current: true` marks the caller's), never the token material. `DELETE .../{row_id}` revokes one of the caller's sessions (owner-checked; 404 otherwise).

---

## App sessions + conversation (ADR-013)

### `POST /sessions` — bootstrap

`200 {"session_id": "<server-uuid-hex>", "session": {"id", "phase": "PROFILING"}}` — the `session` value is the read-only PROJECTION of the bootstrap state (internal `history` is not projected). Under `TAX_ENABLE_ANON_DEMO=1` a cookie-less caller creates a user-less session (never usable with `/history`).

### `POST /chat`

Request (the client-authored `session` dict is GONE from the wire):

```json
{ "message": "I am a software engineer earning 18 LPA", "session_id": "<server-issued id>" }
```

| Field | Type | Notes |
|---|---|---|
| `message` | `str` | ≤ 4000 chars (422 above); same NLP semantics as always ([nlp-pipeline.md](nlp-pipeline.md)) |
| `session_id` | `str` | A session THIS USER owns (POST /sessions first); foreign/unknown → 404 |

An old-style body containing `session` → `422 {"detail": "Validation error", ...}` with the migration hint "Session state is now server-side; send session_id".

Processing: load OWNED state → `nlp.process_message(message, state)` (unchanged) → engine **only if** any of `salary`/`business`/`rental`/`other_income`/`agriculture` > 0 → re-validate the mutated state (fail-closed 422 on validator regression) → persist → audit (background) + blackbox (synchronous).

Response — 200:

```json
{
  "response": "✅ Mapped — SALARY: ₹1,800,000. 💰 **Section 80C** — …",
  "session_id": "<id>",
  "session": { "id": "<id>", "phase": "PROFILING", "salary": 1800000.0, "…": "…" },
  "extracted": ["SALARY: ₹1,800,000"],
  "plan": "Ask about Section 80C investments …",
  "tax_report": null
}
```

| Field | Notes |
|---|---|
| `session` | READ-ONLY projection: `history`, `_last_question`, `_last_val`, `_prev_salary`, `memory` dropped; every frontend key kept (`id`, `phase`, `profile`, incomes, deductions, flags). The client cannot write state back |
| `tax_report` | `null` when no income yet OR when the engine raised — a calculation failure degrades gracefully and logs `logger.exception` server-side with the request id + session-id hash (never in the response) |

Errors: `401` no/invalid cookie · `404` foreign/unknown session · `422` validation (legacy body, oversized message, rejected state) · `429` rate limit.

### `POST /calculate`

Request `{ "session_id": "<id>", "tax_year": "fy_2025_26"? }` — computes the full report from the OWNED server-side state. `tax_year` (ADR-008) overrides the state's pin, else the registry default; an unregistered value → 422.

Response — 200: the dual-regime statement (unchanged shape — `old_regime`/`new_regime` `TaxResult` nodes with `income_details`, `deduction_details`, `explanations`, `slabs_breakdown`, plus top-level `recommendation`, `savings`, `efficiency_score`; documented field-by-field in [tax-rules.md](tax-rules.md) §2). Any engine exception → the global handler logs it (with request id) and returns `500 {"detail": "Internal server error"}` — no stack traces in the body, ever.

### `GET /sessions` · `GET /sessions/{session_id}` · `DELETE /sessions/{session_id}`

List (id + timestamps, newest use first) · owned projection · owner-checked delete (204 / 404).

---

## `GET /history/{sid}` — paginated, owned

Returns audit entries for an **owned** session from the append-only global stream `logs/audit/session_audit.jsonl`. Requires an authenticated user whose `app_sessions` row matches `sid`; foreign/unknown → `404 {"detail": "Session not found"}` (same as every ownership miss); unauthenticated → `401`; the `TAX_ENABLE_HISTORY=0` kill-switch → `404` (never reveals existence).

Query params: `limit` (1–200, default 50), `offset` (default 0).

Response — 200:

```json
{
  "entries": [
    {
      "timestamp": "2026-11-01T12:00:00.000000",
      "session_id": "…",
      "event": "chat_turn",
      "user_input": { "stored": false, "sha256_16": "…", "char_length": 34 },
      "ai_response": { "stored": false, "sha256_16": "…", "char_length": 220 },
      "extracted": ["SALARY: ₹1,800,000"],
      "internal_state": { "profile": "Salaried", "salary": 1800000.0 },
      "tax_calculation": { "old_regime": { "total_tax": 289770.0 }, "…": "…" },
      "user_id": "<owner uuid>"
    }
  ],
  "corrupt_lines_skipped": 0,
  "has_more": false
}
```

PII note: `user_input`/`ai_response` are correlation records (sha256[:16] + char length) unless `TAX_AUDIT_STORE_TEXT` opted in server-side; `internal_state` is scrubbed of the internal keys. `user_id` is the additive Wave D owner field. Read-only legacy fallback: if the JSONL stream is absent but `logs/session_audit.json` exists, it is served (unpaginated legacy entries).

## `GET /health`

```json
{ "status": "ok", "checks": { "db": "ok", "audit": "ok" }, "app_env": "prod", "version": "0.3.0" }
```

- `db`: `SELECT 1` against `TAX_DB_PATH` (mode=rw — never creates the file) + dir write permission.
- `audit`: `logs/audit` dir writable.
- Any failing check → `503` with `"status": "degraded"` and the failing check named. `?verbose=1` adds uptime + registry keys in dev only. Unauthenticated, rate-limit exempt; this is the Docker HEALTHCHECK target.

---

## Worked curl examples (Windows cmd style)

```bash
:: 0. Register + login (cookie jar)
curl -c jar -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" ^
  -d "{\"email\":\"demo@example.com\",\"password\":\"correct horse battery staple\"}"
curl -c jar -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" ^
  -d "{\"email\":\"demo@example.com\",\"password\":\"correct horse battery staple\"}"

:: 1. Bootstrap a server-side session
curl -b jar -X POST http://localhost:8000/sessions
:: -> {"session_id":"<sid>","session":{"id":"<sid>","phase":"PROFILING"}}

:: 2. Chat (server state mutates; the response `session` is read-only)
curl -b jar -X POST http://localhost:8000/chat -H "Content-Type: application/json" ^
  -d "{\"message\":\"I am a software engineer earning 18 LPA\",\"session_id\":\"<sid>\"}"
curl -b jar -X POST http://localhost:8000/chat -H "Content-Type: application/json" ^
  -d "{\"message\":\"1.5 lakhs in PPF\",\"session_id\":\"<sid>\"}"
curl -b jar -X POST http://localhost:8000/chat -H "Content-Type: application/json" ^
  -d "{\"message\":\"/end\",\"session_id\":\"<sid>\"}"

:: 3. Full report from server-side state
curl -b jar -X POST http://localhost:8000/calculate -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"<sid>\"}"

:: 4. Audit trail for YOUR session (paginated)
curl -b jar "http://localhost:8000/history/<sid>?limit=50&offset=0"

:: 5. Health
curl http://localhost:8000/health
```

## Environment variables

Runtime (backend, read at call time; defaults on absent/invalid): `APP_ENV`, `CORS_ORIGINS`, `TAX_DB_PATH`, `TAX_HOST`/`TAX_PORT`, `TAX_SESSION_TTL_MINUTES`, `TAX_SESSION_ABS_TTL_HOURS`, `TAX_COOKIE_SECURE`, `TAX_ENABLE_ANON_DEMO`, `TAX_ENABLE_HISTORY`, `TAX_AUDIT_MAX_BYTES`/`_MAX_FILES`/`_RETENTION_DAYS`/`_STORE_TEXT`, `TAX_RATE_LIMIT_AUTH|CHAT|CALC|GLOBAL_PER_MIN`, `TAX_MAX_BODY_BYTES`, `TAX_LOG_LEVEL`, `TAX_APP_LOG_MAX_BYTES`/`_MAX_FILES`/`_RETENTION_DAYS`. Build-time (frontend): `NEXT_PUBLIC_API_URL`. Full table with container paths: [deployment.md](deployment.md) §3. No signing secret exists.

## Known limitations

- **Double annualization trap** (unchanged NLP semantics): `"my salary is 80,000 per month"` annualizes twice → `salary = 11,520,000` ([nlp-pipeline.md](nlp-pipeline.md) §11).
- **Rate limits are per-process** (in-memory) — valid under the documented single-worker deployment only.
- **`/history` reads the whole global stream** per request (line-scan, corrupted lines skipped and counted); latency grows with total stream size.
- **Anonymous demo sessions are ephemeral by design** — user-less rows are invisible to `/history` and to authenticated callers even with the demo flag on.

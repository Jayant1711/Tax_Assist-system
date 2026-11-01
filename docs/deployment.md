# Deployment Guide

> Rewritten 2026-11-01 for the Sprint 3 Wave F stack (Dockerfiles, compose, hardening edge, health checks). Statuses cite [decisions.md](decisions.md) ADR-012/013/014; the API contract lives in [api-reference.md](api-reference.md); backup/recovery in [backup-recovery.md](backup-recovery.md).

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker + Compose v2 | any current | The documented production deployment unit |
| Python | 3.10+ (image uses 3.12-slim) | Only for bare-metal dev runs; NumPy required (ANFIS) |
| Node.js | 20 (image uses node:20-alpine) | Only for bare-metal frontend dev; Next.js 16 |
| Reverse proxy with TLS | nginx / Caddy / traefik / any | Terminates HTTPS, routes to loopback ports |

## 2. Files in the stack

| File | Purpose |
|---|---|
| `backend/Dockerfile` | python:3.12-slim, pinned `requirements.txt`, non-root uid 10001, `HEALTHCHECK` (stdlib urllib probe of `/health`), **one uvicorn worker** (see §6) |
| `frontend/Dockerfile` | node:20-alpine multi-stage (deps → build → runner); `NEXT_PUBLIC_API_URL` build arg; non-root uid 10001; `npm run start` |
| `docker-compose.yml` | backend + frontend on host loopback only; named volumes `db-data` + `logs-data`; healthcheck + `depends_on: service_healthy`; restart unless-stopped |
| `.env.example` | Every env var of the design §5 inventory, with comments — copy to `.env` and fill in |

## 3. Environment inventory (Sprint 3 design §5)

All backend variables are read at call time; an absent/blank/invalid value falls back to the documented default with a logged warning (`config.py`, `audit_logger.py`, `observability.py`).

| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `dev` | `prod` enables the production posture (docs/redoc/openapi off, Secure cookies, CORS fail-closed). Only the exact value `prod` counts |
| `CORS_ORIGINS` | dev: `http://localhost:3000` | Comma-separated exact browser origins. **Prod fails closed**: unset/empty/`*` raises at the point of use — no origin is trusted |
| `TAX_DB_PATH` | `data/taxassist.db` | SQLite store (users, auth sessions, app sessions). Container: `/app/data/taxassist.db` (volume `db-data`) |
| `TAX_HOST` / `TAX_PORT` | `127.0.0.1` / `8000` | Bind address of the `python main.py` dev entry. The container CMD binds `0.0.0.0` explicitly (dev bind safety only applies to the bare entry) |
| `TAX_SESSION_TTL_MINUTES` | `30` | Sliding session TTL (ADR-012) |
| `TAX_SESSION_ABS_TTL_HOURS` | `24` | Absolute session cap |
| `TAX_COOKIE_SECURE` | `APP_ENV=prod` | Force/clear the Secure flag; `__Host-` cookie prefix in prod |
| `TAX_ENABLE_ANON_DEMO` | off | Deny-by-default anonymous demo (`/chat` + `/calculate` only, never `/history`) |
| `TAX_ENABLE_HISTORY` | **on** | `/history` kill-switch (C5 is closed by auth + ownership; this is an emergency shutoff only) |
| `TAX_AUDIT_MAX_BYTES` | `10000000` | Audit stream rotation threshold |
| `TAX_AUDIT_MAX_FILES` | `5` | Rotated audit generations kept |
| `TAX_AUDIT_RETENTION_DAYS` | `30` | Sweeps rotated audit generations only; the active file is never deleted |
| `TAX_AUDIT_STORE_TEXT` | off | DPDP opt-in: keep first 512 chars of raw user/AI text (default: sha256[:16] correlation hashes only) |
| `TAX_RATE_LIMIT_AUTH_PER_MIN` | `10` | `/auth/*` per IP |
| `TAX_RATE_LIMIT_CHAT_PER_MIN` | `30` | `/chat` + `/sessions*` per user |
| `TAX_RATE_LIMIT_CALC_PER_MIN` | `60` | `/calculate` per user |
| `TAX_RATE_LIMIT_GLOBAL_PER_MIN` | `120` | Aggregate per IP |
| `TAX_MAX_BODY_BYTES` | `1000000` | 413 above this Content-Length |
| `TAX_LOG_LEVEL` | `INFO` | Root log level (`DEBUG|INFO|WARNING|ERROR|CRITICAL`) |
| `TAX_APP_LOG_MAX_BYTES` / `TAX_APP_LOG_MAX_FILES` / `TAX_APP_LOG_RETENTION_DAYS` | `10000000` / `5` / `30` | App-log (`logs/app/app.jsonl`) rotation/retention — same mechanics as the audit stream (Wave H) |
| `NEXT_PUBLIC_API_URL` | `""` | **Build arg, not runtime.** Browser-reachable API base URL baked into the client bundle. `""` = single-origin prod; `http://localhost:8000` = dev; `https://api.your-app.example` = split-host prod |

No signing secret exists (ADR-012): session tokens are opaque 256-bit random values stored only as sha256.

## 4. Production startup (compose)

```bash
cp .env.example .env          # then edit:
#   CORS_ORIGINS=https://your-app.example   (exact browser origin, required in prod)
#   TAX_COOKIE_SECURE=1                     (HTTPS terminates at the proxy)
#   NEXT_PUBLIC_API_URL=                    ("" for single-origin, see §5)

docker compose up -d --build
docker compose ps             # backend -> healthy before frontend starts
curl http://127.0.0.1:8000/health
```

- Backend listens on `127.0.0.1:8000`, frontend on `127.0.0.1:3000` — both loopback-only; the reverse proxy is the only public entry.
- State: named volumes `db-data` → `/app/data` (SQLite), `logs-data` → `/app/logs` (audit + app + blackbox JSONL). They survive `docker compose down`; they do NOT survive `down -v`. Back up with `backend/tools/backup_db.py` ([backup-recovery.md](backup-recovery.md)).
- The backend container reports `healthy` only while `GET /health` returns 200 (a 503 degraded state marks it unhealthy); the frontend waits for `backend: condition: service_healthy`.
- `.env` is gitignored — never commit it. A missing `.env` fails `docker compose up` because `env_file: .env` is required.

## 5. Reverse-proxy / TLS topology

```text
[Browser] ──HTTPS──> [Reverse proxy]          # TLS, HSTS, access logging
                         │  /             \
                         │ /               \
                         v                  v
              127.0.0.1:3000 frontend    127.0.0.1:8000 backend
```

- **Single-origin production (recommended):** the proxy serves the frontend at `/` and proxies the API (e.g. `/api/*` or `api.your-app.example`) to the backend. Build the frontend with `NEXT_PUBLIC_API_URL=""` so `apiFetch` uses same-origin relative URLs (`frontend/src/lib/api.ts`, ADR-010) — no cross-origin cookies, no preflights, the CSRF origin-check allowlist has exactly one entry.
- **Split-host production:** set `NEXT_PUBLIC_API_URL=https://api.your-app.example` (rebuild the frontend image) and add both origins to `CORS_ORIGINS`. The session cookie is `__Host-ta_session` (Secure, SameSite=Lax, Path=/) — cookies do not cross sites, so both hostnames must share a registrable domain and the proxy must serve the API on the SAME site as the frontend for the cookie to ride along. Single-origin avoids this class of misconfiguration entirely.
- Proxy guidance: forward `Host` and `X-Forwarded-For`; do NOT strip `Origin`/`Referer` (the backend's CSRF origin-check middleware validates them on state-changing routes); terminate TLS 1.2+; keep client_max_body_size ≥ `TAX_MAX_BODY_BYTES`.
- The backend must never be published to a public interface directly — ports are pinned to `127.0.0.1` in compose and TLS is exclusively the proxy's job (ADR-014).

## 6. Why exactly ONE uvicorn worker

The Dockerfile CMD is `python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1` — **this is a documented correctness requirement, not a placeholder**:

1. The append-only audit stream serializes every write through a **process-wide `threading.Lock`** (`audit_logger.py`) — with multiple workers there are multiple processes, each with its own lock, and `os.append` line atomicity is the only remaining guard.
2. The SQLite store (`db.py`) relies on single-process access + WAL. Multi-process SQLite works, but the session/lockout/revocation semantics were designed and tested for one writer.
3. The in-memory rate limiter (`rate_limit.py`) is per-process — N workers would multiply every limit by N.
4. Rotation/retention of the JSONL streams is best-effort under the lock; concurrent rotators across processes would fight over `os.replace`.

Scale by adding whole containers behind the proxy load-balancing at L4 only if you first migrate the store/audit to a shared backend (out of scope for Sprint 3).

## 7. `GET /health` semantics

Public, unauthenticated, rate-limit-exempt (design §3):

- `200 {"status":"ok","checks":{"db":"ok","audit":"ok"},"app_env","version"}` when every check passes.
- `db`: `SELECT 1` against `TAX_DB_PATH` (opened `mode=rw` — it NEVER creates the file) + data-dir write permission.
- `audit`: `logs/audit` dir exists and is writable.
- Any failing check → `503` with the failing check named (`"status":"degraded"`), which the Docker/Compose healthcheck reports as `unhealthy`.
- `?verbose=1` adds uptime + registry keys **in dev only** (never in prod responses).

## 8. Hardening edge summary (ADR-014)

- **CORS:** explicit allowlist + `allow_credentials=True`; prod fails closed on unset/`*` — the Sprint-1 wildcard is retired permanently.
- **CSRF (no token):** SameSite=Lax + JSON-only bodies + Origin/Referer validation middleware (403 on mismatch) + credentials-forcing CORS.
- **Rate limits:** sliding windows per IP/user; `429 {"detail","retry_after_seconds"}` + `Retry-After`; `/health` exempt. Per-process only — one worker (§6).
- **Body cap:** 413 over `TAX_MAX_BODY_BYTES` (1 MB default).
- **Security headers** on every response (including 413/403/429): nosniff, DENY, strict-origin-when-cross-origin, no-store, `default-src 'none'; frame-ancestors 'none'`, permissions lock-down.
- **App factory:** `create_app(app_env)` — prod disables `/docs`, `/redoc`, `/openapi.json`.
- **Observability (Wave H):** request-ID middleware (`X-Request-ID` response header), structured JSON logs, app-log rotation — see [security.md](security.md) §5 and the in-code docstrings.

## 9. Auth endpoints summary (ADR-012/013)

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /auth/register` | none | 201 `{user_id, email}`; 409 duplicate; 422 policy (12–1024 chars) |
| `POST /auth/login` | none | 200 + HttpOnly cookie; uniform 401 (timing-equalized); 423 locked (5 fails / 15 min) |
| `POST /auth/logout` | none required | 204, revokes the presented session, clears cookie (never a validity oracle) |
| `GET /auth/me` | cookie | 200 `{user_id, email, expires_at}` / 401 |
| `GET /auth/sessions` | cookie | Active session rows (hashed-token 12-hex prefixes) |
| `DELETE /auth/sessions/{id}` | cookie | Owner-checked revoke; 404 otherwise |
| `POST /sessions` | cookie (or demo) | Server-issued app-session id |
| `POST /chat`, `POST /calculate` | cookie (or demo) | `{message, session_id}` / `{session_id, tax_year?}` — state is server-side (ADR-013) |
| `GET /history/{sid}` | cookie + owner | Paginated audit entries; foreign/unknown → 404 |

Rate limits: `/auth/*` 10/min/IP, `/chat`+`/sessions` 30/min/user, `/calculate` 60/min/user, global 120/min/IP.

## 10. Local development (bare metal)

```bash
# backend
cd backend
python -m venv .venv && .venv\Scripts\activate   # POSIX: source .venv/bin/activate
pip install -r requirements.txt
python main.py                                   # 127.0.0.1:8000, /docs enabled

# frontend
cd frontend
npm install
npm run dev                                      # http://localhost:3000 (dev default CORS origin)
```

- Dev keeps `/docs` (interactive API docs) enabled; prod disables them.
- A pre-trained `backend/anfis_weights.json` is committed — training is only needed if you change the feature vector (20 inputs × 64 rules); if weights are regenerated with different dimensions, startup crashes at reshape.
- Do not run `anfis_refine.py` against those weights (10×50 vs 20×64 topology mismatch — dead code).
- Container-based local run: `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env`, then `docker compose up -d --build`.

## 11. Validation smoke (post-deploy)

```bash
# 1. health
curl http://127.0.0.1:8000/health

# 2. register + login (cookie jar), chat, report
curl -c jar -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" ^
  -d "{\"email\":\"ops@your-app.example\",\"password\":\"deploy-smoke-passphrase\"}"
curl -c jar -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" ^
  -d "{\"email\":\"ops@your-app.example\",\"password\":\"deploy-smoke-passphrase\"}"
curl -b jar -X POST http://127.0.0.1:8000/sessions
# -> use the returned session_id in /chat {\"message\":\"...\",\"session_id\":\"...\"}

# 3. prod disables docs
curl -s -o NUL -w "%{http_code}" http://127.0.0.1:8000/docs        # 404 in prod

# 4. headers + request id on every response
curl -s -D - -o NUL http://127.0.0.1:8000/health | findstr /i "X-Request-ID X-Frame-Options"
```

The full compose E2E smoke (register → chat → report → volumes survive down/up) runs in the Sprint 3 certification step on a Docker-capable host.

## 12. Runtime artifacts

| Artifact | Path (container) | Written by | Notes |
|---|---|---|---|
| SQLite store | `/app/data/taxassist.db` (volume `db-data`) | `db.py` | users, auth_sessions, app_sessions; WAL |
| Audit stream | `/app/logs/audit/session_audit.jsonl(.N)` (volume `logs-data`) | `audit_logger.py` | Append-only JSONL; PII-minimized |
| Blackbox | `/app/logs/blackbox/<sid>.jsonl` (volume `logs-data`) | `session_lab.py` | Per-session append-only JSONL |
| App log | `/app/logs/app/app.jsonl(.N)` (volume `logs-data`) | `observability.py` | Structured JSON log (Wave H) |

All three JSONL families are covered by the backup tool: `python tools/backup_db.py --out-dir /backups` ([backup-recovery.md](backup-recovery.md)).

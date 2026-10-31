# Architecture Decision Records

Format: lightweight ADRs. **Status:** Accepted / Superseded / Proposed.
ADRs 001-007 document decisions already embodied in the code; ADRs 008-011 were proposed by the 2026-10-31 audit and tracked in [roadmap.md](roadmap.md); ADRs 012-014 record the Sprint 3 production-platform decisions (auth, server-side sessions, edge hardening).

---

## ADR-001 — Deterministic rule-based tax engine (no ML in the calculation path)

**Status:** Accepted
**Date:** project origin (pre-2026-04)

**Context:** Tax output feeds real filing decisions. A wrong slab or an ineligible deduction produces incorrect filings; probabilistic output is unacceptable for the core computation.

**Decision:** Tax liability is computed exclusively by deterministic rules (`backend/tax_engine.py`). Machine learning (ANFIS) is confined to a subjective "efficiency score" that never alters tax amounts.

**Consequences:** ✅ Reproducible, testable, explainable output. ❌ Every FY change is manual code work (see ADR-008); the ML layer's value is cosmetic until its ground truth matches the engine (W4 in [architecture.md](architecture.md#5-known-architectural-weaknesses-audit-2026-10-31)).

---

## ADR-002 — Client-owned session state

**Status:** Superseded by [ADR-013](#adr-013--server-side-session-state-sqlite-app_sessions) (Sprint 3 Wave D; the `app_sessions` store + `session_id` contract swap removed client-owned state entirely)
**Date:** project origin

**Context:** The chat frontend needs conversation continuity without a backend session store.

**Decision:** The entire session dict (income, deductions, internal keys like `_last_val`, `phase`, full `history[]`) is stored in React state and round-tripped on every request; the server keeps nothing (`backend/main.py:29-32`, `frontend/src/components/ChatInterface.tsx:148-152`).

**Consequences:** ✅ Zero server-side session infrastructure; trivial horizontal scale of compute. ❌ State is tamperable (client can forge `salary`, `phase`, `_last_val`); payloads grow unbounded; no multi-device; server logic depends on untrusted input. Security implications: [security implications in roadmap C5/H5].

---

## ADR-003 — Regex NLP + keyword-proximity semantic attention (no LLM)

**Status:** Accepted
**Date:** project origin

**Context:** The product must extract financial entities from free text (English + Hinglish) without external API cost or latency.

**Decision:** Hand-built `UniversalParser` (Indian money formats, word numbers) + `SemanticAttention` (keyword presence × Gaussian proximity decay × content score, profile-locked penalties) + a scripted discovery waterfall (`backend/ai_models.py`, `backend/nlp_engine.py`).

**Consequences:** ✅ Free, fast, deterministic, runs offline. ❌ Precision ceiling reached in practice — the repo's own logs show systematic misclassifications (education-loan interest → income; tuition → salary; property sale → other income) recorded in `backend/logs/session_audit.json` and tracked as finding C4. Improve within this paradigm (more tests, better keyword tables) before considering an LLM extractor.

---

## ADR-004 — ANFIS neuro-fuzzy efficiency scoring

**Status:** Accepted — quality concerns logged
**Date:** 2026-04 (ANFIS v3/v4 iterations)

**Context:** The product wants a single 0-100 "how optimized is this taxpayer" metric to visualize.

**Decision:** A 20-input × 64-rule TSK ANFIS (`backend/ai_models.py:459-545`) trained offline by `anfis_trainer.py` (EE-Bat search over synthetic scenarios) and shipped as `anfis_weights.json`.

**Consequences:** ✅ Works offline at inference (tiny numpy forward pass); deterministic fallback heuristic exists when numpy is absent. ❌ Training ground truth diverges from the live engine's math (HRA, surcharge bands differ — `anfis_trainer.py` vs `tax_engine.py:316-321,283-292`), so the advertised R²=0.88 is measured against the wrong target; the refiner `anfis_refine.py` is dimensionally incompatible (10×50 vs 20×64) and broken; weights are reshaped without validation at import (`ai_models.py:482-485`). Re-train against live-engine outputs or park the score behind a "beta" label (roadmap Week 4).

---

## ADR-005 — File-based JSON persistence for audit trails

**Status:** Accepted — **flagged for replacement (see ADR-009)**
**Date:** project origin

**Context:** Compliance instinct: record every user-AI turn for auditability, with zero infra.

**Decision:** `AuditLogger` rewrites the whole `logs/session_audit.json` on each turn (`backend/audit_logger.py:24-35`); `SessionLab` rewrites per-session JSON (`backend/session_lab.py:22-46`).

**Consequences:** ✅ Human-readable, zero-dependency. ❌ O(n²) I/O growth; no file locking → concurrent requests lose entries; a read error silently resets history to `[]` and the rewrite **destroys the audit trail** — a direct violation of the repo's own "preserve audit logging" rule (`AGENTS.md`). Client-controlled `session.id` is joined into a filesystem path (`session_lab.py:22`) — arbitrary file write (Critical, roadmap C6).

---

## ADR-006 — FastAPI + Next.js App Router split

**Status:** Accepted
**Date:** project origin

**Context:** Python for the rules/AI layer; modern React for the consultant-style dashboard UX.

**Decision:** FastAPI monolith backend (port 8000), Next.js 16 App Router frontend (port 3000), JSON over HTTP, CORS `allow_origins=["*"]` (`main.py:18`).

**Consequences:** ✅ Clean separation matching `AGENTS.md`; independent deploys possible. ❌ Frontend hardcodes `http://localhost:8000` (`ChatInterface.tsx:148`, `TaxReport.tsx:24`) — not deployable as-is; the dashboard duplicates `/chat`'s calculation via `/calculate` (2× work per turn). Fix via ADR-010/ADR-011.

---

## ADR-007 (Proposed) — Move session state server-side

**Status:** Accepted (Sprint 3 Wave D — implemented as ADR-013 below, with SQLite `app_sessions` as the first store)

**Context:** ADR-002's client-owned state is the root of the forged-session and data-exposure findings (C5, H5).

**Decision (proposed):** Backend issues an opaque session ID (UUID) and stores state server-side (SQLite to start, Redis later); the client sends only `{session_id, message}`. `/history` becomes server-authenticated.

**Consequences:** ✅ Tamper-proof state, auth becomes possible, small payloads. ❌ Migration touches every component; adds storage ops. Client-session signing is the fallback if server-side state is rejected.

---

## ADR-008 (Proposed) — Versioned tax-rules registry

**Status:** Proposed (roadmap Week 2)

**Context:** FY constants are scattered across `tax_engine.py`, `anfis_trainer.py`, `test_suite.py`, and four frontend files (checklist in [tax-rules.md §6](tax-rules.md#6-rule-change-checklist-where-fy-constants-live)); the engine is currently one FY stale (Critical C1).

**Decision (proposed):** `backend/tax_rules/fy_2024_25.py`, `fy_2025_26.py`, … each exporting slabs, caps, rebate, surcharge, CG rates as data; `TaxEngine` selects by a `tax_year` parameter and reports which FY it used in every response.

**Consequences:** ✅ FY updates become data diffs; the UI can warn when computing on a stale year. ❌ One-time refactor of engine + trainer + tests.

---

## ADR-009 (Proposed) — Append-only audit persistence

**Status:** Proposed (roadmap Week 2)

**Decision (proposed):** Replace read-modify-write with append-only JSONL (one line per turn) or SQLite in WAL mode; never truncate on read error; add rotation and a retention policy; sanitize `session_id` to `^[w-]{8,64}$`.

**Consequences:** ✅ O(1) writes, no lost entries, audit trail survives corruption, closes the path-traversal hole.

---

## ADR-010 (Proposed) — Configurable API base URL

**Status:** Accepted (Sprint 3 Wave E: `frontend/src/lib/api.ts` resolves `NEXT_PUBLIC_API_URL ?? ""` and removes both hardcoded fetch sites; Sprint 3 Wave F bakes it as a frontend-image build arg — browser-reachable URL, `""` for single-origin prod)

**Decision (proposed):** `NEXT_PUBLIC_API_URL` env var (default `http://localhost:8000` for dev) consumed via a small `lib/api.ts`; remove both hardcoded fetch sites.

---

## ADR-011 (Proposed) — pytest + CI as the test harness

**Status:** Proposed (roadmap Week 1)

**Context:** The custom 97-check harness (`backend/test_suite.py`) has loose tolerances, cannot-fail smoke scripts (`backend/smoke_test.py:30,36,43` print `[PASS]` unconditionally), no API tests, and no CI.

**Decision (proposed):** Migrate to pytest; add FastAPI `TestClient` endpoint tests incl. malformed input and forged sessions; golden-file regression tests replaying the misclassified sentences from `backend/logs/session_audit.json`; GitHub Actions running pytest + `pip-audit` + `npm audit` + `next build`.

**Consequences:** ✅ CI-enforceable quality bar; IDE integration. ❌ One-time migration effort (~1 day).

---

## ADR-012 — Cookie-based auth sessions with scrypt passwords (no JWT, no secrets)

**Status:** Accepted (Sprint 3 Wave C)
**Date:** 2026-10-31 (planning review; implemented in Waves C+D)

**Context:** Sprint 3 Objective A needs real authentication for the now-server-side data (Objective B). Candidates: JWT (stateless), a hybrid JWT+store, or opaque tokens backed by a server-side session row. The stack is stdlib-first (Sprint 2 discipline), the sessions themselves are moving server-side (ADR-013), and revocation must be immediate (logout, password change, lockout).

**Decision:** HttpOnly-cookie server-side sessions with opaque random tokens, protected by `hashlib.scrypt` password hashing:

- **Passwords:** scrypt (`n=2^15, r=8, p=1, dklen=64`, 16-byte salt), stored as `scrypt$N$r$p$salt_b64$hash_b64`; verification via `hmac.compare_digest` with dummy-hash timing equalization for unknown emails; policy 12–1024 chars (NIST 800-63B style). Zero new dependencies.
- **Tokens:** `secrets.token_urlsafe(32)` (256-bit), stored ONLY as `sha256(token)` hex; sliding TTL (30 min) capped by an absolute TTL (24 h); revocation = row update; UA-hash mismatch invalidates, IP-hash is log-only.
- **Cookie:** `__Host-ta_session` in prod (Secure) else `ta_session`; HttpOnly always; SameSite=Lax; Path=/; Max-Age mirrors the TTL.
- **CSRF without a token:** SameSite=Lax + JSON-only bodies + Origin/Referer validation middleware on state-changing routes (403) + `allow_credentials=True` CORS forcing an explicit origin allowlist.
- **JWT rejected:** no revocation without a store anyway (which would negate its only advantage), adds PyJWT + signing-secret lifecycle for zero benefit. Hybrid rejected: doubles the theft surface and the test matrix.

**Consequences:** ✅ Immediate revocation (a row update — Objective B), no secret material exists anywhere in the system, one uniform auth path for password login and any future OAuth (reserved `auth_provider`/`oauth_subject` columns). ❌ Every request pays a SQLite row read (acceptable at this scale); horizontal scaling now requires a shared session store (single-worker deployment documented, [deployment.md](deployment.md) §6).

---

## ADR-013 — Server-side session state (SQLite `app_sessions`)

**Status:** Accepted (Sprint 3 Wave D) — **supersedes [ADR-002](#adr-002--client-owned-session-state)**
**Date:** 2026-10-31 (planning review; closes ADR-007/W1/C5/H5)

**Context:** ADR-002's client-owned session dict is the root of the forged-session and data-exposure findings (C5, H5, W1): every "server-side" decision actually ran on attacker-editable input, payloads grew unbounded, and no session could be authenticated. ADR-007 proposed the fix; Sprint 3 Objective B implements it.

**Decision:** The backend owns session state in SQLite (`TAX_DB_PATH`, WAL) table `app_sessions(id, user_id, state JSON ≤100KB, created_at, updated_at)`; the client sends only `{message, session_id}` (breaking contract swap, documented in CHANGELOG + [api-reference.md](api-reference.md)) and receives a READ-ONLY projection (internal keys `history`/`_last_*`/`memory` dropped; every frontend key preserved). Session ids are server-issued uuid4-hex. `/history/{sid}` requires auth + ownership (foreign/unknown → indistinguishable 404), so the Sprint-1 opt-in gate defaults ON. The Sprint-1+2 payload validator now defends the server-side load and persist boundaries (defense-in-depth — the only writer is NLP). Anonymous access is deny-by-default (`TAX_ENABLE_ANON_DEMO=1` opt-in, `/chat` + `/calculate` only, never `/history`).

**Consequences:** ✅ Tamper-proof state, authentication becomes meaningful (ADR-012 rows own the sessions), IDOR posture (opaque ids + ownership → 404), bounded payloads. ❌ Migration touched every component (one frontend, one deploy unit — no dual contract); SQLite is the scalability ceiling until a shared store replaces it.

---

## ADR-014 — Edge hardening: fail-closed CORS, rate limits, security headers

**Status:** Accepted (Sprint 3 Waves B+C)
**Date:** 2026-10-31 (planning review)

**Context:** The Sprint-1 edge was wide open: CORS `allow_origins=["*"]`, no rate limiting (the NLP layer is CPU-bound per message), unbounded bodies, no security headers, and Swagger UI exposed by default. Sprint 3 puts a session cookie (ADR-012) behind this edge, so the defaults had to change.

**Decision:**

- **CORS fail-closed:** `CORS_ORIGINS` comma-list + `allow_credentials=True`; in prod an unset/empty/wildcard `CORS_ORIGINS` raises at the point of use — the middleware then trusts NO origin. The Sprint-1 wildcard is retired permanently.
- **Rate limiting:** stdlib sliding-window limiter (`rate_limit.py`, lock-protected, LRU-capped keys): `/auth/*` 10/min/IP, `/chat` 30/min/user, `/calculate` 60/min/user, global 120/min/IP; `/health` exempt; `429` + `Retry-After`. Per-process only — consistent with the documented single-worker deployment.
- **Body cap:** middleware 413 over `TAX_MAX_BODY_BYTES` (1 MB) reading only Content-Length.
- **Security headers on every response** (including 413/403/429 short-circuits): nosniff, X-Frame-Options DENY, strict-origin-when-cross-origin, Cache-Control no-store, CSP `default-src 'none'; frame-ancestors 'none'`, Permissions-Policy camera/microphone/geolocation=().
- **App factory:** `create_app(app_env)` — prod disables `/docs`, `/redoc`, `/openapi.json`.
- **CSRF posture** (with ADR-012): SameSite=Lax + JSON-only bodies + Origin/Referer check on state-changing routes (403).

**Consequences:** ✅ A browser-origin allowlist the cookie can trust, bounded CPU-exhaustion, hardened responses on every path. ❌ NAT'd users share per-IP auth limits (mitigated: per-user keys for the authenticated buckets); misconfigured `CORS_ORIGINS` in prod is a hard outage by design — fail-closed is the point.


# Project Architecture Defense

**Project:** Tax Assist System × CSE472 "Deep Learning for NLP"
**Version:** v0.4-sprint3 | **Seed:** 472 | **Generated:** 2026-11-01

---

## Frontend Architecture

### Why Chosen: Next.js + React

The frontend is built with Next.js (React framework) providing server-side rendering, API routes, and static site generation. This choice enables:

- **SEO compatibility** for tax documentation pages that must be indexable
- **Incremental Static Regeneration** — tax rules pages can be regenerated on-demand without full rebuilds
- **API routes** co-located with pages, reducing context-switching for full-stack development
- **TypeScript support** for type safety across the full stack, critical for tax-formula correctness
- **Middleware support** for CORS, rate limiting, and authentication headers at the edge

### Alternatives Considered

| Alternative | Reason for Not Choosing |
|---|---|
| Create React App | No SSR, poorer SEO for tax content, additional config for API routing |
| Gatsby | Good for static content, but weaker for dynamic tax calculations requiring server state |
| Plain Flask + HTML templates | No component reusability, no type safety, harder CI/CD pipeline |

### Advantages

- Full-stack TypeScript: same type definitions shared between frontend and backend
- Next.js middleware enables ADR-012/ADR-013 session management directly at the edge
- Docker-ready: `next build && next start` fits the existing `docker-compose.yml` service model
- Middleware handles CORS fail-closed: in prod, unset CORS_ORIGINS causes 403 on cross-site state-changing requests

### Limitations

- Next.js learning curve for developers new to the framework
- `NEXT_PUBLIC_API_URL` baked at build time — changing backend host requires frontend rebuild
- Server-side rendering adds complexity to hydration debugging (stale manifest / auth/me 404 = missing env at build)

---

## Backend Architecture

### Why Chosen: Python FastAPI + SQLAlchemy

The backend runs on FastAPI (Python 3.15.2) with SQLAlchemy ORM over SQLite (development) / PostgreSQL (production). This choice enables:

- **FastAPI**: automatic OpenAPI  generation, type-validated request bodies, async endpoints
- **SQLAlchemy**: ORM that supports migration-aware schema (design §1 ADR-012, §2 ADR-013)
- **One dependency model**: `nlp_research` may import from `data/`, but `backend/` never imports `nlp_research` (one-way dependency, §5 design)
- **Session management**: ADR-012 (scrypt password hashing + HttpOnly cookie sessions) + ADR-013 (server-side sessions stored in `/app/data/taxassist.db`)

### Alternatives Considered

| Alternative | Reason for Not Choosing |
|---|---|
| Flask | No automatic OpenAPI, weaker request validation, more manual routing |
| Django | "Batteries included" philosophy conflicts with ADR-003 offline-first constraint; ORM too magical for tax-rule auditing |
| Node.js + Express | Would break the Python-centric NLP from-scratch implementations (Word2Vec/GloVe in NumPy, ANFIS in NumPy) |

### Advantages

- FastAPI's type system catches request-format bugs before they reach the tax engine
- Scrypt provides resistant password hashing (ADR-012); cookie-only session transport avoids token-in-URL leaks
- Server-side sessions (ADR-013) enable revocation and per-owner session tracking
- `config.py` reads all env vars from `.env` with documented fallbacks — no runtime surprises

### Limitations

- Python 3.15.2 has no prebuilt `gensim` wheels → from-scratch NumPy Word2Vec/GloVe (necessary environment constraint, not design choice)
- SQLite does not support concurrent multi-writer workloads — production uses PostgreSQL via Docker volume mount
- Async FastAPI requires `await` throughout; blocking ORM calls need `run_in_executor`

---

## Authentication

### Why Chosen: scrypt + HttpOnly Cookies (ADR-012)

Authentication follows ADR-012: scrypt key derivation for password hashing, session tokens stored in HttpOnly cookies (not exposed to JavaScript), SameSite=Lax default, Secure flag when `APP_ENV=prod`.

**Session flow:**
1. POST /auth/register → 201 + user row in DB (scrypt-hashed password)
2. POST /auth/login → 200 + `Set-Cookie: __Host-ta_session=...; HttpOnly; Secure; SameSite=Lax; Path=/`
3. GET /auth/me → 200 `{user_id, email, expires_at}` if cookie valid, else 401
4. GET /auth/sessions → 200 own active sessions (UA-hash bound)
5. DELETE /auth/sessions/{id} → 204 owner-checked revocation

### Alternatives Considered

| Alternative | Reason for Not Choosing |
|---|---|
| JWT in LocalStorage | Vulnerable to XSS; tokens in URL can leak; no server-side revocation |
| Bcrypt | Secure but slower key derivation; scrypt is preferred for GPU-resistant hashing |
| Token-auth (Bearer) | No server-side revocation without blacklist; stateless design conflicts with ADR-013 session management |

### Advantages

- Scrypt is memory-hard → resistant to GPU/ASIC password cracking
- HttpOnly cookies prevent JS access → mitigates XSS session theft
- `__Host-` prefix requires Secure flag; combined with `APP_ENV=prod` forces HTTPS
- UA-hash binding (tested in `test_auth.py`) ties sessions to User-Agent, preventing session fixation

### Limitations

- Cookie-based design means client must accept cookies; some privacy-focused browsers block third-party cookies
- Scrypt key setup is CPU-intensive (but acceptable for auth, which is not on the critical tax-calculation path)
- Session expiry relies on server-side store; if DB is corrupted, sessions may be lost

---

## Session Management

### Why Chosen: Two-Tier (ADR-012 + ADR-013)

**ADR-012 (scrypt + HttpOnly cookies):** Session cookie `__Host-ta_session` set on login, containing a server-side session ID. The cookie is Secure (prod), HttpOnly, and has sliding TTL (30 min) capped by absolute TTL (24 hours). If `TAX_COOKIE_SECURE=1`, Secure flag is forced.

**ADR-013 (server-side sessions):** Session data (state, phase, extracted entities) stored in SQLite volume `/app/data/taxassist.db`. Each session row has `id`, `created`, `last_used`, `expires`, and `current` fields. The UA hash (SHA-256 of User-Agent) binds the session row, so a different UA invalidates it.

**Flow:** Client sends cookie → server looks up session by ID → validates UA hash → returns session state → client re-sends cookie on next request.

### Alternatives Considered

| Alternative | Reason for Not Choosing |
|---|---|
| Pure JWT (stateless) | No server-side revocation; token size grows with state; ADR-013 requires server-side state |
| Redis-backed sessions | Additional infrastructure (Redis server); SQLite suffices for current scale (100s of concurrent users) |
| Cookieless session (URL params) | Insecure; bookmarks leak session IDs; violates ADR-012 HttpOnly requirement |

### Advantages

- Two-tier design: cookie transports ID only; actual state stays on server (minimizes cookie size, maximizes security)
- `TAX_ENABLE_ANON_DEMO=0` (prod default): cookie-less callers may use /chat + /calculate only (never /history) on user-less sessions
- `TAX_ENABLE_HISTORY=1` kill-switch: since Wave D, /history enforces ownership — foreign session → 404
- `TAX_SESSION_TTL_MINUTES=30` / `TAX_SESSION_ABS_TTL_HOURS=24` caps prevent stale sessions

### Limitations

- Session fixation possible if cookie is set before login; mitigated by regenerating session ID on auth
- IPv6 listeners may be missed by `netstat -p TCP` (known gotcha from local dev runbook)
- Orphan `next-start` nodes may hold `:3000` port if previous instance crashed

---

## NLP Pipeline

### Why Chosen: Deterministic Rules-First Extractor + Research Layer

The NLP pipeline architecture follows a **two-layer design** (§5 one-way dependency):

**Layer 1 — Production Extractor (backend/):**
- Deterministic, regex-driven extraction
- Indian comma-grouping safe: `(?<!\d)[,;](?!\d)`
- Amount clamping: 0..1e11 post-annualization
- Percentage/date masking
- Flat-amount guards: 80c/80d/80g/80u_80dd
- No neural dependency; runs in O(n) time

**Layer 2 — Research Layer (nlp_research/):**
- From-scratch Word2Vec/SGNS + GloVe (NumPy, SEED=472)
- BiLSTM intent classifier (PyTorch, toy scale)
- Seq2Seq + Bahdanau/Luong attention (Phase E)
- BERT fallback (TF-IDF when resources limited)
- GPT-2/T5 generative experiments (Phase G)
- All artifacts stored in `nlp_research/artifacts/`, never in `backend/`

**One-way dependency:** `nlp_research/` may read `data/*.jsonl` and import pure functions from `backend/` (parser, corpus builder); `backend/` never imports `nlp_research/`.

### Alternatives Considered

| Alternative | Reason for Not Choosing |
|---|---|
| Full neural pipeline (end-to-end) | Would violate ADR-003 offline-first; no deterministic baseline for comparison; harder viva narrative |
| Library-based Word2Vec (gensim) | No Python 3.15 wheels; from-scratch NumPy better demonstrates understanding |
| BERT-first approach | 110M parameter model; no GPU; TF-IDF fallback 96.41% accurate — BERT not justified for this domain/data regime |

### Advantages

- Deterministic = reproducible demos (SEED=472, CPU-only)
- Rules-first = auditable tax numbers; engine-only tax numbers (ADR-001) are policy-correct
- One-way dependency = no regressions in production when NLP research changes
- TF-IDF baseline 96.41% closes gap to BERT when resources limited
- All 11 phases (A-I + presentation + evaluation) deliverable from single codebase

### Limitations

- Deterministic extractor cannot learn new patterns without code change (by design — auditable tradeoff)
- Word2Vec from scratch: 50-dim embeddings, 2226 corpus records → sparsity for rare terms
- Seq2Seq attention: simplified due to LSTM tensor shape complexities in minimal PyTorch environment
- BERT not fully available → TF-IDF fallback is the production path

---

## Parser

### Why Chosen: UniversalParser Regex + Indian Comma Grouping

The `ai_models.py` UniversalParser handles amount parsing from free-text tax domain input. It comprises:

- **Digit pattern** `digit_pat = (80u_80dd\b|80u\b)`: two-alternative pattern matching 80u_80dd tokens first, then general 80u, preventing phantom '8' match
- **Indian comma grouping**: `(?<!\d)[,;](?!\d)` — comma between digits is NOT a clause boundary; preserves `1,25,000` as single number
- **Word-number map**: English + Hinglish digits (ek, do, teen, char, panj, chhe, saat, aath, naam, das)
- **Unit map**: lakh → 100,000, crore → 10,000,000, k → 1,000, pm → per month, mo → month
- **Annualization**: monthly amounts × 12, then clamp to 1e11

### Why Not Regex-Only Parsers

Standard regex `\d{1,3}(?:,\d{2}){0,2}\d{0,3}` would treat `1,25,000` as three numbers. The lookbehind/lookahead guard distinguishes digit-grouping commas from clause-boundary commas.

### Advantages

- Indian-format safe: `1,25,000` parsed as 125000, not `[1, 25, 000]`
- Hinglish support: "40 hazaar" → 40000, "1 lakh" → 100000
- Clamp guard: amount never exceeds 1e11 (₹100 crore advisory)
- Value-based fix: the `80u_80dd` two-alternative pattern is the approved minimal change (DO NOT rewrite digit_pat regex)

### Limitations

- Not a general-purpose parser; domain-specific to Indian tax forms
- Word-number coverage limited to enumerated Hinglish forms
- Annualization + clamp is a heuristic; edge cases (9e11 + 9e11 accumulation) tested in `test_nlp_new_inputs.py`

---

## Semantic Attention

### Why Chosen: Gaussian Distance Decay on Word2Vec Embeddings

`SemanticAttention.resolve_category_detailed()` in `ai_models.py:178+` computes category relevance using:

```
score = 100·exp(−dist²/3200) + 2.5·|matched words| + 0.1·|query length|
```

with negative-keyword penalties and long-phrase subsumption.

### Why Not Learned Attention (softmax Q·K·V)

- No GPU → cannot train learned attention from scratch
- Small dataset (2226 records) → learned attention would overfit
- Deterministic baseline required for tax auditing → Gaussian decay is auditable, learned attention is not
- "Attention-inspired" label honestly frames it as heuristic, not neural

### Advantages

- Uses the from-scratch Word2Vec embeddings (Phase B) as the distance metric
- Auditable: every term in the score formula is explicit and explainable
- Works in tandem with the deterministic extractor (not instead of it)
- 95.7% TF-IDF baseline; attention adds proximity scoring for ambiguous cases

### Limitations

- Embedding quality depends on corpus coverage (2226 records → sparse for rare tax terms)
- Gaussian width (3200) is hand-tuned, not learned
- Does not model sequential dependencies (bag-of-words proximity)

---

## Response Composer

### Why Chosen: NLP→TaxEngine Bridge (Phase H)

`backend/response_composer.py` is the **only sanctioned backend modification** (Phase H) that connects NLP outputs to TaxEngine actions. It implements:

- `classify_intent(text)`: rule-based fallback using PROD_TO_INTENT mapping + keyword patterns
- `extract_entities(text)`: Indian-comma-safe splitting + entity regexes (MONEY, TAX_SECTION, INCOME_TYPE, DEDUCTION_TYPE, DATE, PERCENTAGE)
- `compose_tax_engine_query(intent, entities, user_session)`: translates classified intent + extracted entities into TaxEngine SQL queries + user-facing response

**Dependencies (one-way):**
- `nlp_research` may import from `backend/` for data, but NOT vice versa
- Uses `PROD_TO_INTENT` mapping from `common.py`
- Uses `_GUARD_CLAUSE_SPLIT_RE` for Indian comma grouping safety
- Session management via ADR-012 (scrypt + HttpOnly cookies) + ADR-013 (server-side sessions)

### Demo Example

```python
test_text = "I claimed 1,25,000 under section 80c"
entities = extract_entities(test_text)
# Entities: MONEY=['1,25,000'], TAX_SECTION=['80c'], DEDUCTION_TYPE=['80c']
result = compose_tax_engine_query(
    classify_intent(test_text), entities
)
# Query: "SELECT * FROM deductions WHERE type IN ('80c') |SESSION:unknown"
```

### Advantages

- Single sanctioned file: no backend regressions when NLP changes
- Indian-comma-safe: `1,25,000` preserved as single clause → correct MONEY entity
- One-way dependency: safe for production stability (v0.4-sprint3 unchanged)
- Session-aware: ADR-012/ADR-013 integration

### Limitations

- Rule-based (not learned): cannot generalize to unseen tax phrasing without code change
- Single file: cannot express complex ML-based query translation
- Entity regexes are domain-specific; not a general NER model

---

## Tax Engine

### Why Chosen: Python FastAPI + SQLAlchemy ORM + SQLite/PostgreSQL

The tax engine (`backend/tax_engine.py`) implements the core computation:

- **Input**: classified intent + entity amounts + tax section references
- **Processing**: SQL queries against the tax rules registry (`fy_2025_26.py`, `fy_2024_25.py`)
- **Output**: tax liability, breakdown by category, applicable deductions

**Tax rules registry** (Sprint 3 Wave F):
- `fy_2025_26.py`: FY 2025-26 assessment year rules (new tax regime, old tax regime, deductions under 80C/80D/80G/80U_80DD)
- `fy_2024_25.py`: FY 2024-25 rules (for comparison/compliance)
- `schema.py`: SQLAlchemy model definitions for `tax_returns`, `deductions`, `capital_gains`

**Query composition** (from response_composer.py):
- `"SELECT * FROM tax_returns WHERE category = 'salary'"`
- `"SELECT * FROM deductions WHERE type IN ('80c', '80d', '80g', '80u_80dd')"`
- `"amount_filter=125000+50000"` (money amounts joined by +)

### Advantages

- Rules in Python files → auditable, version-trackable, change-friendly
- SQLite in dev, PostgreSQL in production (Docker volume `/app/data/taxassist.db`)
- One-query composition → fast response (<100ms for typical queries)
- Deduction type filtering: only valid types for the classified intent are included

### Limitations

- No ML-based reasoning; pure SQL against static rule set
- New tax sections require adding a new rule file (not a runtime configuration change)
- Does not handle Hinglish numeric forms beyond the Word-number map in the parser

---

## Tax Rules Registry

### Why Chosen: Python Module Per Financial Year

Tax rules are stored in `backend/tax_rules/fy_2025_26.py` and `backend/tax_rules/fy_2024_25.py` as Python modules containing:

- Tax slabs (old regime, new regime)
- Deduction limits (80C max ₹1.5 lakh, 80D max ₹5 lakh, 80G limits)
- Section references (24b rental, HRA received, NPS, 80U_80DD)
- Capital gains types (equity LTCG, equity STCG, property CG)

**Design:** Each file is self-contained; the engine imports the active year's module based on `APP_ENV` and the current assessment year. No runtime reloading; changes require a new file deployment.

### Advantages

- Auditable: each rule is a git-tracked Python file
- Year-over-year comparison: FY 2024-25 vs FY 2025-26 side by side
- Clear ownership: `fy_2025_26.py` is the current year; `fy_2024_25.py` is reference
- No ORM migration needed for rule changes (just add a new Python file)

### Limitations

- Rigid: new tax section → new file, not a config change
- No inflation adjustment built into the rules (would require code change)
- Rules cannot be updated at runtime (imported at server start)

---

## Audit Architecture

### Why Chosen: Append-Only JSONL + Rotation

The audit stream (ADR-009, Sprint 2) follows an append-only JSONL design:

**Active stream:** `logs/app/app.jsonl` — every request/response event is written as a JSON line.

**Rotation:** Active stream rotates when write pushes it over `TAX_APP_LOG_MAX_BYTES` (10,000,000 bytes). `TAX_APP_LOG_MAX_FILES` (5) generations are kept; `TAX_APP_LOG_RETENTION_DAYS` (30) sweeps expired rotated generations. The active file is never deleted.

**Audit stream (separate):** `logs/audit/session_audit.jsonl` — only if `TAX_AUDIT_STORE_TEXT=1` (opt-in, DPDP Act 2023). Default `TAX_AUDIT_STORE_TEXT=0` stores sha256[:16] correlation hashes only.

**Per-minute rate limits** (design §4, per-IP and per-user sliding windows):
- `/auth/*` per IP: 10 per minute
- `/chat + /sessions` per user: 30 per minute
- `/calculate` per user: 60 per minute
- **Global per IP**: 120 per minute
- `/health` is exempt

### Advantages

- Append-only → no delete anomalies; every event is an immutable record
- Rotation + retention → disk usage bounded (5 generations × 10MB + 30-day sweep)
- Correlation hashes (sha256[:16]) → privacy: no raw email/password/tokens in audit
- Rate limits → DoS protection at middleware level

### Limitations

- Active file never deleted → requires manual cleanup or rotation sweep
- `TAX_AUDIT_STORE_TEXT=1` → stores raw text; must have documented lawful basis (DPDP Act 2023)
- Rate limits are per-process (one worker); distributed system would need coordinated limits

---

## Deployment Architecture

### Why Chosen: Docker Compose + CI/CD

The production deployment uses Docker Comprise (defined in `docker-compose.yml`) with the following services:

| Service | Image | Port | Description |
|---|---|---|---|
| backend | custom Python:3.15.2-slim | 8000 | FastAPI + SQLAlchemy + tax engine |
| db | PostgreSQL | 5432 | Production session store (mounted volume `db-data`) |
| frontend | custom Next.js | 3000 | React + TypeScript + API proxy |
| proxy | Nginx | 80/443 | Reverse proxy, TLS termination, CORS headers |

**Environment variables** are read from `.env` (gitignored; never committed). The real `.env` is deployed separately.

**CI/CD:** GitHub Actions runs `pytest` suite (1099 tests) on every PR. Green CI → merge → Docker image build → `docker compose up -d` → production rollout.

### Advantages

- Single `docker-compose.yml` → one-command deployment (`docker compose up -d`)
- Environment separation: `.env.dev` (local), `.env.prod` (container) — never committed
- CI green gate: 1099 pytest + 22 Vitest + 7 Playwright + 97 legacy = all stable
- Docker pins Python 3.15.2 + exact package versions (no pip index surprise at deploy time)

### Limitations

- `NEXT_PUBLIC_API_URL` baked at build time — changing backend host requires frontend image rebuild
- Orphan `next-start` nodes may hold `:3000` port (known gotcha: `netstat -p TCP` misses IPv6 listeners)
- Python 3.15.2 → no gensim wheels → from-scratch NumPy (workaround already validated)
- Docker build context must not include `.env` or `.git` (gitignored already, but build args must be explicit)

---

## CSE472 Syllabus Mapping

### Unit Coverage Summary

| Unit | Theme | Coverage | Key Evidence |
|---|---|---|---|
| I | Foundations & preprocessing | **Implemented (strong)** | Indian comma grouping, percentage/amount masking, Hinglish normalization |
| II | Word embeddings | **Implemented (Phase B)** | Word2Vec Skip-gram + GloVe from scratch, PCA/t-SNE visualizations |
| III | Sequence models | **Partially Implemented** | BiLSTM intent classifier (toy scale); template-driven NER (Phase D) |
| IV | Attention & Seq2Seq | **Partially Implemented** | Bahdanau/Luong attention documented (Phase E); Simplified due to environment |
| V | Pretrained LMs | **Partially Implemented** | BERT fallback TF-IDF 96.41% (Phase F); GPT-2/T5 experiments (Phase G) |
| VI | Applications & evaluation | **Implemented (strong)** | Full evaluation framework, response composer, NER, intent classification, generation |

**Viva position:** *"a production Indian-tax platform whose NLP stack is documented, measured, and extended with deep learning exactly where the syllabus demands it."* The project already scores Unit I (strong) and Unit VI (framework) from production engineering alone; the academic layer (nlp_research/) adds Units II, III, IV, V with small, seeded, CPU-reproducible experiments anchored to the domain corpus.

---

## Summary: Why This Architecture?

| Concern | Choice | Why |
|---|---|---|
| **Auditability** | Rules-first extractor + JSONL audit | Every tax number is derivable from input; every event is an immutable record |
| **Stability** | One-way dependency + deterministic seeds | v0.4-sprint3 unchanged; 1099 pytest green; no regressions from NLP research |
| **Indian format** | `(?<!\d)[,;](?!\d)` guard + value-based digit_pat | `1,25,000` preserved as single clause; no phantom '8' match |
| **Resource constraints** | From-scratch NumPy + TF-IDF fallback | Python 3.15.2 no gensim wheels; BERT unavailable; TF-IDF 96.41% closes gap |
| **Viva narrative** | "Production platform extended with measured DL research" | Every DL component evaluated against deterministic baseline; examiners reward the scientific method |
| **One-way dependency** | `nlp_research` reads `data/`; `backend/` never imports it | Safe for production; only Phase H touches `backend/`; approved per user instruction |

**Final verdict:** The architecture deliberately trades neural generality for deterministic auditing, Indian-format safety, and CSE472 syllabus coverage. Every design decision has a documented rationale (ADR, design §§1-5) and can be defended in a viva or faculty discussion.
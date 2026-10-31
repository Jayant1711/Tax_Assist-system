# Deployment Guide

> Written 2026-10-31 from the codebase as it exists. **Read [§4 Security checklist](#4-security-checklist-before-any-public-exposure) before exposing this app beyond localhost** — as shipped, it is dev-only.

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | NumPy required (ANFIS); `scikit-learn`/`pandas` declared but unused by runtime code |
| Node.js | 18+ (Next.js 16) | |
| OS | any | Developed on Windows |

## 2. Local development (verified against README)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on POSIX)
pip install -r requirements.txt

# One-time: train the ANFIS scorer (writes anfis_weights.json)
python anfis_trainer.py            # ~200k synthetic scenarios, EE-Bat search

python main.py                     # Uvicorn on 0.0.0.0:8000
```

- A pre-trained `backend/anfis_weights.json` is already committed — training is only needed if you change the feature vector (20 inputs × 64 rules, `ai_models.py:461-462`).
- ⚠ Do **not** run `anfis_refine.py` against those weights: it expects a 10×50 topology (`anfis_refine.py:15`) and will crash. It is dead code (roadmap Week 1, item 7).
- If weights are regenerated with different dimensions, startup crashes at reshape (`ai_models.py:482-485`) — keep 20×64 or update the class constants together.
- Interactive API docs: `http://localhost:8000/docs` (FastAPI auto).

### Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:3000
```

### Verify the stack

```bash
curl http://localhost:8000/docs                          # backend up
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d "{\"message\":\"I earn 12 lakhs\",\"session\":{\"id\":\"sid_test1\"}}"
```

The frontend hardcodes `http://localhost:8000` (`ChatInterface.tsx:148`, `TaxReport.tsx:24`) — it works only against a locally running backend until ADR-010 lands.

## 3. Runtime artifacts & configuration

| Artifact | Path | Written by | Notes |
|---|---|---|---|
| Audit log | `backend/logs/session_audit.json` | `audit_logger.py` | Whole-file rewrite per chat turn; contains raw user text (PII) |
| Black box | `backend/logs/blackbox/<sid>.json` | `session_lab.py` | Per-session turn log; `<sid>` is client-controlled (sanitize before deploying) |
| Model weights | `backend/anfis_weights.json` | `anfis_trainer.py` | Committed; 95 KB |
| Test report | `backend/test_report.json` | `test_suite.py` | Committed artifact — regenerates on test run |

`.gitignore` already excludes `backend/logs/` and `.env`; there are **no env vars today** — ports, CORS, and the API URL are all hardcoded (`main.py:18,101`, frontend fetches).

## 4. Security checklist before any public exposure

Everything below is currently **missing**; treat this as a launch blocker list (details and evidence in the audit, mirrored in [decisions.md](decisions.md)):

- [ ] **Authentication** — no endpoint requires auth today; `/history/{sid}` returns any session's financial data and IDs are timestamp-guessable (`main.py:82-91`). (C5)
- [ ] **Session-ID sanitization** — client-supplied `session.id` is used in a filesystem path (`session_lab.py:22`) → arbitrary file write. (C6)
- [ ] **Input validation** — `/calculate` accepts raw dicts; malformed amounts/capital-gains raise 500s; message length unbounded. (H5)
- [ ] **CORS** — `allow_origins=["*"]`, all methods/headers (`main.py:18`). Restrict to the deployed origin.
- [ ] **HTTPS** — Uvicorn serves plain HTTP on `0.0.0.0:8000`; terminate TLS at a reverse proxy.
- [ ] **Rate limiting** — none; the regex NLP layer is CPU-bound per message.
- [ ] **PII handling** — raw chat + financial figures persisted in plaintext with no retention policy (DPDP Act 2023 exposure). (S6)
- [ ] **Dependency pinning** — `requirements.txt` unpinned; add `pip-audit` / `npm audit` to CI.

## 5. Production topology (recommended)

```text
[Browser] ──HTTPS──> [Reverse proxy / CDN: TLS, static frontend export]
                          │
                          └──> [Uvicorn × N workers behind gunicorn] ──> [SQLite/Redis: sessions + audit]
```

- **Do not scale workers before fixing the audit log**: the read-modify-write pattern (`audit_logger.py:24-35`) loses entries under concurrency. Land ADR-009 first.
- Run Uvicorn behind a process manager; `python main.py` is the dev entry (`main.py:101`). Production form: `gunicorn -k uvicorn.workers.UvicornWorker main:app`.
- The frontend has no server-side data dependencies — `next build` output can be served statically or via `next start` in a container.
- Healthcheck: none exists yet; add `GET /health` (roadmap Week 3).

### Minimal Docker sketch (illustrative — not yet in the repo)

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build
CMD ["npm", "run", "start"]
```

> The frontend Dockerfile only works after the hardcoded URLs are replaced by `NEXT_PUBLIC_API_URL` (ADR-010).

## 6. Known deployment blockers (summary)

| Blocker | Why it blocks | Fix tracked in |
|---|---|---|
| Hardcoded `localhost:8000` in both data paths | App cannot reach its API in any hosted environment | [roadmap.md](roadmap.md) Week 3 / ADR-010 |
| No auth on `/history` | Financial data of any session readable by anyone | Week 3 / C5 |
| Path traversal in `session_lab.py` | Remote file write via crafted session ID | Week 1 / C6 |
| Stale tax year (FY 2024-25) | Output is legally wrong for current filings | Week 2 / C1 |
| Unpinned dependencies + no CI | Non-reproducible, unauditable builds | Week 1 / Week 3 |
| Audit log race + PII retention | Data loss under load; compliance exposure | Week 2 / H6, S6 |

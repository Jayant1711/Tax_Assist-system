# Tax Assist AI (India) — Transparent AI Tax Consultant 🇮🇳

![Release](https://img.shields.io/badge/Release-v0.6--sprint6-blue?style=for-the-badge)
![FY](https://img.shields.io/badge/Tax_Year-FY_2025--26_(AY_2026--27)-orange?style=for-the-badge)
![Backend Tests](https://img.shields.io/badge/pytest-1%2C166_passed-brightgreen?style=for-the-badge)
![Frontend Tests](https://img.shields.io/badge/vitest-31_passed-brightgreen?style=for-the-badge)
![CI](https://img.shields.io/badge/CI-GitHub_Actions-passing?style=for-the-badge&logo=githubactions&logoColor=white)

An AI-powered tax consultant for Indian taxpayers that pairs a **deterministic, rules-exact tax engine** with a **conversational NLP discovery flow** — and shows its work: every rupee it quotes is recomputed by the engine, every recommendation carries its evidence, and the system learns from what you accept.

> **Core invariant:** the rules engine is the *only* thing in the system that computes tax. No model, heuristic, or estimate ever produces a rupee figure (ADR-001).

## ✨ What it does

- **Guided discovery (NLP)** — a conversational flow (English + Hinglish) maps profession, income, and deductions into a validated session; ambiguous input triggers ask-backs instead of guesses.
- **Dual-regime computation, exactly** — Old vs New (Sec 115BAC) regimes computed side-by-side from a versioned rules registry, including surcharge, marginal relief, 87A rebate, HRA Rule-2A, cess.
- **Intelligence cards** — at the final report, ranked opportunities show recommendation, confidence, engine-priced savings, reason, and an evidence trail — with **Apply / Not-for-me** actions that the system records (ADR-017) and aggregates into an acceptance funnel.
- **Applied-vs-Ignored transparency** — the report shows which of your deductions each regime actually applied, and why (115BAC), so the regime choice is never a black box.
- **Exact per-deduction impact** — a leave-one-out recomputation prices what each booked deduction *actually* removed from your tax, in both regimes. Exact arithmetic, no estimates.
- **CA-style outputs** — ITR-format computational statement, slab-by-slab breakdown, audit observations, and regime-gated savings tips.

## 🚀 Quickstart (Docker)

```bash
git clone https://github.com/Jayant1711/Tax_Assist-system.git
cd Tax_Assist-system
docker compose up -d --build
```

Then open **http://127.0.0.1:3000** (use `127.0.0.1`, not `localhost` — the bundled `.env` pins CORS and the API URL to the loopback address).

**Demo login:** `demo@student.local` / `DemoPass@123`

Run a consultation: type your profile (e.g. *"I am a software engineer earning 24 LPA, 1.5L in 80C, 25k in 80D"*), answer the follow-ups, and type `/end` to generate the final report with the intelligence cards.

### Local development (without Docker)

```bash
# backend — Python 3.10+
cd backend && pip install -r requirements.txt
uvicorn main:app --port 8000

# frontend — Node 18+
cd frontend && npm install && npm run dev
```

## 🧪 Verification

| Suite | Status |
|---|---|
| Backend (pytest) | **1,166 passed** / 0 failures |
| Frontend (vitest + tsc) | **31 passed**, TypeScript clean |
| NLP extraction gate | macro **F1 1.000** (certified, `docs/reports/NLP_EVALUATION_REPORT.md`) |
| CI | GitHub Actions — backend, frontend, e2e (Playwright) green on every push |

```bash
cd backend && python -m pytest tests/ -q     # backend suite
cd frontend && npx vitest run                 # frontend suite
```

## 🏗️ Architecture

```
frontend/  Next.js 16 + React 19 + TypeScript — chat UI, intelligence cards,
           Applied-vs-Ignored panel, exact-impact table, regime comparison
    │      REST + HttpOnly cookie sessions
backend/   FastAPI — 17 endpoints, auth, rate limits, append-only audit
    ├──   nlp_engine.py — prepass guards → UniversalParser → SemanticAttention
    │     → waterfall extraction → response composer → shared closing intelligence
    ├──   tax_engine.py — THE calculator (+ exact per-deduction impact)
    │     tax_rules/{fy_2024_25, fy_2025_26} — versioned statutory rules
    ├──   tax_intelligence.py — composite efficiency, exact rule heads, ranked review
    ├──   calibration.py — confidence-calibration instrument (ECE + canary, G7 gate)
    └──   SQLite (WAL) — users, sessions, recommendation_events (ADR-017)
data/      corpus-v1 (sha256-pinned) · anfis-v3 benchmark dataset (regenerable)
nlp_research/  research models (one-way dependency; never in the serving path)
docs/      engineering documentation + full sprint report archive (docs/reports/)
```

**How the intelligence stays honest:** candidates are priced by running the actual engine on hypothetical top-ups (two-pass), ranked by exact engine savings, and decorated with rule heads that are exact by construction (P/R 1.0, savings MAE ₹0.00). Learned components that failed their gates (TSK heads) were denied promotion on evidence and stay off the serving path — see `docs/reports/TSK_PROMOTION_REPORT.md` and `docs/reports/ML_NEGATIVE_RESULTS.md`.

## 📚 Documentation

| Start here | What it is |
|---|---|
| [`docs/index.md`](docs/index.md) | full engineering documentation (architecture, API, NLP pipeline, tax rules as coded, security, testing, deployment) |
| [`docs/decisions.md`](docs/decisions.md) | Architecture Decision Records (ADR-001 … ADR-017) |
| [`CHANGELOG.md`](CHANGELOG.md) | every release, sprint by sprint |
| [`PROJECT_BASELINE_CURRENT.md`](PROJECT_BASELINE_CURRENT.md) | the frozen current-state baseline (facts + metrics) |
| `DATASET_REGISTRY.md` / `MODEL_REGISTRY.md` / `TRAINING_REGISTRY.md` / `EXPERIMENT_REGISTRY.md` | living traceability registries |
| [`docs/reports/`](docs/reports/) | complete sprint-report archive (89 engineering reports, audits, reviews) |

## 🗺️ Status & roadmap

- **Released:** `v0.4-sprint3` → `v0.5-sprint4` → `v0.6-sprint6` (Sprints 5–6: acceptance loop, calibration, intelligence cards, exact impact).
- **Next (proposed, not started):** adoption sprint — effectiveness dashboard, viewed-events, one-click Apply. See `docs/reports/SPRINT7_PROPOSAL.md`.
- **Honest limits:** salaried profiles are deepest; business/capital-gains flows are partial; FY 2025-26 is the certified year; this is an advisory/education tool — it does not file returns.

## ⚖️ Governance

Tax rules are versioned per FY in `backend/tax_rules/` and verified against the statute (`docs/tax-verification.md`). Every architectural decision has an ADR; every model attempt — successful or not — is registered. The system never invents tax law, and the audit log is append-only.

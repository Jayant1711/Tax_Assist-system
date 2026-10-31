# Tax Assist AI — Documentation

**Tax Assist AI** is a conversational Indian income-tax assistant: a **Next.js 16 / React 19** chat frontend drives a **Python / FastAPI** backend that extracts financial facts from free text (English + Hinglish) with a hand-built NLP layer, computes dual-regime (Old vs New) tax liability with a deterministic rule engine for **FY 2024-25 (AY 2025-26)**, and renders a CA-style computation statement with an ANFIS-derived "efficiency score". There is no database and no authentication — all conversation state is client-owned JSON round-tripped on every request, and persistence is flat JSON files under `backend/logs/`. The system is a summer-internship project that is **development-grade only**: see [security.md](security.md) before exposing it beyond `localhost`.

## Documentation map

| Document | Description |
|---|---|
| [architecture.md](architecture.md) | System overview, component inventory, request lifecycle, session state model, known weaknesses (W1-W7), tech stack, repo layout. Start here. |
| [api-reference.md](api-reference.md) | Every HTTP endpoint (`/chat`, `/history/{sid}`, `/calculate`): request/response JSON shapes with real field names, status/error behavior, worked curl examples, CORS and auth limitations. |
| [nlp-pipeline.md](nlp-pipeline.md) | How a message becomes session mutations: `UniversalParser` number formats, `SemanticAttention` scoring formula, zero-sentinel, corrections, monthly annualization, discovery waterfall, profession classification — with a traced multi-turn example and known misclassification patterns. |
| [tax-rules.md](tax-rules.md) | FY 2024-25 rules **as coded** (slabs, deduction caps, 87A, surcharge, capital gains) with path:line evidence, plus documented deviations from statute and the FY 2025-26 gap. |
| [testing.md](testing.md) | Inventory of the six test scripts, how to run them, coverage vs. gaps (no API tests, no frontend tests, no CI), and the pytest migration target. |
| [security.md](security.md) | Factual threat model with path:line evidence (path traversal, unauthenticated history, unvalidated input, CORS wildcard, plaintext PII) and a prioritized hardening checklist. |
| [deployment.md](deployment.md) | Local development setup, runtime artifacts, pre-exposure security checklist, production topology, Docker sketch, deployment blockers. |
| [roadmap.md](roadmap.md) | 30-day remediation plan (Weeks 1-4) plus 60/90-day horizon, keyed to the audit findings. |
| [decisions.md](decisions.md) | Architecture Decision Records: ADR-001-007 document decisions embodied in the code; ADR-008-011 are proposed fixes. |

## Suggested reading order

- **New engineer:** [architecture.md](architecture.md) → [api-reference.md](api-reference.md) → [nlp-pipeline.md](nlp-pipeline.md) → [decisions.md](decisions.md)
- **Changing tax logic:** [tax-rules.md](tax-rules.md) first (especially §6, where every FY constant lives), then [roadmap.md](roadmap.md) Week 2.
- **Deploying anywhere:** [security.md](security.md) → [deployment.md](deployment.md) → [roadmap.md](roadmap.md) gating rule.
- **Writing tests:** [testing.md](testing.md) → [decisions.md](decisions.md) ADR-011.

## Ground rules used across this documentation set

- Every factual claim cites `path:line` in the code as of the 2026-10-31 audit; line numbers refer to the files as they exist in this repository.
- Tax figures in [tax-rules.md](tax-rules.md) are transcriptions of the code, **not** statutory advice, and no new statutory figures are introduced anywhere in the set.
- Known-behavior examples in [nlp-pipeline.md](nlp-pipeline.md) and [testing.md](testing.md) were verified by executing the current engine (Python 3.15.2) on 2026-10-31.

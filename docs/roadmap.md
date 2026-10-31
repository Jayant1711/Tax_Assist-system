# Roadmap

> Source: full-repo audit, 2026-10-31. Issue IDs (C# = Critical, H# = High) reference the audit report delivered that day; evidence lives in [architecture.md](architecture.md) and [tax-rules.md](tax-rules.md).
>
> **Gating rule:** Week 1 before any external user; Week 2 before claiming FY-current; Week 3 before public internet exposure.

## Week 1 — Stop the bleeding (correctness & containment)

| # | Task | Fixes | Done when |
|---|------|-------|-----------|
| 1 | Remove the second ×12 in the NLP monthly-conversion path | C3 | Test asserts `"80,000 per month"` → session salary 960,000 through the **full** NLP flow |
| 2 | Exempt agricultural income in both regimes; emit a warning when partial-integration rules would apply | C2 | Old-regime gross excludes agri; regime comparison no longer biased |
| 3 | Aggregate the ₹1.25L LTCG exemption across all `equity_ltcg` entries | H1 | Multi-entry test matches per-assessee exemption |
| 4 | Sanitize `session_id` (`^[\w-]{8,64}$`, basename) in `session_lab.py` | C6 | Traversal/absolute-path IDs rejected at the API boundary |
| 5 | Pydantic request models with bounds for `/chat` + `/calculate` (message ≤ 4k chars, amounts ≤ 1e11, typed `capital_gains[]`); global exception handler | H5 | Malformed payloads → 422, never 500/stack trace |
| 6 | CORS from env var; pin `requirements.txt` versions | — | `pip freeze` committed; no wildcard origins in non-dev |
| 7 | Delete/repair dead modules: `nlp_engine_v2.py`, `anfis_refine.py`, `view_lab_logs.py`, `debug_run.py`, `session_lab.__main__`; strip `"summer_internship_project"` marker keys from JSON files | W3 | `grep`-clean; imports resolve |
| 8 | Migrate tests to pytest; make `smoke_test.py` assertions real; add golden-file tests replaying the misclassified sentences in `backend/logs/session_audit.json` | H8, C4-net | pytest green in CI-less local run; regression corpus covered |

## Week 2 — Compliance & data integrity

| # | Task | Fixes | Done when |
|---|------|-------|-----------|
| 1 | Build the tax-rules registry (ADR-008) and implement FY 2025-26 (AY 2026-27) new-regime slabs/rebate — **constants verified against the Finance Act 2025 text before merge** | C1 | `TaxEngine` accepts `tax_year`; FY-versioned test matrix; every response reports its FY |
| 2 | Fix HRA (metro flag + separate rent-paid input) and surcharge marginal relief (threshold-comparison method) | H2, H3 | Boundary tests at ₹50L/₹1Cr/₹2Cr/₹5Cr vs hand-computed ground truth |
| 3 | Wire in or remove 80EEA / 80U / 80DD / 80DDB; stop defaulting professional tax to ₹2,500 | H4, M1 | No silent input → 422/used/removed consistently |
| 4 | Replace audit persistence with append-only JSONL or SQLite WAL; never truncate on read error; rotation + retention; PII minimization | H6, ADR-009 | Concurrent-write test loses nothing; corrupt file does not wipe history |
| 5 | Remove PII-bearing logs from the working tree; verify `.gitignore` coverage | S6 | `backend/logs/` clean; retention documented |

## Week 3 — Security & deployment

| # | Task | Fixes | Done when |
|---|------|-------|-----------|
| 1 | Auth: opaque UUID session tokens minimum; `/history` bound to the caller; target OAuth/API-key for any real deployment | C5 | Unauthenticated cross-session `/history` returns 401/403 |
| 2 | Server-side session storage (ADR-007): client sends `{session_id, message}` only | W1 | No session dict in any request body |
| 3 | `NEXT_PUBLIC_API_URL` config (ADR-010); Dockerfile + docker-compose for both services; `/health` endpoint | H7 | `docker compose up` serves the full app without localhost hardcoding |
| 4 | GitHub Actions: pytest + `pip-audit` + `npm audit` + `next build` on every PR | H8 | Red build blocks merge |

## Week 4 — Trust & polish

| # | Task | Fixes | Done when |
|---|------|-------|-----------|
| 1 | Frontend Vitest unit tests (SavingsGraph/TaxReport math display) + Playwright chat→report happy path | H8 | Tests green in CI |
| 2 | Remove the 400 ms artificial reply delay; `next/font`; drop the duplicate `/calculate` fetch by reusing `/chat`'s `tax_report` | P4, P6 | One engine run per turn |
| 3 | Re-train ANFIS against **live-engine** outputs (regenerate ground truth from `TaxEngine`) or label the score "beta" in the UI | W4 | Score provenance documented |
| 4 | Align README + `research_report.md` with reality (200k training cases, R² target, supported FY, security posture); add an FY selector/warning in the UI | Doc drift | Docs match code |
| 5 | Tag `v0.2`; file the audit findings as issues; re-run the engineering-suite audit (Mode 9) to re-score | — | New scorecard recorded |

## 60-day horizon

- NLP accuracy push: expand the regression corpus to 200+ labeled utterances; per-category precision targets (income heads ≥ 95%); consider an evaluation harness that replays logs nightly.
- DB migration: SQLite → Postgres if multi-user is real; Alembic migrations.
- Observability: structured logging, request IDs, error tracking, `/metrics`.
- ITR-form mapping: map engine output to actual ITR-1/ITR-3/ITR-4 schedule lines.

## 90-day horizon

- Optional LLM-assisted extraction with the deterministic rules as guardrails (never for computation — ADR-001 stands), behind a feature flag and eval suite.
- Explainable-efficiency scoring (feature attributions) replacing the black-box ANFIS number, or ANFIS retired.
- Multi-user auth with accounts, saved computations, and PDF export of the computation statement.
- Public beta only after: auth, FY-current rules, input validation, rate limiting, and a passing security re-audit.

# Sprint 1 Release Notes — Tax Assist AI

**Tag:** `v0.2-sprint1` · **Date:** 2026-10-31 · **Baseline:** `main @ 50d8eda` (2026-07-29)
**Scope:** Correctness, security hardening, and testing foundation. **Sprint 2 (tax-year update) NOT included.**

---

## ⚠ Read this first

- The backend now **rejects malformed input with HTTP 422** instead of crashing with 500s, and **`GET /history/{sid}` returns 404 by default** (enable with `TAX_ENABLE_HISTORY=1`). The bundled frontend is unaffected; direct API consumers must send well-formed payloads.
- **Do not expose the backend beyond localhost.** Authentication is still not implemented (Sprint 3), and the CORS wildcard remains. Sprint 1 closes the file-write and input-validation holes; it does not make the API internet-safe.
- Tax figures still target **FY 2024-25 (AY 2025-26) only**. The tax-year update (FY 2025-26 / AY 2026-27) is Sprint 2 and requires verified Finance Act 2025 constants before merge.

## Highlights

### Security hardening (C6, H5/N1, C5-interim)
- **Closed an unauthenticated arbitrary-file-write primitive**: client-supplied session IDs are now validated (`^[A-Za-z0-9_-]{4,64}$`) at the API boundary and defensively aliased (`untrusted_<sha1>` ) at the persistence layer — audit trail preserved, path escape impossible.
- **All endpoints validate input**: typed request models with bounds (amounts ≤ 1e11, message ≤ 4k chars, session ≤ 100 KB, typed `capital_gains[]`, age 0–120); non-finite floats (NaN/Infinity) rejected; malformed payloads → 422, never 500/stack-trace. A sanitized global 500 handler was added.
- **Validation errors no longer reflect attacker input** (bounded `{loc, msg, type}` error entries, cap 20).
- `/history` gated off by default (was: unauthenticated cross-session financial disclosure with guessable IDs).
- Certified by an independent security review: C6 closed, H5 closed, C5-interim closed for the localhost-only posture.

### Calculation & NLP correctness (C2, C3, C4a/b/c)
- **Agricultural income is no longer taxed** as ordinary income in the old regime (Sec 10(1)); a partial-integration advisory is emitted instead of silently miscomputing.
- **Monthly amounts are annualized exactly once** ("₹80,000 per month" was computing ₹1.15 Cr of salary; now ₹9.6 L).
- **Four production misclassification patterns fixed** (proven by the repo's own April 2026 conversation logs, now a permanent regression corpus): tuition payments no longer overwrite declared salary; PPF + health insurance split correctly to 80C/80D; property-sale proceeds book to capital gains instead of rental income; values are bound to their clause so unrelated keywords cannot capture them. Unrecognized amounts are flagged (`UNRECOGNIZED AMOUNT`) instead of silently destroying user data.
- Capital-gains statements now carry a gross-value-vs-gain advisory.

### Testing foundation (#16, #17)
- New pytest suite: **153 tests** (parser, profession classifier, semantic attention, conversations, tax engine with exact-rupee ground truth, edge cases, API, security, validation) — the prior ±₹2,000–5,000 tolerances and a tautological check are gone.
- **Golden-file regression corpus** replaying the real production misclassifications; every fix is proven red→green.
- Legacy 97-check harness retained and still green (97/97).

### CI & dependencies (#19, #27)
- GitHub Actions: backend job (pytest + pip-audit on pinned deps) and frontend job (npm ci + audit + build) on every push/PR.
- Backend dependencies pinned exact (fastapi 0.162.0, pydantic 2.14.2, numpy 2.5.4, uvicorn 0.54.0); unused `scikit-learn`, `pandas`, `python-multipart` removed.

### Hygiene (#28)
- Deleted dead/broken modules (`nlp_engine_v2.py`, `anfis_refine.py`, `view_lab_logs.py`, `debug_run.py`); removed a broken `__main__` demo; stripped non-standard marker keys from JSON files.

## Metrics

| Metric | Before | After |
|---|---|---|
| Automated backend tests | 97 (legacy only, loose tolerances) | **153 pytest + 97 legacy**, exact-rupee where applicable |
| Known Critical findings open | 6 | **2** (C1 tax-year → Sprint 2; C5 auth → Sprint 3) |
| Production misclassification patterns reproducing | 5 | **0** |
| Unhandled-500 input classes | ≥ 4 | **0** |
| Pinned backend dependencies | 0 / 7 | 4 / 4 (3 unused removed) |

## Verification

```text
cd backend && python -m pytest tests/ -q   →  153 passed
cd backend && python test_suite.py         →  97/97
```
Independent certifications: architecture conformance 7/7 PASS; QA: CERTIFIED; security review: C6/H5/C5-interim closed.

## Known remaining (tracked)

CORS wildcard (localhost-only rule in force) · auth + server-side sessions (Sprint 3) · HRA formula and surcharge marginal-relief approximations (Sprint 2) · LTCG ₹1.25L exemption applied per entry (Sprint 2) · FY 2024-25 constants (Sprint 2) · `smoke_test.py`/`final_test.py` cannot-fail prints (superseded by pytest) · documentation punch-list for the post-sprint state (6 docs files).

## Upgrading

1. Pull; backend deps unchanged at runtime except removals — recreate the venv or `pip install -r backend/requirements.txt -r backend/requirements-dev.txt`.
2. `cd backend && python -m pytest tests/ -q` must show **153 passed**.
3. Frontend: no changes required (`npm ci` unchanged).
4. Set `TAX_ENABLE_HISTORY=1` only if you accept the exposure documented in `docs/security.md`.

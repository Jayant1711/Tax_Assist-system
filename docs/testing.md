# Testing — current assets and gaps

> Verified against the code 2026-10-31. There is **no pytest, no CI, no frontend test runner** — everything below is standalone scripts under `backend/`. Migration target: ADR-011 in [decisions.md](decisions.md). Related: [nlp-pipeline.md](nlp-pipeline.md) (what the tests exercise) · [roadmap.md](roadmap.md) Week 1 item 8, Week 3 item 4.

## 1. Inventory

| File | What it does | How to run | Can it fail? |
|---|---|---|---|
| `backend/test_suite.py` | The main harness: 97 checks across 6 blocks (parser, profession, attention, conversations, tax accuracy, edge cases); writes `backend/test_report.json` | `cd backend && python test_suite.py` | Yes — real pass/fail counters, failure details, exit-less but visible `[FAIL]` lines |
| `backend/smoke_test.py` | Quick sanity: 4 parser checks with real comparisons, then TaxEngine 50L / surcharge / NLP / waterfall sections that only *print* | `cd backend && python smoke_test.py` | **Partially** — lines 30, 36, 43 print `[PASS]` unconditionally |
| `backend/final_test.py` | ANFIS scores for 4 profiles + TaxEngine output for 6 cases; pure value printing | `cd backend && python final_test.py` | **No** — zero assertions; ends with a hardcoded `"ALL TESTS PASSED"` (`final_test.py:38`) |
| `backend/industrial_stress_test.py` | One 90-word mega-prompt through NLP + engine; prints extracted state, tax summary, risk observations | `cd backend && python industrial_stress_test.py` | **No** — demonstration script; output is for eyeballing (this is the prompt behind the log entries cited in [nlp-pipeline.md](nlp-pipeline.md) §11) |
| `backend/manual_parity_check.py` | 50L salaried case vs a hand-computed expectation (~₹12,71,400 old regime), printed side by side | `cd backend && python manual_parity_check.py` | **No** — prints expected vs actual; no comparison is made in code |
| `backend/verify_upgrade.py` | Performance benchmarks only: 50,000 engine cases and 500,000 NLP extractions timed | `cd backend && python verify_upgrade.py` (minutes to run) | **No** — reports ms/case; no correctness checks |

Artifacts: `backend/test_report.json` is committed and currently shows `{"pass": 97, "fail": 0}`; it regenerates on every `test_suite.py` run. The README badge ("97/97 Passed") reflects this file — see the caveats in §3 before trusting it.

There is also `backend/debug_run.py`, not a test: a scratch script debugging parser test P15 and conversation C05b.

## 2. What `test_suite.py` covers (blocks and checks)

| Block | Checks | Content | Rigor notes |
|---|---|---|---|
| 1 — Parser (`P01`-`P20`) | 20 | Digit, lakh/crore/k/LPA, word forms, `pm` annualization (`test_suite.py:41-71`) | Exact-match (tolerance < 1). Honest unit-level coverage of `UniversalParser` |
| 2 — Profession (`PR01`-`PR20`) | 20 | Salaried vs Business classification incl. one typo (`enigneer`) and `"I trade in stocks"` (`test_suite.py:78-103`) | Exact-match |
| 3 — Attention (`A01`-`A20`) | 20 | Category resolution for income heads and deduction sections incl. typo `tution fees` (`test_suite.py:110-138`) | Exact-match, but at sentence level only — never through the full `process_message` path |
| 4 — Conversations (`C01`-`C10`) | 22 | Multi-turn flows: salaried, business + rental, context-carry, correction remap, multi-entity sentence, Hinglish, word-form, senior, complex CA case, `/end` (`test_suite.py:143-249`) | Some assertions are deliberately soft: `C03b` passes if *either* of two conditions holds (`test_suite.py:190-191`); `C08` only checks profile, not the 80TTB routing its comment promises |
| 5 — Tax accuracy (`T01`-`T05`) | 7 | Hand-computed ground truth for 5 salary scenarios (`test_suite.py:256-293`) | **Loose tolerances**: ±100 / ±2000 / ±5000 rupees; `T04`/`T05` only assert "no crash and result ≥ 0" — a surcharge or rebate regression there would pass silently |
| 6 — Edge cases (`E01`-`E08`) | 8 | Empty, whitespace, no-numbers, zero, negative, garbage, immediate `/end` — crash-safety only (`test_suite.py:300-319`) | Passes if a string response is returned, regardless of content |

## 3. Known gaps (why "97/97" overstates readiness)

| Gap | Evidence | Consequence |
|---|---|---|
| **No API tests** | Nothing imports `fastapi.testclient`; `main.py` is never imported by any test | Endpoints (`/chat` session round-trip, `/calculate` 500s, `/history` filtering, Pydantic 422s) are completely untested |
| **No frontend tests** | `frontend/package.json:6-11` has only `dev/build/start/lint` scripts; no vitest/jest/playwright deps | Regime-math display, markdown renderer, and the 400 ms chat loop can regress invisibly |
| **Cannot-fail smoke prints** | `smoke_test.py:30,36,43` hardcode `[PASS]` strings | Running the smoke test *always* looks green regardless of engine state |
| **Assertion-free scripts** | `final_test.py` has no comparisons; `manual_parity_check.py` computes an expected value and never diffs it | Parity must be verified by a human reading the console |
| **Loose tolerances** | `test_suite.py:264-265,270` (±2000, ±5000) | A ₹2,000-₹5,000 error per case — exactly the size of a misapplied professional-tax default or 87A edge — is invisible |
| **No regression corpus from production logs** | The misclassifications recorded in `backend/logs/session_audit.json` (see [nlp-pipeline.md](nlp-pipeline.md) §11) are not replayed anywhere | The same tuition/PPF/property-sale errors can ship again |
| **No CI** | No `.github/` directory in the repo | Nothing prevents a red suite from being committed; tests only run when someone remembers |
| **No negative-path tests** | Edge block checks crash-safety, not wrong-but-plausible output | e.g. forged `age: 80` on `/calculate` changing 80TTB/80D caps is untested |
| **Test/report artifacts committed** | `backend/test_report.json` in git | Stale green badge risk; README cites it |

## 4. pytest migration target (ADR-011)

Per [decisions.md](decisions.md) ADR-011 and roadmap Week 1 item 8, the target state is:

1. **Port the harness to pytest** — map blocks 1-6 to `backend/tests/test_parser.py`, `test_profession.py`, `test_attention.py`, `test_conversation.py`, `test_tax_engine.py` (tighten tolerances to exact-rupee or ±1), `test_edge_cases.py`. Keep the existing scenario tables as parametrize fixtures; the `check()` helper maps 1:1 to `assert`.
2. **Add API tests** with `fastapi.testclient.TestClient`:
   - `/chat` happy path (session round-trip, `tax_report` presence gate), malformed body → 422, forged session (`phase: "FINAL"` on turn 1, negative amounts);
   - `/calculate` for every case in `test_suite.py` Block 5 (catches engine/endpoint drift), plus malformed `capital_gains` shapes (today these 500 — see [api-reference.md](api-reference.md));
   - `/history/{sid}` filtering, unknown-sid → `[]`, corrupt-file behavior (currently silently `[]`).
3. **Golden-file regression tests** replaying the misclassified utterances from `backend/logs/session_audit.json` (the §11 patterns in [nlp-pipeline.md](nlp-pipeline.md)) with pinned expected categories — these are the tests that would have caught the April regressions.
4. **CI (roadmap Week 3 item 4)**: GitHub Actions running `pytest`, `pip-audit`, `npm audit`, and `next build` on every PR.
5. Frontend tests arrive later (roadmap Week 4 item 1): Vitest for the `SavingsGraph`/`TaxReport` display math, Playwright for the chat→report happy path.

## 5. Quick verification recipes (until pytest lands)

| Concern | Command | What "good" looks like |
|---|---|---|
| Full harness | `cd backend && python test_suite.py` | `TOTAL: 97 tests | PASS: 97 | FAIL: 0`, fresh `test_report.json` |
| Smoke | `cd backend && python smoke_test.py` | 4 real parser lines `[PASS]`; read the remaining sections manually (they cannot fail) |
| ANFIS / engine sanity | `cd backend && python final_test.py` | Scores printed per profile; compare against prior runs (the committed `anfis_weights.json` self-reports R² ≈ 0.50, not the README's 0.88 — see [decisions.md](decisions.md) ADR-004) |
| Parity | `cd backend && python manual_parity_check.py` | `Old Regime Tax` ≈ expected ₹12,71,400 (±prof-tax assumption) |
| Stress prompt | `cd backend && python industrial_stress_test.py` | Inspect the extraction block — expect the misclassifications documented in [nlp-pipeline.md](nlp-pipeline.md) §11 |
| Performance | `cd backend && python verify_upgrade.py` | ms/case figures; no pass/fail |

Note: on Windows consoles the scripts self-configure UTF-8 output (`test_suite.py:7`, `final_test.py:3`); on other platforms set `PYTHONIOENCODING=utf-8` if emoji-laden responses garble the terminal.

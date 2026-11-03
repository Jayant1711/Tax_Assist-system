# FINAL_VALIDATION_REPORT.md

**Final independent validation — Sprint 4 / v0.5-sprint4 tag decision**
**QA lead (independent re-run — prior reports treated as claims, not evidence)**
**Date:** 2026-11-04 · **Branch:** `sprint-4-ai-modernization`
**Requested commit:** `2ff960871c246b800f7fb9413d2e618387bdacce` · **HEAD at end of run:** `01661ebda658c4d395374778a83f5c24edeaaec0` (see §1 — docs-only drift, all gates re-run on both)

Every number below was measured fresh in this session. Tooling: Python 3.15.2, pytest 9.2.0, Docker 29.9.2 / Compose v5.6.1, Windows 10 x64 (Git Bash).

---

## 1. Environment integrity event (disclosed, not a blocker)

At **00:27:43 +0530**, mid-validation, commit `01661eb` ("docs: final audit hygiene (D1-D8) — ADR-016 recorded, registry metrics current, roadmap P0.1 normalization fixes") appeared on the branch. **This validation did not author it.** Scope check (`git diff 2ff9608..01661eb --stat`): **7 markdown files only** (ANFIS_RETRAINING_PLAN, ANFIS_VNEXT_ARCHITECTURE, FINAL_TECHNICAL_AUDIT (new), MODEL_REGISTRY, PROJECT_STATUS_REPORT_V3, SPRINT5_ROADMAP (new), docs/decisions.md). **`git diff 2ff9608..01661eb -- backend/` is empty — zero code change.** Nevertheless, every fast gate (pytest, vitest, eval, ANFIS training, ADR-001 audit) was **re-run on `01661eb`** and reproduced identical results (both runs recorded in §2). The Docker image and live E2E were built/run from the post-commit tree. Working tree clean before and after all runs (`git status --porcelain` empty); no artifacts written by training (no `anfis_v5_weights.json` — correct: v4 `anfis_weights.json` untouched, v5 TSK candidate intentionally not deployed).

---

## 2. PASS/FAIL table

| # | Check | Expected | Measured (at `2ff9608`) | Measured (re-run at `01661eb`) | Verdict |
|---|---|---|---|---|---|
| 1 | Backend pytest (`python -m pytest -q --tb=short -p no:cacheprovider`) | 1,146 passed / 1 deselected / 0 failed | **1,146 passed, 1 deselected, 0 failed** in 52.97s | **1,146 passed, 1 deselected, 0 failed** in 47.15s | **PASS** |
| 2 | Frontend vitest (`npx vitest run`) | 22/22 | **22 passed / 22** (4 files) in 1.94s | identical | **PASS** |
| 3 | Eval gate (`python tools/run_eval.py`) | GATE PASS, macro bookable F1 1.000 | **GATE (>= 0.95): PASS**; MACRO P=1.0 R=1.0 **F1=1.0**; MACRO (bookable only) **F1=1.0**; 21/21 categories F1 1.0; abstention 17/17 | identical | **PASS** |
| 4 | ANFIS v5 (`python tools/train_anfis_v5.py`) | "DEPLOYMENT PATH: exact rule heads PASS"; TSK G4/G5 fail documented off-deployment | exit 0, wall 73.8s; **"DEPLOYMENT PATH: exact rule heads PASS — v0.5 ships engine-priced intelligence (TSK experiment continues off-deployment). v4 untouched; no candidate weights needed."**; G1 MAE 0.136 (<=2.0) PASS · G2 cal −0.112 PASS · G3 20/20=100.00% PASS; TSK: G4 savings MAPE **794.69%** on 209/220 material rows (MAE INR 100,352) FAIL · G5 opportunity **P=0.000 R=0.000** FAIL · G6 top-1 **2744/4811 = 57.04%**; RULE HEADS **P=1.000 R=1.000, savings MAE=0.00**; learned eff head MAE 15.675 (experiment) | byte-for-byte same gate lines | **PASS** |
| 5 | ADR-001 audit (independent, script outside repo) | every `estimated_savings` == QA recomputation; zero-benefit ⇒ NO BENEFIT / 0 | **15/15 candidate rows exact**; **0 findings**, exit 0 (§4) | identical | **PASS** |
| 6 | Determinism (identical scripted 7-turn sessions) | byte-identical reply transcripts | **sha256 identical across 3 sessions**: `d2a36ff4758869ce899f2f41446fc962562939456175491343f8312af266a61d` (3,094 bytes; per-turn 225/303/319/442/336/833/588 B) (§5) | same | **PASS** |
| 7 | Docker/live E2E (`docker compose up -d --build backend`) | build → healthy → register/login/session/chat → closing turn correct → clean down | build OK; container **healthy**; `/health` 200 `{"status":"ok","checks":{"db":"ok","audit":"ok"},"app_env":"prod"}`; register **201**, login **200**, POST /sessions **200**, 7× chat **200**, GET state **200**; closing turn correct in both directions (§6); `docker compose down` removed container + network, pre-existing volumes left intact | ran entirely on `01661eb` tree | **PASS** |
| 8 | Security probes (adversarial ×300) | all replies < 8 KB | HTTP: **max 6,218 B** (all < 8,192 B); NLP-layer direct: **254–599 B** (§7) | same code | **PASS** |
| 9 | Deliverable prerequisites | 12 files present | **12/12 present, non-empty, git-tracked** (§8) | — | **PASS** |

**Overall: 9/9 PASS → verdict VALIDATED (§10).**

---

## 3. Eval gate detail (measured)

```
records: 434  labeled spans: 454  predicted spans: 435  matched: 437
MICRO  P=1.0045977011494254  R=0.9625550660792952  F1=0.9831271091113611
MACRO  P=1.0  R=1.0  F1=1.0
MACRO (bookable only)  P=1.0  R=1.0  F1=1.0
GATE (>= 0.95): PASS
```
All 21 categories (incl. `ABSTAIN`) F1 = 1.0; confusion matrix has zero off-diagonal cells.
*Observation:* MICRO precision 1.0046 (>1) is an artifact of the harness's span-matching (matched 437 > predicted 435) — not gate-relevant, worth a harness fix someday.
The 1 deselected pytest item is the advisory extraction-gate test (`tests/test_nlp_eval.py::TestExtractionGateAdvisory`, marker `eval`, excluded by `addopts = -m "not eval"` in `backend/pytest.ini`) — the gate itself was run explicitly here (step 3) and PASSES.

## 4. ADR-001 audit — measured results

Method: temp script **outside the repo** (`C:\Users\lenovo\qa_validation_tmp\adr001_audit.py`) calls `recommend(session, engine, get_intelligence())` on 5 diverse sessions with the real `TaxEngine`, then **independently** recomputes every row: `expected = round(min(old,new)_{base} − min(old,new)_{base+headroom_topup}, 2)` via direct `engine.calculate_tax_advanced(..., tax_year="fy_2025_26")` calls. Also asserts verdict semantics and `ti=None` pricing identity.

| Session | Regime advisory ok | Top-3 rows (head: QA-expected = served) | Result |
|---|---|---|---|
| S1 salaried ₹15L, metro HRA | True (New Regime, sav ₹75,660) | 80e: **47,060 = 47,060** RECOMMEND · 24b: 0 = 0 NO BENEFIT · 80c: 0 = 0 NO BENEFIT | MATCH |
| S2 senior ₹8L, 80c/80d maxed | True (New Regime, sav ₹26,000) | 24b: 0=0 · 80d_parents: 0=0 · 80e: 0=0 — all NO BENEFIT | MATCH |
| S3 zero-benefit ₹3L | True (engine_sav 0.0) | **all candidates NO BENEFIT, estimated_savings 0** | MATCH (zero-benefit contract holds) |
| S4 business ₹20L | True (New Regime, sav ₹186,680) | 24b: 0=0 · 80c: 0=0 · 80d: 0=0 — all NO BENEFIT | MATCH |
| S5 mixed ₹48L+CG+rental+agri | True (New Regime, sav ₹7,667.40) | 80e: **148,332.6 = 148,332.6** · 24b: **7,932.6 = 7,932.6** · 80g: **4,812.6 = 4,812.6** — all RECOMMEND | MATCH |

**15/15 rows: served `estimated_savings` and `savings_engine` exactly equal the independent engine recomputation (tolerance 0.005; all exact).** No fabricated rupees; zero-benefit rows honestly rejected with `NO BENEFIT (current regime ignores this head)` and `estimated_savings: 0`. `ti=None` produces identical pricing (learned layer cannot alter served rupees even if loaded).

## 5. Determinism — measured

Scripted 7 turns (`salary 15L → 80c 50k → 80d 25k → NPS 50k → rent/HRA Mumbai → 80g 15k → "no"` reaching the natural FINAL closing turn), run through the **live HTTP API** by three distinct registered users:
- transcript sha256 (over `turnN\n<reply>` ×7): **`d2a36ff4758869ce899f2f41446fc962562939456175491343f8312af266a61d`** for users A, B, C — byte-identical, 3,094 bytes.
- Cross-environment: the same script against a **local dev uvicorn** (APP_ENV=dev, port 8123) produced the **same sha256** as the **prod container** — byte-identical replies across dev/prod postures.

## 6. Docker/live E2E — measured

`docker compose up -d --build backend` (python:3.12-slim, pinned requirements) → container `tax_assist-system-main-backend-1` **Up (healthy)**; `/health` → 200 ok (db ok, audit ok, app_env prod). Auth flow over plain HTTP with the Secure `__Host-ta_session` cookie replayed manually (token lives only in the cookie by design):
- POST /auth/register → **201**; POST /auth/login → **200** (+Set-Cookie); POST /sessions → **200**; 7× POST /chat → **200**; GET /sessions/{id} → **200** (projection: `phase FINAL`, all slots booked).
- **Closing-turn correctness, both directions:**
  - Benefit session (final state ₹15L salaried): independent `recommend(top_n=1)` prices **80e top-up ₹5,00,000 → ₹62,140 (RECOMMEND)** ⇒ served closing turn **contains** `🧠 **Best opportunity** … est. savings ₹62,140 (confidence 85%; engine-verified)`; savings figure equals my recomputation. `block_iff_benefit = true`.
  - Zero-benefit session (₹3L teacher, all deductions 0 via "no" answers): closing turn **contains no block** (`block_present = false`), reply ends with the composer closing + Quick Tip only. Invariant holds iff-both-ways.
- Teardown: `docker compose down` → container + network **Removed**; `docker ps` empty. Named volumes `db-data` (created 2026-11-01) / `logs-data` (2026-11-03) **pre-date this validation and were left untouched**.
- Incidental positive finding: rate limiting observed live — after ~10 auth calls/min from one IP the API returned **429 `Rate limit exceeded` (retry_after 25s)** as configured (`TAX_RATE_LIMIT_AUTH_PER_MIN=10`).

## 7. Security probes — measured (<8 KB required)

| Probe (exact string) | Chars | Surface | HTTP | Reply size | <8,192 B |
|---|---|---|---|---|---|
| `sold last year. `×300 | 4,800 | live API | **422** (wire cap `message max_length=4000`) | **152 B** body | PASS |
| `sold last year. `×249 (in-bounds variant) | 3,984 | live API | 200 | **5,559 B** | PASS |
| `80u. `×300 | 1,500 | live API | 200 | **5,770 B** | PASS |
| `donation. `×300 | 3,000 | live API | 200 | **6,218 B** | PASS |
| `sold in 2024 `×300 | 3,900 | live API | 200 | **5,702 B** | PASS |
| `sold last year. `×300 | 4,800 | NLP layer direct (`process_message`) | — | **265 B** | PASS |
| `80u. `×300 | 1,500 | NLP layer direct | — | **459 B** | PASS |
| `donation. `×300 | 3,000 | NLP layer direct | — | **599 B** | PASS |
| `sold in 2024 `×300 | 3,900 | NLP layer direct | — | **254 B** | PASS |

The per-message note-dedupe guards (`nlp_engine.py` — the previously-measured 25–64 KB amplifications) hold: worst measured reply 6,218 B = 76% of the 8 KB budget. All sizes are full HTTP bodies.

## 8. Deliverable prerequisites — measured

All 12 files exist at repo root, non-empty, **git-tracked** on the branch:

| File | Lines | Bytes |
|---|---|---|
| ANFIS_ROOT_CAUSE_REPORT.md | 336 | 27,799 |
| ANFIS_V5_EVALUATION_V2.md | 55 | 3,667 |
| DATASET_QUALITY_REPORT_V2.md | 54 | 4,065 |
| EXPLAINABILITY_ENGINE_REPORT.md | 204 | 21,572 |
| CA_RECOMMENDATION_ENGINE_REPORT.md | 147 | 19,181 |
| INTELLIGENT_RESPONSE_REPORT.md | 41 | 2,951 |
| DATASET_REGISTRY.md | 14 | 3,357 |
| EXPERIMENT_REGISTRY.md | 20 | 4,534 |
| MODEL_REGISTRY.md | 20 | 4,312 |
| TRAINING_REGISTRY.md | 60 | 4,353 |
| SPRINT4_RELEASE_CANDIDATE_REPORT_V2.md | 72 | 5,901 |
| PROJECT_STATUS_REPORT_V3.md | 64 | 5,121 |

## 9. Observations (non-blocking, recorded for the tag decision)

1. **G6 figure protocol-dependence.** My current-protocol run measures TSK G6 ranking top-1 **57.04%** (`2744/4811`); registries/reports cite **95.72%** "on the previous run's protocol (engine-ordered)" — the reconciliation is documented in `ANFIS_V5_EVALUATION_V2.md` and `FINAL_TECHNICAL_AUDIT.md`. **Not a deployment risk:** the served ranking is engine-priced (verified in §4 — sorted by engine savings, exact), the TSK ranking head is off-deployment, and G4/G5 failures are correctly documented. Recommend the registries lead with the current-protocol 57.04% figure to avoid a viva/audit gotcha.
2. **HEAD drift** (§1): a concurrent process committed docs-only `01661eb` during validation. All gates were re-run and reproduced. The tag decision should be taken against a pinned, quiescent tree — `01661eb` currently, or re-pin to `2ff9608` if that was the intended tag base (code-identical).
3. **Eval harness MICRO precision >1** (1.0046) — matched>predicted span accounting artifact; gate is MACRO-based and unaffected.
4. `sold last year. `×300 exceeds the documented 4,000-char `/chat` wire cap and is (correctly) rejected 422 — the adversarial-reply bound is proven by the in-bounds variant and the NLP-layer direct probes.
5. `anfis_v5_weights.json` intentionally absent; v4 weights untouched; no candidate weights written — matches all three reports' claims ("no candidate weights needed").

## 10. Verdict

**VALIDATED.** All 9 checks PASS on independently measured evidence: 1,146/0 backend, 22/22 frontend, eval gate PASS with macro bookable F1 1.000, ANFIS v5 deployment path exact-rule-heads PASS with TSK G4 (MAPE 794.69%) / G5 (P/R 0/0) failures honestly documented off-deployment, ADR-001 audit 15/15 exact with the zero-benefit contract holding, 3-way byte-identical transcripts (cross-environment), live Docker E2E healthy end-to-end with the closing-turn block present iff the engine prices a benefit (both directions verified), all adversarial replies ≤ 6,218 B, and 12/12 deliverable prerequisites present. **No regressions and no blockers found.** The `v0.5-sprint4` tag decision is supported.

*Validation artifacts (outside the repo): `C:\Users\lenovo\qa_validation_tmp\` — `adr001_audit.py` + result JSON, `e2e_determinism_harness.py` + local/docker result JSONs, `train_anfis_v5.log` (both runs).*

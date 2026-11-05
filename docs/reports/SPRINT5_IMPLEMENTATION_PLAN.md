# SPRINT5_IMPLEMENTATION_PLAN.md — Phase 7 Execution Plan
**Generated:** 2026-11-04 · **Duration:** 2 weeks (single-developer cadence, ~10 working days) · **Baseline:** v0.5-sprint4 · **Owner agents:** per task (the mission's specialist roster)

---

## Phase order (dependencies drive the sequence)

```
Week 1
  M1 (day 1-2)   A: P0.1 normalization fixes + P3 tip regime-gating
  M2 (day 3-6)   B: P0 continuous sampler v3 → dataset v3 (≥5,000 positives)
                 C: P2 acceptance-event schema + capture endpoint (parallel with B)
Week 2
  M3 (day 7-8)   D: TSK retrain on v3 → gates → deploy-on-pass behind the flag
  M4 (day 8-9)   E: P6 frontend intelligence cards + P5 capture enablement
  M5 (day 10)    F: full validation + registries + docs + v0.6-rc
```

## Task table (Priority · Expected Impact · Effort · Owner Agent)

| # | Task | Pri | Impact | Effort | Owner Agent | Gate |
|---|---|---|---|---|---|---|
| 1 | P0.1: u80g normalization + 80d_parents probe + 80U/80DDB legs | P0 | label verifiability | S | data-engineer | mismatch count 0; suite green |
| 2 | P3: regime-gate `get_savings_tips` | P0 | user trust | S | backend-engineer | no tip contradicts the served regime (test-pinned) |
| 3 | P0: continuous sampler v3 (`generate_anfis_dataset.py` v3) | P0 | dataset growth | M | data-engineer | ≥5,000 positives; strata quotas; leakage green |
| 4 | P2: acceptance events (schema + `/sessions/{id}/recommendations` + capture) | P0 | feedback loop | M | backend-engineer | event per shown rec; ownership 404; audit minimized |
| 5 | P0: dataset v3 quality report (DATASET_QUALITY_REPORT_V3) | P0 | evidence | S | ml-data-scientist | floors met; leakage green |
| 6 | P1: TSK retrain on v3 + gates (G4 ≤10% · G5 · G6) | P1 | ML promotion attempt | M | ml-engineer + ml-evaluation-engineer | deploy-on-pass; else documented continuation |
| 7 | P1: shadow-compare tsk vs rules on 200 live sessions | P1 | deployment evidence | M | ml-evaluation-engineer | parity report; flag decision |
| 8 | P6: frontend intelligence cards (TaxReport) | P1 | UX | M | frontend-engineer | vitest + Playwright card checks |
| 9 | P5: enable `TAX_CORPUS_CAPTURE` on demo + monitor | P2 | organic growth | S | backend-engineer | capture rows appear; PII minimized |
| 10 | Registries: dataset v3, RUN-004, EXP-014..016, acceptance-v1 | P0 | traceability | S | research-scientist | 4 registries current |
| 11 | Full validation + v0.6-rc report | — | release | M | qa-lead | all suites green; VALIDATED verdict |
| 12 | ADR-017 (acceptance events) + ADR-018 (sampler) drafted | P1 | governance | S | architect | recorded in docs/decisions.md |

## Dependencies

```
1 (P0.1) ──► 3 (sampler) ──► 6 (retrain) ──► 7 (shadow) ──► (deploy? flag)
2 (tips) ──────────────── independent ──────────────►
4 (events) ──► 8 (cards) ──► (P2 loop closes next sprint)
9 (capture) ──► Sprint 6 organic eval
10 (registries) ◄── everything
```

## Validation gates (every phase exits through one)

| Gate | Tool/Command |
|---|---|
| Full suite | `cd backend && python -m pytest -q` (≥1,146, 0 failed) |
| Frontend | `npx vitest run` (≥25) + Playwright 7 |
| Extraction | `python tools/run_eval.py` → GATE PASS |
| Dataset v3 | DATASET_QUALITY_REPORT_V3: ≥5,000 positives · leakage green · floors met |
| TSK promotion | G4 ≤10% · G5 P/R · G6 top-1 ≥80% on v3 val |
| ADR-001 | recomputation suite on every new surfaced figure |
| Live | Docker rebuild + Playwright E2E (chat → report → cards) |

## Success metrics (Sprint 5 definition of done)

1. Dataset v3: ≥5,000 positives, strata quotas met, leakage green.
2. TSK heads: deployed behind the flag on gate pass — OR a documented gate-failure continuation (both are acceptable outcomes; hiding a failure is not).
3. Acceptance capture live: ≥80% of shown recommendations produce an event row.
4. Tips: 100% regime-consistent.
5. Suites: pytest ≥1,160/0 failed · Vitest ≥28 · Playwright green · eval gate PASS.
6. Scorecard: ≥90/100 (from 89) with no dimension regressed.

## Rollback plan (per deliverable)

| Deliverable | Rollback |
|---|---|
| Tip gating | revert the single gating commit (tips return to legacy) |
| Acceptance events | table unused if the endpoint is feature-flagged off; no session-payload change |
| TSK deployment | flag default `rules`; candidate weights never overwrite v4 |
| Cards | single component revert |
| Dataset v3 | additive files; anfis-v1 rows immutable in the registry |

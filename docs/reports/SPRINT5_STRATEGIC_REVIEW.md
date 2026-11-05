# SPRINT5_STRATEGIC_REVIEW.md — Strategic Reassessment After the Wave-3 Evidence
**Generated:** 2026-11-04 · **Trigger:** Sprint 5 produced decisive new evidence (dataset v3 at 51,873 positives; TSK denied at a third data scale; exact rule heads triple-verified) · **Basis:** `PROJECT_STATUS_REPORT_SPRINT5.md`, `TSK_PROMOTION_REPORT.md`, `DATASET_V3_QUALITY_REPORT.md`, `ANFIS_STRATEGY_V6.md`, `SPRINT5_PRIORITY_MATRIX.md`

---

## 1. The new evidence that forces a reassessment

| Finding | Measurement | Why it changes the plan |
|---|---|---|
| TSK G4/G5 fail at **377,753 rows, 323k train** (105× RUN-003b) | G4 MAPE 1.5M% · G5 P/R 0 · G6 65.26% | The "data volume" hypothesis is **falsified permanently** — the failure is structural (regime-flip discontinuity + additive-rule dilution), not data-shaped |
| The savings label is exactly linear in the paid ratios | val MAPE 1.6e-14 with f21/f22 | The correct model for this target is **an exact formula** — the rule heads already are one |
| Exact rule heads: P/R 1.0/1.0, MAE 0.00 at every scale | three deployment-shape verifications | There is nothing a learned head can add to these targets — approximation strictly loses |
| Dataset v3 exists (21,964 scenarios, continuous, LF-deterministic) | registry row anfis-v3 | The sampler **worked** — but its original consumer (TSK training) is cancelled; its purpose must be redefined |
| Grid saturation | deterministic rounds add zero scenarios | The generator's growth model is exhausted; only continuous sampling grows data |

## 2. Roadmap item classifications

| Roadmap item | Classification | Rationale (evidence) |
|---|---|---|
| **P1 TSK promotion attempt** | ❌ **CANCEL** (was: conditional on P0 data) | Three data scales falsified promotion (3.5k / 77k / 378k rows). The targets are closed-form; the rule heads compute them exactly. Re-open ONLY if a new target emerges that is genuinely non-computable (e.g. acceptance-derived preferences — Sprint 6 decision) |
| **P0 continuous sampler (row scaling)** | **MODIFY** — stop at v3; no further row scaling | The ≥5,000-positive gate is cleared 10× (51,873) yet promotion failed — more rows serve no current consumer. Keep the sampler code (works, deterministic); dataset v3 becomes a **benchmark/eval asset**, not a TSK feeder |
| **P0.1 remaining normalization fixes** (80d_parents probe, 80U/80DDB legs) | ⏸ **DEFER** to Sprint 6 (archive with the TSK experiment) | These features feed only the cancelled TSK heads; the served path (rule heads + composite) does not consume them. Document in `ANFIS_STRATEGY_V6.md` §deferred |
| **P2 acceptance capture** | ▶ **ACCELERATE** — becomes the top Sprint 5/6 priority | With TSK cancelled, the feedback loop is the **only** remaining path to better intelligence. The capture shipped in Wave 1; what remains: frontend acceptance wiring + analytics |
| **P3 tip regime-gating** | ✅ **CONTINUE** (done; mature it) | Shipped + test-pinned this run; verify across profiles in validation |
| **P5 organic corpus capture** | ▶ **CONTINUE** (background, unchanged) | Feeds the ADR-015 trigger; zero-cost enablement |
| **P6 frontend intelligence cards** | ▶ **ACCELERATE into Sprint 6 opening** | Now the highest user-value item: renders the ranked advisor list + acceptance buttons (wired to P2). The backend surface exists (`GET /sessions/{sid}/recommendations`, action endpoint) |
| **P4 NER expansion** | ⏸ **DEFER** to Sprint 6 (unchanged) | Research track; no new evidence changes its priority |
| Personalization / behavioral | ⏸ **DEFER** to Sprint 7 (data-gated) | Requires P2 acceptance history that does not exist yet |

## 3. Re-assessed Sprint 5 remaining scope (recommended)

The sprint's original goal — "close the learning loop; promote TSK on evidence" — is **substantially achieved and honestly closed**: the loop's capture half is live, and the promotion question is answered with a three-scale falsification. Remaining work that is genuinely Sprint 5:

1. **Close-out validation** (done: 1,155 pytest / 25 vitest / gates PASS — reported in `PROJECT_STATUS_REPORT_SPRINT5.md`).
2. **Docs/registry sync** (done this review: ANFIS_STRATEGY_V6 records the cancellations).
3. **Recommended: shorten Sprint 5** — declare it closed at the current HEAD (`eeb6937` + docs). P6 cards and P4 NER move to Sprint 6.

## 4. Recommended Sprint 6 scope (replaces the tail of Sprint 5)

1. **Merge the sprint branch to main** (opening action; CI green throughout).
2. **Frontend acceptance UI** (ex-P6): recommendation cards + accepted/rejected buttons wired to the action endpoint.
3. **Acceptance analytics v1**: acceptance rate per head × confidence band (funnel.py extension).
4. **Exact per-deduction impact estimator**: marginal-rate arithmetic per applied item (no ML — the f21/f22 lesson applied to UI honesty).
5. **Confidence calibration study**: with Wave-1 acceptance events accumulating, measure ECE of the 0.85 anchor; define the G7 gate for any future learned confidence.
6. **NER expansion** (background track, unchanged).
7. **Regime-gate the legacy NPS tip** (carried; small).

## 5. What Sprint 6 must NOT do (evidence)

- No TSK retraining on the same target family (three-scale falsification).
- No grid-based dataset growth (saturated).
- No learned confidence without an acceptance dataset + ECE gate.

## 6. The strategy in one line

**The engine prices; the rules decide what to show; the users teach the system what to rank.** Everything else is documentation.

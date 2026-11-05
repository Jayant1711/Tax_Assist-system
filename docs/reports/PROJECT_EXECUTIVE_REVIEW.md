# PROJECT_EXECUTIVE_REVIEW.md — Board-Level Project Review
**Prepared:** 2026-11-05 · **Span reviewed:** Sprint 1 → Sprint 6 (releases v0.4-sprint3 → v0.5-sprint4 → v0.6-sprint6) · **Sources:** the six strategy deliverables, the four registries, PROJECT_STATUS_REPORT_SPRINT5/6, MERGE_EXECUTION_REPORT, and the release evidence — every conclusion below carries its measurement · **Status:** review only; no code written, nothing committed

---

## 1. Project Evolution — Sprint 1 → Sprint 6

| Sprint | What was built | Release / evidence |
|---|---|---|
| **1** | The product exists: dual-regime Indian tax engine (FY-registered rules), Next.js 3-pane chat shell, guided discovery flow | base app |
| **2** | The trust foundation: **ADR-001** (TaxEngine = only calculator), scrypt auth + HttpOnly sessions (ADR-012/013), tax-rules registry (ADR-008), append-only audit (ADR-009), fail-closed CORS (ADR-014) | ADR set 001–014 |
| **3** | The NLP substrate: UniversalParser + SemanticAttention + waterfall extraction, corpus-v1 (2,226 records, sha256-pinned), Wave-D server-side session contract, evaluation framework | **v0.4-sprint3** |
| **4** | The intelligence layer: ANFIS v5 composite (MAE 0.136), **exact rule heads** (P/R 1.0, savings MAE 0.00), response composer, extraction certification (**macro F1 1.000**), Applied-vs-Ignored transparency panel, 6 governance audits, security APPROVE, scorecard 89/100 | **v0.5-sprint4** (PR #4) — 1,146 pytest / 25 vitest |
| **5** | The evidence sprint: dataset v3 (**377,753 rows / 51,873 positives** via continuous deterministic sampler), **TSK promotion denied at three data scales**, acceptance capture designed + shipped (ADR-017), regime-gated tips | waves 1–3 + strategic reassessment |
| **6** | The loop closes: shown→accepted→funnel live (one-click acceptance verified end-to-end), calibration instrument + canary (ECE 0.0) + **G7 gate**, intelligence cards in the report UI, **exact per-deduction impact engine** (leave-one-out, no ML), 5 real bugs caught live and pinned | **v0.6-sprint6** (PR #5) — **1,166 pytest / 31 vitest, CI green, 0 regressions** |

Trajectory in one line: *calculator → trusted calculator → explaining calculator → teaching-and-learning copilot.*

## 2. Biggest Successes

1. **The exactness architecture (ADR-001) held through everything.** Three sprints of "AI features" never produced a single unexplained rupee. Every number in cards, impact table, and advice is engine-recomputed (EXP-008, Sprint-6 E2E).
2. **The negative results became assets.** The TSK denial (3 scales), the grid saturation, and the closed-form label discovery were converted into permanent policy and a never-repeat ledger (`ML_NEGATIVE_RESULTS.md`) — the rarest artifact in student ML work.
3. **The dataset strategy worked** where it mattered: 1,623 → 51,873 positives (32×), deterministic, registry-tracked, CI-reproducible — and it *answered* its question (falsification) rather than just growing.
4. **Live-verification discipline** caught five bugs that every review and every test suite missed (sign inversion, `/end` capture skip, random ids, 115BAC semantics, JSX corruption) — now a release gate (D8).
5. **Two clean releases with governance**: PR #4 and PR #5, both CI-gated, tagged, changelogged, certified post-merge, baseline-frozen — release engineering is now routine, not heroic.

## 3. Biggest Failures

1. **The learned savings/opportunity heads never shipped** — three eras, three failures (G4 MAPE 795% → 1.5M%; G5 P/R 0). The honest framing: this was the *right* failure — it exposed that the target was a formula, not a learning problem (N4/N5).
2. **A ₹-1,30,000 benefit displayed as negative** in the first impact table — caught only by running the product, not by 1,155 tests or review. Failure of imagination, fixed and pinned, and institutionalized as D8.
3. **The `/end` path silently skipped the entire closing intelligence** — a whole user flow had no recommendations recorded. Found by clicking, not by reading.
4. **Adoption data is nearly absent** despite correct capture — the bottleneck moved from engineering to usage, and no sprint planned for *generating* usage until Sprint 7 was proposed.
5. **Documentation mass** — 30+ reports across two sprints; excellent for traceability, but discoverability now depends on the baseline document and registries doing their job.

## 4. Decisions Proven Correct

| Decision | Proof |
|---|---|
| Engine-only pricing (ADR-001) | zero pricing incidents across 3 sprints; the 46L "bug" was frontend transparency, not the engine |
| Gates + rollback-by-default for any learned component | ANFIS rollback held (Sprint 4); TSK denied 3× without ever reaching users |
| Deterministic extraction retained (ADR-015) over a learned extractor | macro F1 1.000; zero extraction regressions since |
| Dataset-as-benchmark pivot after falsification | no further spend on a dead consumer; sampler retained as an eval asset |
| One shared closing-intelligence helper (over copy-paste) | the `/end` fix became a 2-line reuse, regression-pinned |
| Release governance (PR → CI → merge → tag → certify → freeze) | two releases, zero post-merge surprises, clean rollback notes |

## 5. Decisions Proven Wrong

| Decision | What happened | Correction |
|---|---|---|
| "More data will promote the TSK heads" (Sprint 5 P1) | 105× data made G4/G5 worse — structural, not statistical | D2: closed permanently; effort moved to the loop |
| "Marginal-rate savings estimates suffice in the UI" | invited user distrust (46L incident) | replaced by exact leave-one-out impact (Phase 5, Sprint 6) |
| "Random recommendation ids are fine" | every card acceptance would 404 | deterministic `uuid5(session|head)` |
| "Capture shipping = data flowing" | `/end` sessions recorded nothing until the Sprint-6 fix | both closing paths share one helper, pinned |
| "Class imbalance is a loss-weighting problem" | P/R 0 at 20:1 weighting; equal-balance underdetermined | stratum design (v3) — and then the heads were cancelled anyway |

## 6. Technical Debt Remaining

| Debt | Severity | Note |
|---|---|---|
| 24(b) impact reason string doesn't distinguish self-occupied vs let-out | Low | cosmetic; applied-column is already correct |
| `viewed`/`dismissed` actions captured but never auto-fired | Low | Sprint 7 S7.2 |
| Per-session only analytics (no per-user lifetime view) | Medium | the dashboard is the fix; store schema is ready |
| 30+ root-level reports, uneven discoverability | Medium | PROJECT_BASELINE_CURRENT.md is the index; consider a docs/ consolidation sprint item |
| `data/anfis_v3` (270MB) local-only, regenerable | Low | documented; gitignored deliberately |
| 80d_parents feature strata + P0.1 residuals feed cancelled heads | Low | archived with the TSK experiment |
| SQLite single-node storage | Accepted | correct for the threat model; revisit only if the deployment story changes |

No debt touches the trust core: the engine, audit, auth, and determinism layers are clean.

## 7. Current Competitive Advantages

1. **Provably exact tax arithmetic** — one calculator, versioned FY rules, recomputed evidence on every claim. No LLM wrapper can claim this.
2. **A closed, auditable learning loop** — show → accept → funnel → calibration gate (G7) — rare even in production tax products.
3. **A negative-results ledger + permanent policy** — institutional memory that prevents re-spending lost effort.
4. **Deterministic, reproducible ML artifacts** — seeded datasets, sha256 manifests, CI-repro builds.
5. **Release engineering maturity** — two governed releases, baselines, rollback paths; a viva-ready paper trail (30+ evidence documents).
6. **Honest scarcity** — the system says "no benefit" and "unmeasured" out loud; evaluators consistently reward this.

## 8. Current Weaknesses

1. **Adoption volume is near zero** — the loop is correct but young; every data-gated feature is blocked until real usage exists.
2. **Reach is narrow** — salaried profiles dominate; business, CG, and Form-16 input flows are partial or absent.
3. **Single-FY depth** — FY 2026-27 will require a rules drop + re-certification (designed for, not yet exercised).
4. **No outbound artifact** — the computation statement is screen/print only; no ITR-mapped export yet.
5. **Solo-reviewer risk** — the security and tax-expert passes were single-agent reviews; a second independent pass would strengthen claims (process risk, not a known defect).
6. **Discoverability of evidence** — 30+ documents; without the baseline index, navigation is hard for a newcomer.

## 9. Sprint 7 GO / NO-GO Assessment

**GO** — on the proposed (adoption-only) scope, and only that scope.

| Factor | Assessment |
|---|---|
| Strategic fit | exact — completes the loop the last two sprints built; nothing in scope touches frozen policy (D1–D4) |
| Risk | LOW-MED — dashboard is read-only; Apply is the only write path, with defined stop conditions (ship-without-It fallback) |
| Effort | ~11 days ≈ 2 weeks, within house cadence |
| Expected evidence | ≥ 1,180 pytest / ≥ 36 vitest, 100% funnel coverage, one full live apply-loop E2E |
| Data-gated items | correctly deferred (personalization, learned ranking, learned confidence) |
| Stop conditions | defined and actionable (SPRINT7_PROPOSAL §4) |

NO-GO would be justified only for: (a) any scope containing model retraining (excluded), or (b) no capacity to run the live-verification gate (D8 requires it).

## 10. Recommendation: **CONTINUE**

- **Continue** — one more sprint (Sprint 7, adoption scope), then re-assess at the ~50-resolved-event data gate. The architecture is proven, releases are routine, the roadmap is evidence-first, and the remaining value is reachable at low risk.
- **Not Pause** — pausing halts exactly the acceptance-data accumulation that every deferred decision needs; the carrying cost of continuing is lower than the restart cost of pausing.
- **Not Pivot** — no evidence supports a direction change: all quality gates are green, the differentiator (exactness + auditability + honest learning) is validated, and the identified weaknesses (reach, adoption) are extensions of the current product, not arguments against it.
- **Not Finish** — v0.6-sprint6 is a defensible stopping point, but it ships a loop nobody has watched run; one adoption sprint converts infrastructure into demonstrable value (Accepted-₹) — the difference between "it works" and "it was worth building."

**Board-level bottom line:** the project has spent its risk budget wisely — every speculative path was either validated and shipped, or falsified cheaply and converted into policy. The remaining plan is execution, not exploration. Continue.

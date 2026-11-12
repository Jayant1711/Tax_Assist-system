# PROJECT_STATUS_REPORT_SPRINT7.md — Sprint 7 Status
**Generated:** 2026-11-13 · **Theme:** Adoption + Explainability (the paper's Section VIII program, made real) · **Verdict: COMPLETE (S7.5 research half corrected, practitioner sign-off pending) — pushed, CI green, released v0.7-sprint7**

---

## 1. Executive summary

Sprint 7 turned the closed feedback loop into a **usable, explainable product** and closed the project's biggest honesty debt. The user can now see WHY the CA layer suggests what it suggests (fired readable rules), accept a suggestion with one click (the engine re-prices the whole report), and see everything they have ever accepted (the Adoption Dashboard with the Accepted-Rupee metric). And the NER research track — which reported a fabricated 0.143 "accuracy" — was audited, corrected, and now measures a real 91.36% token accuracy / 0.756 macro F1.

## 2. Deliverables

| Item | State |
|---|---|
| Explainable CA layer (`fuzzy_ca.py`: authored rulebase R01-R10, decoder, gated firing) | ✅ live, pinned |
| Engine-priced plans (`ca_plans.py`, phantom-actuals partition, regime_before/after) | ✅ live, pinned |
| Fired-rules card + plans card + Apply in the report UI | ✅ live |
| Adoption Dashboard view (`GET /analytics/overview`, Accepted-Rupee, gate 1/30) | ✅ live |
| Action finality + viewed auto-fire | ✅ live, SQL-enforced |
| One-click Apply (clamp → acceptance → reprice) | ✅ live |
| 24(b) occupancy-aware impact reason | ✅ live |
| NER correction: real evaluator, BIO label space, deterministic vocab, seeded split, expanded templates | ✅ measured 91.36% / 0.756 macro F1 |
| CA rule validation (practitioner-proxy) | ✅ report written; real-CA pass pending |
| S7.5 remainder: real-practitioner validation + wider NER grammar | ⏸ deferred (honest scope) |

## 3. Engineering facts

- Commits: `4dc5dfb` (CA layer), `7a9dfbe` (paper + deck), `72192ab` (adoption loop), plus the closure commit.
- Tests: **1,209 pytest / 44 vitest** (from 1,166/31 at v0.6).
- New modules: `fuzzy_ca.py`, `ca_plans.py`, `AdoptionDashboard.tsx`; new endpoints: `/analytics/overview`, `/apply_plan`, `.../{event_id}/apply`.
- Subagent review wave: tax-expert (2 P0 statutory fixes + formal CA validation report), qa-lead (2 P1 data-corruption bugs in the NER corpus + coverage program), security-auditor (approve-with-nits, hardening applied).
- Two REAL bugs found by the review wave that no test had caught: the fabricated NER evaluator, and phantom-actuals plan suggestions. Both fixed and pinned.

## 4. The release

Tagged **v0.7-sprint7** with release notes; CHANGELOG `[Unreleased] — sprint7` promoted to `[0.7.0-sprint7] — 2026-11-13`.

## 5. What Sprint 8 inherits

- The adoption instruments accumulate data: personalization (D6) and learned confidence (G7) unlock on real resolved-event volume.
- The explainable CA layer's rule validation needs a REAL practicing CA (the model-proxy report exists at `CA_RULE_VALIDATION.md`).
- NER grammar widening (the corrected pipeline is ready for it).
- Deferred: cohort analytics, multi-year dashboard history.

## 6. One-line conclusion

Sprint 7 made the loop usable, made the layer explainable, and — by auditing its own evaluator — proved the honesty policy works in both directions: it stops inflated claims AND catches quietly broken measurements.

# SPRINT7_VALIDATION_REPORT.md — Sprint 7 Validation
**Generated:** 2026-11-13 · **Scope:** the full Sprint 7 theme — explainable CA layer, adoption loop completion, NER correction · **Verdict: 0 REGRESSIONS — 1,209 pytest / 44 vitest / CI green / live E2E verified**

---

## 1. Test matrix

| Suite | Result | Delta vs v0.6 |
|---|---|---|
| Backend pytest | **1,209 passed** / 0 failed | +43 |
| Frontend vitest | **44 passed** (+ tsc clean) | +14 |
| CI | 3 jobs green on every push | — |
| Live E2E (Playwright) | full adoption loop verified (below) | — |

## 2. What shipped and how it is pinned

| Feature | Pins |
|---|---|
| Explainable CA layer (`fuzzy_ca.py`) | rulebook decode completeness; NO-rupee invariant (no engine import); firing determinism; known-answer firings (R02/R03/R10); **floors are hard gates** (validator fix); R06 metro-rent band; R01 gated at 15L; membership bounds |
| Engine-priced plans (`ca_plans.py`) | top-plan savings = independent engine recomputation; combo priced as one recomputation; **phantom-actuals partition** (contribution vs actual heads, validator fix); determinism; empty/invalid sessions safe; per-plan `regime_before/after` |
| Adoption Dashboard (S7.1) | `user_adoption_overview` aggregation; Accepted-Rupee sum; endpoint auth; caller scoping; gate fields |
| Action finality (S7.2) | viewed never overwrites accepted (SQL CASE); accepted upgrades viewed; endpoint 200 no-op semantics |
| One-click Apply (S7.3) | headroom clamp to statutory cap; idempotent 409 at cap; foreign/unknown 404; **applying records acceptance** (funnel integrity); engine repricing |
| Frontend | cards render confidence/savings/reason/evidence; viewed auto-fire once; apply success state ONLY after server ok (QA fix); apply-plan payload `{levers:[{head,delta}]}`; fired-rules card; dashboard tiles/gate/empty/error states |
| NER correction (S7.5) | torch-free `test_phase_d_corpus.py`: 13-tag BIO space, corpus determinism, all 6 entity types, multi-entity samples, B-/I- known-answers (incl. the late-span case), vocab determinism/alignment, seeded split |

## 3. The Sprint 7 findings (each earned a fix)

1. **The NER evaluator was fabricated** — the reported 0.143 "accuracy" was a softmax confidence of a NaN-diverged model; per-class metrics were synthesized from entity counts; the label encoding had no B-/I- entries so every entity token collapsed to "O". Corrected: real token-level evaluator + BIO label space + corpus-built vocabulary + seeded split + gradient clipping. **Measured after: 91.36% accuracy / 0.756 macro F1** on 471 samples.
2. **Phantom actuals in plans** — the plan layer suggested "Add Rs 2,00,000 home-loan interest" to clients with no home loan. Fixed with the contribution/actual-head partition (actual levers only when the underlying fact is booked).
3. **R06 rent band bug** — rent read against the headroom scale zeroed out above Rs 1.2L rent; metro renters never got the HRA note. Fixed with a dedicated rent scale.
4. **Floors were decorative** — per-condition min-strength floors never gated; R01 fired at 15L income. Fixed: floors gate; thresholds recalibrated.
5. **80E mislabeled as new-regime-allowed** (tax-expert P0) — corrected sentences + regime tags on every lever.

## 4. Live E2E transcript (running stack)

1. Login → 15L + 80E + 24(b) profile → `/end` → FINAL.
2. Fired-rules card renders R03 et al. with strengths.
3. Plans card: Plan A (combined) ₹41,600 / Plan B ₹31,200 / Plan C ₹10,400 with per-step reasoning.
4. Click "✓ Apply this" (80C card) → 80C booked → statement re-priced (deductions ₹9,00,000, net ₹6,00,000) → card shows "✓ Applied".
5. Adoption Dashboard: 24 shown / 1 accepted / Accepted-Rupee ₹32,500 / gate 1/30 — cross-session.
6. Regression checks: pre-FINAL cards show no buttons; failed apply shows the error state (unit-pinned).

## 5. Reviews

- **tax-expert** (rules + plans): CHANGES-REQUIRED → all P0/P1 applied (80E 115BAC(2)(i) correction; 87A bands; regime tags; phantom actuals; R06 band; floors). Follow-up formal validation: `CA_RULE_VALIDATION.md` (APPROVE-WITH-NITS on sentences; the plan-level findings are fixed in code).
- **qa-lead** (coverage): CHANGES-REQUIRED → the 3 highest-value tests added (finality/firing/stub-engine) plus the torch-free pinning suite; top findings fixed.
- **security-auditor** (surface): APPROVE-WITH-NITS → hardening applied (advisor_review try/except, limits cap, non-finite skip, combo fresh-copy).

## 6. Deferred (honest)

- S7.5's remaining half: rule-base validation against a REAL practicing CA (the model-proxy report exists; practitioner sign-off pending).
- NER template grammar is still template-limited (~470 unique samples; wider grammar needs its own pass).
- Cross-session dashboard is per-user only; no cohort analytics yet.

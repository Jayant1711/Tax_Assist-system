# INTELLIGENCE_IMPROVEMENT_REPORT.md — Phase 5 Intelligence Improvements
**Generated:** 2026-11-04 · **Scope:** confidence, ranking, usefulness, explainability — evidence-gated changes only

---

## 1. What improved this sprint (all test-pinned)

| Improvement | Mechanism | Evidence |
|---|---|---|
| **Confidence semantics** | fixed 0.85/0.30 replaced by the exact rule heads: `rule_confidence` — 0.85 anchored on the engine two-pass, 0.30 for priced-zero benefit | `tax_intelligence.py::rule_confidence`, wired into `recommend()` (audit finding F5 closed: the rule functions are now the served path) |
| **Ranking correctness** | ranked strictly by engine-priced savings (ties by head/delta order) — the TSK's 57-65% ranking is bypassed | `recommend()` sort key; qa-verified on 5 sessions |
| **Usefulness** | the Applied-vs-Ignored panel + the per-item estimated savings at the top slab rate — the user sees the rupee impact per deduction | live-verified ₹46L scenario (`TAX_COMPUTATION_TRANSPARENCY_REPORT.md`) |
| **Explainability** | three-layer decomposition documented (architect report); per-recommendation reasoning chains (why/evidence/impact/confidence) rendered in the panel | `EXPLAINABILITY_ENGINE_REPORT.md` |
| **f9/f11/f12 feature truth** | the intelligence features now match the composite's own normalization and the enum reality — any future estimator trains on honest inputs | `features_v2` probes |

## 2. What was attempted and honestly rejected

1. **TSK promotion at 378k rows** — G4 MAPE 1.5M% / G5 P-R 0: the regime-flip discontinuity is structural (`TSK_PROMOTION_REPORT.md`). The exact rule heads serve instead.
2. **Learned confidence** — the fixed 0.85 is engine-anchored; a learned confidence has no ground truth until acceptance data exists (Sprint 5 P2 creates it; calibration is Sprint 6).

## 3. Confidence formula (served, documented)

```
confidence = 0.85  if savings_engine > 0   (engine two-pass priced it)
confidence = 0.30  otherwise               (priced, genuinely no benefit)
```

Anchored on the authoritative two-pass; no model error term can reach the user. Sprint 6 replaces the constants with acceptance-derived calibration once ≥1,000 shown/accepted events exist (ECE gate ≤ 0.05).

## 4. Usefulness metrics (from the validation run)

- The advisor block appears exactly when the engine prices a benefit (verified both directions live).
- The panel answers the user-reported ₹46L question: which deductions applied (6 items, old regime), which were ignored (all, new regime — Sec 115BAC), why the regime was chosen (₹1,65,360 cheaper even with all deductions), per-item impact (applied × top slab rate).

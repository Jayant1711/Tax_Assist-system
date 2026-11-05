# DATASET_V3_QUALITY_REPORT.md — Phase 3 Quality Gates
**Generated:** 2026-11-04 · **Dataset:** anfis-v3 · **Target:** ≥5,000 positive-savings rows

---

## Gates

| Gate | Target | Measured | Verdict |
|---|---|---|---|
| Positive-savings rows | ≥ 5,000 | **51,873 (13.73%)** | ✅ PASS (10× target) |
| Leakage | strata/template-disjoint validation | every-7th val split; strata-disjoint by construction; template checks unchanged | ✅ PASS |
| Reproducibility | seeded, deterministic | sampler_version 3 · seed 472 · LF-deterministic writes; rebuild-repro green in the Linux py3.12 container | ✅ PASS |
| Coverage | all 9 heads probed, all 4 profiles | 80C/80D/80D-parents/NPS/24b/80G/80E/80TTA/80TTB × {Salaried, Business Owner, Senior Citizen, General} | ✅ PASS |
| Duplicates | no (session, head, delta) triples | continuous amounts → unique by construction | ✅ PASS |

## Composition

| Stratum | Share |
|---|---|
| Deterministic base grid (coverage anchors) | ~18% |
| Continuous heavy-deduction corner (24L-5Cr) | ~31% |
| Continuous flip band (12L-40L) | ~29% |
| HRA Rule-2A band | ~8% |
| CG 112A/STCG band | ~8% |
| Senior heads | ~6% |

## Why density jumped 0.31% → 13.73%

v1 probed fixed deltas at grid incomes where the New Regime dominates — almost no probe flips the regime. v3 (a) probes the FULL remaining headroom (regime flips live there), (b) samples the near-flip income band deliberately, (c) books heads at continuous utilizations so partial top-ups land inside the old-regime win region. Every positive is a genuine engine-priced regime flip or old-regime saving — no label inflation.

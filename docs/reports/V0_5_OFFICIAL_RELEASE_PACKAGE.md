# V0_5_OFFICIAL_RELEASE_PACKAGE.md — Phase 3 Official Release Contents
**Release:** `v0.5-sprint4` · **Generated:** 2026-11-04 · **Evidence:** all figures measured this run

---

## 1. Release notes (official)

**v0.5-sprint4 — Tax Intelligence Layer (ANFIS v5), Explainability Engine, CA Recommendations, and Computation Transparency**

Tax Assist AI's fourth sprint delivers the intelligence era: an ANFIS v5 Tax Intelligence Layer that annotates (never computes) tax figures, an explainability engine with three attribution layers, a CA-style recommendation system that refuses to invent savings, a response composer with deterministic data-aware phrasing, and a computation-transparency panel that shows users exactly which deductions applied, which were ignored and why, and why the recommended regime won — verified live on a ₹46L user scenario.

### Key achievements
1. **Intelligence layer** (`tax_intelligence.py`): two-pass engine-priced recommendations (P/R 1.0/1.0 exact rule heads), composite efficiency (MAE 0.136), saturation/opportunity analysis, documented confidence.
2. **Extraction certification**: macro F1 **1.000** on the eval split, gate PASS, abstention 17/17 — the "precision ceiling" premise falsified (ADR-015: no extractor model warranted).
3. **Transparency fix**: the user-reported ₹46L "deductions change nothing" case traced hop-by-hop — backend exonerated (matrix arithmetic exact incl. caps), frontend gap found and fixed with the Applied-vs-Ignored panel.
4. **Dataset expansion**: 5,964 TaxEngine-priced scenarios / 76,960 opportunity rows / 1,623 positives (11× density) with HRA, CG, and senior strata.
5. **Security hardening**: 5 reply-amplification/PII vectors closed (probes ≤587B), two APPROVE reviews.
6. **Test suite**: 1,146 pytest / 0 failures (from 1,099+6), 25 Vitest, 7 Playwright — plus the ADR-001 recomputation suite.

## 2. Changelog entry (the shipped `[Unreleased]` content)

Intelligence: `tax_intelligence.py` (recommend two-pass, rule heads, composite efficiency, explainability), composer 🧠 block, ADR-015/016. Fixed: 6 stale tests, phantom-8/earn/earner/NGO/lakh-stem extraction bugs, 5 amplification vectors, eval CLI gate render, statement double-count. Added: eval CLI, ANFIS v1 dataset/training tools (5,964 scenarios / 76,960 rows), forensics experiments, transparency panel, responsive shell. Full detail: `CHANGELOG.md`.

## 3. Key metrics

| Metric | Value |
|---|---|
| pytest | 1,146 passed / 0 failed (+47 net this sprint) |
| Vitest / Playwright / legacy | 25/25 · 7 · 97 |
| Extraction | macro F1 1.000 · gate PASS · abstention 17/17 |
| Intelligence | rule heads exact · composite MAE 0.136 · ranking 95.72% (engine-ordered) |
| Security | APPROVE-WITH-NITS ×2 → all findings closed |
| Scorecard | 89/100 (7 dimensions, floor 87) |

## 4. Audit evidence (the six-report chain)

`ANFIS_ROOT_CAUSE_REPORT.md` (6 measured experiments) → `ANFIS_V5_EVALUATION_V2.md` (expanded retrain + rule-head deployment) → `FINAL_TECHNICAL_AUDIT.md` (PASS, 10/10 claims verified) → `FINAL_VALIDATION_REPORT.md` (VALIDATED 9/9, determinism sha-verified dev+prod) → `FINAL_SYSTEM_VERIFICATION.md` (live DOM checks) → governance trio (`REPO_CONSISTENCY_AUDIT`, `RELEASE_EVIDENCE_AUDIT` 5/6 EVIDENCED, `TRACEABILITY_AUDIT` all-entries-mapped).

## 5. Intelligence layer summary

- **Two-pass ADR-001 pattern**: TaxEngine prices; ANFIS annotates. Verified by `TestADRBoundary` (every estimate = engine recomputation) and the qa recomputation audit.
- **Exact rule heads** (ADR-016): opportunity ⟺ engine-priced benefit; savings = engine delta; confidence 0.85/0.30. The learned TSK heads (48 additive rules, ridge-LSE) remain off-deployment experiments with promotion gates — the forensics report measured why (label = closed-form function of features; rule dilution).
- **Advisor coverage**: 9 deduction heads probed at full headroom (partial probes miss regime flips — measured), regime advisory, 87A band position, saturation analysis.

## 6. Transparency summary

The user-reported ₹46L case resolved hop-by-hop: NLP extraction correct (monthly rent/hra annualized), session correct, engine arithmetic exact to the rupee (incl. the 80D ₹25k cap and Rule-2A ₹20k), new regime correctly recommended (₹9.75L vs ₹11.4L — Sec 115BAC disallows the booked deductions). The gap was frontend narrative — now fixed with the Applied-vs-Ignored panel (live-verified: taxable ₹45,25,000 matches the matrix; ignored rows carry the 115BAC reason; the 80D cap callout visible).

## 7. Registries

`DATASET_REGISTRY.md` · `MODEL_REGISTRY.md` · `TRAINING_REGISTRY.md` · `EXPERIMENT_REGISTRY.md` — current, audit-verified, and the project can answer at any moment: where is the dataset, which model produced this result, how was it trained, which metrics support it, where is the code.

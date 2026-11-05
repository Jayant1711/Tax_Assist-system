# DATA_STRATEGY_V2.md — Phase 4 Next-Generation Data Pipeline
**Generated:** 2026-11-04 · **Baseline:** anfis-v1 v2.1 (5,964 scenarios / 76,960 rows / 1,623 positives — grid saturated) · **Registry:** DATASET_REGISTRY.md v2.1 → v3

---

## 1. The measured problem

| Constraint | Evidence |
|---|---|
| Grid saturation | generator rounds 3→4 added **zero** scenarios (periodic combos) |
| Positive scarcity | 1,623 positives (2.11%) vs the ≥5,000 the TSK gates need |
| Label expressibility | labels must be exact functions of schema features (f21/80ttb lessons) |
| No feedback signal | recommendations are never tracked → no acceptance data |

## 2. Pipeline v3 — four data sources, one registry

### 2.1 Continuous-value sampler (replaces the grid — Sprint 5 P0)
- **Amounts**: seeded `rng.uniform`/log-uniform ranges per head (e.g. 80C ∈ [0, 1.5L] continuous), incomes log-uniform 3L–2Cr.
- **Combinations**: seeded head-subset sampling (1-9 heads active per scenario) — no periodicity, no saturation.
- **Determinism**: fixed seed, versioned sampler config (sampler-version in the manifest).
- **Target**: ~18k scenarios × ~9 probes ≈ 120k+ opportunity rows, **≥5,000 positives** (density rises because old-regime-optimal corners are sampled deliberately, not stumbled into).
- **Strata guarantee**: per-stratum minimum quotas (heavy-deduction corner, HRA band, CG band, seniors, flip-adjacent incomes) — the strata pattern that delivered the 11× density gain, now continuous.

### 2.2 Acceptance-derived weak labels (Sprint 5 P2, later waves)
- Every recommendation shown/accepted/rejected/ignored → an event row.
- Accepted recommendations = weak positive labels for the head/context; reviewed before eval use.
- Never trains TaxEngine inputs — only intelligence-layer heads (ADR-001).

### 2.3 Organic capture (Sprint 5 P5)
- `TAX_CORPUS_CAPTURE=1` on the demo deployment → `data/corpus/` grows.
- ADR-015 trigger tracking (≥5k organic turns).
- DPDP constraints: opt-in only, minimized fields (existing audit rules).

### 2.4 Synthetic template growth (corpus-v2, opportunistic)
- Extend the NLP corpus templates (Hinglish families, multi-entity, monthly forms) — the proven 11× density pattern from Phase 5, applied to corpus-v1's successor.

## 3. Schema v3 (registry-versioned)

| Change | Why |
|---|---|
| `sampler_version` + `seed` + `strata_id` in every row | provenance for the continuous sampler |
| `f21_old_tax_ratio` + hypothetical `f22_old_tax_ratio_hyp` promoted to schema (forensics: the savings label is exactly linear in the paid ratios — MAPE 1.6e-14) | the missing predictor, formalized |
| 80ttb composite term dropped or feature added (v2.1 lesson: labels must be feature-expressible) | no unlearnable terms |
| acceptance events as a SEPARATE dataset (acceptance-v1) — never mixed with engine-priced rows | clean label semantics |
| leakage checker extended: strata-disjoint validation (not just template-disjoint) | the sampler's strata can straddle templates |

## 4. Quality gates (every dataset version must pass)

1. Rebuild-repro test green (the CI test this strategy fixes the last gap for — EOL-deterministic writes landed).
2. Positive count ≥ target with per-stratum floors.
3. Leakage checker green (template + strata + session disjointness).
4. Coverage floors per category/head.
5. No duplicate (session, head, delta) triples.

## 5. Registry discipline

- `anfis-v3` gets its own DATASET_REGISTRY row at creation; `anfis-v1` rows are never rewritten (history immutable).
- `acceptance-v1` likewise.
- Every sampler/generator change = a new version + a registry row (RUN-*), never an edit of the old.

## 6. What this unlocks

| With ≥5,000 positives | Unlocked |
|---|---|
| TSK savings head G4 (MAPE ≤10%) | instant savings estimates (UI latency) |
| TSK opportunity head G5 (P≥0.95/R≥0.90) | pre-probe filtering (fewer engine calls) |
| Confidence calibration | learned P(benefit) replaces the fixed 0.85 |
| Personalization | per-profile confidence (P2 data) |

Until then: **rule heads serve, exactly** — the pipeline is the only path, and it is fully specified above.

# DATA_PIPELINE_V3_REPORT.md — Phase 2 Data Pipeline v3
**Generated:** 2026-11-04 · **Generator:** `tools/generate_anfis_dataset.py` v3 (sampler_version 3, seed 472) · **Output:** `data/anfis_v3/`

---

## Pipeline design (DATA_STRATEGY_V2 implemented)

1. **Continuous stratum** (the core fix): seeded RNG (472) draws — incomes log-uniform 3L-2Cr with the flip band (12L-40L) overweighted 50%; per-head utilization uniform [0,1] booked at u*limit; HRA legs on ~14% of scenarios; CG on ~20%; seniors 20%. No grids → no saturation (v1 rounds 3-4 added zero scenarios; v3 adds thousands per stratum).
2. **Base + expansion strata retained** for coverage (deterministic anchors).
3. **f21 baseline old-tax ratio + probes**: every opportunity row embeds the full session (provenance) and the engine-priced delta (two-pass `calculate_tax_advanced`).
4. **LF-deterministic writes** (`newline="
"`) — the corpus CI lesson applied to the anfis pipeline (EOL no longer shifts content hashes).
5. **Schema v3 savings matrix**: X = [features_v2(20), delta_norm, head_idx, f21] (23-dim) — the forensics-specified predictors.

## Measured output

| Artifact | Rows |
|---|---|
| scenarios | 21,964 |
| utilization.jsonl | 197,676 |
| optimization.jsonl | 377,753 |
| recommendation.jsonl | 377,753 |
| features.npz | 21,964 × 20 |
| savings.npz | 377,753 × 23 |

## Registry

DATASET_REGISTRY.md row `anfis-v3` (sampler-version 3, seed 472); supersedes anfis-v1 for training; anfis-v1 retained as the registry-documented pilot.

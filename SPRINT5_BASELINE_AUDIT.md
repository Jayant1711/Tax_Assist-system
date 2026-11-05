# SPRINT5_BASELINE_AUDIT.md — Phase 1
**Generated:** 2026-11-04 · **Baseline:** v0.5-sprint4 (`PROJECT_BASELINE_V0_5.md`) · **Method:** every claim cites a measured number from the sprint-4 runs

---

## 1. Strengths (keep — they are the sprint's compounding assets)

| Strength | Evidence |
|---|---|
| Gate + rollback discipline | TSK heads failed G4/G5 twice; rollback held both times; zero bad artifacts shipped (`ANFIS_V5_EVALUATION_V2.md`) |
| Deterministic extraction at ceiling | macro F1 1.000 · gate PASS · abstention 17/17 (`tools/run_eval.py`, re-run at HEAD) |
| Exact rule heads (ADR-016) | P/R 1.0/1.0, savings MAE 0.00 — engine-priced by construction, wired into `recommend()` |
| Single-source features | `features_v2` — train/serve divergence structurally impossible for intelligence inputs |
| Registry system | 4 registries, audit-verified; lineage answerable in minutes |
| Honest-findings culture | NER 0.143, TSK failures, eval-CLI bug — all documented, none hidden |
| Transparency panel | user's ₹46L case resolved and live-verified (panel + 115BAC reasons + cap callouts) |
| Test fortress | 1,146 pytest / 25 Vitest / 7 Playwright / 97 legacy — all green at HEAD |

## 2. Weaknesses (evidence-backed)

| Weakness | Measured evidence | Consequence |
|---|---|---|
| TSK learned heads data-bound | G4 MAPE 795% / G5 P0-R0 at 1,623 positives; label is an exact function of features | learned savings/opportunity unusable; only rule heads serve |
| anfis-v1 grid saturated | rounds 3→4 added zero scenarios (periodic combos) | dataset cannot grow without a sampler |
| Positive density 2.11% | 1,623/76,960 | TSK promotion needs ≥5,000 positives (forensics min-count) |
| NER at 0.143 | 51 template samples | sequence labeling is a documented non-capability |
| Legacy NPS tip not regime-gated | quotes ₹15,600 old-regime arithmetic to new-regime users (`ai_models.py:585-591`) | user-trust erosion; measured ₹0 engine price |
| Composite not wired to the results tile | frontend still renders the v4 ANFIS tile | two efficiency scores could confuse users |
| Single-worker deployment | rate limiter + audit writer are per-process | scaling beyond one worker needs design |

## 3. Bottlenecks (the constraint chain)

1. **Positive density (binding)**: every ML ambition downstream of anfis-v1 is gated on ≥5,000 positives — only the continuous-value sampler unlocks this.
2. **Grid saturation**: the deterministic generator is exhausted; the sampler must replace it, not extend it.
3. **No acceptance signal**: recommendations are never tracked → no feedback data → personalization and calibration have no training signal.
4. **Organic capture off**: `data/corpus/` is empty; the ADR-015 ≥5k-organic-turns trigger cannot move.

## 4. What is already Sprint-5-ready

- `SPRINT5_EXECUTION_READY.md`: P0.1 → P3+P2 → P0 → P1 sequencing validated with measured evidence.
- Gate infrastructure: `train_anfis_v5.py` gates + `run_eval.py` + ADR-001 recomputation suite — reusable as-is.
- Expansion strata pattern: proven 11× density gain; the sampler generalizes it to continuous values.

## 5. Audit verdict

**BASELINE SOUND — Sprint 5 is a data-and-feedback sprint, not an architecture sprint.** The architecture carried v0.5 intact; the deficits are all data-shaped (positives, acceptance, organic capture) plus two small trust items (NPS tip, v4 tile). No structural rework is justified by evidence.

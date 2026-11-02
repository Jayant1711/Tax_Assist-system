# ANFIS vNext Architecture — ANFIS Reborn as the Tax Intelligence Engine
**Phase 6 · ANFIS REBIRTH · 2026-11-02**
Companions: [`ANFIS_FEATURE_SCHEMA.md`](ANFIS_FEATURE_SCHEMA.md) (input/output contract, schema v1) · [`ANFIS_RETRAINING_PLAN.md`](ANFIS_RETRAINING_PLAN.md) (dataset, losses, gates) · [`ANFIS_EXPLAINABILITY_FRAMEWORK.md`](ANFIS_EXPLAINABILITY_FRAMEWORK.md) (explanation contract + worked traces).

---

## 0. Mission and hard invariants

ANFIS is **not removed**. It is transformed from a single opaque 0–100 tile into a **Tax Intelligence Engine** — a multi-head Takagi-Sugeno-Kang (TSK) inference layer that scores, ranks and annotates the output of `TaxEngine.calculate_tax_advanced` (`backend/tax_engine.py:238`).

Invariants (non-negotiable, enforced by tests):

1. **ADR-001**: `TaxEngine` is the ONLY source of tax numbers. The ANFIS layer may only score/rank/annotate engine OUTPUTS. No code path lets an ANFIS output mutate `total_tax`, `taxable_income`, `savings`, `recommendation`, slabs, or any `Explanation.amount`.
2. **Never invent tax law.** Every statutory number the layer prints (80C ₹1,50,000 · 80CCD(1B) ₹50,000 · 80D ₹25,000/₹50,000 · 24(b) ₹2,00,000 · 87A ₹12,00,000 band FY 2025-26 · 115BAC · 10(13A) Rule 2A) is read from the registry `backend/tax_rules/fy_2025_26.py:164-195` — never hardcoded in model text.
3. **Two-pass pattern**: pass 1 engine computes → pass 2 ANFIS annotates. Annotation is a pure function of `(session, engine_result)`; with the layer disabled the engine response is byte-identical to today.
4. Sprint-4 spec invariants hold: 952 pytest + 22 Vitest + 7 Playwright + 97 legacy stay green (`docs/sprint4-execution.md` "Hard invariants").

---

## 1. What exists today (code-verified findings)

These findings motivate every design decision below. All were reproduced on 2026-11-02 by running the live engine and shipped weights on three pinned scenarios (A/B/C, defined in §7 and fully traced in `ANFIS_EXPLAINABILITY_FRAMEWORK.md`).

| # | Finding | Evidence |
|---|---|---|
| F1 | **Trainer ground truth is not the live engine** (the ADR-004 core defect). `anfis_trainer.py:21-41` vectorized slabs target FY 2024-25; the registry default is now FY 2025-26 (Finance Act 2025 slabs `fy_2025_26.py:58-66`, 87A rebate 60,000 to ₹12L with the derived post-cess band endpoint 12,73,934 `fy_2025_26.py:100-115`). The trainer's HRA leg (`anfis_trainer.py:73`) is a random approximation, not the Rule 2A three-leg least-of test (`tax_engine.py:939-957`). The trainer books capital gains into the surcharge base but **never taxes them** — no 112A (12.5% over ₹1.25L), no 111A (20%), no property CG (`tax_engine.py:826-861`). Surcharge ignores the 1Cr band and marginal relief (`tax_engine.py:729-824`). 80G ignores the four-category model (`tax_engine.py:873-909`). | `docs/decisions.md` ADR-004 ❌ |
| F2 | **Shipped accuracy is far below advertised.** `backend/anfis_weights.json` metrics: `r2 = 0.4976`, `mse = 0.00818` — measured against the trainer's own synthetic formula, not the engine. ADR-004 records the advertised 0.88. | artifact tail |
| F3 | **The 64-rule base has collapsed to one rule.** On probe scenarios A, B and C, rule 2 carries normalized firing weight w̄ = 0.99987 / 0.99994 / 0.99995. The other 63 rules contribute ≈ 0. Explanations per-rule are therefore meaningless in v4. | probe, §7 |
| F4 | **Feature-vector divergence between serving and training.** `ai_models.py:689-710` (serving) vs `anfis_trainer.py:109-131` (training) share 20 slots but disagree on at least 6: f05 (serving reads dead legacy key `"hra"`; engine now books `hra_received`/`rent_paid`), f09 (serving divides 80TTA by 50,000 — statutory cap is ₹10,000 `fy_2025_26.py:142`), f15 (serving hardcodes `0.3`; trainer expected `age/100`), f18 (serving keys on `profile == "Senior Citizen"`; trainer used age ≥ 60), f19 (serving `1−80C/150k`; trainer aggregate headroom /275,000), f10-f12 (serving reads legacy numeric `"80u_80dd"`, `"80ddb"`, `"80eea"` — all dead: the engine books `80u_80dd_category` flats 75,000/1,25,000 and `80ddb_expenditure` tiers 40,000/1,00,000 since Sprint 2 Step D, and 80EEA is removed). | `ai_models.py:689-710`, `tax_engine.py:308-353` |
| F5 | **Production feature f16 is always 0.** `tax_engine.py:366` calls `anfis.score_efficiency(data, final_res.__dict__)` **before** `savings` is assigned at `:371-373`, so `result.get("savings")` is 0 at scoring time. Measured: scenario C scores 34.5 in production vs 42.6 with the intended feature. | probe |
| F6 | **The score is untethered from tax reality.** Probe scenario A (salary ₹12,00,000, 80C ₹1,00,000, 80D ₹15,000): engine says New Regime, tax ₹0 (inside the 87A band), engine-derived efficiency 100.0 (raw 101.04, clipped) — shipped v4 prints **39.7**. Scenario B (fully booked ₹18L salaried): engine-derived 76.76 vs shipped 62.7. Scenario C (senior + LTCG): 84.19 vs 34.5. | probe, §7 |
| F7 | **Tips can be wrong in the 87A band.** `ReasoningAgent.get_savings_tips` (`ai_models.py:572-608`) recommends topping up 80C/NPS whenever `session["80c"] < 150000` etc. In scenario A every Chapter VI-A top-up yields **Δtax = ₹0.00** (engine-verified, 8/8 heads) because total income sits inside the 87A rebate band. A model layer with engine-verified opportunity targets fixes this; the deterministic tips alone cannot. | probe |

ADR-004's prescribed fix is exactly this document: *"Re-train against live-engine outputs or park the score behind a beta label."* We re-train, and we keep the v4 artifact as rollback.

---

## 2. Target design — `TaxIntelligence` (multi-head TSK v5)

### 2.1 Model shape

One shared Gaussian rule base, multiple consequent heads — the ANFIS identity (20 inputs × 64 rules, first-order TSK) is preserved; only the consequent tensor grows a head axis.

```
Layer   Operation                                           Shape (v5)
L1      membership  μ[i,r] = exp(-0.5·((x_i - m[i,r])/s[i,r])²)   20 × 64
L2      firing      w[r]  = Π_i μ[i,r];  w̄ = w / Σw + 1e-9        64
L3      consequents f[h,r] = b[h,r] + Σ_i a[h,r,i]·x_i            9 × 64 × 21
L4      output      ŷ[h]  = Σ_r w̄[r]·f[h,r]  ∈ [0,1]              9
```

- Inputs: the 20 features of **`anfis-feature-schema/1`** (`ANFIS_FEATURE_SCHEMA.md` §2) — engine-derived and registry-capped, replacing every dead/miscalibrated legacy slot (F4).
- Outputs (9 heads, all ∈ [0,1]):
  - `out_eff` — efficiency score ×100 at display. Ground truth: the trainer's utilization formula recomputed **from live-engine numbers** (§4.3).
  - `opp_80c`, `opp_80d_self`, `opp_80d_parents`, `opp_nps`, `opp_24b`, `opp_hra`, `opp_80g`, `opp_80tta_ttb` — per-head **opportunity strength = normalized engine-verified tax delta** of topping the head up to its registry cap: `clip(Δtax / (gti·0.05 + 1), 0, 1)`. The same number, denormalized (× `(gti·0.05 + 1)`), is the **projected savings in ₹**; the engine confirms it. Ranking = sorting the heads by predicted value.
- Parameter count: `2·20·64 + 64·21·9 = 2,560 + 12,096 = 14,656` (v4: 3,904). Still a sub-millisecond NumPy forward on CPU.
- Artifact: `backend/anfis_weights_v5.json`, `schema_version: "anfis-feature-schema/1"`, `head_names: [out_eff, opp_80c, …]`. The loader dispatches by `schema_version`: v4 file (`backend/anfis_weights.json`, no version field) → legacy extractor + single head, byte-compatible with today; v5 file → schema-v1 extractor + 9 heads. Rollback is therefore a file presence decision, not a code branch (§6).

### 2.2 Serving module

New file `backend/tax_intelligence.py`:

```python
class TaxIntelligence:
    def __init__(self, engine: TaxEngine, anfis: ANFIS): ...
    def calculate_with_intelligence(self, state, tax_year=None, confirm: bool = False) -> dict:
        result = self.engine.calculate_tax_advanced(state, tax_year)     # PASS 1 — ADR-001
        result["intelligence"] = self.annotate(state, result, confirm)   # PASS 2 — annotation
        return result
```

`annotate()` (pure, no mutation of engine fields):
1. Extract schema-v1 features from `(state, result)`.
2. One forward pass → 9 head values.
3. Deterministic utilization block (exact ratios, no ML): `used / registry_cap` per head.
4. Opportunity list: heads with headroom > 0, sorted by predicted delta. In `confirm=True` mode each listed opportunity is **engine-verified** by re-running `calculate_tax_advanced` on a deep-copied state with the head topped to cap; `projected_savings_engine = base_best_tax − topped_best_tax` and `confirmed: true`. In instant mode (`confirm=False`) values carry `confirmed: false` and UI badges say "estimated".
5. CA-style insights + explanation trace (rule memberships, per-feature attributions) per `ANFIS_EXPLAINABILITY_FRAMEWORK.md`.

Config flags: `TAX_ANFIS_V5` (default on once §8 gates pass; off → v4 path + legacy extractor, today's behavior) and `TAX_INTELLIGENCE_CONFIRM` (per-endpoint confirm mode). No new dependencies; stdlib + numpy only (ADR-003 discipline).

### 2.3 Why one shared rule base (and not 9 small models)

- F3 shows v4's failure mode is collapse; a shared base with per-head consequents gives the EE-BAT trainer one membership landscape to regularize and the explainability framework one rule narrative to render.
- Head outputs remain individually interpretable: `φ[h,i] = Σ_r w̄[r]·a[h,r,i]·x_i` is an exact per-feature attribution for each head (TSK first-order property) — see `ANFIS_EXPLAINABILITY_FRAMEWORK.md` §2.

---

## 3. Dataflow and the two-pass pattern

```
user turn ──► NLP (nlp_engine.py, deterministic, ADR-003) ──► session state (SQLite app_sessions, ADR-013)
                                                                    │
                                                    PASS 1: TaxEngine.calculate_tax_advanced
                                                    (sole source of amounts — ADR-001)
                                                                    │
                                                    PASS 2: TaxIntelligence.annotate
                                                    (features → 9 heads → utilization/opportunities/
                                                     insights/trace; optional engine-confirm re-runs
                                                     on COPIED state — never the returned amounts)
                                                                    │
                             ┌───────────────────────────────────────┴──────────────────────┐
                             ▼                                                              ▼
                 /chat response (instant mode)                                  /calculate response (confirm mode)
                 intelligence.estimates + "estimated" badge                     intelligence.opportunities + "engine-confirmed"
```

The engine-confirm re-runs in pass 2 execute `calculate_tax_advanced` on **deep copies** with one head topped to its registry cap. Their results are used only to fill `projected_savings_engine` / ranking ground truth inside the `intelligence` block. The top-level `old_regime`, `new_regime`, `savings`, `recommendation` fields are always the **base** computation. A guard test asserts field-level equality of the engine payload with the layer on and off.

---

## 4. The seven mission capabilities → heads mapping

| Capability | Mechanism | Source of truth |
|---|---|---|
| 1. Tax efficiency scoring (0–100) | `out_eff × 100`; retrained vs engine-derived ground truth (F6: today's error is up to 60.3 points) | engine-derived GT formula (retraining plan §3.2) |
| 2. Deduction utilization modeling | Deterministic per-head ratios `used/cap` against registry caps (80C 150k · 80D self 25k/50k · 80D parents 25k/50k · NPS 50k · 24b 200k · 80G 10% qualifying limit · 80E uncapped · 80TTA 10k / 80TTB 50k · HRA Rule 2A) | `tax_rules/fy_2025_26.py:164-195` — no ML |
| 3. Opportunity detection | 8 `opp_*` heads predict engine-verified normalized Δtax per head; zero-yield inside the 87A band is a learned, engine-labeled outcome (F7) | engine top-up deltas |
| 4. Recommendation ranking | Sort candidate heads by predicted Δtax; engine-computed ranking is the training target (top-1 ≥ 80% gate) | engine top-up deltas |
| 5. Projected savings | Denormalized `opp_*` of the selected head = instant estimate; `confirm` mode re-runs the engine and returns the verified delta | engine |
| 6. CA-style insights | Template library keyed on features/utilization/opportunities; every sentence cites the section and states the binding rule | templates (explainability §4) |
| 7. Explainable reasoning | Exact decomposition: firing strengths × consequent contributions × input memberships, traceable to raw values | explainability §2 |

## 5. Integration points (exact sites)

| Site | Change |
|---|---|
| `backend/main.py:1165` (`/chat`) | `tax_result = intelligence.calculate_with_intelligence(result["session"], result["session"].get("tax_year"), confirm=False)`. Instant mode keeps the chat turn fast; estimates are badged. |
| `backend/main.py:1326` (`/calculate`) | Same call with `confirm=True` — the decision surface shows engine-verified deltas. `clean_json` already serializes the block. |
| `backend/tax_engine.py:366` | Reorder only: move the `eff_score` call **after** `:371-373` so feature f16 sees the final `savings` (fixes F5). Zero tax-amount impact; pinned `efficiency_score` test expectations updated red→green with disclosure. The engine keeps exactly one ANFIS call site. |
| `backend/nlp_engine.py:1098` | `ReasoningAgent.get_savings_tips` remains the deterministic tip source. `TaxIntelligence` post-filters/ranks: a tip whose head's confirmed delta is ₹0 (87A band, F7) is suppressed and replaced by the zero-yield insight; surviving tips are annotated with engine-verified savings. Tips remain prose; amounts still come only from the engine. |
| `frontend/src/components/TaxReport.tsx` | Tile at `:182` ("ANFIS Efficiency Score", `effScore` resolved at `:96-99`) keeps its slot and gains the v5 value + a tooltip rendering the top attribution (φ) sentence. New **Tax Intelligence** panel under the CA Advice tab (next to `savings_tips` rendered at `:367-368`): utilization bars, opportunity cards (`head`, section, headroom ₹, projected savings ₹, `estimated`/`engine-confirmed` badge), and a "Why this score" expansion (top features + firing summary). No amount in the panel may render without either the `estimated` badge (model) or `engine-confirmed` badge (engine). |
| `backend/ai_models.py` | `ANFIS` gains artifact-version dispatch + multi-head forward (`_forward_heads`); `score_efficiency` keeps its legacy signature and behavior under v4 fallback. `ReasoningAgent` untouched. |
| `backend/anfis_trainer.py` | Superseded by `backend/tools/train_anfis_v5.py` (retraining plan §6); the v4 trainer stays in-tree as heritage. |

### Payload contract (`intelligence` block)

```json
"intelligence": {
  "schema": "tax-intelligence/1",
  "engine_authoritative": true,
  "efficiency_score": 76.8,
  "utilization": {"80c": 1.0, "80d_self": 1.0, "80d_parents": 1.0, "nps": 1.0,
                   "24b": 1.0, "hra": 0.9, "80g": 0.111, "80tta_ttb": 0.0},
  "opportunities": [
    {"head": "hra", "section": "10(13A)", "headroom_amount": 120000,
     "projected_savings": 35880.0, "confirmed": true, "strength": 0.399,
     "insight_id": "TPL-OPP-HEADROOM"}
  ],
  "ranked_actions": ["hra", "80g", "80tta_ttb"],
  "insights": ["..."],
  "explanation": {"features": {"f05_util_hra_exemption": 0.9}, "phi_top": [...],
                   "top_rules": [...], "trace_id": "..."}
}
```
(The numbers above are scenario B's real measured values — see §7.)

## 6. ADR-004 resolution path

1. **Correct the target** (this doc + retraining plan): ground truth generated by the live `TaxEngine` at the registry default `fy_2025_26` via `backend/tools/generate_anfis_dataset.py` (Phase-7 generator). This retires the F1 divergence class entirely — there is no second tax implementation to drift.
2. **Correct the features** (schema v1): every dead/wrong slot replaced with a registry- or engine-sourced definition (`ANFIS_FEATURE_SCHEMA.md` §6 records the per-slot legacy defect).
3. **Correct the call order** (F5): one-line reorder at `tax_engine.py:366` with test updates.
4. **Re-train and gate** (retraining plan §8): efficiency MAE ≤ 2.0 pts, savings MAPE ≤ 10%, ranking top-1 ≥ 80%, rule-diversity ≥ 8 effective rules (F3), suite green, ADR-001 byte-equality guard.
5. **Record ADR-016** (proposed for `docs/decisions.md` at release): *"ANFIS v5 Tax Intelligence layer — multi-head TSK scoring/annotation over TaxEngine outputs; TaxEngine remains the sole source of amounts; v4 artifact retained as rollback."* ADR-004 status becomes *Superseded by ADR-016*.
6. **Rollback**: delete/rename `anfis_weights_v5.json` or set `TAX_ANFIS_V5=0` → loader falls back to `anfis_weights.json` v4 + legacy extractor (today's exact behavior, minus the F5 ordering bug, which is kept fixed). If numpy is absent, the deterministic heuristic at `ai_models.py:681-687` remains the final fallback, unchanged.

## 7. Pinned probe scenarios (regression canaries)

These three sessions were run through the live engine + shipped v4 on 2026-11-02; they become pytest fixtures (`tests/fixtures/anfis_canaries.json`) pinning engine outputs (ADR-001 guard) and serving as explainability worked examples.

| Scenario | Session (keys per schema v1) | Engine (live, FY 2025-26) | v4 score | Engine-derived eff GT |
|---|---|---|---|---|
| A `mid_underutilizer` | salary 12,00,000 · age 32 · 80c 1,00,000 · 80d 15,000 | New Regime · old ₹1,27,920 · new **₹0** · savings ₹1,27,920 · GTI ₹12,00,000; **all 8 head top-ups Δtax = ₹0.00** | 39.7 | 100.0 (raw 101.04 → clipped) |
| B `optimized_salaried` | salary 18,00,000 · age 41 · 80c 1,50,000 · 80d 25,000 · 80d_parents 25,000 · nps 50,000 · 24b 2,00,000 · hra_received 3,00,000 · rent_paid 3,60,000 · is_metro true · 80g 20,000 | New Regime by ₹520 (old ₹1,51,320 / new ₹1,50,800); top-ups: **hra +₹35,880** (rent_paid→4,80,000, flips Old Regime) · **80g +₹11,960** (→1,00,000, flips) · **80tta +₹2,600** (→10,000, flips); 80C/80D/80Dp/NPS/24b Δ₹0 (at cap) | 62.7 | 76.76 |
| C `senior_with_cg` | salary 9,00,000 · age 67 · 80c 80,000 · 80d 20,000 · 80ttb 30,000 · other_income 60,000 · capital_gains [equity_ltcg 2,00,000] | New Regime · old ₹78,390 · new **₹9,750** (= (2,00,000−1,25,000)×12.5%×1.04 — 87A wipes slab tax, never the 112A special-rate) · savings ₹68,640; **all 8 top-ups Δ₹0** (rebate band) | 34.5 (production; 42.6 with intended f16 — F5) | 84.19 |

Scenario B is also the worked ranking example: engine ranking `hra (₹35,880) > 80g (₹11,960) > 80tta_ttb (₹2,600)`, normalized strengths 0.399 / 0.133 / 0.029.

## 8. Validation checklist (architecture-level)

- [ ] ADR-001 guard: for the 3 canaries + 1,000 generator scenarios, engine payload fields (`old_regime`, `new_regime`, `savings`, `recommendation`, `efficiency_score` excepted) byte-identical with `annotate()` on/off.
- [ ] No ANFIS output is ever assigned to a `TaxResult` field or an `Explanation.amount` (grep-level test + field-freeze test).
- [ ] `/chat` p95 added latency ≤ 15 ms (instant mode: 1 forward, no engine re-runs); `/calculate` confirm mode ≤ 120 ms (≤ 9 engine calls).
- [ ] Feature extraction is a pure function; same `(state, result)` → same vector (determinism test, seed-pinned).
- [ ] v4 fallback path reproduces today's `score_efficiency` outputs on the canaries (39.7 / 62.7 / 34.5) within float tolerance.
- [ ] All statutory numbers rendered by templates resolve from `tax_rules` registry values, never string literals (template unit test).
- [ ] 952 pytest + 22 Vitest + 7 Playwright + 97 legacy green.

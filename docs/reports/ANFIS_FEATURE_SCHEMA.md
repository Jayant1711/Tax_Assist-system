# ANFIS Feature & Output Schema — `anfis-feature-schema/1` (THE definitive contract)
**Phase 6 · ANFIS REBIRTH · 2026-11-02**
This file is the single source of truth for the 20 inputs and 9 outputs of the Tax Intelligence Engine. The generator (`backend/tools/generate_anfis_dataset.py`), the trainer (`backend/tools/train_anfis_v5.py`), and the serving extractor (`backend/anfis_schema.py`, shared import) all implement THIS file — one extractor, three consumers, zero drift (the v4 failure mode, ADR-004).
Companions: [`ANFIS_VNEXT_ARCHITECTURE.md`](ANFIS_VNEXT_ARCHITECTURE.md) · [`ANFIS_RETRAINING_PLAN.md`](ANFIS_RETRAINING_PLAN.md) · [`ANFIS_EXPLAINABILITY_FRAMEWORK.md`](ANFIS_EXPLAINABILITY_FRAMEWORK.md).

---

## 1. Versioning and artifacts

| Artifact | Version marker | Contents |
|---|---|---|
| `backend/anfis_weights_v5.json` | `"schema_version": "anfis-feature-schema/1"` | `params` (14,656 = 2·20·64 + 64·21·9), `n_inputs: 20`, `n_rules: 64`, `head_names` (§3), `feature_norm` echo of §2, `metrics` (retraining plan §7), `trained_on` {manifest hash, `tax_year: "fy_2025_26"`, rows, seed 42} |
| `backend/anfis_weights.json` (v4, UNTOUCHED — rollback) | no `schema_version` field | `params` (3,904 = 2·20·64 + 64·21), `n_inputs: 20`, `n_rules: 64`, `metrics {r2: 0.4976, mse: 0.00818}` |
| Loader dispatch (`ai_models.ANFIS`) | on `schema_version` presence | absent → legacy extractor + single head (today's exact behavior); present → this schema + 9 heads. Shape mismatch or failed gates → fail closed to v4. |
| Dataset records | `"schema": "anfis-feature-schema/1"` in every JSONL line | `data/anfis_v1/{train,val,test}.jsonl` + `manifest.json` |

Schema evolution: any input/output change bumps to `/2`, adds a new weights artifact, and re-runs certification; `/1` loaders must reject `/2` files (fail closed).

## 2. Inputs — 20 features (all float32, all clipped to [0,1], NaN/Inf → 0.0)

Conventions: `session` = the server-side state dict (ADR-013; the only writer is the NLP layer). `result` = the `TaxEngine.calculate_tax_advanced` response for THIS state (two-pass). `best` = `result.old_regime if result.recommendation == "Old Regime" else result.new_regime`. `gti` = `best.gross_total_income` (≥ 1e−9 guard). `senior` = `age ≥ 60`. Registry caps from `backend/tax_rules/fy_2025_26.py:164-195` (`tax_year` from the session pin; the schema is cap-agnostic — values are read from the resolved registry, never hardcoded).

| idx | name | source | normalization | why it matters | v4 legacy defect fixed |
|---|---|---|---|---|---|
| f00 | `gross_income_norm` | `gti` (engine: salary + business + rental×0.7 [24(a)] + other; exempt agri 10(1) and special-rate CG excluded) | `gti / 10_000_000` | scale of the taxpayer — drives which marginal rates are in play | v4 summed only salary+business+other from the session, missing rental and the engine's own net-rental math |
| f01 | `util_80c` | `session["80c"]` | `min(v, 150000)/150000` (80C cap) | the largest Chapter VI-A head; cap is statutory | none (kept) |
| f02 | `util_80d_self` | `session["80d"]` | `min(v, 50000 if senior else 25000) / cap` (80D self cap incl. senior) | health-insurance utilization, age-sensitive | v4 divided by 25,000 always → overstated seniors |
| f03 | `util_80d_parents` | `session["80d_parents"]` | `min(v, 25000)/25000` (parents' cap; the 50,000 senior-parent cap is registered but not booked until the parents_senior input lands, `tax_engine.py:293-294`) | second 80D leg | v4 divided by 50,000 → understated (÷2) |
| f04 | `util_nps` | `session["nps"]` | `min(v, 50000)/50000` (80CCD(1B)) | exclusive over-and-above-80C head | none (kept) |
| f05 | `util_hra_exemption` | `best`/old-regime `Explanation(particular="HRA Exemption", section="10(13A)").amount` (Rule 2A three-leg least-of, `tax_engine.py:939-957`; read old_regime — HRA exists only there) | `amount / 200000` | the largest regime-dependent deduction; regime-flip driver | v4 read the dead legacy key `"hra"` → always 0 for modern sessions (measured: scenario B legacy f5 = 0 while the engine booked ₹1,80,000) |
| f06 | `util_24b` | `session["24b"]` | `min(v, 200000)/200000` (24(b) self-occupied cap) | home-loan interest, old-regime only | none (kept) |
| f07 | `util_80e` | `session["80e"]` | `min(v, 500000)/500000` (80E has NO statutory cap — `sec_80e=None`; 500,000 is the saturation reference inherited from the trainer) | education-loan interest, old-regime only, uncapped | none (kept, documented) |
| f08 | `util_80g_limit` | `session["80g"]` | `min(v, gti·0.1 + 1)/…` → `v / (gti·0.1 + 1)` | donation utilization vs the 10% qualifying limit (`_80G_QUALIFYING_LIMIT_PCT`, `tax_engine.py:233`) | kept; the category model (4 categories, `tax_engine.py:873-909`) stays engine-side — the feature sees the raw amount vs limit, the engine books the category math |
| f09 | `util_80tta_ttb` | senior: `session["80ttb"]`; else `session["80tta"]` | senior: `min(v, 50000)/50000`; else `min(v, 10000)/10000` | interest-income deduction; mutually exclusive by age (engine books 80TTA only non-senior, 80TTB only senior, `tax_engine.py:341-342`) | v4 divided 80TTA by 50,000 (statutory cap 10,000) and ignored 80TTB entirely |
| f10 | `util_80u_flat` | engine-booked `ded_80u` from `session["80u_80dd_category"]` ∈ {40_79 → 75,000, 80_plus → 1,25,000} (`tax_engine.py:308-316`) | `booked / 125000` → {0, 0.6, 1.0} | flat disability deduction — category-driven, amount irrelevant | v4 read legacy numeric `"80u_80dd"` which the engine NEVER books (H4 fix, Sprint 2 Step D) → dead feature |
| f11 | `util_80ddb` | engine-booked `ded_80ddb` = `min(80ddb_expenditure, 40000 or 100000 senior)` (`tax_engine.py:319-321`) | `booked / 100000` | tier-capped treatment expenditure | v4 read legacy numeric `"80ddb"` — dead key |
| f12 | `util_80gg` | old-regime `Explanation(particular="Section 80GG").amount` (least-of: 60,000 / 25% income / rent−10% income, `tax_engine.py:863-871`) | `amount / 60000` | rent-without-HRA head (old regime only) | slot repurposed from v4's `"80eea"` — 80EEA is REMOVED from the engine (31-Mar-2022 sunset, Step D) |
| f13 | `cg_income_ratio` | `sum(c["amount"] for c in session["capital_gains"])` | `sum / (gti + 1)` | special-rate income share — changes whether 87A/slab reasoning applies | v4 denominator `(inc+1)` missed rental/other; engine GTI is authoritative |
| f14 | `business_income_ratio` | `session["business"]` | `business / (gti + 1)` | business vs salaried mix (presumptive/audit context) | denominator fixed to engine GTI |
| f15 | `age_norm` | `session["age"]` (int, NLP-booked, default 30) | `age / 100` | drives senior caps, old-regime exemption floors (2.5L/3L/5L) | v4 hardcoded **0.3** — age never reached the model at all |
| f16 | `regime_savings_ratio` | `result["savings"]` (= \|old_tax − new_tax\|, engine) | `savings / (gti·0.1 + 1)` | how much the regime decision is worth | v4 production always saw 0 — `tax_engine.py:366` scores before `savings` is assigned at `:371-373` (bug F5, reordered in vNext) |
| f17 | `tax_burden_ratio` | `best.total_tax` (engine) | `total_tax / (gti·0.3 + 1)` | realized burden vs a 30%-of-income ceiling | none (kept) |
| f18 | `senior_citizen_flag` | `age ≥ 60` (int) | 1.0 / 0.0 | regime + cap routing (80TTB, 80D senior, exemption floors) | v4 keyed on the `profile` STRING ("Senior Citizen") — absent for engine callers → measured 0 on the 67-year-old canary C |
| f19 | `core_headroom_agg` | f01+f02 (25k base) + f03 + f04 raw capped sums | `1 − min(sum, 250000)/250000`; sum = min(80c,150k)+min(80d,25k)+min(80d_p,25k)+min(nps,50k) | the aggregate "core four" headroom the efficiency formula uses | v4 used `1 − 80c/150k` in serving vs `…/275,000` in training — two different features under one slot; cap corrected to the engine-true 250,000 |

Absent keys default to 0 (sessions may carry explicit `None` until a slot is collected — `tax_engine.py:266-275` pattern); booleans coerce strictly (`is_metro`); `capital_gains` must be a list of `{type, amount}` dicts (engine tolerance, `tax_engine.py:253-255`).

## 3. Outputs — 9 heads (all ∈ [0,1] after the [0,1] clip)

| head | meaning | ground truth (generator, retraining plan §3) |
|---|---|---|
| `out_eff` | efficiency score; ×100 at display | `clip(40·ded_util/250000 + 20·savings/(gti·0.05+1) + 40·(1 − best_tax/gti), 0, 100)/100` — every term engine-derived; canaries 100.0 / 76.76 / 84.19 (A/B/C) |
| `opp_80c` | opportunity strength = normalized engine Δtax of topping 80C → 1,50,000 | `clip(Δtax/(gti·0.05+1), 0, 1)`; `mask=0` when headroom=0 or ineligible |
| `opp_80d_self` | same, 80D self → 25,000 (50,000 senior) | ditto |
| `opp_80d_parents` | same, 80D parents → 25,000 | ditto |
| `opp_nps` | same, NPS → 50,000 (80CCD(1B)) | ditto |
| `opp_24b` | same, 24(b) → 2,00,000; mask requires `has_home_loan` or `24b > 0` | ditto |
| `opp_hra` | same, HRA: `rent_paid → max(rent_paid, hra_received + 0.1·salary)`; mask requires salary > 0 and an HRA leg > 0 | ditto |
| `opp_80g` | same, 80G → min(1,00,000, qualifying limit); engine books category math on the copy | ditto |
| `opp_80tta_ttb` | same, 80TTA → 10,000 (non-senior) / 80TTB → 50,000 (senior) | ditto |

Reading rules:
- **Ranking** = sort unmasked `opp_*` descending (predicted); engine Δtax ranking is the training target (top-1 ≥ 80% gate).
- **Projected savings ₹** = `opp_h × (gti·0.05 + 1)` for the selected head `h` — instant estimate, badged `estimated`; `confirmed: true` + engine delta only after the confirm-mode re-run. The model NEVER prints an unbadged rupee amount.
- **Zero-opportunity** = all unmasked heads < τ (calibrated ≈ 0.001 on val) → the 87A-band zero-yield insight instead of tips (canaries A and C: all 8 engine deltas = ₹0.00).
- Scenario B reference values: `opp_hra` 0.399 (₹35,880) · `opp_80g` 0.133 (₹11,960) · `opp_80tta_ttb` 0.029 (₹2,600).

## 4. Ground-truth canary record (scenario B, measured 2026-11-02)

```json
{
  "schema": "anfis-feature-schema/1",
  "id": "anfis-v1-canary-B",
  "session": {"salary": 1800000, "age": 41, "80c": 150000, "80d": 25000,
               "80d_parents": 25000, "nps": 50000, "24b": 200000,
               "hra_received": 300000, "rent_paid": 360000, "is_metro": true, "80g": 20000},
  "features": [0.18, 1.0, 1.0, 1.0, 1.0, 0.9, 1.0, 0.0, 0.11111, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.41, 0.002889, 0.279259, 0.0, 0.0],
  "engine": {"tax_year": "fy_2025_26", "recommendation": "New Regime",
              "old_tax": 151320.0, "new_tax": 150800.0, "savings": 520.0,
              "gti": 1800000.0, "best_tax": 150800.0},
  "targets": {"out_eff": 0.7676,
               "opp": {"80c": {"mask": 0}, "80d_self": {"mask": 0},
                        "80d_parents": {"mask": 0}, "nps": {"mask": 0},
                        "24b": {"mask": 0},
                        "hra":    {"mask": 1, "delta_tax": 35880.0, "gt": 0.39866},
                        "80g":    {"mask": 1, "delta_tax": 11960.0, "gt": 0.13289},
                        "80tta_ttb": {"mask": 1, "delta_tax": 2600.0, "gt": 0.028889}},
               "ranking_gt": ["hra", "80g", "80tta_ttb"]},
  "meta": {"stratum": "regime_flip", "engine_calls": 4, "seed": 42}
}
```
(Canaries A and C pinned identically in `tests/fixtures/anfis_canaries.json`.)

## 5. Validation rules

Record-level (generator + loader, both enforced):
1. Every feature finite, ∈ [0,1] after clip; f18 ∈ {0.0, 1.0} exactly; binary head targets `mask` ∈ {0,1}.
2. `head_names` array equality with §3; `n_inputs/n_rules` shape check: `len(params) == 14656` (v5) / `3904` (v4).
3. Engine fields recomputable: re-running `calculate_tax_advanced(session)` on a sampled 1% must reproduce `engine.*` to the rupee (determinism audit of the generator itself).
4. Session keys validated against the §6 reference; unknown keys rejected (the session validator already fails closed at the persist boundary, ADR-013).
5. Leakage: no duplicate 20-float vectors across splits; stratum shares within ±2 pp across splits.
6. Aging: `trained_on.tax_year` must equal the registry default at load; a mismatch surfaces a UI warning ("model trained on a prior FY") rather than silent use.

Serving-level:
7. Missing session key → 0.0, never an exception; `None` → 0.0 for numeric slots (engine-consistent).
8. The extractor is pure: same `(state, result)` → same vector (byte-equal float32).
9. Fail-closed ladder: v5 artifact invalid/absent → v4 → numpy-less heuristic (`ai_models.py:681-687`).

## 6. Session-key reference (actual keys, from the code)

Booked by the NLP layer (`nlp_engine.py` — the booking path writes the `SemanticAttention` category name as the key) and consumed by `TaxEngine.calculate_tax_advanced` (`tax_engine.py:248-355`):

- **Income:** `salary` · `business` · `rental` · `other_income` · `agriculture` · `capital_gains` (list of `{type: equity_ltcg|equity_stcg|property_cg, amount}`)
- **Deductions:** `80c` · `80d` · `80d_parents` · `80e` · `80g` · `80g_category` (cat_100_no_limit | cat_50_no_limit | cat_100_qualifying_limit | cat_50_qualifying_limit) · `nps` · `hra_received` · `rent_paid` · `is_metro` (bool) · `24b` · `80tta` · `80ttb` · `80gg` · `80u_80dd_category` (none | 40_79 | 80_plus) · `80ddb_expenditure`
- **Profile/context:** `age` (int) · `profile` (Salaried | Business Owner | …) · `has_home_loan` · `has_parents` · `pays_rent` · `tax_year` (registry-pinned) · `phase` / `history` / `_last_*` (internal, projected out per ADR-013)

**Dead/legacy keys (never read by schema v1):** `hra` (pre-Step-B single key), `80u_80dd` (legacy numeric), `80ddb` (legacy numeric), `80eea` (section removed). They remain in v4's legacy extractor for rollback fidelity only.

**Registry caps this schema normalizes against (FY 2025-26, `fy_2025_26.py:164-195`):** 80C 1,50,000 · 80D self 25,000 (senior 50,000) · 80D parents 25,000 (senior 50,000 registered) · 80CCD(1B) 50,000 · 24(b) 2,00,000 · 80TTA 10,000 (senior 0) · 80TTB 50,000 · 80GG 60,000 (25% income, rent−10% income) · 80U/80DD 75,000 / 1,25,000 · 80DDB 40,000 / 1,00,000 · 80E uncapped · 80G 10% qualifying limit · standard deduction 50,000/75,000 · 87A old 12,500 @ 5L, new 60,000 @ 12L (+ derived post-cess band endpoint 12,73,934) · cess 4% · HRA 50% metro / 40% non-metro / 10% salary excess · CG: 112A 12.5% over 1,25,000, 111A 20%, property 12.5% both regimes.

## 7. Generator emission contract

`backend/tools/generate_anfis_dataset.py` (Phase-7) emits one JSONL line per scenario, exactly the §4 record shape: `schema`, `id`, `session`, `features` (20 floats, schema extractor), `engine` (base call result summary), `targets` (out_eff + per-head opp {mask, delta_tax, gt} + ranking_gt), `meta` (stratum, engine_calls, seed). Manifest is content-addressed (SHA-256 of each split file) and records the stratum histogram, seed, engine `tax_year`, git SHA, and the timing-probe decision (retraining plan §2.2). The SAME extractor module produces `features` at generation, training, and serving time — the schema has exactly one implementation (`backend/anfis_schema.py`), and a unit test asserts generator-extractor == serving-extractor on the canaries.

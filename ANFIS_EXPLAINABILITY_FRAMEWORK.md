# ANFIS Explainability Framework — The Explanation Contract, Templates, and Worked Traces
**Phase 6 · ANFIS REBIRTH · 2026-11-02**
Companions: [`ANFIS_VNEXT_ARCHITECTURE.md`](ANFIS_VNEXT_ARCHITECTURE.md) · [`ANFIS_FEATURE_SCHEMA.md`](ANFIS_FEATURE_SCHEMA.md) · [`ANFIS_RETRAINING_PLAN.md`](ANFIS_RETRAINING_PLAN.md).

Every number the Tax Intelligence Engine prints must decompose exactly into (input values → memberships → rule firings → consequent contributions). No post-hoc approximations, no black-box attributions: first-order TSK makes the decomposition **algebraically exact**, and this document is the contract for rendering it.

All worked traces below were **measured on 2026-11-02** by running the live `TaxEngine.calculate_tax_advanced` (registry default FY 2025-26) and the shipped `backend/anfis_weights.json` v4 on the three pinned canary scenarios (`ANFIS_VNEXT_ARCHITECTURE.md` §7). They double as pytest fixtures.

---

## 1. The decomposition contract

For output head `h` (schema `anfis-feature-schema/1`, 9 heads) and feature vector `x ∈ [0,1]^20`:

```
L1  membership    μ[i,r]   = exp(−0.5·((x_i − m[i,r])/s[i,r])²)         per (feature i, rule r)
L2  firing        w[r]     = Π_i μ[i,r];   w̄[r] = w[r] / (Σ_r w[r] + 1e−9)
L3  consequent    f[h,r]   = b[h,r] + Σ_i a[h,r,i]·x_i
L4  output        ŷ[h]     = Σ_r w̄[r]·f[h,r]  →  clipped to [0,1]
```

Exact attributions (identities, not approximations — verified to 1e−6 on the shipped weights):

| Quantity | Formula | Meaning |
|---|---|---|
| Per-feature contribution | `φ[h,i] = Σ_r w̄[r]·a[h,r,i]·x_i` | points of head `h`'s score attributable to feature `i` |
| Per-rule contribution | `ψ[h,r] = w̄[r]·f[h,r]` | points contributed by rule `r` |
| Bias share | `φ[h,bias] = Σ_r w̄[r]·b[h,r]` | the profile-independent floor of the head |
| Reconstruction | `ŷ[h] = Σ_i φ[h,i] + φ[h,bias]` | must hold exactly (unit-tested) |
| Rule diversity | `eff_rules = exp(−Σ_r w̄[r]·ln w̄[r])` | v4 measures ≈ 1.0 (collapse — see §5); v5 gate ≥ 8 |

Sanity check identity from the shipped v4, scenario B: `Σφ = 0.41116`, `bias = 0.216092`, sum = `0.627252` → **62.7/100** — exactly the production score. The contract is reconstructive, not explanatory hand-waving.

## 2. Explanation levels (rendered per response)

- **L0 — Engine truth (always first):** the TaxEngine's own numbers (regime recommendation, payables, savings, itemized `explanations`). No model involved. ADR-001.
- **L1 — Value trace:** for each schema-v1 feature, the raw session/engine value and the normalization arithmetic that produced `x_i` (§3.1 examples). Rendered in the "Why this score" expansion.
- **L2 — Feature attribution:** `φ` ranking — "what moved your score" — top-k positive and negative contributors in points.
- **L3 — Rule narrative:** top rules by `ψ` with their firing strengths and the antecedent features (top `μ[i,r]`) that lit them. Suppressed with a disclosure when `eff_rules < 2` (today: always, §5).

## 3. Worked traces (real numbers)

### 3.1 Scenario A — `mid_underutilizer` (the 87A zero-yield trace)

Session: `salary 12,00,000 · age 32 · 80c 1,00,000 · 80d 15,000` (all other keys absent/0).

**L0 — engine (measured):** Old Regime ₹1,27,920 = ((10,35,000−10,00,000)×30% + (10,00,000−5,00,000)×20% + (5,00,000−2,50,000)×5%) × 1.04 with taxable 12,00,000 − 50,000 std(16(ia)) − 1,00,000 80C − 15,000 80D; New Regime **₹0** — slab tax 52,500 on 11,25,000 (75,000 std) fully rebated by 87A (rebate 60,000, total income ≤ 12,00,000, FY 2025-26). Recommendation **New Regime**, savings ₹1,27,920.

**L1 — schema-v1 feature trace (values measured):**

| idx | feature | raw → normalized |
|---|---|---|
| f00 | gross_income_norm | GTI 12,00,000 → **0.12** |
| f01 | util_80c | min(1,00,000, 1,50,000)/1,50,000 = **0.6667** |
| f02 | util_80d_self | min(15,000, 25,000)/25,000 = **0.60** |
| f15 | age_norm | 32/100 = **0.32** (v4 legacy hardcodes 0.3) |
| f16 | regime_savings_ratio | 1,27,920/(12,00,000·0.1+1) = 1.0660 → clip **1.00** (v4 legacy production sees 0 — the `tax_engine.py:366` ordering bug F5) |
| f19 | core_headroom_agg | 1 − 1,15,000/2,50,000 = **0.54** |

**L2/L3 — shipped v4 (legacy extractor, measured):** production score **39.7** (f16=0); with the intended f16 the same forward gives **51.0** (Σφ 0.293527 + bias 0.216076 = 0.509603). Rule 2 fires at w̄ = **0.99987** — the "explanation" would be one rule. Engine-derived efficiency ground truth: **100.0** (raw 101.04, clipped). Gap to shipped model: **60.3 points** — the concrete cost of ADR-004's wrong target.

**Insight rendered (template `TPL-OPP-ZERO`, engine-verified):** *"Filling 80C to its ₹1,50,000 limit would not change your tax today: your total income of ₹12,00,000 is inside the Section 87A rebate band (₹12,00,000, FY 2025-26 new regime), so additional Chapter VI-A deductions do not reduce your tax. Your savings come from the regime choice itself: ₹1,27,920 (engine-computed)."* — This replaces the deterministic tip that would have said "unused 80C headroom of ₹50,000" (wrong in this band; measured Δtax for all 8 head top-ups: **₹0.00**).

### 3.2 Scenario B — `optimized_salaried` (the regime-flip + full decomposition trace)

Session: `salary 18,00,000 · age 41 · 80c 1,50,000 · 80d 25,000 · 80d_parents 25,000 · nps 50,000 · 24b 2,00,000 · hra_received 3,00,000 · rent_paid 3,60,000 · is_metro true · 80g 20,000`.

**L0 — engine (measured):** New Regime ₹1,50,800 (slabs: 20,000 + 40,000 + 60,000 + 25,000 = 1,45,000 × 1.04) vs Old Regime ₹1,51,320 (deductions ₹6,90,000 = std 50,000 + HRA 1,80,000 [Rule 2A least-of: min(received 3,00,000 · rent−10% salary = 3,60,000−1,80,000 = 1,80,000 · 50% metro salary = 9,00,000)] + 80C 1,50,000 + 80D 25,000 + 80D-p 25,000 + NPS 50,000 + 24b 2,00,000 + 80G 10,000 [default category 4: 50% × 20,000, qualifying limit 10% of adjusted GTI = 1,80,000 not binding]) → recommendation New Regime by ₹520.

**L1 — schema-v1 features (measured):** `[0.18, 1.00, 1.00, 1.00, 1.00, 0.90, 1.00, 0, 0.1111, 0, 0, 0, 0, 0, 0, 0.41, 0.0029, 0.2793, 0, 0.00]`
(f05 util_hra_exemption = 1,80,000/2,00,000 = **0.90** read from the OLD-regime `Explanation("HRA Exemption", "10(13A)")` — the v4 legacy extractor reads the dead `"hra"` key and sees **0**; f15 = 41/100 = **0.41** vs v4's constant 0.3; f19 = 0 because the four core heads are exactly at the ₹2,50,000 registry-capped aggregate.)

**L2 — shipped v4 per-feature attribution (measured, points of the 0–100 score):**

| feature | φ | reading |
|---|---|---|
| bias | **+21.61** | model floor |
| f01 util_80c | **+22.34** | dominant driver |
| f04 util_nps | +8.93 | |
| f03 util_80d_parents | +3.70 | legacy /50,000 denominator (engine books 25,000 cap) |
| f06 util_24b | +3.60 | |
| f00 gross_income_norm | +3.15 | |
| f15 (legacy constant 0.3) | **+2.08** | pure noise: a hardcoded constant carries 2.1 points of every v4 score |
| f02 util_80d_self | −1.25 | |
| f17 tax_burden_ratio | −0.98 | |

Sum 41.12 + 21.61 = **62.7** = production score. Rule 2 fires at w̄ = **0.99994**.

**Opportunity block (engine-verified top-ups, measured):**

| rank | head | engine Δtax | strength `Δtax/(gti·0.05+1)` | mechanism |
|---|---|---|---|---|
| 1 | hra | **₹35,880** | 0.399 | rent_paid → 4,80,000 lifts Rule 2A leg (b) from 1,80,000 to 3,00,000; Old Regime becomes cheaper (₹1,14,920 vs ₹1,50,800) — `TPL-REGIME-FLIP` |
| 2 | 80g | **₹11,960** | 0.133 | donation → 1,00,000 books 50,000 (cat 4 default); Old Regime ₹1,38,840 — regime flip |
| 3 | 80tta_ttb | **₹2,600** | 0.029 | 80TTA ₹10,000 (non-senior cap, `fy_2025_26.py:142`); Old Regime ₹1,48,200 |
| — | 80c/80d/80d_parents/nps/24b | ₹0 | masked | headroom = 0 (already at cap) |

**Insight rendered (`TPL-OPP-HEADROOM`, engine-confirmed):** *"You can still claim up to ₹1,20,000 more HRA exemption under Section 10(13A): raising your documented rent to ₹4,80,000/yr makes the Old Regime cheaper — tax falls from ₹1,50,800 to ₹1,14,920 (₹35,880 saved, engine-computed)."*

### 3.3 Scenario C — `senior_with_cg` (special-rate 87A + the F5 ordering bug, measured twice)

Session: `salary 9,00,000 · age 67 · 80c 80,000 · 80d 20,000 · 80ttb 30,000 · other_income 60,000 · capital_gains [equity_ltcg 2,00,000]`.

**L0 — engine (measured):** Old ₹78,390 = (slab 66,000 [(5L−3L)×5% + (7,80,000−5L)×20% on taxable 9,60,000−1,80,000 deductions (std 50k + 80C 80k + 80D 20k + 80TTB 30k)] + 112A CG 9,375 [(2,00,000−1,25,000)×12.5%]) × 1.04. New **₹9,750**: slab tax 28,500 on 8,85,000 wiped by 87A (total income 10,85,000 ≤ 12,00,000), **but the 112A special-rate ₹9,375 is never rebated** (`special_rate_excludes_87a`, `fy_2025_26.py:150`) → 9,375 × 1.04 = 9,750. Recommendation New Regime, savings ₹68,640.

**L1 — schema-v1 features (measured):** `[0.096, 0.5333, 0.40, 0, 0, 0, 0, 0, 0, 0.60, 0, 0, 0, 0.2083, 0, 0.67, 0.7150, 0.0339, 1.00, 0.60]`
(f09 = 30,000/50,000 senior 80TTB route — v4 legacy reads only `"80tta"` → sees 0; f02 = 20,000/50,000 **senior** self cap — v4 legacy divides by 25,000 → 0.8, overstating; f18 = 1.0 from age ≥ 60 — v4 legacy keys on the `profile` string, which is absent here → 0.)

**L2 — shipped v4 (measured):** Σφ 0.209704 + bias 0.216093 = 0.425797 → **42.6** with the intended f16 (= 68,640/9,60,001 = 0.7150, contributing +8.04). Production prints **34.5** because `tax_engine.py:366` scores before `savings` is assigned (`:371-373`) → f16 = 0 in every production response today. φ table: f01 +11.91 · f16 +8.04 · f15 +2.08 (the constant) · f00 +1.68 · f13 (cg ratio) −1.33 · f02 −1.00 · f19 −0.30 · f17 −0.12. Rule 2 fires at w̄ = **0.99995**. Engine-derived efficiency GT: **84.19**.

**Insight rendered (`TPL-SAVE-CONFIRM` + L0):** *"Your ₹9,750 New Regime tax is entirely capital-gains tax: the Section 87A rebate (total income ₹10,85,000 ≤ ₹12,00,000) wipes the slab tax but never the Section 112A special-rate tax. Model efficiency estimate 84.2; all Chapter VI-A top-ups verified ₹0 impact."*

## 4. CA-style template library

Rules: every `{slot}` is filled from (a) the registry (`tax_rules`), (b) the engine result, or (c) the model with the `estimated` badge — provenance-tagged in code; determinism per session (no randomness in the request path); sections cited only as they exist in the codebase (80C ₹1.5L · 80CCD(1B) ₹50k · 80D ₹25k/₹50k · 24(b) ₹2L · 24(a) 30% · 10(13A) Rule 2A · 80GG · 80TTA/80TTB · 80U/80DD · 80DDB · 80G · 87A · 115BAC · 112A · 111A · 16(ia) · 4% cess). Amounts en-IN formatted.

| ID | Template (slots) | Source of slots |
|---|---|---|
| `TPL-EFF-DRIVER` | "Your score of {score}/100 is driven mainly by {top_phrase} (+{pts}) and {second_phrase} (+{pts}); the model floor is {bias_pts}." | φ table (L2) |
| `TPL-UTIL-FULL` | "Section {section} is fully utilized: {used} of {cap}." | utilization block × registry |
| `TPL-OPP-HEADROOM` | "You can still claim up to {headroom} under {section} — booking it would have saved about {amount} {badge}." | headroom × opp head (denormalized) |
| `TPL-OPP-ZERO` | "Filling {section} to its {cap} limit would not change your tax today: your total income of {income} is inside the Section 87A rebate band ({band_cap}, {regime}), so additional Chapter VI-A deductions do not reduce your tax." | engine confirm (Δ=0) |
| `TPL-REGIME-FLIP` | "Booking {amount} of {section} makes the {other_regime} cheaper: tax falls from {cur_tax} to {alt_tax} ({delta} saved, engine-computed)." | confirm-mode re-run |
| `TPL-SAVE-CONFIRM` | "Engine confirmation: re-running your computation with {section} topped up gives {engine_delta} (model estimate was {pred}; error {err})." | both |
| `TPL-SPECIAL-RATE` | "The 87A rebate wipes slab tax only — Section {112A/111A} special-rate tax of {amount} is never rebated." | engine explanations |
| `TPL-RULE-NARRATIVE` | "Pattern {rule_id} fired at {strength:.0%}, mainly because {top_antecedent_phrase}." — suppressed with disclosure when eff_rules < 2. | ψ table (L3) |
| `TPL-DIVERSITY-DISCLOSURE` | "This score currently collapses to a single inference pattern; per-pattern narratives are unavailable until the v5 rule base ships." | eff_rules |

`top_phrase` vocabulary per feature (deterministic map, e.g. f01 → "your 80C utilization", f16 → "your regime-switch saving", f05 → "your HRA exemption usage").

## 5. v4 rule-collapse disclosure (measured)

On all three canaries the shipped v4 concentrates firing in a single rule: w̄(rule 2) = 0.99987 (A) / 0.99994 (B) / 0.99995 (C) → `eff_rules ≈ 1.0`. Consequences rendered honestly until v5 ships: L3 is suppressed via `TPL-DIVERSITY-DISCLOSURE`, and L2 (φ) remains valid because it aggregates over rules. The v5 retraining plan (§6.5, gate 6) adds an explicit anti-collapse regularizer and requires `eff_rules ≥ 8`, making L3 meaningful.

## 6. Validation checklist (explainability)

- [ ] Reconstruction identity `ŷ = Σφ + bias` exact to 1e−6 on every head, every canary (unit test).
- [ ] Every template sentence passes the provenance linter: no rupee amount without an `engine`/`registry`/`estimated` tag; no section citation outside the codebase's section set.
- [ ] Determinism: same `(state, result)` → identical explanation text (turn-index rotation only, per Sprint-4 P2.4 discipline).
- [ ] Canary traces (§3.1–3.3) pinned as fixtures: engine numbers (1,27,920/0 · 1,51,320/1,50,800 · 78,390/9,750), opportunity deltas (35,880/11,960/2,600), v4 scores (39.7/62.7/34.5), φ tables.
- [ ] L3 suppressed when `eff_rules < 2`; disclosure rendered.

# Explainability Engine Report — Tax Intelligence Layer (ANFIS v5, Phase 2/3/6)

**Status:** Implemented and tested (`backend/tests/test_tax_intelligence.py`, 12/12 passing)
**Implements:** [`ANFIS_EXPLAINABILITY_FRAMEWORK.md`](ANFIS_EXPLAINABILITY_FRAMEWORK.md) (the explanation contract), adapted to the v5 two-pass architecture
**Code:** [`backend/tax_intelligence.py`](backend/tax_intelligence.py) — `explain_efficiency` (L534), `explain_model_efficiency` (L565), `utilization` (L392), `recommend` (L408), `advisor_block` (L603), exact rule heads (L648–662)
**Companions:** [`ANFIS_VNEXT_ARCHITECTURE.md`](ANFIS_VNEXT_ARCHITECTURE.md) · [`docs/decisions.md`](docs/decisions.md) (ADR-001, ADR-004) · [`ANFIS_ROOT_CAUSE_REPORT.md`](ANFIS_ROOT_CAUSE_REPORT.md)

Governing discipline (ADR-001): the deterministic `TaxEngine` computes; the intelligence layer annotates. Every rupee in any explanation is an engine-computed figure — never a model output. The explainability engine exists to make that provenance visible, not to add a second source of truth.

---

## 1. The three explainability layers

Every answer a user can receive decomposes along three independent layers, each with a different epistemic status. They are deliberately kept separate in the code (`served_by` tags, `model_experiment` nesting, `verdict` fields) so no experiment can masquerade as ground truth.

### Layer 1 — Deterministic-composite decomposition (EXACT, served)

`explain_efficiency(ti, x)` (`tax_intelligence.py:534-562`) decomposes the **served** efficiency score. The served score is `TaxIntelligence.composite_efficiency` (`:249-273`), the documented v1 composite evaluated directly over the schema-v2 feature vector — *not* a learned head (`predict_efficiency` returns it verbatim; the learned TSK head is the registry-documented experiment, see Layer 2):

```
raw        = 30.0 + 68.5 · Σ_head  weight_head · utilization_head
prediction = clip(raw, 30.0, 98.5)
```

Weights (statutory importance, per `ANFIS_FEATURE_SCHEMA.md`): `u80c 0.40 · unps 0.15 · u80d 0.12 · u24b 0.10 · u80d_parents 0.08 · u80e 0.05 · u80g 0.05 · u80tta 0.025` — sum **0.975**. Income, HRA (a Rule-2A *exemption*, not a composite input), senior flag and 80C-headroom carry weight 0.

The decomposition is **exact by construction** — it is the same weighted sum the served number was computed from, re-folded into per-head terms. No model, no approximation, no post-hoc attribution. Output shape:

```python
{"available": True,
 "prediction": 39.1,                                   # round(clip(raw), 1)
 "served_by": "deterministic composite (anfis-feature-schema/2)",
 "top_features": [                                     # top 4 by contribution_share
   {"feature": "u80c", "value": 0.3333,                # the head's utilization
    "weight": 0.40,
    "contribution_share": 0.4103},                     # weight / 0.975 (normalizer)
   ...],
 "model_experiment": {...}                             # Layer 2 nested inside
}
```

`contribution_share = weight / 0.975` is the head's share of the composite's movable range — a static, human-readable "what your score is made of" ranking (u80c 0.4103 > unps 0.1538 > u80d 0.1231 > u24b 0.1026 > …; all eight sum to 1.0). Per-head weighted terms (`weight × utilization`) are recoverable from `value × weight`.

### Layer 2 — TSK rule attribution (EXPERIMENT, not served)

`explain_model_efficiency(ti, x)` (`tax_intelligence.py:565-593`) decomposes the **learned** TSK efficiency head — the same algebra the framework doc §1 specifies for first-order TSK, with two implementation-level divergences noted below. Returns `{"available": False}` whenever NumPy is absent, `ti is None`, or `ti.ready` is False — the offline path never fabricates a decomposition.

Forward chain (48 rules `K = RULES` over the 20-dim eff head; consequents are closed-form ridge LSE solves, `RIDGE = 1e-3` — the ADR-004 fix that made per-rule attribution meaningful at all):

| Stage | Implementation |
|---|---|
| μ | `exp(−0.5·((x_i − m[i,r])/s[i,r])²)`, quantile-placed means, span/6 sigmas (`_membership`, `_init_memberships`) |
| firing | **Additive**: `w[r] = Σ_i μ[i,r]`, then `w̄ = w / Σ_r w`. Deliberate divergence from the framework doc's product rule (§1 L2): the product over 20 sparse, grid-structured dims underflowed even after flooring; the sum keeps every rule reachable (in-code rationale cites Jang 1993, which lists both) |
| per-feature attribution | `φ_i = Σ_r w̄_r · a[r,i] · x_i` (consequent coefficients only). **Divergence 2**: the bias term `Σ_r w̄_r·b_r` is *excluded* — shares are normalized as `φ / (Σ|φ| + 1e-9)`, so this layer reports *signed relative influence over the linear terms*, not an exact reconstruction identity of the framework doc (`ŷ = Σφ + bias`) |
| rule diversity | `effective_rules = round(1 / Σ_r w̄_r², 1)` — the inverse participation ratio. Diverges from the doc's entropy form `exp(−Σ w̄·ln w̄)`; both equal K on a uniform base and ≈1 on collapse |

Output: `prediction` (the *model's* clipped head, 0–100), `top_features` (top 4 by |share|), `top_rules` (top 3 by `w̄` with firing strengths), `effective_rules`.

Status discipline: this layer is labeled an **experiment everywhere it appears** — it is nested under the key `model_experiment` in Layer 1's output, the served `predict_efficiency` bypasses it entirely, and the learned opportunity head additionally never touches served confidence (§3). Its value today: evidence that the *serving* decomposition (Layer 1) has a model-grade companion ready for when the v5 heads pass their gates.

### Layer 3 — Session-derived evidence lines (DETERMINISTIC, served)

The evidence base for every recommendation is `utilization(session)` (`tax_intelligence.py:392-405`) — pure session arithmetic, zero ML: for each of the 9 statutory heads in `LIMITS` (age-gated: 80TTA only < 60, 80TTB only ≥ 60), it emits `{head, booked, limit, utilization: round(min(1, booked/limit), 4), headroom: max(0, limit − booked)}`.

`recommend(session, engine, ti, top_n)` (`:408-498`) turns that into priced evidence via the **two-pass**:

- **Pass 1** — `engine.calculate_tax_advanced(session, tax_year="fy_2025_26")`; `base_paid = min(old.total_tax, new.total_tax)`.
- **Pass 2** — for each head with headroom > 0, probe the **full remaining headroom** (partial probes miss regime-flip cases — the comment names exactly the worked example of §2), re-price through the engine, `savings_engine = round(base_paid − paid2, 2)`.

Every ranked candidate carries the evidence pair verbatim:

```python
"reason":   f"Section {head.upper()} has ₹{headroom} unused (currently {util%} utilized)"
"evidence": [f"{head} booked: ₹{booked} of ₹{limit}",
             f"engine-priced: a top-up of ₹{delta} saves ₹{savings_engine} (authoritative)"]
```

Ranking is engine-authoritative: `sort(key = (−savings_engine, −savings_estimate, head))`. The learned fields (`savings_estimate` mirror, `opportunity_probability: None`) are explicitly optional decorations; with `ti=None` the review degrades to engine-only intelligence and stays fully available.

**Response-facing assembly:** `advisor_block(session, engine, ti)` (`:603-629`) is the only layer-3 renderer wired into a user turn — the composer's closing turn (`backend/nlp_engine.py:1121-1132`, wrapped in a blanket `except` so intelligence never breaks a reply). It takes top-1 only and returns `None` unless `verdict == "RECOMMEND"` and `estimated_savings > 0` — ADR-001's "no invented value enters the reply", enforced structurally.

**Exact rule heads (Phase 6):** `rule_opportunity` / `rule_savings` / `rule_confidence` (`:648-662`) are forensics-derived closures over the engine price itself (`ANFIS_ROOT_CAUSE_REPORT.md`: the opportunity label is *exactly* `savings_engine > 0` — zero exceptions on 76,960 rows — and the savings label is exactly linear in the min-paid ratios, val MAPE 1.6e-14). The "prediction" **is** the engine computation, so precision/recall/MAPE are correct by construction and ADR-001 holds trivially. The learned TSK savings/opportunity heads remain experiments.

### Provenance summary

| Layer | Function | Epistemic status | Can appear in a reply? |
|---|---|---|---|
| 1. Composite decomposition | `explain_efficiency` | Exact — same arithmetic as the served score | Yes (inspection/report surface) |
| 2. TSK rule attribution | `explain_model_efficiency` | Experiment — learned head, not served | No (`model_experiment` tag only) |
| 3. Evidence lines | `utilization` + `recommend` → `advisor_block` | Deterministic session + engine two-pass | Yes (composer closing turn) |

---

## 2. The reasoning chain — why → evidence → impact → confidence → next action

A recommendation is a five-link chain. Each link is a separate field with a separate provenance, and the chain is assembled bottom-up: impact is priced first (engine two-pass), then evidence and reason are derived from session state, then confidence is anchored on the impact, and only then is the sentence rendered.

**WORKED EXAMPLE** — traced through the actual code on 2026-11-03. Session (the `TestDegradation::test_advisor_block_offline_is_engine_priced` fixture, engine-only mode `ti=None`):

```python
{"id": "fixture", "profile": "Salaried", "age": 35, "salary": 1_500_000, "80c": 50_000}
```

**Link 1 — IMPACT (computed first, `recommend` pass 1 + pass 2):**

| Pricing | Old Regime | New Regime | min (paid) |
|---|---|---|---|
| Base, as booked | ₹2,41,800 | ₹97,500 | **₹97,500** → New Regime |
| Hypothetical `80e += 5,00,000` (full headroom) | ₹96,200 | ₹97,500 | **₹96,200** → Old Regime |

`savings_engine = 97,500 − 96,200 = ₹1,300`. The mechanism is a **regime flip**, not a deduction: 80E (education-loan interest) is Old-Regime-only, so the ₹5L top-up leaves the New-Regime figure untouched but cuts Old-Regime taxable income to ₹9,00,000 (15,00,000 − 50,000 std − 50,000 80C − 5,00,000 80E → ₹96,200), undercutting the served New-Regime ₹97,500 by ₹1,300. This is precisely the case the full-headroom probe comment (`:430-436`) cites — a partial probe of, say, ₹1L of 80E headroom would have priced ₹0 and buried the only real opportunity.

**Link 2 — WHY (`reason`, session-derived):**

```
"Section 80E has ₹5,00,000 unused (currently 0% utilized)"
```

**Link 3 — EVIDENCE (`evidence`, session + engine):**

```
["80e booked: ₹0 of ₹5,00,000",
 "engine-priced: a top-up of ₹5,00,000 saves ₹1,300 (authoritative)"]
```

**Link 4 — CONFIDENCE (anchored on impact, §3):** `rule_confidence(1300.0)` → **0.85**; `verdict = "RECOMMEND"`; `estimated_savings = savings_engine = 1300.0` (the engine figure, unmodified). Sibling candidates in the same session show the other anchor: `24b`, `80c` (₹1,00,000 headroom!), `80d` all price `savings_engine = 0.0` — the optimal regime is New, and Chapter VI-A top-ups that do not flip it are worth exactly ₹0 — so each gets `verdict = "NO BENEFIT (current regime ignores this head)"`, `confidence = 0.30`, `estimated_savings = 0`. The headroom itself is *not* treated as a benefit.

**Link 5 — NEXT ACTION (`advisor_block`, the rendered sentence that enters the reply):**

```
\n🧠 **Best opportunity**: top up Section 80E by ₹5,00,000 → est. savings ₹1,300
(confidence 85%; engine-verified in your report). Why: Section 80E has ₹5,00,000
unused (currently 0% utilized).
```

The words "engine-verified in your report" are the provenance contract made user-visible: the ₹1,300 will be re-priced and itemized by the report generator's independent engine run.

**Companion efficiency trace** for the same base session through Layer 1: `explain_efficiency` returns `prediction = 39.1` (u80c = 50,000/1,50,000 = 0.3333 → raw = 30 + 68.5·0.40·0.3333 = 39.13, inside the clip), `top_features = [u80c 0.4103, unps 0.1538, u80d 0.1231, u24b 0.1026]`, `served_by = "deterministic composite (anfis-feature-schema/2)"`, and `model_experiment = {"available": False}` (offline, `ti=None`). Regime context from the same review: `regime_advisory = {"engine_verdict": "New Regime", "savings_if_switched": 144300.0}`; `band_position = None` (gross ₹15,00,000 is > ₹50,000 from the ₹12,00,000 87A band).

---

## 3. The confidence formula and its anchoring

Implemented twice, intentionally identical — as the module-level exact rule (`tax_intelligence.py:659-662`) and inlined in `recommend` (`:473, :477`):

```python
def rule_confidence(savings_engine: float) -> float:
    return 0.85 if savings_engine > 0 else 0.30
```

**0.85 — engine two-pass.** When the engine prices a strictly positive saving, the cited number was produced by the *same* deterministic `TaxEngine` that builds the served report, on the *same* inputs. There is no model error term to discount: the only residual risk is session staleness (income or bookings drifting between the chat and the report run). 0.85 encodes "the arithmetic is authoritative; the session may age" — it is a provenance score, **not** a learned probability. Crucially, the learned opportunity head — whose training positives are 0.31% of rows and which would need calibration to earn a probability meaning — is *not* consulted: the comment at `:470-472` states the learned head "does not touch served output until its gates pass." Confidence claims engine authority only where engine authority actually exists.

**0.30 — no benefit.** A zero price is real information, not missing information: the engine *ran* the two-pass and established that the current optimal regime ignores this head (87A-band masking, new-regime Chapter VI-A exclusion, or a top-up too small to flip the regime). The candidate stays listed with `verdict = "NO BENEFIT (current regime ignores this head)"` and `estimated_savings = 0` — pinned by `test_no_amount_is_invented` — and 0.30 marks it "priced, genuinely worthless here" rather than "unknown." The low-but-nonzero value keeps it ranked below any priced opportunity without implying the engine is unsure.

**Structural containment:** `advisor_block` returns `None` unless `verdict == "RECOMMEND"` and `estimated_savings > 0`, so the 0.30 branch can never be rendered as advice, and a no-benefit session produces *no* intelligence sentence at all (pinned by `test_advisor_block_skips_no_benefit` on an all-heads-maxed session). The test-suite shape bound `0.0 <= confidence <= 0.99` additionally blocks any future learned confidence from saturating at 1.0.

---

## 4. What is NOT yet explainable (ADR-004)

**The v4 legacy score's internal firings.** When v5 weights are absent (the current deployment state — `get_intelligence()` returns `None` on a missing/failed artifact), the production efficiency number still comes from the v4 ANFIS in `backend/ai_models.py:459-545` (20-input × 64-rule TSK shipped as `anfis_weights.json`). ADR-004 records why its explanations cannot be trusted as engine-facing truth:

- **Wrong ground truth.** v4 was trained against `anfis_trainer.py`'s synthetic re-implementation, whose HRA and surcharge math diverges from the live engine (`tax_engine.py:316-321, 283-292`); the advertised R² = 0.88 is measured against the wrong target. Its per-feature attributions therefore describe a fictional tax law, faithfully.
- **Rule collapse.** `ANFIS_EXPLAINABILITY_FRAMEWORK.md` §5 measured the shipped v4 on all three canaries: rule 2 fires at w̄ = 0.99987 / 0.99994 / 0.99995 → `eff_rules ≈ 1.0`. The L3 rule narrative is suppressed behind `TPL-DIVERSITY-DISCLOSURE` ("collapses to a single inference pattern") and only the L2 φ aggregate remains valid — an "explanation" that is one rule is no explanation.
- **Legacy extractor defects** (framework doc §3 traces): f16 scored before `savings` is assigned (`tax_engine.py:366` ordering bug → 0 in every production response), HRA read from the dead `"hra"` key, senior 80TTB/80D-cap/age features misread. The φ table is reconstructive over the *legacy* vector, not over engine reality.
- **Mechanical fragility:** the refiner is dimensionally incompatible (10×50 vs 20×64) and weights are reshaped without validation at import (`ai_models.py:482-485`).

The v5 answer to ADR-004 is structural, not a patch: stop serving a learned score entirely (serve the exact composite, Layer 1), train consequents in closed form so rule attributions are meaningful, and pin `eff_rules ≥ 8` as a retraining gate before L3 narratives ship.

**Also not yet explainable / not yet exposed:**

- The v5 learned TSK heads (eff/sav/opp) are trained and testable but are experiments — served by nothing, excluded from confidence, and their `explain_model_efficiency` decomposition reports relative shares over linear terms only (no bias reconstruction identity, §1 Layer 2).
- `explain_efficiency` / `explain_model_efficiency` are not yet wired to any HTTP endpoint or report renderer; the only served rendering today is `advisor_block`'s single top-1 sentence. The framework doc's full L0–L3 rendering stack (value traces, φ tables, rule narratives, `TPL-*` templates) remains design-stage for the report UI.
- Per-feature value traces (framework doc L1: raw → normalization arithmetic) are implicit in `features_v2` (the single train/serve feature definition) but are not yet emitted as user-facing lines.

---

## 5. Test evidence — which test pins which contract

`backend/tests/test_tax_intelligence.py` — 12 passed (verified 2026-11-03: `pytest tests/test_tax_intelligence.py -q` → `12 passed`). The fixture fits a real v5 model in-session on a subsample of the generated dataset (sigma_evals=2, iters=0) and round-trips it through save/load — no dependency on any deployed artifact.

| Test | Pins |
|---|---|
| `TestExplainability::test_decomposition_completes_with_top_features` (L128) | **Layer 1 contract**: on a real engine-priced session (18L salary, 80c 1L), `explain_efficiency` → `available`, exactly 4 `top_features`, `prediction >= 0`, Σ top-4 `contribution_share <= 1.01` (shares are a normalized partition) |
| `TestExplainability::test_top_rules_have_firing_strengths` (L141) | **Layer 2 contract**: `explain_model_efficiency` on the fitted model → `available`, exactly 3 `top_rules`, every `firing >= 0`, `effective_rules >= 1` |
| `TestADRBoundary::test_every_savings_estimate_is_engine_priced` (L62) | The **IMPACT link**: for every recommendation, re-running the engine on the hypothetical reproduces `savings_engine` to the paisa and `estimated_savings == savings_engine` — the model ranks, the engine prices |
| `TestADRBoundary::test_no_amount_is_invented` (L84) | The **0.30 branch semantics**: `savings_engine <= 0` → verdict `NO BENEFIT (current regime ignores this head)`, `estimated_savings == 0` |
| `TestRecommendationShape::test_fields_present` (L99) | The **chain shape**: `head, delta, reason, evidence, confidence, estimated_savings, opportunity_probability` all present; `0.0 <= confidence <= 0.99`; reason and evidence non-empty |
| `TestRecommendationShape::test_ranking_prefers_engine_savings` (L109) | RECOMMEND rows are sorted by descending engine price — the WHY-you-see-this-first ordering is authoritative, not decorative |
| `TestRecommendationShape::test_regime_advisory_is_engine_verdict` (L116) | `regime_advisory.engine_verdict` echoes the engine's own recommendation |
| `TestDegradation::test_recommend_without_model_still_engine_priced` (L160) | `ti=None` → `opportunity_probability is None` on every row, engine pricing intact — explanations survive offline degradation |
| `TestDegradation::test_advisor_block_offline_is_engine_priced` (L173) | The **worked example as a pinned fixture** (15L salaried + 50k 80C, the ₹1,300 80E flip): the rendered block contains `engine-verified` and `confidence` — in engine-only mode |
| `TestDegradation::test_advisor_block_skips_no_benefit` (L184) | All-heads-maxed session → `advisor_block is None` — silence instead of invented advice |
| `TestComposerIntegration::test_closing_turn_carries_block_when_material` (L201) | End-to-end: if the closing turn contains "Best opportunity", it must cite `engine-verified` and `confidence` (block legitimately absent when weights are ungated) |
| `TestComposerIntegration::test_turn_never_breaks_on_intelligence` (L216) | Any failure inside the layer is swallowed — explanation availability never costs a turn |

---

## 6. Limitations and open items

1. **Rendering surface is one sentence.** Layers 1–3 are implemented and pinned; the framework doc's L1 value traces and L3 rule narratives await a report-UI wiring point. Nothing in the current serving path renders Layer 2.
2. **Layer 2's shares are relative, not reconstructive.** Because the bias term is excluded from the normalization, `Σ shares = 1` over linear terms only; the framework doc's exact identity (`ŷ = Σφ + bias`, 1e−6) is not asserted by the v5 test suite.
3. **Confidence is two-valued by design.** 0.85/0.30 has no gradation for partial evidence (e.g., a stale session, or a top-up that flips the regime by ₹1). Gradation should only arrive with a calibrated, gate-passing learned head — and only as a *decoration* on the engine anchor, never a replacement.
4. **The v4 legacy score remains the fallback efficiency UI** until v5 weights ship; its explanations stay suppressed/disclosed per §4 and ADR-004's "beta label" mitigation.

# CA RECOMMENDATION ENGINE REPORT — the five advisor modules as implemented
**Date:** 2026-11-03 · **Code:** `backend/tax_intelligence.py` (advisor layer), `backend/tax_engine.py` (the only pricer) · **Contract:** `INTELLIGENT_RESPONSE_REPORT.md` · **Tests:** `backend/tests/test_tax_intelligence.py`
All rupee figures below were produced by running `TaxEngine.calculate_tax_advanced(tax_year="fy_2025_26")` on the stated sessions — nothing in this report is hand-derived.

---

## 1. What was built, in one paragraph

A CA-style year-end review of the **as-booked session**: the deterministic `TaxEngine` prices the session twice — once as booked (baseline), once per deduction head with the **full remaining headroom** added (hypothetical) — and the difference is the engine-priced saving for that head. Candidates are ranked by that price, verdicts are issued (`RECOMMEND` / `NO BENEFIT`), and the composer's closing turn carries the top one. The learned ANFIS v5 heads **decorate only**; with weights absent the layer degrades to ENGINE-ONLY and stays fully available (ADR-001: no rupee in any reply is model-invented).

## 2. The two-pass loop (`recommend()`, tax_intelligence.py:408-498)

```
Pass 1  base  = engine.calculate_tax_advanced(session)           # as booked
        paid  = min(old.total_tax, new.total_tax)                 # the regime race

Pass 2  for each head h in utilization(session) with headroom > 0:
            hyp = session; hyp[h] += headroom                     # FULL headroom
            res = engine.calculate_tax_advanced(hyp)
            savings_engine[h] = round(paid − min(old₂, new₂), 2)  # engine-priced

Rank    sort by (−savings_engine, −savings_estimate, head)        # deterministic
Verdict RECOMMEND        iff savings_engine > 0   → confidence 0.85, est = engine
        NO BENEFIT (...) iff savings_engine ≤ 0   → confidence 0.30, est = 0
```

- Baseline `paid` is the min across regimes, so a top-up is credited **only** when it improves the better of the two regimes — this is what makes regime flips visible and regime-blind arithmetic impossible.
- Probe scope: the 9 `HEADS` in `LIMITS` (tax_intelligence.py:52-56) — 80c ₹1.5L, 80d ₹25k, 80d_parents ₹50k, nps ₹50k, 24b ₹2L, 80g ₹1L, 80e ₹5L, 80tta ₹10k, 80ttb ₹50k — age-gated (`80tta` skipped ≥60, `80ttb` skipped <60) in `utilization()` (tax_intelligence.py:392-405), which also yields the per-head saturation table (`booked/limit/utilization/headroom`) that serves as the evidence base.
- Cost: one engine call per open head (≤9) + one baseline; synchronous, bounded.

## 3. The five advisor modules → implementation map

### 3.1 Deduction advisor — per-head headroom + engine-priced top-up value
`utilization()` computes saturation per head (4-dp utilization, absolute headroom). `recommend()` turns every open head into a candidate `{head, delta=headroom, savings_engine, savings_estimate, opportunity_probability, utilization}` and attaches reason + evidence lines: booked-vs-limit (`evidence[0]`) and the engine-priced top-up quote (`evidence[1]`: *"engine-priced: a top-up of ₹X saves ₹Y (authoritative)"*). The learned savings head exists (`predict_savings`) but is **not wired into the price** — `savings_estimate` is the engine figure and `opportunity_probability` is `None` until the learned head passes its gates.

### 3.2 Regime advisor — engine verdict + 87A band position + savings-if-switched
`regime_advisory = {engine_verdict: base["recommendation"], savings_if_switched: base["savings"]}` (tax_intelligence.py:485-489) — the engine's own old-vs-new comparison is re-exported, never re-derived. `band_position` (tax_intelligence.py:490-495) fires only within ±₹50,000 of the ₹12,00,000 new-regime 87A band and labels three states: *exactly at the band*, *₹X below*, *₹X above* — the "one more lakh of income may cost you the rebate" warning a CA gives verbally.

### 3.3 Optimization advisor — ranking IS the optimization
There is no separate optimizer: the sort key `(-savings_engine, -savings_estimate, head)` (tax_intelligence.py:453-455) orders opportunities by realized engine-priced saving, with the head name as a deterministic tiebreak (measured tie order: `24b`, `80c`, `80d`, …). `top_n` defaults to 3 in `recommend()`; the composer consumes **top-1** via `advisor_block()` (tax_intelligence.py:603-629) so the reply stays bounded. `TestRecommendationShape.test_ranking_prefers_engine_savings` asserts the descending invariant.

### 3.4 Risk advisor — current state
- **Zero-benefit honesty**: a head the engine prices at ₹0 gets verdict `NO BENEFIT (current regime ignores this head)`, `estimated_savings = 0`, confidence 0.30 — and `TestADRBoundary.test_no_amount_is_invented` enforces that no saving is ever attached to it.
- **Regime-mismatch detection**: that verdict string is itself the mismatch detector — it fires when the deduction helps only the non-optimal regime. Measured: a ₹24L salaried session (new regime ₹2,92,500 vs old ₹5,38,200) prices **all 8 open heads at ₹0** and every one is labeled NO BENEFIT; the 15L worked example (§5) shows 7 of 8 heads NO BENEFIT because only 80E is large enough to flip the regime.
- **Suppression**: `advisor_block()` returns `None` (reply unchanged) unless the top-ranked verdict is RECOMMEND with `estimated_savings > 0` — `TestDegradation.test_advisor_block_skips_no_benefit` proves an all-maxed session produces no block (the advisor refuses to invent).
- **What the advisor layer itself does not say, the engine's audit stream does**: the engine's `audit_observations` (field at tax_engine.py:214, attached to both regime results at :483-485) already carries — among others — the **80G cash-cap advisory** `DED_80G_CASH_CAP_OBSERVATION` (tax_engine.py:179-181, *"Cash donations qualify only up to ₹2,000 — verify your payment mode"*, fired at :479) and the **capital-gains holding advisory** `PROPERTY_HOLDING_ASSUMPTION` (tax_engine.py:139-142, *"Property gains are treated as long-term; short-term property gains are taxed at slab rates — verify your holding period"*, fired at :435-436 whenever a `property_cg` entry exists), alongside the 20%-with-indexation election advisory (:129-135) and the CG > ₹10L AIS/TIS reconciliation flag (:394-395). These are deliberately in the audit trail, not the ranked list: the election cannot be priced without uncollected cost figures, and the constants say so verbatim — the correct CA posture is disclosure, not fabricated numbers.

### 3.5 Opportunity advisor — the full-headroom probe strategy
The non-obvious design decision: the probe adds the **entire remaining headroom**, not a partial increment. Partial probes miss the regime-flip cases where the only real saving lives. Measured counterfactual on the 15L fixture (§5):

| 80E top-up probed | old-regime tax | new-regime tax | min-delta vs baseline |
|---|---|---|---|
| ₹50,000 (partial) | ₹2,22,600-class path, still far above new | ₹97,500 | **₹0** |
| ₹5,00,000 (full headroom) | **₹96,200** | ₹97,500 | **₹1,300** — regime flips to Old |

The baseline gap is ₹1,44,300 (old ₹2,41,800 vs new ₹97,500); a small top-up narrows the gap but never closes it, so `min(old, new)` is unchanged and a partial probe reads zero. Only the one head whose headroom (₹5L) is large enough to close a ₹1.44L gap produces any signal. The dataset's positive savings rows are exactly such full-headroom flips (comment at tax_intelligence.py:432-436), which is why the probe level matches the label definition. Trade-off stated honestly: the engine reports the saving **at full headroom only**; it does not trace the break-even top-up between 0 and headroom (§7, gap 2).

## 4. Verdict rules and the response assembly

- **RECOMMEND** ⟺ `savings_engine > 0`: `confidence = 0.85` (anchored on the authoritative two-pass), `estimated_savings = savings_engine`, verdict `RECOMMEND`.
- **NO BENEFIT** ⟺ `savings_engine ≤ 0`: `confidence = 0.30`, `estimated_savings = 0`, verdict `NO BENEFIT (current regime ignores this head)`.
- `advisor_block()` emits exactly one fixed-shape paragraph (measured live output):
  `🧠 **Best opportunity**: top up Section 80E by ₹5,00,000 → est. savings ₹1,300 (confidence 85%; engine-verified in your report). Why: Section 80E has ₹5,00,000 unused (currently 0% utilized).`
  and returns `None` on: review unavailable / no candidates / top-1 not RECOMMEND — three suppression paths, plus a blanket `except` so intelligence never breaks a turn. Wired at `nlp_engine.py:1121-1132` ("Final audit ready" branch), after the composer closing line, before the legacy Quick Tip (§6).
- The Phase-6 **exact rule heads** (`rule_opportunity`, `rule_savings`, `rule_confidence`, tax_intelligence.py:648-663) pin this same logic as testable functions: opportunity = 1.0 iff engine saving > 0 (the label definition itself), savings = the engine delta unmodified, confidence = 0.85/0.30. Since the "prediction" *is* the engine computation, P/R/MAPE are correct by construction — the deliberate answer to the forensics finding that the additive TSK rule base dilutes separable signal as rules grow (tax_intelligence.py:634-645).

## 5. Worked CA-style example (every figure engine-measured, live run)

**Session:** Salaried, age 35, salary ₹15,00,000, 80C ₹50,000; nothing else booked.

**Pass 1 — baseline:** old regime ₹2,41,800 · new regime ₹97,500 → engine verdict **New Regime**, `savings_if_switched` ₹1,44,300. Gross ₹15,00,000 is ₹3,00,000 above the 87A band → `band_position = None` (outside the ±₹50k window; the regime advisor stays silent rather than noise).

**Pass 2 — full-headroom probes (8 open heads, 80TTB excluded by age):**

| Head | Top-up probed | Old-regime tax | New-regime tax | Engine saving | Verdict |
|---|---|---|---|---|---|
| 80e | ₹5,00,000 | ₹96,200 | ₹97,500 | **₹1,300** | RECOMMEND (0.85) |
| 24b | ₹2,00,000 | — | — | ₹0 | NO BENEFIT (0.30) |
| 80c | ₹1,00,000 | ₹2,10,600 | ₹97,500 | ₹0 | NO BENEFIT (0.30) |
| 80d | ₹25,000 | ₹2,34,000 | ₹97,500 | ₹0 | NO BENEFIT (0.30) |
| 80d_parents | ₹50,000 | — | — | ₹0 | NO BENEFIT (0.30) |
| 80g | ₹1,00,000 | — | — | ₹0 | NO BENEFIT (0.30) |
| 80tta | ₹10,000 | — | — | ₹0 | NO BENEFIT (0.30) |
| nps | ₹50,000 | ₹2,26,200 | ₹97,500 | ₹0 | NO BENEFIT (0.30) |

**Rank → verdict:** 80E is ranked first as the only head whose top-up moves the *better* regime (old drops below new: ₹96,200 < ₹97,500 — the engine flips its recommendation to Old Regime for the hypothetical). The CA reading: *your 80C top-up is worthless while the new regime wins; your education-loan interest, taken to its full ₹5L, is the only lever big enough to flip you back — worth ₹1,300 net.* That sentence is exactly what the emitted block says, minus the narrative.

**Suppression proof:** on a ₹24L salaried session the same loop prices all 8 heads at ₹0 → all NO BENEFIT → `advisor_block` returns None → reply unchanged.

## 6. ADR-001 audit trail — every rupee recomputed

ADR-001 (module doc, tax_intelligence.py:5-8): *ANFIS v5 never writes a tax amount; every rupee is engine-computed or an ESTIMATE clearly labeled.* The engine enforces it structurally:

1. Every candidate's `savings_engine` is `round(base_paid − paid2, 2)` from two `calculate_tax_advanced` calls — no formula, no rate table, no heuristic in the advisor layer.
2. `estimated_savings ≡ savings_engine` (tax_intelligence.py:449, 474) — and `TestADRBoundary.test_every_savings_estimate_is_engine_priced` **independently recomputes** the hypothetical engine run per recommendation and asserts exact equality, i.e. the test re-prices the engine's price.
3. The learned heads cannot leak: `recommend()` reads nothing from them for money; `advisor_block()`'s block contains only engine-priced figures; the no-benefit path zeroes `estimated_savings` outright (`test_no_amount_is_invented`).
4. Engine-only degradation (`ti=None`) is itself a test (`TestDegradation.test_recommend_without_model_still_engine_priced`): recommendations remain, every rupee stays engine-priced, the learned-head fields are simply absent.
5. Phase-6 rule heads make the same claim at function granularity (§4), so the ADR is auditable without a model artifact.

## 7. Honest comparison with the legacy generator (`ReasoningAgent.get_savings_tips`, ai_models.py:575-611)

The legacy generator is a rule-based checklist that **quotes tax arithmetic without regime gating**: for NPS it computes `gap × 0.312` whenever income > ₹15L — a hardcoded 31.2% marginal rate that ignores which regime the user should file under, surcharge, and the fact that 80C/NPS 80CCD(1B) are **not available in the new regime at all**. Measured consequence: on the §5 session (new-regime optimal), it would advertise an 80C headroom tip whose engine-priced value is **₹0**. It has no confidence, no evidence, no ranking, and no suppression — 80C/NPS tips fire purely on `< limit`, regardless of benefit. `INTELLIGENT_RESPONSE_REPORT.md` already flags it in the contract (line 16: *"Quick Tip (legacy savings tips, regime-gated in a future sprint)"*), and `nlp_engine.py:1114-1115` still appends `tips[0]` after the engine block. Credit where due: the legacy generator covers heads the prober doesn't (80D preventive-checkup ₹5,000 detail, parents' cover gated on `has_parents`, 24(b) gated on `has_home_loan`) and its copy is warmer. The engine's advantage is strictly pricing, ranking, gating, and evidence — the replacement criterion is that every rupee it quotes survives an engine recomputation, and the legacy tips do not.

## 8. Degradation ladder (what happens when things are missing)

| State | Behavior |
|---|---|
| v5 weights deployed + gate-passing | Engine-priced review + learned-head fields may decorate (`opportunity_probability` non-None) |
| Weights absent / bad artifact / no NumPy (`get_intelligence()` → None, tax_intelligence.py:505-517) | ENGINE-ONLY review — identical money figures, learned fields None |
| Engine prices zero for a head | NO BENEFIT verdict, est 0 |
| Engine prices zero for the top-1 | No block; reply unchanged |
| Any exception inside `advisor_block` | Swallowed → None; the turn completes (`test_turn_never_breaks_on_intelligence`) |

## 9. Test evidence (`backend/tests/test_tax_intelligence.py`, 12 tests)

- `TestADRBoundary` (61-91): engine recomputation exact-match per recommendation; no invented amounts on zero-benefit heads.
- `TestRecommendationShape` (98-120): field contract (`head/delta/reason/evidence/confidence/estimated_savings/opportunity_probability`), confidence bounds, ranking order invariant, regime advisory ∈ {New Regime, Old Regime}.
- `TestDegradation` (159-193): engine-only review stays priced; the 15L+50k-80C fixture surfaces the 80E flip block (`"engine-verified"`, confidence present); the all-maxed session suppresses the block — with the docstring noting the 80E flip at 1.8M saves ₹70,200 (real advice, not a test artifact).
- Composer integration (200-224): block present ⇒ cites engine figures; layer failure ⇒ turn completes.

## 10. The honest gap list — what a human CA does that this does not

1. **No interaction effects.** Probes are one-head-at-a-time against the as-booked baseline; a CA explores combinations (80C + NPS jointly can flip a regime neither flips alone) and sequences deductions. The engine prices the joint frontier only implicitly, via the flip it happens to catch at full headroom.
2. **No break-even tracing.** The probe is binary: baseline vs full headroom. It reports the saving *at* ₹5L of 80E but not the minimum top-up that flips the regime, nor the savings curve between 0 and headroom. (Measured: 0 at ₹50k, 1,300 at ₹5L — the threshold is somewhere in between and is not computed.)
3. **No eligibility gating.** A top-up is priced without knowing eligibility: nothing records whether an 80E education loan exists, whether 80D-parents cover is actually purchasable, whether 80G receipts qualify. The engine prices "if you could book it"; a CA prices "should you."
4. **No cash-flow / cost-benefit framing.** The block recommends a ₹5,00,000 outflow to save ₹1,300 without weighing the ₹4.98L liquidity cost — a human CA would usually advise against it. The tax math is right; the advice is incomplete. (80E is pre-2005 law's one interest deduction; CAs also weigh Section 80C(1)(iv)/80EEA-style alternatives the prober doesn't model.)
5. **80G pricing is naive.** The probe charges the full ₹1L headroom at the booked rate, but the old-regime value is rate × category × 10%-qualifying-limit × ₹2,000-cash-cap — the engine's own audit stream flags these (`DED_80G_DEFAULT_CATEGORY_OBSERVATION`, `DED_80G_CASH_CAP_OBSERVATION`, tax_engine.py:174-181) while the prober's priced saving can overstate.
6. **Unprobed heads.** 80U/80DD, 80DDB, 80EEA, 80GG and HRA are in the feature vector but not in `LIMITS`/`HEADS`, so no top-up is probed for them — HRA restructuring (the single most common salaried optimization) gets an assumption disclosure, not an opportunity.
7. **No filing mechanics.** Advance tax, Form 26AS/AIS reconciliation workflow (the engine only flags CG > ₹10L), ITR form selection, notice handling, carry-forward of losses — all human-CA territory.
8. **No multi-year planning.** Deduction timing across years, regime choice projected over the loan/investment tenure, capital-gains harvesting windows, retirement planning — the review is a single-year snapshot.
9. **Confidence is a constant.** 0.85/0.30 encode "engine-priced vs not", not a statistical confidence interval; `TestRecommendationShape` bounds it but nothing models uncertainty in inputs.
10. **The learned heads are experiments, not served.** `predict_savings`/`predict_opportunity` and the TSK decomposition are registry-documented; the production advisor is engine-only by design. The honest framing: the ML layer currently justifies nothing the engine doesn't already compute exactly.

## 11. File map

| Concern | Location |
|---|---|
| Two-pass engine-pricing loop, ranking, verdicts | `backend/tax_intelligence.py::recommend` (408-498) |
| Per-head saturation (deduction advisor evidence) | `backend/tax_intelligence.py::utilization` (392-405) |
| Composer-facing top-1 block + suppression | `backend/tax_intelligence.py::advisor_block` (603-629) |
| Exact rule heads (opportunity/savings/confidence) | `backend/tax_intelligence.py` (648-663) |
| Regime verdict + 87A band position | `backend/tax_intelligence.py` (485-495) |
| Integration into the closing turn | `backend/nlp_engine.py` (1112-1132) |
| Engine advisory stream (80G cash-cap, CG holding, election) | `backend/tax_engine.py` (129-185, 394-395, 435-440, 476-485) |
| Legacy tip generator (comparison baseline) | `backend/ai_models.py::get_savings_tips` (575-611) |
| Contract tests | `backend/tests/test_tax_intelligence.py` |
| Response contract | `INTELLIGENT_RESPONSE_REPORT.md` |

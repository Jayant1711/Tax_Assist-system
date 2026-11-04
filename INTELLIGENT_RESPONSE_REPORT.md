# INTELLIGENT RESPONSE REPORT — Composer × Tax Intelligence Integration
**Generated:** 2026-11-03 · **Integration point:** `backend/nlp_engine.py` closing turn (`"Final audit ready"` branch) · **Layer:** `backend/tax_intelligence.py::advisor_block`

---

## 1. The integrated response contract

When discovery completes, the reply now assembles as:

```
[composer ack — booked specifics, en-IN]
🧠 Best opportunity: top up Section <HEAD> by ₹<delta> → est. savings
   ₹<engine-priced> (confidence 85%; engine-verified in your report).
   Why: Section <HEAD> has ₹<headroom> unused (currently <pct>% utilized).
[composer closing line]
💡 Quick Tip (legacy savings tips, regime-gated in a future sprint)
```

Every field of the mission contract is present: **recommendation** (the head + top-up), **explanation** (the reason line = utilization state), **confidence** (0.85, anchored on the engine two-pass), **evidence** (`evidence[]` lines: booked vs limit, engine-priced delta), **estimated savings** (engine-priced — never model-invented), **next best action** (the top-up itself, sized to the remaining headroom).

## 2. Behavior matrix (all verified by tests + live E2E)

| Session state | Reply |
|---|---|
| Material opportunity exists (engine prices > 0) | 🧠 block with the top-ranked one |
| Every head maxed / engine prices zero | No block — reply unchanged (advisor refuses to invent) |
| Intelligence layer offline / exception | No block — turn never breaks (`advisor_block` swallows + returns None) |
| Regime flip case (e.g. 80E ₹5L top-up on a 15L salary) | Block appears with the flip saving (₹1,300) — the regime-flip advice a CA would give |

## 3. Honest-advice properties (measured)

1. **Zero-invented-rupees**: `estimated_savings == savings_engine` asserted by `TestADRBoundary` (engine recomputation exact-match).
2. **Regime honesty**: a top-up that only helps the non-recommended regime is labeled `NO BENEFIT (current regime ignores this head)` — stricter than the legacy Quick Tip (which quotes old-regime arithmetic on new-regime users; regime-gating that tip is filed as next-sprint work).
3. **Determinism**: same session state → same block (composer rotation is turn-indexed; the block content is engine-priced).
4. **Bounded reply**: the block is a single fixed-shape paragraph; the amplification guards cap everything else.

## 4. Test coverage

- `tests/test_tax_intelligence.py` (12): ADR-001 recomputation, recommendation shape, ranking order, regime advisory, explainability decomposition, offline/engine-only degradation, no-benefit suppression, closing-turn integration, never-breaks-a-turn.
- `tests/test_response_composer.py` (23): composer determinism/variety/data-awareness (>95% contextual), advisory correctness.
- Live E2E: consultant flow verified — block correctly absent when the engine prices zero (new-regime consultant), present on old-regime-optimal fixtures.

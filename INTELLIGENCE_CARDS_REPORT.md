# INTELLIGENCE_CARDS_REPORT.md — Frontend Intelligence Cards (Sprint 6 Phase 3)
**Generated:** 2026-11-05 · **Basis:** `frontend/src/components/TaxReport.tsx`, `/calculate` intelligence attach, live Playwright verification · **Status:** LIVE — cards render, actions persist, funnel updates

---

## 1. What the user sees

At the FINAL report, a **"CA Recommendations — Ranked Opportunities"** card
renders the top-3 engine-ranked opportunities. Every card shows all six
mission-required elements:

| Element | Rendering |
|---|---|
| Recommendation | `1. Section 24B` (or `— no benefit` for zero-benefit heads, muted) |
| Confidence | `confidence 85%` (the engine-anchored value, calibration §Phase 2) |
| Estimated savings | `est. saves ₹32,500` — engine-priced, en-IN formatted |
| Reason | "Section 24B has ₹2,00,000 unused (currently 0% utilized)" |
| Evidence | bullet list: booked-vs-limit + "engine-priced: a top-up of ₹2,00,000 saves ₹32,500 (authoritative)" |
| Acceptance action | `✓ Apply this` / `✕ Not for me` → ADR-017 action endpoint |

Below it, the **"Per-Deduction Impact — Exact (Engine-Priced)"** table
(Phase 5) renders the leave-one-out impact per booked head.

## 2. Architecture decisions (all evidence-driven)

1. **Cards render from `/calculate`, not a separate fetch.** `/calculate`
   attaches the live ranked review (and impact rows) when the session phase
   is FINAL — mid-flow profiles would rank zero-benefit noise. Best-effort:
   a review failure never breaks the calculation.
2. **Deterministic rec_ids.** `uuid5(session_id|head)` — the id on a card
   equals the id recorded as a shown event at the closing turn, so the
   action endpoint resolves it. The first cut used `uuid4` per call: every
   click would have 404'd.
3. **Acceptance gated on the FINAL phase.** Buttons render only when
   `projection.phase === 'FINAL'` (the shown events exist exactly then);
   before that the card shows "Acceptance unlocks in the final report."
   Pin: `TaxReport.test.tsx` (both the FINAL and pre-FINAL renders).
4. **The `/end` override fix.** `/end` used to return early — no ranked
   review, no shown events, every action 404. The closing intelligence is
   now a shared helper (`_closing_intelligence`) used by both closing
   paths. This was found by the live E2E (404 on first Apply click) and is
   pinned in pytest.

## 3. Live verification (Playwright, running stack)

- Profile: ₹15L salary + ₹5L 80E + ₹2L 24(b) → `/end` → phase FINAL.
- Cards: 3 × RECOMMEND (24B ₹32,500 / 80C ₹22,100 / 80G ₹1,300 — all
  confidence 85%) with evidence bullets and buttons.
- Click "✓ Apply this" on 24B → `POST .../recommendations/{rec_id}/action`
  → analytics readback: `total_shown: 3, total_accepted: 1, rate 0.3333`.
- Screenshots: `sprint6-intelligence-cards-live.png`,
  `sprint6-deduction-impact-live.png` (repo root).

Also verified live: a fully-booked ₹24L profile renders the cards honestly
as **no-benefit** (Section 24B — no benefit, confidence 30%) — the cards do
not manufacture opportunities.

## 4. Tests

- vitest **31/31** (4 files): 6 new TaxReport tests — cards render
  (confidence/savings/reason/evidence/buttons), action POST wire
  (URL + method + `{action: "accepted"}`), omission without payload,
  pre-FINAL button gating, impact table render/omission.
- `npx tsc --noEmit` clean.
- pytest: `TestCalculateIntelligenceAttach` + `TestEndOverrideCapture`
  pin the backend half of the wire.

## 5. Bugs found and fixed during this phase

| Bug | Symptom | Fix |
|---|---|---|
| Stray duplicate JSX block in TaxReport.tsx | tsc TS1128/TS1109, vitest collection failure (bracket depth −2 at EOF) | removed the duplicated marginalRate note + orphaned closers |
| Python `int()` in JSX | TS2552 on card confidence | `Math.round` |
| Random card rec_ids | every acceptance click would 404 | deterministic `uuid5(session|head)` |
| `/end` skip of the closing intelligence | zero shown events on `/end` sessions | shared `_closing_intelligence` helper |
| deduction_impact sign inversion | table showed ₹-1,30,000 for a ₹1,30,000 benefit | delta direction fixed + pins |

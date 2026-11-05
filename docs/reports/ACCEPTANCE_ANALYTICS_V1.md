# ACCEPTANCE_ANALYTICS_V1.md — Recommendation Acceptance Analytics (Sprint 6 Phase 1)
**Generated:** 2026-11-05 · **Basis:** ADR-017 (recommendation acceptance events), Sprint 5 Wave-1 capture, Sprint 6 extension · **Status:** LIVE — verified end-to-end in the running stack

---

## 1. What shipped

The acceptance feedback loop closes end-to-end: every ranked recommendation the
system shows is recorded as a **shown event**, the user's response is recorded
as an **action event**, and the per-session/per-head funnel is queryable.

| Piece | Where | Contract |
|---|---|---|
| Event store | `recommendation_events` table (migration 3) | `(id, session_id, user_id, head, delta, savings_engine, confidence, action, created_at, resolved_at)` — id IS the recommendation's `rec_id` |
| Shown capture | `main.py` /chat step 5b | fires when `plan == "Final audit ready."` and the session carries `_recommendations_shown`; best-effort — never fatal to a turn |
| Action capture | `POST /sessions/{sid}/recommendations/{event_id}/action` | body `{action}` ∈ accepted / rejected / ignored / viewed / dismissed; 404 foreign/unknown event; ownership double-checked in SQL |
| Funnel analytics | `GET /sessions/{sid}/recommendations/analytics` | `db.recommendation_analytics()` — totals + per-head shown/accepted/rejected/ignored/viewed/dismissed + max savings |
| Listing | `GET /sessions/{sid}/recommendations` | all shown events for one owned session, newest first |

## 2. The Sprint 6 capture fixes (both regression-pinned)

1. **`/end` override recorded nothing** — the early return skipped the
   closing-turn intelligence entirely, so `/end` sessions had zero shown
   events and every card action 404'd. Fix: the closing intelligence
   (engine-priced review → shown stash + regime-gated tips + advisor text)
   is extracted into `NLPEngine._closing_intelligence()` and shared by the
   natural closing turn AND the `/end` override. Pin:
   `tests/test_recommendation_events.py::TestEndOverrideCapture`.
2. **Card rec_ids were random per call** — `uuid4` made every `/calculate`
   render carry fresh ids that could never match a persisted event. Fix:
   `rec_id = uuid5(NAMESPACE_URL, f"{session_id}|{head}")` — deterministic,
   so the id on a card is the id in the table. Pin:
   `TestCalculateIntelligenceAttach` (two `/calculate` calls return identical ids).

## 3. Live funnel (verified in the running stack)

Profile: salary ₹15,00,000 + ₹5,00,000 80E + ₹2,00,000 24(b), closed via `/end`:

```json
{
  "total_shown": 3, "total_accepted": 1, "acceptance_rate": 0.3333,
  "per_head": [
    {"head": "24b", "shown": 1, "accepted": 1, "savings_engine": 32500},
    {"head": "80c", "shown": 1, "accepted": 0, "savings_engine": 22100},
    {"head": "80g", "shown": 1, "accepted": 0, "savings_engine": 1300}
  ]
}
```

The "✓ Apply this" click on the Section 24B card is the `accepted` action —
the deterministic rec_id resolved the shown event recorded by the same
session's closing turn.

## 4. Honest limitations

- The action enum accepts `viewed`/`dismissed` but nothing auto-fires them
  yet (the cards fire accepted/rejected only). Reserved for the dashboard's
  deeper funnel.
- Events are per-session; a cross-session dashboard (per-user lifetime
  funnel) is Sprint 7 scope once real volume exists.
- `savings_engine` is the ENGINE-priced top-up saving at shown time; it does
  not update if the user edits the session afterwards.

## 5. Verification

- pytest: 11 tests in `tests/test_recommendation_events.py` (migration, capture,
  scoping, action auth/ownership/validation, `/end` capture, `/calculate` attach).
- Live: the funnel above was read back from the running container's DB.

# RECOMMENDATION_ANALYTICS_REPORT.md — Recommendation Analytics (Sprint 6 Phase 4)
**Generated:** 2026-11-05 · **Basis:** `GET /sessions/{sid}/recommendations/analytics`, `db.recommendation_analytics()`, live session data · **Status:** LIVE

---

## 1. The analytics surface

The Effectiveness Dashboard's data source — one endpoint, no client-side
aggregation:

```
GET /sessions/{session_id}/recommendations/analytics
```

Response shape (live, owned session; 404 foreign/unknown):

```json
{
  "session_id": "1d251bdd8e4c4c2b8e2e5393c443f792",
  "total_shown": 3,
  "total_accepted": 1,
  "acceptance_rate": 0.3333,
  "per_head": [
    {"head": "24b", "shown": 1, "accepted": 1, "rejected": 0, "ignored": 0,
     "viewed": 0, "dismissed": 0, "savings_engine": 32500},
    {"head": "80c", "shown": 1, "accepted": 0, "rejected": 0, "ignored": 0,
     "viewed": 0, "dismissed": 0, "savings_engine": 22100},
    {"head": "80g", "shown": 1, "accepted": 0, "rejected": 0, "ignored": 0,
     "viewed": 0, "dismissed": 0, "savings_engine": 1300}
  ]
}
```

## 2. The four mission metrics, mapped

| Mission metric | Source field |
|---|---|
| Shown count | `total_shown` / `per_head[].shown` |
| Acceptance rate | `acceptance_rate` (accepted ÷ shown, session-level) |
| Ignore rate | `per_head[].ignored` (+ `rejected`, `dismissed` — the negative funnel) |
| Savings delivered | `per_head[].savings_engine` (engine-priced at shown time; accepted subset = the heads with `accepted ≥ 1`) |

## 3. Live session evidence

From the running stack (ADR-017 store, session `1d251bdd…`): 3 shown,
1 accepted (Section 24B via the card's "✓ Apply this"), rate 0.3333. The
head savings — 24B ₹32,500 / 80C ₹22,100 / 80G ₹1,300 — are the engine's
own leave-one-out prices for that profile (salary ₹15L + 80E ₹5L + 24b ₹2L).

The full funnel was previously exercised in the Sprint 5 wave-1 E2E
(9 shown events across a 9-turn discovery); the Sprint 6 `/end` fix
(`TestEndOverrideCapture`) guarantees both closing paths populate it.

## 4. Reading the analytics honestly

- **Sparse by design while young.** Events accumulate per real session;
  nothing is synthesized. The ECE study (Phase 2) consumes the resolved
  subset of this same store.
- **`savings_engine` is a stock, not a flow.** It is the engine-priced
  opportunity at shown time — "savings delivered" in the audited sense
  (what the engine would price if the user took the top-up), not a claim
  about the user's actual filing.
- **Negative funnel matters.** A head with high `shown` but high
  `rejected` is a ranking bug signal; the dashboard's per-head split makes
  that visible (currently all zeros except one acceptance — too early to
  read).

## 5. Verification

pytest: `TestClosingTurnCapture`, `TestEndOverrideCapture`,
`TestCalculateIntelligenceAttach`, and the action-endpoint auth/ownership
suite in `tests/test_recommendation_events.py` (11 tests). Live: the JSON
above read back from the running container.

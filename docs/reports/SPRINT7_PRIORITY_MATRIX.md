# SPRINT7_PRIORITY_MATRIX.md — Sprint 7 Candidate Scoring (Phase 4)
**Generated:** 2026-11-05 · **Method:** each mission-listed candidate scored 1–5 on user value / engineering value / research value, with risk and honest effort (in sprint-days of focused work) · **Constraint context:** D1–D10 policy (see `PROJECT_DECISIONS_2026.md`); the pricing layer is FROZEN — candidates are scored on adoption, reach, and research fronts only

---

## 1. The matrix

| Candidate | User value | Eng value | Research value | Risk | Effort | Weighted verdict |
|---|---|---|---|---|---|---|
| **1. Acceptance Analytics** (Effectiveness Dashboard: cross-session funnel, per-head adoption, ECE tracking view) | **4** — turns the invisible loop into the owner's proof-of-value; the single best demo artifact | **5** — the store + endpoint exist; only aggregation+UI missing; makes every future data-gated decision measurable | **3** — adoption curve becomes observable | LOW (read-only over a live store) | **3d** | ★ **9.0 — DO FIRST** |
| **2. Confidence Calibration** (full study) | 2 — invisible to end users | 3 — completes G7's data path | **4** — the G7 decision needs ≥30 resolved events to matter | LOW | 1d (rerun when data exists) | 6.0 — instrument DONE; only the rerun remains, data-gated. Fold the rerun into the dashboard (a live ECE tile) |
| **3. Recommendation Adoption** (one-click **Apply**: card button pre-books the top-up into the session and recomputes via the engine) | **5** — the loop's action half: acceptance stops being a diary entry and becomes one click that changes the tax outcome | 4 — new write path into the session + engine recompute; small ADR-001-safe (engine recomputes) | 3 — measures REAL adoption vs stated intent | MED (session-state write path needs careful ownership + audit) | **4d** | ★ **8.0 — DO SECOND** |
| **4. Personalization** (acceptance-derived ranking) | 3 — but **blocked by D6** (~50 resolved events; current: single digits) | 2 — no consumer data yet | 4 — the intended payoff of the whole loop | HIGH (would train on noise today) | 8d+ | **3.0 — DEFER** (hard-gated; revisit at ~50 resolved events) |
| **5. Intelligence UX** (card states, empty-states, 24b reason string, mobile polish of the new panels) | 4 — the cards are the product's face for evaluators | 3 — small, mostly CSS/copy | 1 | LOW | 2d | 7.0 — fold the small items into the dashboard sprint (they share files) |
| **6. NER Expansion** (template growth, more heads, eval re-run) | 2 — invisible until input coverage grows | 3 — better prepass robustness | **4** — the standing research track (ADR-015 trigger watch) | LOW-MED | 3d | 6.5 — keep as the research half of the sprint (timeboxed) |
| **7. Corpus Growth** (promote organic capture from opt-in to default-on with minimization) | 2 — no immediate UI value | **4** — ADR-015 re-open trigger needs real utterances; cheap infrastructure win | 3 — the eval corpus stops being synthetic-only | MED (PII minimization must be re-audited) | 2d | 6.5 — flip the default + document minimization |
| **8. Recommendation Ranking v2** (learned ordering of candidates by predicted acceptance) | 3 | 3 | 4 | HIGH (needs the same missing data; G8 gate must be defined first) | 5d+ | **3.5 — DEFER** behind the same data gate as #4 |

## 2. What the scoring says

- The top two — **Dashboard (1)** and **Apply (3)** — are the only
  candidates that are simultaneously high-value and LOW-data-risk. They
  complete the loop the project spent Sprints 5–6 building: **show →
  accept → measure → apply → recompute**.
- Both data-consumers (#4 personalization, #8 ranking) score low TODAY for
  one reason only: the store is young. The correct move is not to defer the
  *decision* but to defer the *work* — the dashboard is exactly the
  instrument that will tell us when the gate opens.
- NER (#6) and corpus default (#7) are the standing research/infrastructure
  track: cheap, independent of data gates, and they keep the ADR-015
  re-open option alive.

## 3. Recommended Sprint 7 shape (from this matrix)

**Theme: "Adoption — make the loop usable and watchable."**
Scope = #1 Dashboard (3d) + #3 Apply (4d) + the small UX items from #5
(folded, 1d) + timeboxed #6 NER (2d) ≈ **10 focused days ≈ 2 calendar
weeks** — with #7 as a stretch item and #2's ECE rerun riding the
dashboard tile. Full proposal with gates and stop conditions:
`SPRINT7_PROPOSAL.md`.

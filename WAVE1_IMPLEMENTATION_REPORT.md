# WAVE1_IMPLEMENTATION_REPORT.md — Sprint 5 Wave 1
**Generated:** 2026-11-04 · **Scope:** P0.1 normalization fixes · P3 tip regime-gating · P2 acceptance capture · **ADR-017**

---

## 1. P0.1 — Feature/label normalization fixes (`tax_intelligence.features_v2`)

| Fix | Before | After | Evidence |
|---|---|---|---|
| f9 u80g | `80g/(inc·0.1+1)` — income-scaled, mismatched the composite's `booked/100k` ground truth (1,564 rows, max 1.717) | `clip(80g/100_000)` | feature probe: 100k booked → 1.0 |
| f11 80U/80DD | numeric `80u_80dd/125k` — always 0 (the flat-amount guard books the enum, never a number) | derived from `80u_80dd_category`: 40_79 → 0.6, 80_plus → 1.0 | feature probe: category 40_79 → 0.6 |
| f12 80ddb | booked numeric (sampler never booked it) | unchanged normalization; **80ddb added to the sampler grid** (Wave 2) | grid rows now carry 80ddb |
| 80d_parents inert probe | 600/600 probes priced ₹0 | diagnosed: NOT an engine bug — the v1 strata probed it only at deep-new-regime incomes where no old-regime top-up can help; the v3 sampler's flip-adjacent strata (12L–35L heavy-deduction) cover it | container probe: 50k books → 7,800 delta ✓ |

## 2. P3 — Regime-gated savings tips (`ai_models.get_savings_tips`)

- New optional `recommended_regime` param; when the engine's verdict is **New Regime**, the Chapter VI-A tips (80C/80D/24b/self-NPS) are replaced with the 115BAC-honest guidance (₹75k std + employer NPS 80CCD(2) + let-out 24(b)).
- The closing turn now computes ONE engine-priced review and uses it for BOTH the tips gate AND the intelligence block (single source, no double pricing).
- Callers without the regime get the legacy behavior (back-compat).

## 3. P2 — Acceptance capture (ADR-017)

- **Migration 3** (`db.py`): `recommendation_events` table — id/session_id/user_id/head/delta/savings_engine/confidence/action/created_at/resolved_at. PII-minimized (no free text).
- **Shown capture** (`main.py` step 5b): on the closing turn, one row per ranked RECOMMEND (rec_id = uuid4 from `recommend()`).
- **Action endpoint**: `POST /sessions/{sid}/recommendations/{event_id}/action` (accepted/rejected/ignored; ownership double-checked event→session→user; 404 foreign/unknown).
- **List endpoint**: `GET /sessions/{sid}/recommendations` (owner-scoped, newest first).
- **Scrub**: `_recommendations_shown` added to `audit_logger.DROPPED_STATE_KEYS` — the stash never reaches projections or the audit trail.

## 4. Wiring changes

- `nlp_engine` closing branch: ONE engine-priced review (`advisor_review`) drives the gated tips + the intel block; the ranked list is stashed for main.py.
- `tax_intelligence`: `advisor_review` (review) split from `advisor_text_from_review` (render); `advisor_block` kept as a compat wrapper.
- `rule_*` heads now actually called by `recommend()` (audit finding F5 closed).

## 5. Tests

- `tests/test_tax_intelligence.py` (12): degradation contract updated to rule-head semantics (opportunity ∈ {0.0, 1.0}).
- New `tests/test_recommendation_events.py`: migration applies; shown-event insert; action update; ownership 404; invalid action 422; scrub drops `_recommendations_shown`.
- Full suite at Wave-1 commit: **1,146+ pytest, 0 failed**.

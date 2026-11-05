# INTELLIGENCE_ROADMAP.md — Phase 5
**Generated:** 2026-11-04 · **Baseline:** v0.5 intelligence (composite served · exact rule heads · CA advisor · transparency panel) · **Invariant:** ADR-001 — every figure engine-priced or clearly labeled estimate

---

## Maturity ladder (where we are → where this roadmap goes)

| Stage | Status |
|---|---|
| L0 — static rules | ✅ v0.4 |
| L1 — measured intelligence (gates, registries, forensics) | ✅ v0.5 |
| L2 — exact rule heads + transparency | ✅ v0.5 (deployed) |
| **L3 — feedback loop** (acceptance capture → weak labels → calibration) | 🎯 Sprint 5-6 |
| **L4 — learned estimators on gates** (TSK promotion) | 🎯 Sprint 5-6 (data-gated) |
| L5 — adaptive personalization | Sprint 6+ (L3 data-gated) |

## Capability roadmap

### 1. Recommendation feedback learning (L3 — Sprint 5 P2)
- Capture: shown / accepted / rejected / ignored per recommendation (event row, PII-minimized, audit-streamed).
- Learn: acceptance rate per head × confidence band × profile → recalibrate the confidence formula (replace fixed 0.85 with an empirically grounded score).
- Guard: acceptance influences RANKING and CONFIDENCE only — never amounts, never the regime verdict (that stays engine-computed).

### 2. Confidence calibration (L3 → L4)
- Current: fixed 0.85/0.30 (documented, honest, crude).
- v6 path: learn P(benefit | schema features) from the acceptance + probe datasets; validate with a calibration curve (reliability diagram) as a new gate (G7: ECE ≤ 0.05).
- Deploy only on gate pass; otherwise the fixed formula stays.

### 3. Recommendation analytics (L3)
- Funnel extension: which heads are recommended most, accepted most, ignored most; acceptance-by-profile.
- Surfaces: internal analytics report first (funnel.py extension); user-facing later (P6).

### 4. Adaptive personalization (L5 — data-gated, Sprint 6+)
- Profile-aware head priors (e.g. salaried users see HRA/NPS ranked higher) — only after acceptance history exists per profile.
- Cold-start rule: no history → the v0.5 deterministic behavior.

### 5. Behavioral intelligence (L5 — rejected for now)
- Patterns like "users who max 80C also want NPS" require cross-session history + privacy review — rejected until P2/P5 produce data (this run's evidence standard: no data, no feature).

## ADR-001 compliance note (every item)

None of the above writes a tax amount. Acceptance and confidence shape **which** engine-priced opportunity is shown first and **how sure** we claim to be — the rupees remain `calculate_tax_advanced` output, and every recommendation keeps its engine-priced `savings_engine` alongside any estimate.

## Sprint mapping

| Roadmap item | Sprint | Gate |
|---|---|---|
| Feedback capture | 5 (P2) | event schema + tests |
| Confidence calibration | 6 (data-gated) | G7 ECE ≤ 0.05 |
| Recommendation analytics | 5-6 (funnel extension) | report exists |
| Personalization | 6+ | per-profile acceptance history ≥ threshold |
| Behavioral intelligence | 7+ | cross-session privacy review + data volume |

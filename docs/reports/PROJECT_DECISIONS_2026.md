# PROJECT_DECISIONS_2026.md — Permanent Project Policy (Phase 2)
**Adopted:** 2026-11-05, post-Sprint-6 · **Nature:** these are POLICY — decisions that bind all future sprints until a documented, evidence-carrying reversal · each traces to a measurement, none to opinion

---

## D1 — The TaxEngine is the only calculator. Permanently.
No model, heuristic, cache, or client-side arithmetic ever produces a rupee
figure shown to a user. (ADR-001, held since Sprint 2; re-certified by EXP-008
and the Sprint 6 impact engine.) *Reversal bar: never — this is the trust
foundation.*

## D2 — Learned regression on closed-form targets: CLOSED.
The TSK savings/opportunity heads are permanently denied (three-scale
falsification: 3.5k / 77k / 378k rows — `TSK_PROMOTION_REPORT.md`). Any future
modeling attempt on this target family requires **new evidence that the target
is no longer computable** (e.g., the engine's own logic changed) AND an
explicit re-open memo. *Default answer: no.*

## D3 — Dataset strategy: benchmark, not growth.
anfis-v3 is the FINAL dataset scale (21,964 scenarios / 51,873 positives). Row
scaling is stopped; the sampler code is retained as a deterministic eval-asset
generator. No future sprint "grows data" without naming the new consumer
first.

## D4 — Rule heads are the production intelligence.
The exact rule heads (P/R 1.0, savings MAE 0.00) are the serving path
(ADR-016). Intelligence work moves to **ranking, relevance, and presentation**
— never to re-pricing what the engine already prices.

## D5 — No learned confidence without G7.
A confidence model may replace the 0.85/0.30 anchor only after: ≥ 30 resolved
acceptance events AND ECE ≤ 0.05 on them AND no acceptance-rate degradation
(`CONFIDENCE_CALIBRATION_REPORT.md` §G7). Until then the anchor stays constant
— a number whose meaning we can state exactly.

## D6 — No personalization without adoption data.
Behavioral ranking/personalization is blocked until the acceptance store holds
**~50 resolved events** (strategic review §2; still the gate at v0.6).

## D7 — Every user-facing claim carries engine evidence.
Cards show booked-vs-limit + the engine's own pricing line; zero-benefit is
labeled zero-benefit (never hidden); the impact table is exact recomputation.
No unsourced numbers in the UI, the reports, or the advisor text.

## D8 — Live end-to-end verification is a release gate.
Sprint 6 proved review misses whole bug classes (sign inversion, `/end`
capture skip, bracket corruption) that a 5-minute live session catches. Every
sprint ships only after a scripted live E2E against the running stack
(screenshots archived).

## D9 — Determinism and EOL discipline for all data artifacts.
Seeded generators, `newline="\n"` writes, sha256 content-addressed manifests
(the 726d735 lesson). A dataset that cannot be rebuilt byte-stably is a bug.

## D10 — Honest reporting is policy.
Sparse data is reported as sparse; failed gates are reported as failures; the
registries are append-only. No metric is rounded toward flattering.

## What these decisions do to the roadmap
They END the model-building era on current targets and make **adoption
measurement, UX of the intelligence, and reach** the only open fronts —
`SPRINT7_PRIORITY_MATRIX.md` scores exactly that.

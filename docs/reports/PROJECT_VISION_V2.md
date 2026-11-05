# PROJECT_VISION_V2.md — Next-Generation Vision (Phase 5)
**Generated:** 2026-11-05 · **Horizon:** 6–12 months · **Question:** what should Tax Assist BECOME? · **Constraint:** the answer must survive every D1–D10 policy — no ML-priced rupees, no invented tax law, offline-deterministic, audit-first

---

## 1. The one-line vision

**From "an AI tax calculator that explains itself" to "the transparent tax copilot that learns what taxpayers actually adopt."**

## 2. The three pillars

### Pillar 1 — TRUST (built, keep green)
The reason this project is defensible in a viva, an audit, or a demo: every
rupee recomputed by one engine (ADR-001), every claim carrying evidence,
every decision logged append-only, every calculation explainable down to
the slab. Sprints 2–6 built this. **Nothing in the next 12 months may
weaken it.** Trust is the moat — the AI-label alone is not.

### Pillar 2 — LEARNING (instruments live, value pending)
The loop exists: show → accept → measure (funnel) → calibrate (ECE/G7).
The next 6–12 months make it produce *decisions*: the dashboard makes
adoption observable, one-click Apply makes acceptance real, and — when
~50 resolved events exist — acceptance-derived ranking and G7-gated
confidence become the first LEARNED layers the project has ever shipped.
The learning here is **behavioral**, not arithmetic: the engine prices,
the users teach the system what to rank (the strategic review's line,
now policy).

### Pillar 3 — REACH (the growth axis)
Today the consultant is excellent for salaried profiles in FY 2025-26 and
honest about its limits elsewhere. Reach means widening the same exactness
guarantee to:
- **More taxpayers**: business owners (presumptive 44AD/ADA), capital
  gains flows (the strata exist in the dataset), seniors (80TTB/80U paths
  already engine-priced), Hindu Undivided Families as a profile type.
- **More inputs**: Form-16 / salary-slip parsing (the NLP extraction
  pipeline is already the right substrate; ADR-015's corpus trigger lives
  here).
- **More outputs**: ITR-ready JSON export mapped to the real ITR-1/ITR-2
  field names, a print-grade PDF computation statement, and a
  "what changed this FY" regulatory diff note (the tax-rules registry
  already versions FY logic).
- **More years**: FY 2026-27 lands with a rules-file addition + registry
  re-certification, not a rewrite — that resilience is already designed.

## 3. What Tax Assist must NOT become (anti-vision)

- Not an LLM wrapper: no network dependency, no hallucinated sections, no
  non-reproducible advice (ADR-003 stands).
- Not a filing service: e-filing/PII handling changes the security posture
  an order of magnitude — out of scope for a student project's threat model.
- Not a model zoo: D2/D3 end the build-models-because-we-can era.
- Not a multi-tenant SaaS: loopback-first deployment stays until the
  security budget genuinely changes.

## 4. The north-star metric

**Accepted-₹**: the engine-priced sum of recommendations users actually
accepted. It fuses correctness (engine-priced), adoption (accepted), and
value (₹) in one auditable number. Everything in Pillars 2–3 is justified
by its effect on Accepted-₹ per session; everything in Pillar 1 is
justified by keeping that number *honest*.

## 5. Milestone ladder (6–12 months, each gate-carried)

| When | Milestone | Gate to pass |
|---|---|---|
| Sprint 7 (2 wks) | Adoption sprint: dashboard + one-click Apply | 0 regressions; funnel coverage 100% of shown |
| Sprint 8 | Reach sprint: business/CG profile depth + ITR-JSON export | tax-expert review; engine-only pricing holds |
| Sprint 9 | Input sprint: Form-16 parsing on the extraction substrate | macro F1 gate ≥ 0.95 on the new corpus |
| Sprint 10+ | First learned layer IF data gates open: acceptance-ranked ordering (G8) / calibrated confidence (G7) | the gates themselves — no data, no ship |
| Any time | FY 2026-27 rules drop | registry re-certification + full suite green |

## 6. The vision in one sentence

A tax consultant whose every number is provably exact, whose every
recommendation shows its evidence, and which — uniquely — **learns from
what taxpayers accept** without ever learning to make a number up.

# SPRINT7_PROPOSAL.md — Sprint 7 Recommendation (Phase 6)
**Proposed:** 2026-11-05 · **Theme:** "Adoption — make the loop usable and watchable" · **Status:** PROPOSAL — implementation NOT started (per mission STOP)

---

## 1. Recommended scope (from the priority matrix)

| ID | Item | Days | Why it's in |
|---|---|---|---|
| S7.1 | **Effectiveness Dashboard**: cross-session acceptance funnel (shown/accepted/rejected per head), Accepted-₹ total, live ECE tile, empty-states for young data | 3 | the loop becomes observable; every later data-gated decision gets its instrument |
| S7.2 | **Card acceptance states + viewed auto-fire**: cards render accepted/rejected state after action; a `viewed` action fires once per card render at FINAL | 1 | closes the funnel's passive slots; makes the dashboard's numbers complete |
| S7.3 | **One-click Apply**: card button pre-books the recommended top-up into the owned session (head → headroom), recomputes via the engine, shows the new outcome; audit-logged; undo row | 4 | the loop's action half — acceptance changes the tax outcome; engine remains the only calculator (ADR-001 safe) |
| S7.4 | **UX smalls**: 24(b) impact reason string (self-occupied vs let-out), card copy pass, mobile width pass on the two new panels | 1 | cheap polish on the same files |
| S7.5 | **NER expansion (research track, timeboxed)**: +2 template families, eval re-run, registry row | 2 | keeps the ADR-015 watch alive; independent of all gates |
| — | *Stretch (only if everything else is green):* flip organic corpus capture default-on with documented minimization | 1 | corpus growth for the extraction trigger |

**Total: ~11 focused days ≈ 2 calendar weeks** (house sprint cadence).

Explicitly EXCLUDED: personalization, learned ranking (G8), learned
confidence — all data-gated (D5/D6); any TSK work (D2); any dataset growth (D3).

## 2. Expected metrics (the sprint's own acceptance criteria)

| Metric | Target |
|---|---|
| pytest | ≥ 1,180, 0 failures (new: dashboard aggregation, viewed events, Apply write path) |
| Vitest | ≥ 36, 0 failures (dashboard, card states, Apply flow) |
| Funnel coverage | 100% of shown recommendations resolvable to an action (viewed fires on render) |
| Live E2E | one full session: show → view → accept → **Apply recomputes the engine** → dashboard reflects all of it (screenshots) |
| Accepted-₹ | first honest measurement published in the dashboard (even if ₹0) |
| ADR-001 | zero violations — Apply recomputes, never estimates |

## 3. Validation gates

1. Full suite green locally BEFORE push (house rule).
2. CI green on the PR (backend / frontend / e2e).
3. Live Playwright pass of the new loop (D8 — a release gate now).
4. tax-expert sanity check on the Apply semantics (top-up must respect the
   statutory limits the engine already enforces).
5. security-auditor pass on the new write path (session-state mutation from
   a card click — ownership + rate limits + audit).

## 4. Stop conditions (when to cut scope or halt)

- **Stop S7.3** if the Apply write path cannot be made idempotent and
  ownership-clean in ≤ 4 days — ship S7.1/S7.2 alone (they stand alone).
- **Halt-and-rollback** if any acceptance-store migration would break the
  existing event contract (append-only; ALTER only).
- **Cut the stretch item** the moment PII-minimization review flags anything.
- **Do not start** S7.3 before the dashboard (S7.1) — the dashboard is the
  proof the loop works; Apply without measurement is un-auditable product
  instinct.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Apply makes the session state diverge from the chat's NLP flow | Apply goes through the SAME extraction-validated write path (booked head += headroom, clamped); a "Recalculate" chat turn confirms |
| Dashboard computes over large event tables | per-session endpoint exists; the dashboard aggregates per-USER with a LIMIT + index on user_id |
| Viewed events inflate the store | one per (event, session) — unique constraint, best-effort capture |

## 6. Why this and not anything else

The pricing layer is exact and frozen (D1–D4). The loop's capture half is
live. The ONLY remaining value on the current architecture is **usable
adoption + its measurement** — and both are low-risk, engine-safe, and
demo-defining. Everything data-gated waits for the data this sprint
generates.

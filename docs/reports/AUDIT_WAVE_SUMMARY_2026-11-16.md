# Fresh-Eyes Audit Wave — Summary (2026-11-16)

Scope: full-codebase adversarial re-review (trust nothing), specialist subagent
waves (backend-engineer, security-auditor, tax-expert, qa-lead,
frontend-engineer, ml-evaluation-engineer, architect), fix-all-P0/P1, re-audit.
Commits: `9c9ff37` (wave 1), `42d4df4` (wave 2), `9e8d10f` (frontend marker fix).

## Suite state after the wave

| Suite | Result |
|---|---|
| backend pytest | **1,234 passed / 0 failed / 0 skipped** (extraction gate BINDING) |
| frontend vitest (node:20-slim container) | **44 passed / 0 failed** |
| tsc --noEmit (container) | clean |
| parity fixture (FY 2024-25) | 300 scenarios green, re-pinned via the generator with citations |
| Live E2E (API, prod containers) | full loop green (below) |

## Wave 1 — statutory money math + conversation semantics (`9c9ff37`)

Tax-expert rulings (hand-verified):
- **87A rebate band cap applied PRE-cess** — the department's own method
  (TI 12,10,000 → 10,400 example). `band_cap_includes_cess=False` both FYs;
  marginal-relief cells re-pinned via `tests/tools/generate_parity_snapshot.py`
  with citations.
- **Sec 24(b) occupancy-aware**: let-out interest deducts against NET RENTAL
  in full in HP (loss set-off capped ₹2L, s.71(3A)); self-occupied capped ₹2L;
  the new regime (115BAC(2)(i)) bars only self-occupied — let-out allowed with
  no loss set-off. 19 parity cells re-pinned (all traced; old-regime tax
  byte-identical in every changed scenario).

Backend-review P0s (nlp_engine):
- Correction semantics rewritten: re-attribution undoes the booked head via
  `_last_cat`; corrections REPLACE, never accumulate; numberless corrections
  no longer 500 (last_val init + gate).
- Asked-cat prior: trailing-line slice + income-slot skip + ask-shape gate —
  closing tips no longer prime the prior.
- `/end` override clears `_last_question` (a report is not an ask).
- Zero-sentinel/walk double-consumption: one bare "no" used to book TWO
  discovery slots; the walk now yields to a sentinel-consumed turn.
- Monthly rent/HRA bare answers annualize; booked zeros count as answered.

Hardening (security review): GET throttling, chunked-body 411, non-dict-body
422 guards, registration KDF ordering, forwarded_allow_ips pin,
`DROPPED_STATE_KEYS += _last_cat`, CI permissions pinned, `.dockerignore`
keeps the credentials DB out of image layers.

## Wave 2 — QA / frontend / ML-eval reviews (`42d4df4`, `9e8d10f`)

QA-review P0s:
- **24(b) loss branch crashed both regimes** (`caps` NameError in `_calc_old`):
  any let-out with interest > 70% of rent 500'd `/calculate`. Fixed to
  `rules.deduction_caps.sec_24b` + 2 hand-computed pins (set-off cap; new-
  regime head floored at 0).
- **Cross-head correction misroute**: "oops salary is actually 700000" after
  an 80C booking booked 80D. Root causes BOTH fixed: (1) the profile
  classifier's bigram fuzzy pass matched "investment is" → "investment firm"
  (a deduction booking reclassified the user as Business Owner, nuclear-
  penalizing the named salary head), (2) the asked-cat prior boost outbid the
  penalized head. Function-word guard + `prior_gate=10.0` for corrections.

ML-eval P0:
- The intent artifact's "97.9% test accuracy" was the FULL-CORPUS score with
  the vectorizer fit on all records (leakage) — the same fabrication class as
  the NER 0.143. Now: vectorizer fit on the train split only, held-out
  metrics persisted. The BiLSTM experiment was dead code (sparse `.index`,
  `torch.from_long`, stale eval targets, padding-timestep read, bigram
  vocab) — revived and honest: **held-out TF-IDF 0.9619 / BiLSTM 0.9821** on
  the same 446-sample split; artifact regenerated in-container.

Extraction:
- Keyword boundary check is **per-occurrence** + a plural-suffix allowance
  that fixed 7 PRE-EXISTING failing eval cells (singular keyword vs plural
  text scored zero).
- **The extraction gate now BINDS** in the default run (pytest.ini flip plan
  fired): red = merge blocker.
- "I receive 400000 rent annually" booked RENT PAID → receive-cue remap to
  rental (period-word phrases over-triggered and were reverted). The plan
  layer was starved of the 24(b) let-out lever; the apply_plan test had been
  skipping EVERY run — now a let-out profile, no skip, **Plan A [24b] saves
  ₹31,200**.
- NER CLI epochs aligned to the pinned artifact (20); phase_i stale 75-sample
  config, fabricated 0.9641 fallback and NaN narrative fixed.

Frontend (frontend-engineer review):
- `planError` was never rendered (apply-plan 409/422/429 left the button
  dead) — per-plan error surface, cleared on success.
- `acted` state was written BEFORE the POST (a 404 rendered "recorded") —
  now only on `res.ok`, with distinct apply/decide error markers.
- Chat 429/404 status-specific copy + Retry-After honored; SavingsGraph FY
  label follows the session-pinned year.

Infra: the 411 short-circuit now carries the security-header set (same
contract as 413); chunked-body + non-dict-body pins added; the parity
generator carries forward update annotations (regeneration no longer destroys
provenance).

## Live E2E evidence (prod containers, post-rebuild)

register 201 → login 200 → session 200 → discovery walk (SALARY ₹24,00,000 →
80C ₹50,000 → **RENTAL ₹4,00,000 via the receive-cue remap** → 24B ₹1,00,000)
→ FINAL → `/end` → `/calculate`: New Regime + **Plan A [24b] saves 31,200** →
`apply_plan` applied [24b] → re-apply **409 "All plan headroom already
applied"** → reprice 200 → recommendation accepted → `/analytics/overview`
200 (acceptance_rate, accepted_rupees, per_head, resolved_events…).

GUI evidence: registration → chat with the live dual-regime pricing panel
(screenshots captured during the sweep; the browser automation loop degraded
mid-sweep and the remaining points were completed through the API — the same
endpoints the UI calls).

## Honest limitations

- The architect review was dispatched three times (two concurrency-limited
  aborts, third in background at the time of writing).
- The NER reproducibility caveat remains: torch is not version-pinned in the
  training container (ml-eval P2 — recorded, not yet fixed).
- The dataset-count pin (51,873 positives transcribed in registries/docs)
  still has no committed CI assertion (ml-eval P2 — recorded, not yet fixed).

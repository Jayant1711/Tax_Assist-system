# Sprint 4 — AI Modernization Plan (Objectives: extraction quality, trustworthy confidence, explainability)

> Planning document only — **no code in Sprint 3**. Drafted 2026-11-01 from the evidence base: [nlp-pipeline.md §11](docs/nlp-pipeline.md) (verified misclassification patterns), [decisions.md](docs/decisions.md) ADR-001/003/004, the Sprint 2 append-only blackbox/audit streams (`logs/blackbox/<sid>.jsonl`, `logs/audit/session_audit.jsonl`), and the Sprint 3 observability substrate (`backend/observability.py`, request-ID correlation). Scope guard: the deterministic tax engine is NOT a modernization target (ADR-001 stands); everything here touches the EXTRACTION and SCORING layers only.

## 0. Problem statement (evidence)

The NLP layer (ADR-003: hand-built parser + keyword-proximity attention + scripted waterfall) has hit its precision ceiling. The repo's own recorded sessions ([nlp-pipeline.md §11](docs/nlp-pipeline.md), re-verified against current code 2026-10-31) show systematic failures:

| Pattern | Evidence | Status |
|---|---|---|
| Tuition → salary (overwrite) | `sid_1776965272179` idx 200-201; still reproduces | Open — falls through to profile default, OVERWRITE rule destroys prior salary |
| PPF + health insurance → 80D ×2 | `sid_1776883718048` idx 66; still reproduces | Open — sentence-global negative-keyword penalty sinks 80C |
| Property sale → rental | `test_1776875973906` idx 15; reproduces mutated | Open — `"property sale"` missing from `capital_gains.pos` |
| Education-loan interest → income | idx 31 | Fixed by keyword addition; amount semantics still crude (loan principal booked as interest) |
| Freelance designer → Salaried | probe | Open — salaried-first fuzzy match order |
| "business owner and teacher" → Salaried | idx 109 | Open — exact-substring pass beats ownership signals |
| Double annualization (`80,000 per month` → 11,520,000) | verified | Open (C3) |

Two structural causes: (1) **unmatched categories fall through to the profile default** and overwrite existing values; (2) **sentence-global keyword scoring** cannot attribute an amount to its OWN noun phrase. Both are learnable — which is why Sprint 4 is a model-modernization sprint, run strictly inside the ADR-001/003 guardrails below.

**Binding constraints (do not re-litigate):**
- **ADR-001:** tax liability comes exclusively from the deterministic rule engine. No ML ever alters tax amounts. ML may only propose *inputs* (extraction) and *cosmetics* (efficiency score).
- **ADR-003:** no external API in the request path by default; free, fast, offline, deterministic. Any LLM involvement is opt-in, flagged, and evaluated (§3.3).
- **ADR-004:** the shipped ANFIS efficiency score is measured against the wrong ground truth (trainer math ≠ live engine math; refiner dimensionally incompatible). Retrain against the live engine or demote to "beta" (§3.4).

## 1. Dataset strategy

### 1.1 Sources

1. **Labeled utterance corpus from the blackbox JSONL.** Every chat turn is already appended to `logs/blackbox/<sid>.jsonl` with `user_input` (correlation-hashed), `nlp_extraction`, `agent_plan`, `state_snapshot`, and — since Wave D — `user_id`. The audited global stream (`logs/audit/session_audit.jsonl`) mirrors it. These are real utterances in the wild, including Hinglish and the exact failure patterns of §0. Labeling: replay each stored utterance through the CURRENT parser/attention, diff the extraction against the session state the human's subsequent turns confirm (a corrected value on a later turn is a free negative label for the earlier extraction).
2. **Synthetic augmentation with known-true extractions.** Templates over the production slot vocabulary (income heads × deduction sections × amount formats × word-number forms × monthly keywords × Hinglish variants), each rendered with a KNOWN-TRUE `(span, category, amount)` triple at generation time. This is how the tail (rare sections, multi-entity sentences like §0 row 3) gets coverage the organic logs can't provide. The Sprint-1/2 test tables (`test_suite.py` blocks 1-4) seed the template grammar — they are already hand-verified truths.
3. **The misclassification ledger.** Every §0 pattern (and future ones, filed the same way) becomes a golden case with the TRUE category — the tuition/PPF/property-sale sentences are the first hundred labels of the corpus.

### 1.2 Splits — template-based, leakage-aware

Because synthetic rows come from templates, a RANDOM split leaks (the same template in train and eval). Splits are **template-disjoint and utterance-disjoint**: each template family renders into exactly one split; organic utterances split by session id so the same speaker's paraphrases never straddle. Frozen split manifest (template ids + session ids, content-addressed) committed with the corpus so every eval run is comparable. Ratios: ~70 train / 15 eval / 15 holdout; the holdout is opened only for the §4 gate review.

### 1.3 DPDP Act 2023 constraints (hard)

- Raw free text is stored **only** under the explicit `TAX_AUDIT_STORE_TEXT` opt-in (default OFF: sha256[:16] correlation hash + char length, 512-char cap when opted in — `audit_logger.minimize_free_text`). A training corpus may therefore be built from **opt-in streams only**; hashes cannot be reversed into utterances, so the default-mode streams contribute structure (extraction correctness, state transitions) but not text.
- Every corpus artifact carries: opt-in provenance flag, collection window, and a deletion procedure (corpus version is rebuildable from the streams; deleting the source window + rebuilding honors erasure requests).
- Financial figures in `state_snapshot` are scrubbed of the internal keys (`history`/`memory`/`_last_*`) by the existing `scrub_state` writer — reuse, do not re-derive.
- No corpus leaves the deployment's own storage; no third-party annotation service without a separate DPDP review (out of scope for Sprint 4).

## 2. Model architecture proposal (in-paradigm order)

### 2.1 First: in-paradigm improvements (no new model)

Cheapest, zero-risk wins, shipped as normal regression fixes:

1. Fix the fall-through-to-default + OVERWRITE interaction (§0 cause 1): an utterance that does not CLEARLY name a category must ASK, never guess-and-overwrite — this is a waterfall policy change, not a model.
2. Add the missing keyword phrases the ledger shows (`"property sale"` → `capital_gains.pos`), and make negative-keyword penalties **phrase-scoped** instead of sentence-global (§0 cause 2, the PPF/80D mechanism).
3. Repair profession classification order (ownership signals checked before exact-substring; `"business owner"` added to signals).
4. Fix double annualization (C3) — parser-level `pm` detection must suppress the engine-level ×12.

Gate: the §4 golden corpus must pass BEFORE any model work merges, so model gains are measured against a fixed baseline, not a moving one.

### 2.2 Small local intent classifier as extractor, deterministic engine as guardrail

A compact text classifier (e.g. a bag-of-ngram linear model or a ≤30 MB distilled transformer running locally via ONNX/CPU) maps each **clause/span** to `(category, confidence)` — replacing keyword-proximity for CATEGORY RESOLUTION only:

- The parser (number formats, annualization) stays deterministic and authoritative — the model classifies WHAT a span means, never HOW MUCH.
- The discovery waterfall stays scripted (UX unchanged); the model only feeds it better `extracted` slots.
- **Guardrails (hard-coded):** deterministic post-validators — enum-strict CG types, section caps, the Sprint-1+2 session validator, and the rule that a low-confidence extraction triggers a question instead of a write. The engine's input schema (validated by `_validate_session_payload`) is the last line of defense; a model can only ever propose values that pass it.
- Deployed behind the existing process: same `nlp.process_message(message, state)` signature (Sprint 3 ADR-013 handler flow unchanged), zero API-wire changes.

### 2.3 LLM-assisted extraction — feature flag + eval suite (ADR-003 amendment, opt-in)

For the long tail (multi-entity sentences, ambiguous Hinglish), an LLM extractor may run as a SECOND OPINION, never as the primary path:

- **Flag:** `TAX_LLM_EXTRACT` (default off) + per-deployment allowlist; off-path is the §2.2 stack, byte-identical behavior.
- **Eval suite before any default flip:** the §1 corpus in CI — the LLM path must beat the local path on the holdout by a documented margin AND pass the DPDP review (utterances leaving the process boundary is a new data-flow; §1.3 applies with the opt-in constraint made explicit in the consent copy).
- Output contract: the LLM returns the same `(span, category, amount)` candidates with confidences; it NEVER writes state directly — same validators as §2.2.

### 2.4 ANFIS efficiency score — retrain against live-engine ground truth or retire to "beta"

ADR-004's divergence stands: the advertised R² was measured against trainer math that differs from `tax_engine.py` (HRA, surcharge bands). Sprint 4 decision, in order of preference:

1. **Retrain** `anfis_trainer.py` with ground truth generated BY the live engine (`TaxEngine.calculate_tax_advanced`) over the synthetic scenario grid; validate dimensionally (20×64); delete the dead `anfis_refine.py`; add a reshape-validation at weight load (today an incompatible file crashes at import).
2. If the retrained score still fails the §4 calibration bar, **retire the number to a labeled "beta" heuristic** (UI badge + docs) rather than ship a misleadingly precise figure.

Either way the score never feeds tax numbers (ADR-001).

## 3. Evaluation framework

- **Per-category precision/recall, ≥95% target on income heads** (salary, business, rental, other_income, agriculture, capital_gains) and the major deduction sections (80C, 80D, 80E, 80G, 80TTA/TTB, NPS, HRA, 24B, 80U/80DD, 80DDB). A category below target blocks release of the model that touched it (the §0 patterns are all precision failures).
- **Golden corpus as a CI eval set:** the §1 corpus (frozen manifest) runs in CI on every PR that touches `nlp_engine.py`/`ai_models.py`/extraction config — the same discipline the Sprint 2 parity + FY-matrix suites gave the ENGINE (exact-rupee regression protection), extended to the extraction layer. A red eval is a merge blocker, full stop.
- **Calibration curves:** reliability diagrams per category (predicted confidence vs observed accuracy) — required for §4's abstain threshold to mean anything; a model with 95% accuracy but bad calibration is WORSE for the abstain-and-ask loop than a weaker calibrated one.
- **Nightly audited-stream replay as drift detection:** the deployment's own audit/blackbox streams are replayed nightly through the current extractor; extraction-distribution shift (new phrase families, rising disagreement between old and new extractor on production traffic) is reported as a drift metric against the previous nightly. Spikes page a human review of new ledger entries (the §0 ledger is a living document).

## 4. Confidence scoring

- **Per-decision signals:** classifier margin (top-1 minus top-2 probability) and entropy over the category distribution; ensemble agreement when the LLM second opinion is enabled (§2.3) or when the keyword scorer and the model both fire (the keyword layer is retained as a cheap ensemble member, not deleted).
- **Abstain-and-ask below threshold:** when combined confidence < threshold, the waterfall ASKS a targeted question instead of writing the slot — this formalizes the fix for §0 cause 1 (fall-through-and-overwrite) as a policy the model serves, and it fits the existing discovery loop exactly (the waterfall already knows how to ask; it only needs to know WHEN).
- **Threshold fitted to the discovery loop, not picked by hand:** sweep the threshold on the eval split against the UX cost model — each false write costs a user correction turn (observable in the blackbox: a later turn overwriting the slot), each unnecessary question costs one extra turn. Choose the threshold minimizing expected total turns, then verify on the holdout.
- Confidence values are recorded in the blackbox `nlp_extraction` records (additive field) so calibration can be re-audited from production data — the same append-only, PII-minimized discipline as everything else in the streams.

## 5. Explainability

- **Span attribution:** every extraction names the SPAN that triggered it ("from '14 lakhs from property sale' → capital_gains"), stored in the blackbox record and rendered in the UI badge. This is the direct antidote to sentence-global scoring (§0 cause 2) — a model that cannot name its span does not ship.
- **Rule-ID traceability via the registry:** each extraction/deduction decision carries the identifier of the rule/model version that produced it (keyword-table entry id, model checkpoint hash, or LLM flag state), joinable against the tax-rule registry (`tax_rules/fy_*.py` + `REGISTRY`) so an auditor can walk from a filed number back to the exact rule text AND the exact extraction decision that fed it.
- **Per-entity "why" lines:** the report explains each line item in the user's language: "₹1,50,000 under 80C — you told us '1.5 lakhs in PPF' (span, confidence 0.97, rule 80C-cap-150000, clamped to ₹1,50,000)." Clamps and corrections (Sprint 2's write-time clamping) show the pre-clamp value and the rule that bounded it.

## 6. Sprint 4 execution plan

| Phase | Scope | Exit gate |
|---|---|---|
| P0 — Corpus + ledger freeze (wk 1) | Build §1 corpus (opt-in streams + synthetic + ledger), frozen template-disjoint splits, eval harness in CI; ship §2.1 in-paradigm fixes | Golden corpus green on current code (baseline pinned); ledger items 1-4 closed |
| P1 — Local extractor (wk 2-3) | §2.2 span classifier + guardrail validators + confidence recording; calibration suite | ≥95% P/R on income heads (eval split); no regression on golden corpus; deterministic validator tests (forged model output → rejected) |
| P2 — Abstain-and-ask (wk 4) | §4 threshold fitted on eval; waterfall integration; UI question flow | Expected-turns improvement on eval vs P1; abstain rate within budget; holdout unsealed + passed |
| P3 — ANFIS decision (wk 4-5) | §2.4 retrain vs live-engine ground truth (or beta demotion) | Calibration report; weights load with reshape validation; score docs updated |
| P4 — LLM second opinion (wk 6, optional) | §2.3 behind `TAX_LLM_EXTRACT`; DPDP review; eval suite extension | Holdout margin documented; DPDP sign-off; off-path byte-identical (flag-off test) |
| P5 — Drift + docs (wk 6) | Nightly replay job, drift metric, ledger process handoff | Two consecutive clean nightlies; runbook updated |

**Risks:** (1) corpus too small in tail categories → synthetic-only categories get a "synthetic-backed" marker and their thresholds are set conservative (§4); (2) model latency in the request path → budget is the current keyword scan's cost (single-digit ms), measured in CI perf check; (3) calibration drift in production → the §3 nightly replay IS the monitor; (4) scope creep into the engine — ADR-001 reviews every PR; anything that changes a tax number is rejected by definition; (5) DPDP exposure via opt-in text — §1.3 deletion procedure rehearsed before P0 exits.

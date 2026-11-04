# Sprint 4 Execution Spec — Intelligence & Conversation Quality

> Binding implementation spec, consolidated from the user's Sprint 4 brief + the 4-slice planning review + the AI Value Audit (which re-prioritized: Response Composer and deterministic metrics over model complexity). Branch `sprint-4-ai-modernization` @ merge `7f85305`. Baseline: 952 pytest + 22 Vitest + 7 Playwright + 97 legacy, all green.

## Goal
Conversations that are **intelligent, contextual, explainable and measurable**. NOT infrastructure, NOT deployment, NOT security architecture, NOT model complexity. Better tax assistance, not more AI.

## Hard invariants (every wave)
- ADR-001: TaxEngine is the only source of tax numbers; AI/extraction never alters amounts (parser-authoritative values only; documented derivations: ×12 annualization, 0..1e11 clamp, engine caps).
- 952 pytest + 22 Vitest + 7 Playwright + 97 legacy stay green; golden corpus additive-only; parity fixture untouched.
- Sprint 1-3 security controls intact (auth, ownership, validation, append-only audit, rate limits, headers).
- Every new behavior is measurable via the eval framework (P0) — no unmeasurable change ships.

## P0 — Data & measurement foundation
1. **Dataset layout** (`data/training|validation|test|corpus/*.jsonl` + `manifest.json`): record schema `{id, text, source: synthetic|ledger|organic, template_id|session_hash, lang, spans: [{text, category, amount, annualized}], provenance}`; template-disjoint + session-disjoint 70/15/15 splits; content-addressed manifest; leakage checker.
2. **Labeled corpus build** (`backend/tools/build_labeled_corpus.py`): ≥1,000 labeled utterances across the 21 categories (20 bookable + ABSTAIN). Sources, priority: (a) the §11 misclassification ledger with true labels, (b) synthetic templates with known-true spans — rendered from the test-suite utterance families + Hinglish + word-order variants ("shares sold"), multi-entity sentences, monthly forms, (c) golden-corpus conversations. Per-category floor ≥50; Hinglish families mandatory.
3. **Eval framework** (`backend/nlp_eval.py` + `tests/test_nlp_eval.py`): runs the extraction pipeline per record; per-category precision/recall/F1 (macro+micro), 21×21 confusion matrix, ≥95% gate on income heads + major deduction sections (advisory until P1 verdict), metric self-tests against hand-computed toy values (canary: a sabotaged predictor must FAIL the gate), no-leakage + coverage-floor meta-tests.
4. **Corpus quality metrics**: per-category counts, source distribution, template diversity, duplicate/near-duplicate detection.
5. **Funnel analytics** (`backend/funnel.py` + endpoint or tool): from `app_sessions` — sessions per phase, turns per phase, completion rate (FINAL+report), drop-off per phase; rendered as a report (JSON/markdown). Baseline recorded.
6. **Dataset Health Report** (`Dataset_Health_Report.md` generator in the same tool): counts, coverage, distribution, splits, leakage status.

## P1 — Deterministic extraction improvements (each red→green)
1. Mixed professions: "business owner and teacher" → Business Owner (ownership signals before salaried substring pass; add the literal signal).
2. "freelance designer" → Business Owner (fuzzy-order repair).
3. "shares sold"/"stocks sold" → capital_gains (noun-form pairs for the CG family).
4. Percentage handling: "40 percent disabled" → category, never an amount (extend the preparse guard).
5. Transfer-date handling: "sold in 2023"/"bought before 2024" phrasings → the CG tri-state flag.
6. Financial shorthand: "1.5L", "₹2cr", "12k/mo" robustness + new Hinglish families (kamaata, kiraya, mila, diya).
Gate: full suite green; eval P/R improves vs the P0 baseline (measured, reported).

## P2 — Response Composer (HIGHEST PRIORITY)
`backend/response_composer.py` — replaces `_generate_reply`'s canned strings. Deterministic, pure-Python, ADR-003 compliant.
1. **Data-aware**: every reply references booked specifics (amounts en-IN formatted, category names) and the session's remaining gaps. Example: "You've already invested ₹1.5 lakh in PPF, which fully uses your 80C limit. The next meaningful opportunity might be NPS."
2. **Context-aware**: references tax year (from registry), booked deductions, regime info, previously answered slots; never re-asks an answered slot.
3. **Advisory weaving**: 80G category guidance, CG election/holding-period notes, rebate-band position ("you're ₹25k above the ₹12L rebate band"), deduction headroom — woven into the reply that triggered them, not a wall of text.
4. **Phrasing variation**: pools (≥3 variants per question type), rotating selection (deterministic per session — no randomness in the request path; rotate by turn index).
5. **Explainability**: whenever the composer asks/recommends, it states WHY (which slot is empty, which limit binds, which rule applies — rule IDs from the registry).
6. **Clarification handling**: ambiguous input (abstain) → a natural clarifying question; never guesses.
7. **Confidence-aware messaging**: uncertain extractions surface "I'm not fully certain whether this refers to rental income or capital gains" style messaging.
8. **Composer tests** (`test_response_composer.py` + golden-response corpus): every composed reply asserted to reference booked specifics; variety across a session; no contradiction with state; determinism (same state+turn → same reply); the >95%-contextual metric measured on a reply sample.

## P3 — Conditional model evaluation (verdict, not deployment)
Run the P0 eval framework on the labeled corpus against the P1-improved deterministic pipeline:
- If income-head + major-section P/R ≥ 95% → **KEEP deterministic**; document the decision (ADR note: model not warranted at current data volume); revisit when organic corpus ≥5k turns.
- If < 95% → prototype the char-ngram classifier behind `TAX_NLP_EXTRACTOR` (default keyword; never replaces deterministic; comparison report required).
Output: KEEP/IMPROVE/REPLACE verdict per NLP component (parser, keyword resolver, clause segmentation, waterfall, composer), recorded in `NLP_Evaluation_Report.md`.

## P4 — ANFIS deprecation & replacement
- Remove the ANFIS score from the request path (`ai_models.ANFIS` → retired to `tools/` heritage or gated off); the efficiency score is replaced by **deterministic utilization metrics** computed from session state + registry caps:
  - `80C Usage: %` (used/150,000) · `80D Usage: %` · `NPS Opportunity: ₹X remaining` · `Deduction headroom` · `Potential tax savings: ₹X` (marginal-rate × headroom, from the verified registry rules).
- Every replacement metric is explainable (formula stated in the response), verifiable (unit tests to the rupee), deterministic.
- `anfis_weights.json` + trainer stay in-tree as heritage (documented), or move to `tools/` — the response payload's `efficiency_score` is replaced by the utilization block; frontend `TaxReport` updated (ANFIS tile → utilization panel).

## P5 — LLM preparation (planning only)
`LLM_INTEGRATION_PLAN.md`: the pipeline `User → Extractor → TaxEngine → Response Composer → [Optional LLM Polisher] → Response`; TaxEngine remains the source of truth. Cover: output validation (LLM text may rephrase, never restate numbers differently than the engine), DPDP compliance (no PII to external APIs without consent; local-model option), audit trail (polish events logged), fallback path (composer output ships if the LLM fails/times out), deterministic override. NO implementation.

## Completion artifacts
`Sprint4_RELEASE_NOTES.md` · `AI_Value_Report.md` · `Dataset_Health_Report.md` · `NLP_Evaluation_Report.md` · CHANGELOG v0.5.0-sprint4 · independent audit · scores (incl. **Intelligence**) · PR to main · release v0.5-sprint4.

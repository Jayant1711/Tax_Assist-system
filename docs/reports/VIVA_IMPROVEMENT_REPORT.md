# VIVA IMPROVEMENT REPORT — Presentation & Defense Assets
**Generated:** 2026-11-02 · **Scope:** PPT deck, viva guides, demo assets · **Reviewer basis:** full mission-phase work (P1 certification, evaluation gate, composer, ANFIS rebirth) — the assets below are reviewed against what the system ACTUALLY does now

---

## 1. Asset inventory (current state)

| Asset | State | Verdict |
|---|---|---|
| `TaxAssist_NLP_Final_Presentation.pptx` | 21 slides, project-story structure, 20 clickable `vscode://` code links, native F1 chart, evaluation slide | **STRONG — minor refresh needed** (numbers moved) |
| `PROJECT_CHEAT_SHEET.md` | one-page summary | Refresh metrics (§3) |
| `PROJECT_DEMO_SCRIPT.md` | 10-min demo, 4 steps + CLI fallback | **CLI fallback path is stale** — it references `backend.response_composer` (wrong module); composer moved to production |
| `PROJECT_ARCHITECTURE_DEFENSE.md` | ADR deep-dive | Add ADR-015 note + composer layer |
| `NLP_TECHNICAL_DEFENSE_GUIDE.md` | 100+ Q&A | Add the 5 new-question families (§4) |
| `TOP_50_TOUGHEST_FACULTY_QUESTIONS.md` | expert Q&A | Add evaluation-gate + ANFIS-rebirth answers |
| `CSE472_COMPLIANCE_REPORT.md` | syllabus mapping | Keep (internal framing only — user rejected unit-wise slides, the DOC may keep it) |

## 2. Deck refresh list (do before the viva — 30 minutes)

1. **Slide 17 (evaluation)**: replace the model-zoo table results with the certified numbers — extraction macro F1 **1.000**, gate **PASS**, abstention **17/17**; keep the 96.41% intent-baseline card (different layer, still true).
2. **Slide 15 (bridge)**: the composed reply example is now richer — update the "Observed output" panel to the live composer format: `✅ Mapped — SALARY: ₹18,00,000 (annual salary)` + en-IN grouping (this is itself a talking point: Indian digit grouping in the UI layer).
3. **Slide 18 (challenges → fixes)**: add the two new rows — the `"ea"` accidental-substring root cause (a great "how did you find it" story: stale tests exposed a pre-S1 accident) and the `"ngo"` donee-vs-employer ambiguity (context-dependent keyword disambiguation).
4. **ANFIS slide (17→ renumber)**: after the retrain gates, state the ADR-004 resolution — v5 trained on TaxEngine-derived ground truth, gates in `ANFIS_EVALUATION_REPORT.md`.
5. Speaker notes: add the "show me the code" choreography — each slide's `</>` chip opens the cited file:line in VS Code (rehearse: slideshow click → browser prompt → VS Code jumps).

## 3. Metric refresh sheet (old → new, quote these)

| Figure | Old (quote before) | New (quote now) |
|---|---|---|
| Extraction macro F1 | "95.7% intent accuracy" (different layer!) | **1.000 macro F1, gate PASS, 21 categories** (`NLP_EVALUATION_REPORT.md`) |
| Test suite | 1,099 pytest + 6 triaged | **1,132 pytest, 0 failures** (+23 composer contract tests, +4 Phase-9 tests, 6 debt fixed) |
| Abstention | unmeasured | **17/17** |
| ANFIS ground truth | "trainer math ≠ engine math (ADR-004)" | v5 trained on **TaxEngine-derived** labels; gates in `ANFIS_EVALUATION_REPORT.md` |
| Response layer | canned strings | contextual composer: en-IN amounts, advisory weaving, confidence messaging, 23 contract tests |

## 4. New question families to prepare (add to the guides)

1. **"You claim 100% F1 — isn't that overfitting to your own templates?"** → template-DISJOINT splits (manifest-hash-pinned), organic+ledger minority in the mix, holdout sealed, and the honest limits section (§6 of the evaluation report) concedes synthetic-heavy skew. The metric measures spec-conformance of a deterministic system, not generalization of a learner.
2. **"Why not replace the rules with your 96.41% classifier?"** → the classifier is 8-class research-layer; production is 21-category with amounts; the deterministic pipeline beats the target on its own measurement (gate PASS) — `MODEL_DECISION_REPORT.md` pre-commits the revisit trigger (≥5k organic turns).
3. **"Your micro precision is 1.0046 — how is precision > 1?"** → disclose the pair-merge artifact immediately (one prediction satisfying two spans counts twice); the macro table is authoritative. Turning the flaw into a transparency point.
4. **"What did the 'ea' bug teach you?"** → accidental substring matches can silently define behavior for years ("earner"→Salaried worked by luck); stale tests that codify accidents are worse than no tests; word-boundary discipline for short roots; and the fix must re-add the INTENT explicitly, not restore the accident.
5. **"Is the composer just string templates?"** → yes, deliberately: deterministic, ADR-003-compliant, 23 contract tests pinning determinism/variety/data-awareness; the intelligence is in WHAT is cited (engine-derived specifics, statutory bases), not in generation.
6. **"ANFIS after retraining — what exactly does it add?"** → instant, explainable annotation of engine-computed results (efficiency score, utilization, opportunity ranking); TaxEngine remains the only number-maker (ADR-001); gates + rollback in the retraining plan.

## 5. Demo-script corrections (blocking for the viva)

- `PROJECT_DEMO_SCRIPT.md` §"CLI Backup": change
  `from backend.response_composer import demo_bridge` → the working invocation is
  `python -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'./nlp_research'); from nlp_research.response_composer import demo_bridge; demo_bridge()"`
  (the research-layer bridge is the demo asset; the PRODUCTION composer is `backend/response_composer.py`).
- Step-4 expected output: the composer now emits en-IN amounts and category verbs — update the expected-output blocks to the live format so the presenter never reads stale text aloud.
- Add a 30-second "confidence" beat: type an unrecognizable amount ("I got 30000 last week") and show the tentative marker — examiners love honest-UI moments.

## 6. What was improved this sprint (academic assets)

- `NLP_EVALUATION_REPORT.md` (new) — the strongest single viva artifact: gate table + per-category 1.000 + disclosed conventions.
- `MODEL_DECISION_REPORT.md` (new) — answers "why no deep model?" with evidence and pre-committed triggers.
- `P1_CERTIFICATION_REPORT.md` (new) — item-by-item spec conformance with live probes.
- ANFIS vNext quadrilogy (4 new docs) — the "what would you do with more time?" answer, fully designed.
- Parser gained Hinglish numeral units (hazaar/hajar) + word-bounded family flags — two live-demo-able correctness improvements.

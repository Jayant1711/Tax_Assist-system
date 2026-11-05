# SPRINT4_RETROSPECTIVE.md — Phase 4 Sprint Closure Retrospective
**Generated:** 2026-11-04 · **Scope:** the full Sprint 4 arc (planning → P0 → P1 → certification → composer/transparency waves → v5 forensics/completion → closure)

---

## What worked

1. **Gate + rollback discipline.** The TSK learned heads failed G4/G5 twice — and both times the rollback ladder held, nothing bad shipped, and the failure produced evidence instead of damage. The final rule-head deployment passes *by construction* because the forensics identified what the labels actually are.
2. **Measurement before modeling.** P0's eval framework + corpus turned "the NLP layer hit its ceiling" from an opinion into a falsifiable claim — and falsified it (macro F1 1.000, gate PASS). The ADR-015 decision cites measured numbers.
3. **The forensics pass.** Six small experiments (F0–F5) resolved in one afternoon what weeks of modeling would not have: the opportunity label is exactly the regime verdict; the savings label is exactly linear in the paid ratios; rule dilution is measurable. "Measure the label structure before choosing the model" is the sprint's biggest transferable lesson.
4. **Multi-agent specialization.** The architect/qa/security/ml-eval/frontend/data-engineer passes each caught distinct real defects (scoring-order bug, amplification vectors, the double-counted statement row, the "ea"/lakh-stem/NGO accidents) that the primary loop had normalized around.
5. **Honest-findings culture.** NER 0.143, the TSK gate failures, and the eval-CLI display bug were documented, not hidden — and each became either a roadmap item or a viva answer.

## What failed

1. **EE-BAT at bounded budget** — all-parameter evolutionary search never converged (MAE 11.09 at cut-off). Fixed architecturally: closed-form ridge LSE for consequents.
2. **Product-combination rule bases on sparse 20-D spaces** — firing underflow + dilution (AUC 1.0 → 0.30 as rules grow). Fixed: additive combination.
3. **Deterministic grids saturate** — rounds 3→4 added zero scenarios (periodic combos). Fixed conceptually: continuous-value sampling is the P0 dataset action.
4. **Process near-misses**: two heredoc batch-edits failed on whitespace (atomicity saved us), one freeze report shipped pre-transparency-commit (superseded in-run), test counts drifted across four reports (caught by the consistency audit).
5. **The v1 scenario grid's blind spot**: no HRA legs, no CG, no old-regime-optimal corner — the reason positives were 0.31%. Fixed with expansion strata; the structural lesson is to derive strata from the label structure, not convenience.

## Biggest bugs found (and fixed)

| Bug | Impact | Root cause |
|---|---|---|
| The `"ea"` profession accident | "earner"/"earn" classified Salaried *by luck* since before Sprint 1 — stale tests codified it | ≤3-char roots substring-matched without word boundaries |
| Lakh stem `l(?!e)` | "30000 last month" → **₹3 billion** | the stem matched the "l" of "last" |
| `"ngo"` donee vs employer | donation sentences classified the user Salaried; second-clause amounts fell to salary default | employer root matched inside a donation context |
| `"maa"` in "main" | false `has_parents` flag | same short-substring class |
| Reply amplification (5 vectors) | 28–64KB replies from 2KB inputs; session-brick risk | per-match notes without per-message caps |
| TaxEngine scoring order | feature 17 always 0 in the served path | score computed before savings binding |
| Eval conventions | flat-amount/zero-sentinel/bucket-merge mismatches made correct behavior look like failures | evaluator predated the spec |

## Biggest architecture improvements

1. **Engine-first intelligence** (ADR-016): the layer annotates engine output with exact rules; nothing model-generated touches a rupee.
2. **Single-source features** (`features_v2`): train/serve divergence is now structurally impossible for the intelligence inputs.
3. **msg_ctx per-message guards**: every note/ask-back class is deduped and capped.
4. **Registry system**: dataset/model/training/experiment lineage is answerable without repo archaeology.
5. **The transparency panel**: the user sees the computation's reasoning, not just totals.

## Lessons learned

- Stale tests that codify accidents are worse than no tests — they weaponize luck.
- When a learned model fails gates on a target that is an exact function of the inputs, the fix is exact rules, not more training.
- Provenance drift (146 vs 415 vs 1,623 positives) is inevitable in fast iterations — registries + re-measurement are the antidote.
- One-click profiles (the UI's "⚡ 1-Click SDE ₹24L") are the fastest manual test path — use them for validation, not just UX.

## ANFIS findings (the honest record)

v4: wrong ground truth (ADR-004), served r² 0.4976. v5 program: composite serving exact (MAE 0.136); TSK heads failed G4/G5 twice for measured reasons (optimizer budget, rule dilution, positive scarcity); **the exact rule heads are the deployed answer** — P/R 1.0/1.0, MAE 0.00. The TSK program continues off-deployment with pre-committed promotion gates (continuous-value sampler, ≥5k positives).

## Transparency findings

Backend exonerated hop-by-hop (the ₹46L trace). The gap was narrative: the frontend showed numbers without the regime-vs-deductions story. Now: the Applied-vs-Ignored panel, the 115BAC reasons, the cap callouts, and the intelligence block — all engine-priced, all test-pinned.

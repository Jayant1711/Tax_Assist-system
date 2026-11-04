# TRACEABILITY_AUDIT.md — Phase 3 Registry Traceability Audit

**Auditor:** data-engineer (Phase 3 traceability audit)
**Repo:** Tax_Assist-system-main · branch `sprint-4-ai-modernization` @ `7ca0cfe`
**Date:** 2026-11-04 · **Scope:** DATASET_REGISTRY.md, MODEL_REGISTRY.md, TRAINING_REGISTRY.md, EXPERIMENT_REGISTRY.md
**Method:** every registry entry checked against the working tree — npz shapes loaded with numpy, jsonl line/positive counts, manifest fields, code greps (class/function line numbers, call sites), report cross-references, and live re-runs (`run_eval.py`, `TestADRBoundary`, corpus rebuild test, full backend pytest).

**Status legend:** VERIFIED = measured value matches the registry · MISMATCH = registry value vs actual differs (documentation drift) · MISSING = referenced artifact absent.

---

## 1. DATASET_REGISTRY.md

| Entry | Claim | Actual (measured) | Status |
|---|---|---|---|
| **corpus-v1** — location | `data/{training,validation,test}/*.jsonl` + `data/manifest.json` | all 8 jsonl files + `data/manifest.json` present | VERIFIED |
| corpus-v1 — version | manifest `manifest_version: 1`, build seed 40 | `manifest_version: 1`, `build.seed: 40`, builder `backend/tools/build_labeled_corpus.py`, built 2026-11-01 | VERIFIED |
| corpus-v1 — samples | 2,226 records / 2,255 spans / 197 template families | 2,226 records (2,226 unique ids) / 2,255 spans / 99+69+29 = **197** template families | VERIFIED |
| corpus-v1 — labels | "21 production categories + ABSTAIN" | **20 production categories + ABSTAIN** (= 21 label classes total, incl. ABSTAIN); span-category census: 20 production + ABSTAIN (54) | **MISMATCH (F1)** |
| corpus-v1 — splits | 70/15/15 = 1,537 / 434 / 255, sha256 per split | wc -l: 1,537 / 434 / 255 (= 2,226); manifest carries sha256 for all three splits | VERIFIED |
| corpus-v1 — reproducibility | rebuild pinned by `tests/test_nlp_eval.py::TestCommittedDatasetMeta::test_rebuild_reproduces_the_committed_manifest` | test exists (test_nlp_eval.py:294/319) and **PASSES** (1 passed in 0.54 s) | VERIFIED |
| corpus-v1 — generation | `backend/tools/build_labeled_corpus.py` (P0, commit `a5691dc`) | file exists; commit `a5691dc` ("S4-P0: data & measurement foundation") touched it | VERIFIED |
| corpus-v1 — sources | synthetic \| ledger \| organic | census: synthetic 2,202 / ledger 17 / organic 7 | VERIFIED |
| capture stream | `data/corpus/*.jsonl` empty | directory exists, 0 files | VERIFIED |
| **anfis-v1** — features.npz | X (B,20) float32 + y_eff, y_top, scenario_id; 5,964 scenarios | keys {X, y_eff, y_top, scenario_id}; **X (5964, 20) float32**, y_eff/y_top/scenario_id (5964,) | VERIFIED |
| anfis-v1 — savings.npz | X (B,23 = 20+delta_norm+head_idx+f21), y_sav, y_opp; 76,960 rows | **X (76960, 23) float32**, y_sav (76960,), y_opp (76960,) | VERIFIED |
| anfis-v1 — jsonl counts | 53,676 utilization · 76,960 optimization (1,623 positive = 2.11%) · 76,960 recommendation | wc -l: 53,676 / 76,960 / 76,960; positives (savings_engine>0): **1,623 = 2.11%**; optimization rows embed the full `session` object | VERIFIED |
| anfis-v1 — schema | anfis-feature-schema/**2.1** | `train_anfis_v5.py:60` → `SCHEMA = "anfis-feature-schema/3"`; `v5_metrics.json fit.schema` = "anfis-feature-schema/3" (same content: +f21, 23-dim savings) | **MISMATCH (F2)** |
| anfis-v1 — splits | every-7th-row validation | 5,964/7 = 852 = `val_rows.eff`; 76,960 → `val_rows.sav` 10,995 | VERIFIED |
| anfis-v1 — generation | `backend/tools/generate_anfis_dataset.py`, f21 (EXP-F2) | file exists; f21_old_tax_ratio emitted (lines 266–304) | VERIFIED |
| anfis-v1 — versioning | (not stated) | **`data/anfis_v1/` is gitignored (`.gitignore:34`)** — npz/jsonl/v5_metrics.json are NOT in version control; no sha256 pinned for the current frozen set | **MISMATCH (F3, undisclosed)** |
| **ner-templates-v1** | in-process by `nlp_research/phase_d_ner.py`, 51 samples, NER 0.143 documented | phase_d_ner.py exists; `nlp_research/artifacts/NER_REPORT.md:25` "Overall accuracy: 0.143" | VERIFIED |

## 2. MODEL_REGISTRY.md

| Entry | Claim | Actual (measured) | Status |
|---|---|---|---|
| **anfis-v4** — code | `backend/ai_models.py::ANFIS` + `score_efficiency` | class ANFIS at ai_models.py:617; score_efficiency at :663 | VERIFIED |
| anfis-v4 — params | 3,904 = means 1,280 + sigmas 1,280 + consequents 1,344 | N_INPUTS=20, N_RULES=64 → 20·64=1,280 + 1,280 + 64·21=1,344 = 3,904; `anfis_weights.json` `params` length 3,904 | VERIFIED |
| anfis-v4 — weights | `backend/anfis_weights.json` (v4, untouched by v5 program) | exists; last commit touching it **`fdb6ed9` 2026-10-31** (pre-v5-program); 0 commits since 2026-11-02 | VERIFIED |
| anfis-v4 — LIVE | production score in results view | served via `backend/tax_engine.py:236` (`self.anfis = ANFIS()`); stored metrics r² 0.4976 matches RUN-001's 0.4976 | VERIFIED |
| **anfis-v5 (efficiency)** | composite `TaxIntelligence.composite_efficiency`, formula 30 + 68.5·Σwᵢuᵢ, MAE 0.136 (RUN-003b), LIVE | composite_efficiency at tax_intelligence.py:249; formula at :546 (`30.0 + 68.5 * sum(weights[n] * x[i])`); metrics file `eff_mae_points` = **0.1363** (row already carries the "0.053 was the pilot" correction) | VERIFIED |
| **anfis-v5 (learned TSK)** | `fit`/`model_efficiency`, 20×48 additive, 1,008 LSE + 960 MF; "learned MAE 12.772 vs composite 0.053" | fit:144, model_efficiency:280; additive `_membership` (`mf.sum(axis=2)`, :78); 48·21=1,008 + 20·48=960 ✓ arithmetic. Metrics claim: current `learned_eff_mae_experiment` = **15.6751** (RUN-003b); 12.772 is the RUN-003-era value (preserved at ANFIS_ROOT_CAUSE_REPORT.md:148) presented unlabeled-historical | **MISMATCH (F4, stale metric)** |
| anfis-v5 savings head | `predict_savings`, 23×48, EXPERIMENT — not deployed | predict_savings at :285; candidate NOT written: no v5 weights file in `backend/` (only anfis_weights.json) → `get_intelligence()` degrades to None | VERIFIED |
| anfis-v5 opportunity head | `predict_opportunity`, EXPERIMENT — not deployed | predict_opportunity at :291; TSK heads called from **nowhere** in the serve path | VERIFIED |
| TSK heads not called from main.py | (deployment-status claim) | `grep` of backend/main.py for predict_savings/model_efficiency/predict_opportunity/composite_efficiency/ANFIS: **zero matches** (main.py:116 only imports NLPEngine) | VERIFIED |
| **rule-heads-v5** | `rule_opportunity/rule_savings/rule_confidence` + `recommend()`; LIVE in v0.5; P 1.000 / R 1.000 / savings MAE 0.00 | rule_opportunity:647, rule_savings:653, rule_confidence:658; recommend():408. Note: recommend() **inlines** the rule logic (confidence 0.85/0.30, savings_engine as estimate, opportunity ⟺ savings_engine>0) rather than calling the three functions — behavior equivalent, names not invoked. `v5_metrics.json rule_heads` = precision 1.0 / recall 1.0 / savings_mae_inr 0.0 / pass true. Serve path: `nlp_engine.py:1141` → `advisor_block` | VERIFIED (nuance F5) |
| **tfidf-intent-v1** | phase_c_intent_classification.py; 96.41% research artifact | file exists; 96.41% documented (NLP_EVALUATION_REPORT.md:59, docs/decisions.md:197) | VERIFIED |
| **bilstm-ner-v1** | phase_d_ner.py; 0.143 | file exists; NER_REPORT.md:25 | VERIFIED |
| **seq2seq-attn-v1** | phase_e_seq2seq.py | exists | VERIFIED |
| **bert-base-uncased** | phase_f_bert_classification.py; TF-IDF fallback 96.41% | exists; figure documented | VERIFIED |
| **gpt2 / t5-small** | phase_g_generative.py | exists | VERIFIED |

## 3. TRAINING_REGISTRY.md

| Entry | Claim | Actual (measured) | Status |
|---|---|---|---|
| **RUN-001** | `anfis_trainer.generate_dataset` 200k–1M rows; EE-BAT pop 30, batch 4,096, 500 iters; r² 0.4976 | anfis_trainer.py: `generate_dataset(n=1_000_000, seed=42)` (:43), `pop = ... (30, PARAM_DIM)` (:156), `BATCH = 4096` (:16), `train(..., iters=500)` (:154); weight-file metrics r² = 0.49759 | VERIFIED |
| **RUN-002** | 1,512 scenarios, EE-BAT 300 iters, G1 FAIL MAE 11.09; report ANFIS_EVALUATION_REPORT.md §3 | report header: "EE-BAT, 300 iters … 1,512 TaxEngine-priced scenarios"; table: "G1 … **11.094 points** ❌ FAIL" | VERIFIED |
| **RUN-003** | 3,528 scenarios / 46,816 rows; G1 0.053, G2 −0.013, learned 12.772, 146 positives; Metrics file `data/anfis_v1/v5_metrics.json` | dataset regenerated since (not re-measurable); numbers preserved in ANFIS_ROOT_CAUSE_REPORT.md:148 (12.772) and FINAL_TECHNICAL_AUDIT D2. But the cited metrics file was **overwritten by RUN-003b** (now holds 0.1363/15.6751) and is git-untracked, so RUN-003's own numbers are not recoverable from it or from git history | **MISMATCH (F6, stale pointer)** |
| **RUN-003b** — data | 5,964 scenarios / 76,960 rows / 1,623 positives (2.11%) / f21 | matches npz shapes and jsonl counts exactly (see §1) | VERIFIED |
| RUN-003b — G1 | 0.136 PASS | `eff_mae_points` 0.1363 | VERIFIED |
| RUN-003b — G2 | −0.112 PASS | `eff_calibration_points` −0.1118 | VERIFIED |
| RUN-003b — G3 | 100% PASS | `eff_intra_class_consistency` 1.0 | VERIFIED |
| RUN-003b — G6 | **95.72% PASS** | metrics file `ranking_top1` = **0.5704 (57.04%)** — FAIL vs ≥80% gate; 95.72% is "on the previous run's protocol (engine-ordered)" per ANFIS_V5_EVALUATION_V2.md:19, which itself prints 57.04% as the current-protocol value | **MISMATCH (F7)** |
| RUN-003b — TSK G4/G5 | MAPE 795% / P 0, R 0 FAIL | `savings_mape_material` 7.9469 (= 794.7% ≈ 795%); opportunity_precision/recall 0.0 | VERIFIED |
| RUN-003b — rule heads | P 1.000 / R 1.000 / savings MAE 0.00 | `rule_heads` block: 1.0 / 1.0 / 0.0, pass true | VERIFIED |
| RUN-003b — wall time | 65.5 s | `wall_seconds` **69.8** | **MISMATCH (F8)** |
| RUN-003b — seed | 472 | `seed` 472 | VERIFIED |
| **RUN-004** | training split 1,537; 96.41%; ADR-015 records it | 1,537 verified (split count); 96.41% in NLP_EVALUATION_REPORT.md:59 + docs/decisions.md:197 | VERIFIED |
| **RUN-005** | 51 samples; 0.143 | NER_REPORT.md:25 "Overall accuracy: 0.143" | VERIFIED |

## 4. EXPERIMENT_REGISTRY.md

| Entry | Claim | Actual (measured) | Status |
|---|---|---|---|
| **EXP-001** | `tools/run_eval.py`; eval split 434; macro F1 1.000, gate PASS, abstention 17/17, 0 errors | `backend/tools/run_eval.py` exists; re-ran: "**GATE (>= 0.95): PASS**", perfect diagonal confusion matrix, ABSTAIN 17/17, 434 validation records | VERIFIED |
| **EXP-002** | 1,134 pytest across backend, all green; P1_CERTIFICATION_REPORT.md | re-ran full suite: **1,146 passed, 1 deselected in 49.63 s** (suite grew from the P1-era 1,134; report exists at repo root) | VERIFIED (count moved 1,134 → 1,146, all green) |
| **EXP-003** | RUN-002: MAE 11.09, still descending | see RUN-002 (11.094) | VERIFIED |
| **EXP-004** | RUN-003: composite MAE 0.053, 146 positives | pilot-era figures preserved in later reports (root-cause report, FINAL_TECHNICAL_AUDIT D2); same stale-pointer caveat as F6 | VERIFIED-WITH-CAVEAT |
| **EXP-005** | composite closed form; G1 39.9 → 0.053 | composite formula verified in code (tax_intelligence.py:546); 0.053 documented | VERIFIED |
| **EXP-006** | `_membership` sum vs product; additive adopted | tax_intelligence.py:74–78 — `mf.sum(axis=2)` with the Jang-1993/product-underflow comment | VERIFIED |
| **EXP-007** | 25 contract tests incl. identical-replay; `test_response_composer.py` | file exists; identical-replay test present (:83 `test_engine_replies_stable_across_identical_replays`); pytest collects **23** tests, not 25 | **MISMATCH (F9, count 25 → 23)** |
| **EXP-008** | `tests/test_tax_intelligence.py::TestADRBoundary` | re-ran: **2 passed in 3.16 s** | VERIFIED |
| **EXP-009** | 146 positives era: 292 balanced < 1,104 params | documented in ANFIS_ROOT_CAUSE_REPORT.md RC-1 | VERIFIED |
| **EXP-010** | APPROVE-WITH-NITS; amplification 36.6KB→<1KB | PROJECT_STATUS_REPORT.md:30,54 documents both | VERIFIED |
| **EXP-011** | ml-evaluation-engineer, 6 experiments F0–F5 + stratum pilot, seeds 472/473/474; y_opp ⟺ regime_signal==0 zero exceptions; savings MAPE 1.6e-14; AUC 1.0→0.30; u80g 1,564 rows; positives 1,280 vs 1,104; report ANFIS_ROOT_CAUSE_REPORT.md | report exists; all cited figures found in it (lines 14–22, 43, 46, 52–55). Independently re-verified the equivalence on the CURRENT dataset: regime_signal==0 ⟺ y_opp=1 with **0 exceptions on all 76,960 rows**. Caveat: the six forensics scripts/outputs live in a temp dir outside the repo (`C:\Users\lenovo\AppData\Local\Temp\anfis_forensics\`, `out\*.json|png`) — no `exp_f*.py`/`stratum_pilot.py` committed | VERIFIED (reproducibility caveat F10) |
| **EXP-012** | rounds 1–4: 3,528→5,964 scenarios; positives 415→1,623; G6 54.9%→**95.72%** | scenario/positive counts match current dataset; the G6 95.72% endpoint is previous-protocol (same finding as F7: current-protocol TSK G6 = 57.04%) | **MISMATCH (F7, shared)** |
| **EXP-013** | rule heads on 10,995 val rows: P 1.000 / R 1.000 / MAE 0.00; gate lines in `tools/train_anfis_v5.py` | val_rows.sav = 10,995; train_anfis_v5.py:150–153 prints "RULE HEADS: P=… R=… savings MAE=… (exact by construction)", :179–183 persists them, :200–203 prints "DEPLOYMENT PATH: exact rule heads PASS"; metrics agree | VERIFIED |

---

## Findings (documentation drift) and exact corrections

- **F1 — DATASET_REGISTRY corpus-v1 labels.** Says "21 production categories + ABSTAIN". Actual span-category census: **20 production categories + ABSTAIN** (21 label classes including ABSTAIN; cf. docs/decisions.md:197 "all 21 categories" = including ABSTAIN). Correction: change to "20 production categories + ABSTAIN (21 classes total)".
- **F2 — DATASET_REGISTRY anfis-v1 version.** Says "anfis-feature-schema/**2.1**"; code and metrics both say **anfis-feature-schema/3** (`backend/tools/train_anfis_v5.py:60`, `v5_metrics.json fit.schema`), same content (+f21, 23-dim savings). Correction: registry version → "anfis-feature-schema/3 (f21 old-tax ratio, 23-dim savings)".
- **F3 — anfis-v1 artifacts are not version-controlled.** `.gitignore:34` excludes `data/anfis_v1/`; the registry's "where/which version" answer is incomplete because the frozen 5,964×20 / 76,960×23 artifacts exist only locally and no sha256 is recorded for them (the root-cause report pinned only the older 5,502-scenario snapshot). Correction: add a provenance note to DATASET_REGISTRY (gitignored, regenerable via `backend/tools/generate_anfis_dataset.py` seed 472) and pin the current set's sha256.
- **F4 — MODEL_REGISTRY row "anfis-v5 (learned TSK)".** "learned MAE 12.772 vs composite 0.053" is RUN-003-era; current generation measures 15.6751 / 0.1363 (`v5_metrics.json`). The efficiency row was already fixed; this row was not. Correction: label 12.772/0.053 as RUN-003 pilot figures or update to 15.6751 with a historical note (FINAL_TECHNICAL_AUDIT D2 flagged exactly this).
- **F5 — rule-heads-v5 wiring nuance (VERIFIED, note only).** `recommend()` implements the exact rules inline (confidence 0.85/0.30, `estimated_savings = savings_engine`, opportunity ⟺ savings_engine>0) but does not call the named `rule_opportunity/rule_savings/rule_confidence` functions; the functions have **zero call sites** repo-wide. Correction (optional): have `recommend()` call the named functions so the registry's code pointer is literal.
- **F6 — TRAINING_REGISTRY RUN-003 metrics pointer.** Points at `data/anfis_v1/v5_metrics.json`, which now holds RUN-003b results and is untracked (no git history). Correction: point RUN-003's evidence at `ANFIS_ROOT_CAUSE_REPORT.md:148` (or a restored RUN-003-era report) instead of the overwritten live file.
- **F7 — G6 "95.72% PASS" (RUN-003b, EXP-012).** The measured TSK ranking top-1 on the final dataset is **57.04%** (`v5_metrics.json ranking_top1 0.5704`), below the ≥80% gate; ANFIS_V5_EVALUATION_V2.md:19 discloses that 95.72% is "on the previous run's protocol (engine-ordered)". The registries cite 95.72% as a PASS without the protocol caveat. Correction: state "G6 (TSK) 57.04% FAIL on the current protocol; 95.72% on the previous engine-ordered protocol — deployment carried by exact rule heads (G6 n/a)".
- **F8 — RUN-003b wall time.** Registry says 65.5 s; `v5_metrics.json wall_seconds` = **69.8**. Correction: 65.5 → 69.8 (or "65.5–69.8 across runs").
- **F9 — EXP-007 test count.** Claims 25 contract tests; pytest collects **23** (`tests/test_response_composer.py`). Correction: 25 → 23 (or restore the two removed tests).
- **F10 — EXP-011 forensics reproducibility.** The six experiment scripts and outputs live outside the repo (temp dir per report line 6); `find` finds no `exp_f*.py`/`stratum_pilot.py` committed. Correction: commit the forensics scripts + `out/` JSON outputs (or a regenerated copy) so the measured evidence is reproducible.

## What was NOT found

No MISSING entries: every file, report, test, tool, class, and function cited by the four registries exists at the stated path. All quantitative dataset claims (shapes, row counts, positives, split sizes, manifest fields) reproduce exactly. Both runnable gates re-pass today (`GATE (>= 0.95): PASS`; `TestADRBoundary` 2 passed; full suite 1,146 passed / 1 deselected; corpus rebuild-repro test passed).

## Verdict

**TRACEABLE-WITH-DRIFT** — every registry entry maps to a real artifact and every re-runnable claim re-passes, but 10 documentation-drift findings (F1–F10) need the exact corrections listed above. None of them changes a deployment decision: the only gate-status discrepancy (F7) concerns the TSK experiment head that is explicitly NOT deployed; the deployment path (exact rule heads) measures P 1.000 / R 1.000 / savings MAE 0.00 exactly as claimed.

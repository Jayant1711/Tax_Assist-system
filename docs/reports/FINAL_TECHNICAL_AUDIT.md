# FINAL TECHNICAL AUDIT — Sprint 4 (ANFIS v5 / Tax Intelligence Layer)
**Auditor:** Principal Software Architect (independent final audit)
**Date:** 2026-11-04 · **Repo state audited:** branch `sprint-4-ai-modernization` @ `2ff9608`, working tree clean (0 modified files)
**Method:** every claim below was re-verified against the actual code, data files, and git history — no report was taken on faith. Where the claim was runnable, the engine was run live in this audit.

---

## 1. Verdict per claim

### Claim 1 — ANFIS v5 implementation exists and matches its docs — **VERIFIED** (with deviations, as documented; one doc-drift flag D4/D3)

Verified in `backend/tax_intelligence.py` (661 lines):

| Element | Code evidence | Doc evidence |
|---|---|---|
| `composite_efficiency` exact serving | `tax_intelligence.py:249-278` — evaluates the documented v1 composite directly from schema features (`30 + 68.5·Σ wᵢ·uᵢ`, clip [30, 98.5]); `predict_efficiency` returns it verbatim (`:275-278`) | MODEL_REGISTRY.md row "anfis-v5 (efficiency)" — "deterministic composite … (exact; the learned TSK head is the experiment)" |
| `features_v2` single source | `tax_intelligence.py:328-374`; imported by the generator at `backend/tools/generate_anfis_dataset.py:41` (`from tax_intelligence import features_v2  # noqa: E402 — single source`) and delegated at `:163-167`; consumed by `recommend()`/explainability at serve time — train/serve cannot diverge | DATASET_REGISTRY "Generation" column; SPRINT4_RELEASE_CANDIDATE_REPORT_V2 §2 |
| Multi-head TSK, ridge-LSE | `_lse` closed-form ridge consequents `:82-104`; `_membership` Gaussian base `:69-79`; cascade savings training `:196-217`; balanced opportunity training `:221-230`; SEED 472 `:45` | TRAINING_REGISTRY RUN-003/003b; ANFIS_ROOT_CAUSE_REPORT §1 |
| **48 rules** | `RULES = 48` (`:50`) | MODEL_REGISTRY "20 × 48 Gaussian rules"; ANFIS_ROOT_CAUSE_REPORT RC-3/EXP-F4 (K=48 quantile config) |
| **Additive combination** | `w = mf.sum(axis=2)` with in-code rationale citing Jang 1993 (`:74-79`) | EXPERIMENT_REGISTRY EXP-006 ("additive combination adopted for v5 — documented deviation"); EXPLAINABILITY_ENGINE_REPORT §1 Layer 2 ("Deliberate divergence from the framework doc's product rule") |
| **Schema v2.1 + f21** | `SCHEMA = "anfis-feature-schema/3"` (`:60`, "/3: +f21 old-tax ratio (23-dim sav)"); `SAV_EXTRA = 3` (delta_norm + head_idx + f21) `:47-49`; f21 emitted by the generator at `generate_anfis_dataset.py:270-272` | DATASET_REGISTRY "anfis-feature-schema/2.1 … v2.1: + f21 baseline old-regime tax ratio"; ANFIS_ROOT_CAUSE_REPORT §8-2 |
| Rule heads | `rule_opportunity` / `rule_savings` / `rule_confidence` `:647-661`; forensics rationale `:633-645` | ANFIS_V5_EVALUATION_V2 §4-5; MODEL_REGISTRY "rule-heads-v5" |
| `recommend` two-pass | baseline `:419-424` → per-head **full-headroom** probes `:431-441` (comment `:431-435` names the 80E/15L/₹1,300 flip) → engine-priced ranking `:453-455` → `RECOMMEND` `:474` / `NO BENEFIT` `:478` | CA_RECOMMENDATION_ENGINE_REPORT §2 (verbatim pseudocode match) |
| Explain functions | `explain_efficiency` `:533-561` (statutory weights, contribution_share = w/0.975), `explain_model_efficiency` `:564-592` (μ → w̄ → consequent contributions → top rules + effective rules), `advisor_block` `:602-628` | EXPLAINABILITY_ENGINE_REPORT §1 (three layers, all three match) |

All three stated deviations (additive firing, 48 rules, schema v2.1+f21) are documented in code comments, the registries, and the V2 reports. **Flag D4:** the two Phase-6 design docs themselves — `ANFIS_VNEXT_ARCHITECTURE.md` and `ANFIS_FEATURE_SCHEMA.md` — still describe the superseded design (64 rules, product firing, 9 `opp_*` heads, `TAX_ANFIS_V5` flag, `/chat`+`/calculate` wiring, shared `backend/anfis_schema.py` extractor, `anfis_weights_v5.json` artifact, `data/anfis_v1/{train,val,test}.jsonl`). None of those exist; the actual shape is documented only in the newer registries/reports. **Flag D3:** the schema version label drifts across artifacts: module docstring `/2` (`:28`), `features_v2` docstring `/2` (`:330`), `SCHEMA` constant `/3` (`:60`), DATASET_REGISTRY "2.1", `v5_metrics.json` `fit.schema: "anfis-feature-schema/2"`. Cosmetic (load-time check at `:311-312` is self-consistent), but one contract carries five labels.

### Claim 2 — Tax Intelligence Layer integration (nlp_engine closing turn) — **VERIFIED**

- Closing turn: `backend/nlp_engine.py:1129-1149` — the `"Final audit ready"` branch builds `ack + composer.ask("closing", turn_idx) + intel_text + " (tax year …)" + tip_text`.
- `advisor_block` import + call: `nlp_engine.py:1141-1145`; blanket containment `try/except Exception → intel_text = ""` at `:1139, :1146-1147` ("intelligence never breaks a turn").
- `_TAX_ENGINE` lazy cache: module global `None` (`:19`), setter `:22-24`, lazy `TaxEngine()` construction on first closing turn `:1142-1143`.
- Composer contract: `backend/response_composer.py` (read in full) — pure prose layer, deterministic rotation indexed by `len(session["history"])` (`:338-341`, `:221-223`), no session mutation, ADR-001 boundary stated at `:27-29` (presentation headroom only). `advisor_block`'s output is appended between the closing line and the legacy tip, exactly as INTELLIGENT_RESPONSE_REPORT §1 specifies.
- Live E2E (run in this audit): `advisor_block(sess, engine, None)` on the 15L/80C-50k session returns byte-for-byte the documented block — `'\n🧠 **Best opportunity**: top up Section 80E by ₹5,00,000 → est. savings ₹1,300 (confidence 85%; engine-verified in your report). Why: Section 80E has ₹5,00,000 unused (currently 0% utilized).'` — and returns `None` on the 24L all-zero-benefit session (suppression path proven).

### Claim 3 — Explainability Engine + the worked example — **VERIFIED (live run)**

Ran the engine in this audit on `{"salary": 1_500_000, "age": 32, "80c": 50_000}` (FY 2025-26):

- Engine: New Regime, old ₹2,41,800 / new ₹97,500, savings ₹1,44,300.
- `explain_efficiency` → `prediction = 39.1`, `served_by = "deterministic composite (anfis-feature-schema/2)"`, `top_features = [u80c 0.4103, unps 0.1538, u80d 0.1231, u24b 0.1026]`, `model_experiment = {"available": False}` (weights not deployed ⇒ Layer 2 correctly refuses to fabricate).
- The **80E ₹5L top-up flip**: `recommend()` pass 2 prices `80e += 500_000` → old-regime ₹96,200 < new ₹97,500 → `savings_engine = ₹1,300.0`, verdict `RECOMMEND`, confidence 0.85, evidence lines verbatim as documented (`"engine-priced: a top-up of ₹5,00,000 saves ₹1,300 (authoritative)"`).
- Cross-checked against EXPLAINABILITY_ENGINE_REPORT §2 (worked example, links 1–5) and §1 (39.1 / 0.4103 / …) — **every number matches the live run**. Sibling heads (24b, 80c, 80d, 80d_parents, 80g, 80tta, nps) all price ₹0 → `NO BENEFIT (current regime ignores this head)`, matching CA_RECOMMENDATION_ENGINE_REPORT §5's 8-head table.
- Line-number drift only: the report cites `explain_efficiency (L534)`, `explain_model_efficiency (L565)`, `advisor_block (L603)`, rule heads `(L648-662)`; actual `:533 / :564 / :602 / :647-661` — off-by-one, immaterial.

### Claim 4 — CA Recommendation Engine two-pass — **VERIFIED (live run)**

The run in Claim 3 is the verification: baseline pass (`:422-424`) prices as-booked; pass 2 probes **full remaining headroom** per open age-gated head (`:431-441`, `delta = headroom`), ranks by `(-savings_engine, -savings_estimate, head)` (`:453-455`), issues `RECOMMEND` (0.85) / `NO BENEFIT` (0.30) verdicts (`:468-478`), and returns `regime_advisory` (engine verdict + savings-if-switched) and `band_position` (87A ±₹50k window, `:489-494`; `None` for the 15L session, as documented). The partial-probe counterfactual in CA_RECOMMENDATION_ENGINE_REPORT §3.5 (₹50k probe → ₹0; ₹5L probe → ₹1,300) follows directly from the full-headroom design. Engine-only degradation (`ti=None`) keeps every rupee engine-priced (`opportunity_probability: None` observed on all rows).

### Claim 5 — Dataset lineage — **VERIFIED (measured, exact)**

Loaded `data/anfis_v1/` directly:

| DATASET_REGISTRY.md claim | Measured | Match |
|---|---|---|
| features.npz `X (B,20) float32`, `y_eff`, `y_top`, `scenario_id` | `(5964, 20)` float32 + `(5964,)` ×2 + `(5964,)` | ✅ |
| savings.npz `X (B,23 = 20 + delta_norm + head_idx + f21)`, `y_sav`, `y_opp` | `(76960, 23)` float32 + `(76960,)` ×2 | ✅ |
| 5,964 scenarios | 5,964 | ✅ |
| 53,676 utilization rows | `wc -l utilization.jsonl` = 53,676 | ✅ |
| 76,960 optimization rows | `wc -l optimization.jsonl` = 76,960 | ✅ |
| 76,960 recommendation rows | `wc -l recommendation.jsonl` = 76,960 | ✅ |
| 1,623 positives = 2.11% | `y_opp.sum() = 1623` (2.11%) | ✅ |

Generator (`backend/tools/generate_anfis_dataset.py`): base grid (`_sampled_bookings`, `:324-353`) + 6 expansion strata (`_expansion_bookings`, `:356-419`: S1 heavy-deduction, S2 CG 112A band, S3 HRA Rule-2A metro/non-metro, S4 senior heads, S6 flip-hunter 8×48, S5 near-max knock-outs) — matches the registry's strata description; every label is engine-priced two-pass (`:217-245`); `efficiency_ground_truth` mirrors the served composite (`:137-160`). Dataset is fully untracked (`.gitignore:34`, `git ls-files data/anfis_v1/` = 0 files) — regenerable from committed tools, as PROJECT_STATUS_REPORT_V3 §2 states. Minor flag: `train_anfis_v5.py` docstring still says "X (B, 22 …)" (`:11`) — actual file is 23-wide (f21 added later).

### Claim 6 — Model lineage — **VERIFIED** (git + code), one registry staleness flag (D2)

- **v4 untouched, git-verified:** `git log -- backend/anfis_weights.json` → last commit touching it is `fdb6ed9` (2026-10-31, pre-v5-program). `git diff b88e602^ HEAD -- backend/anfis_weights.json` → empty ("UNCHANGED b88e602^ → HEAD"); worktree matches HEAD. The v5 program (b88e602, 2ff9608) never modified it. ✅
- **Rule heads in code:** `tax_intelligence.py:647-661`. ✅
- **TSK experiment not imported by main.py:** `grep -i anfis backend/main.py` → 0 hits; no import of `tax_intelligence`/`train_anfis_v5`/research modules in main.py at all. The only production v5 wiring is `nlp_engine.py:1141-1145`. ✅
- **Candidate artifact correctly absent:** `backend/anfis_v5_weights.json` does not exist; the trainer writes it only when `gates_pass` (`train_anfis_v5.py:195-196`); `v5_metrics.json` records `gates_pass: false`, TSK `deployed: false`, rule heads `deployment: "EXACT RULE HEADS (engine-priced)"` — matching MODEL_REGISTRY ("candidate NOT written (gates)", "EXPERIMENT — not deployed"). ✅
- **Flag D2 (stale numbers):** MODEL_REGISTRY's LIVE anfis-v5 rows cite RUN-003-era metrics — "MAE vs labels 0.053 points (G1 PASS)" and "learned MAE 12.772" — while the current-generation measurements are 0.1363 / 15.6751 (`data/anfis_v1/v5_metrics.json`, ANFIS_V5_EVALUATION_V2 §2, TRAINING_REGISTRY RUN-003b). TRAINING_REGISTRY correctly separates RUN-003 (0.053/12.772, schema-v2 3,528-scenario era) from RUN-003b (0.136); MODEL_REGISTRY does not mark the old numbers as historical.
- **Nuance (disclosed elsewhere):** the production results-view `efficiency_score` still comes from the v4 ANFIS (`tax_engine.py:375` → `ai_models.py::score_efficiency` legacy extractor); the v5 composite's only callers are the trainer's G1 gate (`train_anfis_v5.py:69`) and tests. EXPLAINABILITY_ENGINE_REPORT §4/§6 discloses this honestly ("the production efficiency number still comes from the v4 ANFIS … until v5 weights ship"), but MODEL_REGISTRY's "LIVE (v0.5-rc)" for the composite overstates its wired surface.

### Claim 7 — The 10 sprint-4 reports: existence + internal consistency — **VERIFIED** (stale numbers flagged)

All ten exist at root: `ANFIS_ROOT_CAUSE_REPORT.md`, `ANFIS_V5_EVALUATION_V2.md`, `DATASET_QUALITY_REPORT_V2.md`, `EXPLAINABILITY_ENGINE_REPORT.md`, `CA_RECOMMENDATION_ENGINE_REPORT.md`, `INTELLIGENT_RESPONSE_REPORT.md`, `SPRINT4_RELEASE_CANDIDATE_REPORT_V2.md`, `SPRINT4_RELEASE_CANDIDATE_REPORT.md` (V1, explicitly superseded), `P1_CERTIFICATION_REPORT.md`, `PROJECT_STATUS_REPORT_V3.md`.

Cross-checks performed:

| Metric in reports | Independent check | Result |
|---|---|---|
| 1,146 pytest / 0 failures (V1 §1, V2 §3, V3 §4) | `python -m pytest` in this audit: **1146 passed, 1 deselected** in 52.6s | ✅ |
| G1 0.136 / G2 −0.112 / G3 100% (V2, RUN-003b) | `v5_metrics.json`: 0.1363 / −0.1118 / 1.0 | ✅ |
| Ranking 95.72% / G4 794.69% / G5 P,R 0 (V2) | `v5_metrics.json`: rule-head protocol + TSK `g4_mape 7.9469 (=794.69%)`, `ranking_top1 0.5704` (TSK), `rule_heads {1.0, 1.0, 0.0}` | ✅ |
| 5,964 / 76,960 / 1,623 (V2, V3, registries) | measured (Claim 5) | ✅ |
| Explainability worked example (39.1, ₹1,300, evidence lines) | live re-run (Claim 3) | ✅ |
| 8-head table + 24L all-NO-BENEFIT (CA report §5) | live re-run incl. 24L suppression = None | ✅ |
| P1 report "55 tests" | file now collects 61 (6 added later: 4 HazaarUnit + 2 EngineScoringOrder — consistent with the post-certification hazaar/lakh-stem work) | ✅ historical |
| **"composer 25" (V3 §2, EXP-007, INTELLIGENT_RESPONSE_REPORT §4)** | collects **23** | ❌ see D1 |
| **"test_sprint4_p1 (59)" (audit claim; reports imply evolving counts)** | collects **61** (40 functions + parametrize) | ❌ see D1 |
| **MODEL_REGISTRY 0.053 / 12.772 as LIVE** | current = 0.136 / 15.675 (RUN-003b) | ❌ see D2 |
| V1's 0.053 / 3,528 scenarios / 46,816 rows | superseded by V2, which says "Supersedes V1" — disclosed staleness | ✅ (disclosed) |
| V3 §2 "Reports (10)" | §6 lists 8 | ⚠ minor (D6) |
| V2 §2 heading "6,5965/10,995 train/val" | typo for 65,965 (matches `v5_metrics.json` `train_rows.sav: 65965`) | ⚠ minor (D6) |

### Claim 8 — Test coverage of the new surface — **VERIFIED** (counts corrected per D1)

- `backend/tests/test_tax_intelligence.py`: **12 tests, all pass.** Read in full — they pin real behavior, not smoke: `TestADRBoundary` re-prices every recommendation through a fresh `calculate_tax_advanced` and asserts exact equality (`:62-82`); `test_no_amount_is_invented` pins the zero-benefit → ₹0 + NO BENEFIT contract (`:84-91`); shape/ranking/regime-advisory contracts (`:98-120`); Layer-1 and Layer-2 decomposition contracts on a real in-session fit over the generated dataset (`:28-47`, `:127-152`); engine-only degradation (`:159-182`, the 15L/80E fixture); no-benefit suppression (`:184-193`); composer closing-turn integration and never-breaks-a-turn (`:200-223`).
- `backend/tests/test_response_composer.py`: **23 tests** (not 25), all pass — determinism/rotation/data-awareness/advisory contracts.
- `backend/tests/test_sprint4_p1.py`: **61 collected items** (40 test functions with parametrize; not 59), all pass — includes `TestEngineScoringOrder` pinning the F5 scoring-order fix.
- Combined run in this audit: **96 passed in 3.57s**; full suite **1,146 passed**.

### Claim 9 — ADR compliance — **VERIFIED**

- **ADR-001 (no model computes tax):** the only sites outside `tax_engine.py` that assign `total_tax`/`taxable_income`/`savings`/`recommendation` — grep across `backend/**.py` — return **zero hits**; the intelligence layer only *reads* engine output (`tax_intelligence.py:347` is a read). The single model call site in the engine is `tax_engine.py:375` writing `efficiency_score` (a 0–100 display score, not a tax amount — the ADR-004 "beta label" concern, unchanged this sprint). `recommend()` prices every rupee via two `calculate_tax_advanced` calls (`:422, :438`); `advisor_block` emits only engine-priced figures and returns `None` unless `verdict == "RECOMMEND" and estimated_savings > 0` (`:613-621`). Enforced by `TestADRBoundary` (verified passing). ✅
- **ADR-003 (no external services):** the new surface (`tax_intelligence.py`, `response_composer.py`, the nlp closing turn) has no network imports/calls — grep for `requests|urllib|http|socket|openai|api_key` hits only the word "ask-backs" in comments. NumPy + stdlib + the in-process engine only. ✅
- **ADR-015 (deterministic extraction retained):** recorded at `docs/decisions.md:191`; research artifacts (`nlp_research/*`, TF-IDF/BiLSTM/BERT) are not imported by `main.py` (grep clean); MODEL_REGISTRY lists them all as "research artifact — never production". ✅
- **Open item (D8):** ADR-016 — proposed by `ANFIS_VNEXT_ARCHITECTURE.md §6.5` to be recorded "at release" and to supersede ADR-004 — is **not yet in `docs/decisions.md`** (ADRs end at 015), and ADR-004's status remains "Accepted — quality concerns logged". Consistent with "at release" since the release (tag/PR) is still pending the user decision, but it is an unfinished step of the documented plan.

### Claim 10 — Known documented gaps accurately stated — **VERIFIED**, one omission (D5)

- **TSK heads off-deployment:** stated in MODEL_REGISTRY (EXPERIMENT — not deployed ×3), ANFIS_V5_EVALUATION_V2 §1/§5, SPRINT4_V2 §2/§4, PROJECT_STATUS_V3 §7.2 — and true in code (no artifact, `get_intelligence()` → `None` path `tax_intelligence.py:504-516`, model fields `None` in served output).
- **Grid saturation:** stated in DATASET_QUALITY_REPORT_V2 §4 ("Rounds 3→4 added zero new scenarios … 76,960 rows / 1,623 positives is the ceiling of the structured grid"), SPRINT4_V2 §4 risk table, V3 §7.4.
- **Legacy NPS tip:** stated in SPRINT4_V1 §4 ("80CCD(1B) … non-deductible under 115BAC — the legacy Quick Tip's '₹15,600 NPS savings' can mislead on the new regime"), CA report §7, INTELLIGENT_RESPONSE_REPORT line 16, V3 §7.3 — and true in code: `ai_models.py:585-591` computes `gap * 0.312` with no regime gating, and the tip is still appended at `nlp_engine.py:1131-1132`.
- **Omission (D5):** ANFIS_ROOT_CAUSE_REPORT §9 listed four "Generator fixes to land with the expansion": f21 (landed, `generate_anfis_dataset.py:270-272`), the **u80g normalization fix** (not landed — generator `:156` still labels u80g as `booked/100,000` while `features_v2` uses `inc·0.1+1`; this residual is why G1 is 0.136 and not ≈0), **bookable-cap-aware 80d_parents probes** (not landed — `LIMITS["80d_parents"] = 50_000` still probes the engine-unbookable 25k–50k band), and **80U/80DDB leg booking** (not landed — measured in this audit: `u80u`, `u80ddb`, `u80eea` remain **all-zero** across all 5,964 rows of the expanded features.npz). No later report falsely claims these landed, but the specified fix list is silently open and the "dead features" finding still holds post-expansion.

---

## 2. Discrepancies

**No functional, ADR, or data-integrity violations found.** All discrepancies are documentation/traceability drift:

- **D1 — Test counts stale in reports.** `test_response_composer.py` collects **23** tests, not the 25 claimed in PROJECT_STATUS_REPORT_V3 §2 ("composer 25"), EXPERIMENT_REGISTRY EXP-007, and INTELLIGENT_RESPONSE_REPORT §4. `test_sprint4_p1.py` collects **61** items (40 functions), not 59. Total for the three files: 96 (12 + 23 + 61), all passing. Off-by-two on both files suggests counts taken at a different commit than HEAD.
- **D2 — MODEL_REGISTRY stale metrics presented as current.** The anfis-v5 (efficiency) row cites "MAE vs labels 0.053 points (G1 PASS)" and the learned-TSK row "learned MAE 12.772 vs composite 0.053" — these are RUN-003 numbers (3,528-scenario schema-v2 era, per TRAINING_REGISTRY). The current-generation measurements are 0.1363 and 15.6751 (`data/anfis_v1/v5_metrics.json`; ANFIS_V5_EVALUATION_V2 §2; TRAINING_REGISTRY RUN-003b, which gets the split right). Both generations PASS the ≤2.0 gate, so the error is cosmetic — but a registry is the wrong place for an unlabeled superseded number.
- **D3 — Schema version-label drift.** One feature contract is labeled `anfis-feature-schema/2` (`tax_intelligence.py:28`, `:330`), `/3` (`:60`), `2.1` (DATASET_REGISTRY, SPRINT4_V2), and `/2` again in `v5_metrics.json fit.schema`. Load-time validation is self-consistent, so nothing breaks; the label proliferation invites future loader mismatch.
- **D4 — The Phase-6 design quadrilogy is stale.** `ANFIS_VNEXT_ARCHITECTURE.md` and `ANFIS_FEATURE_SCHEMA.md` still specify the superseded design (64 rules, product firing, 9 `opp_*` heads, `TAX_ANFIS_V5` env flag, `/chat`+`/calculate` integration, shared `backend/anfis_schema.py`, `anfis_weights_v5.json`, `{train,val,test}.jsonl splits`) — none of which match the implementation. The deviations are properly documented in code comments, EXPERIMENT_REGISTRY (EXP-006), MODEL_REGISTRY, and the V2 reports, but the two architecture docs themselves were never revised (their own §1 versioning rule says a schema change requires re-certification of the doc).
- **D5 — Root-cause fix list partially landed, untracked.** Of the four generator fixes "to land with the expansion" (ANFIS_ROOT_CAUSE_REPORT §9), only f21 landed. The u80g label/feature normalization mismatch (generator `:156` vs `features_v2`), the 80d_parents bookable-cap probe restriction, and 80U/80DDB leg booking did not land — `u80u`/`u80ddb`/`u80eea` are still identically zero in the shipped dataset (measured), and the G1 residual (0.136) is partly the un-fixed u80g defect. Nowhere claims otherwise, but no live document tracks these as open.
- **D6 — Cosmetic report defects.** PROJECT_STATUS_REPORT_V3 §2 says "Reports (10)" while its §6 lists 8; ANFIS_V5_EVALUATION_V2 §2 has the "6,5965" typo (should be 65,965, matching `v5_metrics.json`); several reports cite `tax_intelligence.py` line numbers off by one (the file was edited after them); `train_anfis_v5.py` docstring says the savings matrix is 22-wide (actual 23).
- **D7 — "LIVE" overstatement for the v5 composite (nuance).** MODEL_REGISTRY marks the v5 deterministic composite "LIVE (v0.5-rc)", but its only production-path caller is the trainer's G1 gate; the user-facing results-view efficiency score is still served by v4 (`tax_engine.py:375`). The gap is disclosed honestly in EXPLAINABILITY_ENGINE_REPORT §4/§6 — the registries and that report disagree in emphasis, not in fact.
- **D8 — ADR-016 not yet recorded.** `docs/decisions.md` ends at ADR-015; ADR-004 is not yet marked superseded. The architecture doc defers this "at release", and the release is pending the user's tag decision — open, not violated.

---

## 3. Overall audit verdict

**PASS — release-candidate quality confirmed, with documentation hygiene findings (D1–D8), none release-blocking.**

What was independently proven in this audit: the v4 weights are byte-untouched across the entire v5 program (git); the dataset files match the registry to the row and the rupee; the served intelligence path is engine-priced end-to-end with structural ADR-001 containment (greps + passing recomputation tests); the worked example, the two-pass advisor, the exact rule heads, and the degradation ladder all reproduce live to the documented digit; the full suite is 1,146/0 as claimed; and the three headline known gaps (TSK off-deployment, grid saturation, legacy NPS tip) are real and honestly documented.

Before merge, the recommended (non-blocking) cleanup is: correct the test counts and MODEL_REGISTRY's stale metrics, reconcile the schema version label to a single value, either revise or add a superseded-banner to the two Phase-6 architecture docs, and record ADR-016 at tag time. The root-cause §9 generator-fix list (u80g normalization, 80d_parents cap, 80U/80DDB legs) should be tracked as the first item of the already-planned continuous-value dataset action, since the G1 residual and the three dead features trace directly to it.

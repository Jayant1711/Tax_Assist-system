# Dataset Health Report

Generated: 2026-11-01 06:15 UTC  |  corpus schema v1  |  build seed 40  |  built 2026-11-01

Source of truth: `data/{training,validation,test,corpus}/*.jsonl` + `data/manifest.json` (content-addressed; byte-identical rebuild pinned by `tests/test_nlp_eval.py::TestCommittedDatasetMeta::test_rebuild_reproduces_the_committed_manifest`).

## Totals

- Total labeled records: **2226** (spans: **2255**)
- Split sizes: training 1537, validation 434 (eval split), test 255 (holdout), corpus (runtime capture stream) 0
- Distinct template families: 197 (max renders per family 28)

## Per-category coverage

Floors: >=50 spans per bookable category corpus-wide, >=15 in the eval split (validation).

| Category | Total | Training | Validation | Test | Floor 50 | Eval floor 15 |
|---|---|---|---|---|---|---|
| salary | 162 | 110 | 35 | 17 | met | met |
| business | 145 | 99 | 30 | 16 | met | met |
| rental | 121 | 89 | 16 | 16 | met | met |
| agriculture | 120 | 91 | 15 | 14 | met | met |
| capital_gains | 139 | 105 | 17 | 17 | met | met |
| other_income | 118 | 77 | 27 | 14 | met | met |
| 80c | 137 | 99 | 21 | 17 | met | met |
| 80d | 111 | 63 | 34 | 14 | met | met |
| 80d_parents | 113 | 84 | 15 | 14 | met | met |
| 80e | 100 | 56 | 29 | 15 | met | met |
| 80g | 115 | 78 | 23 | 14 | met | met |
| nps | 96 | 56 | 26 | 14 | met | met |
| hra_received | 92 | 70 | 15 | 7 | met | met |
| rent_paid | 125 | 95 | 16 | 14 | met | met |
| 24b | 107 | 78 | 15 | 14 | met | met |
| 80tta | 77 | 49 | 21 | 7 | met | met |
| 80ttb | 84 | 56 | 21 | 7 | met | met |
| 80gg | 91 | 63 | 21 | 7 | met | met |
| 80u_80dd | 50 | 21 | 19 | 10 | met | met |
| 80ddb | 98 | 70 | 21 | 7 | met | met |
| ABSTAIN | 54 | 32 | 17 | 5 | met | met |

All category floors met (synthetic-backed where the organic ledger slice is thin — every synthetic record carries `provenance.note`).

## Source and language distribution

- Sources: synthetic 2202 (98.9%), ledger 17 (0.8%), organic 7 (0.3%)
- Languages: en 1895 (85.1%), hinglish 331 (14.9% — the mandatory Hinglish slice)

## Split integrity / leakage

- Manifest disjointness: OK — template-disjoint and session-disjoint
- Cross-split near-duplicates (normalized-text hash): **0**
- Ledger gold labels (docs/nlp-pipeline.md §11 + the Sprint 2/3 ledger items) are eval material only: never written to the training split.

## Eval baseline (sprint3)

- Pipeline: NLPEngine.process_message (the current deterministic pipeline, keyword-proximity attention + scripted waterfall), pre-P1
- Records evaluated: 434 (validation split)
- Micro: P=0.7188 R=0.6982 F1=0.7084
- Macro: P=0.8200 R=0.6888 F1=0.6888
- Gate (>= 95% on income heads + major sections): FAIL — failing: 24b, 80c, 80d, 80ddb, 80e, 80g, 80tta, 80ttb, 80u_80dd, business, capital_gains, hra_received, nps, other_income, rent_paid, salary
- This is THE P/R number P1 must improve (docs/sprint4-execution.md P1 gate).

**Eval-marker flip plan:** the >=95% gate ships ADVISORY (`pytest -m eval` reports it; the default run excludes it via `addopts = -m "not eval"` in backend/pytest.ini). At the P1 verdict the exclusion is removed so the gate binds in CI (red = merge blocker).

## Funnel baseline (live session store)

- Sessions: 1815  |  completed (FINAL): 2  |  completion rate: 0.1%

### Funnel detail (live store)


Total sessions: 1815  |  completed (FINAL): 2  |  completion rate: 0.1%
Unknown phases: (missing): 997

| Phase | Sessions (current) | Reached | Total turns | Avg turns | Drop-off from previous | Drop-off rate |
|---|---|---|---|---|---|---|
| PROFILING | 288 | 818 | 0 | 0.0 | — | — |
| INCOME | 327 | 530 | 327 | 1.0 | 288 | 35.2% |
| EXPENDITURE | 201 | 203 | 201 | 1.0 | 327 | 61.7% |
| FINAL | 2 | 2 | 12 | 6.0 | 201 | 99.0% |

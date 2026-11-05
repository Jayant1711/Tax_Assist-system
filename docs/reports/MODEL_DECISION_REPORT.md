# MODEL DECISION REPORT — Deterministic vs Learned Extraction
**Generated:** 2026-11-02 · **Decision owner:** Sprint-4 spec P3 rule (`docs/sprint4-execution.md`) · **Companion:** `NLP_EVALUATION_REPORT.md`

---

## DECISION: **KEEP DETERMINISTIC — no model warranted at current data volume.**

The spec's own decision rule: *"If income-head + major-section P/R ≥ 95% → KEEP deterministic; document the decision (ADR note: model not warranted at current data volume); revisit when organic corpus ≥5k turns."*

**Measured:** gate PASSES on all 13 gate categories; macro F1 = 1.000 across all 21 categories on the eval split (434 records); abstention accuracy 100%; zero pipeline errors. `MODEL_DECISION_REPORT` trigger condition ("evaluation shows deterministic extraction below target") is **not met**.

## 1. Evidence summary

| Criterion (spec) | Target | Measured | Verdict |
|---|---|---|---|
| Income-head precision/recall | ≥95% | salary 100/100 · business 100/100 · rental 100/100 · other_income 100/100 · agriculture 100/100 · capital_gains 100/100 | PASS |
| Major-section precision/recall | ≥95% | all 13 sections 100/100 (80c, 80d, 80d_parents, 80e, 80g, 80tta, 80ttb, nps, hra_received, rent_paid, 24b, 80u_80dd, 80ddb) | PASS |
| Abstention (never guess) | qualitative | 17/17 records correctly book nothing | PASS |
| Determinism / CPU / offline (ADR-003) | required | pure-Python, zero deps, microsecond latency | PASS |

## 2. Why adding a model now would be negative-value

1. **No headroom to buy:** a classifier would be *trained to imitate* the labels the deterministic pipeline now fully matches. Its best case is parity; its realistic case is regression on the long tail (Hinglish, rare sections) where training data is thinnest.
2. **Cost asymmetry (ADR-003):** a model adds weights, drift risk, and an inference dependency into a request path that is currently pure-Python, auditable line-by-line, and explainable to a viva examiner.
3. **Measurement integrity:** the P0 framework canaries against a sabotaged predictor precisely so a model can't silently ship worse-than-baseline. With baseline at ceiling, the canary would (correctly) block it.
4. **Explainability obligation:** every booking today can state *which keyword at what distance* chose the category — a regulatory-grade property (ADR-001 adjacent) a learned extractor cannot offer.

## 3. Revisit triggers (pre-committed, per spec)

- Organic captured corpus ≥ **5,000 turns** (`data/corpus/` stream, `TAX_CORPUS_CAPTURE` opt-in) — re-run `tools/run_eval.py` on an organic-majority split; if gate < 95% → prototype char-ngram classifier behind `TAX_NLP_EXTRACTOR` (default remains keyword; never replaces deterministic; comparison report required).
- Any new §0-style misclassification ledger entry reproducing on the eval split.
- Multilingual expansion (Hindi/Tamil/Marathi) — new-language templates first; model only after the deterministic pass is measured on that language.

## 4. ADR note (for `docs/decisions.md` incorporation at release)

> **ADR-015 (de-facto, this report):** the deterministic extraction pipeline is retained as the sole production extractor. The P0 evaluation framework measured macro F1 1.000 / gate PASS on the eval split (2026-11-02); a learned extractor is not warranted at the current corpus volume (2,226 records, template-heavy). Re-evaluation is pre-committed at ≥5,000 organic turns or on any reproduced ledger regression.

## 5. What was NOT done (scope honesty)

- No classifier was prototyped (spec: only if gate < 95%).
- The 255-record holdout (`data/test/`) was not opened — it stays sealed for the release-gate review per the Sprint-4 dataset strategy.
- The research-layer intent classifier (96.41% TF-IDF baseline, 8-class) is unaffected by this decision — it remains a *research comparison artifact*, not a production component.

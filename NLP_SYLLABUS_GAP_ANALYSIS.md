# NLP Syllabus Gap Analysis — Tax Assist System × CSE472

> **Course:** CSE472 — Deep Learning for Natural Language Processing
> **Project:** Tax Assist System (AI-powered Indian taxation platform)
> **Date:** 2026-11-01 · **Baseline:** `v0.4-sprint3` (tag, frozen) + Sprint 4 branch `sprint-4-ai-modernization`
> **Scope guard:** this analysis maps the EXISTING NLP stack against the syllabus. Production code (auth, deployment, Docker, security, sessions, CI/CD, `tax_rules/` registry) is out of scope and untouched.

---

## 1. Methodology

Every claim below cites `path:line` evidence read directly from the working tree. Status classification:

- **Implemented** — a working, tested implementation exists (production or research path)
- **Partially Implemented** — an analogous mechanism exists but lacks the syllabus concept's defining property
- **Missing** — no implementation in the repository

⚠ Assumption: the official CSE472 unit-wise topic list was not supplied; Units I–VI are reconstructed from the standard "Deep Learning for NLP" curriculum (foundations → embeddings → sequence models → attention/seq2seq → pretrained LMs → applications & evaluation). If the faculty syllabus differs, only the unit *labels* need remapping — the topic tables themselves are unit-agnostic.

---

## 2. Executive Summary

The production NLP stack is a **deterministic, rules-first extractor** (ADR-003: offline, fast, auditable) with one neural component (ANFIS). It is *exceptionally* strong on Unit I (domain-specific preprocessing) and Unit VI (a rigorous evaluation framework), **partially** aligned on Unit IV (attention-inspired proximity scoring) and Unit VI applications (regex NER, keyword classification), and **entirely missing** Units II (embeddings), III (sequence models), and V (pretrained LMs).

| Unit | Theme | Coverage | Gap fill |
|---|---|---|---|
| I | Foundations & preprocessing | **Implemented (strong)** | — |
| II | Word embeddings | **Missing** | Phase B |
| III | Sequence models (RNN/LSTM/BiLSTM) | **Missing** | Phases C, D |
| IV | Attention & Seq2Seq | **Partial** | Phases E, F |
| V | Pretrained LMs (BERT/GPT/T5) | **Missing** | Phases F, G |
| VI | Applications & evaluation | **Partial (strong)** | Phases C, D, H, I |

**Viva position:** rather than hiding the rules-first design, the project's narrative becomes *"a production rules system extended with a measured deep-learning research layer"* — every DL component is evaluated against the deterministic baseline, which is exactly the scientific method examiners reward.

---

## 3. Current NLP Architecture (inventory)

The extraction pipeline (`nlp_engine.process_message` → booking → scripted waterfall):

| # | Component | Where | Technique | Maturity |
|---|---|---|---|---|
| 1 | Preparse guards | `nlp_engine.py:153-207` (definitions), `:344+` (dispatch) | Regex masking: ages vs money lookaheads (`:69-95`), percentage masking (`:93-97`), statutory flat amounts (`:167-171`), transfer-year phrases (`:180-194`), question-sentence no-booking (`:200-207`) | Production |
| 2 | Clause segmentation | `nlp_engine.py:102` `_GUARD_CLAUSE_SPLIT_RE`, `:325-334` `_clause_window` | Delimiter split ("and"/"&"/comma/semicolon) with digit-grouping-safe variant | Production |
| 3 | Amount parser | `ai_models.py` `UniversalParser` (`:46+`) | Regex digit pattern + Indian comma-grouping, word-number map (English + Hinglish digits), unit map (lakh/lac/crore/k/pm/`/mo`), annualization | Production |
| 4 | Category resolution | `ai_models.py` `SemanticAttention` (`:178+`) | Keyword-proximity scoring: Gaussian distance decay `100·exp(−dist²/3200)` + content score `2.5·words + 0.1·len`, negative-keyword penalties, long-phrase subsumption, asked-category prior | Production |
| 5 | Dialogue policy | `ai_models.py` `ReasoningAgent` (`:507+`) | Scripted discovery waterfall (income → 80C → 80D → NPS → HRA → 24b → 80G), ask-backs, savings tips | Production |
| 6 | Profession classification | `profession_db.py` `classify_profession` | Exact-substring → ownership signals → fuzzy repair (Sprint 4 P1) | Production |
| 7 | Neuro-fuzzy scorer | `ai_models.py` `ANFIS` (`:604+`), `anfis_weights.json` | TSK ANFIS: 20 inputs × 64 Gaussian MF rules, learned consequents, numpy forward, efficiency 0–100 | Production (heritage; P4 plans replacement) |
| 8 | Labeled corpus | `data/{training,validation,test,corpus}/*.jsonl` + `manifest.json`; builder `backend/tools/build_labeled_corpus.py` | ≥1,000 utterances, 21 categories (20 bookable + ABSTAIN), template/session-disjoint splits, provenance schema | Production (S4-P0, commit `a5691dc`) |
| 9 | Eval framework | `backend/nlp_eval.py`, `tests/test_nlp_eval.py` | Per-category precision/recall/F1 (macro+micro), 21×21 confusion matrix, ≥95% gate, canary self-tests | Production (S4-P0) |
| 10 | Dataset health | `Dataset_Health_Report.md`, `backend/funnel.py` | Coverage, distribution, leakage status, conversion funnel | Production (S4-P0) |

NLP tests pinning behavior: `tests/test_parser.py`, `tests/test_attention.py`, `tests/test_golden_corpus.py`, `tests/test_nlp_eval.py`, `tests/test_sprint4_p1.py` (55/55 green).

---

## 4. Unit-by-Unit Gap Tables

### Unit I — NLP Foundations (tokenization, normalization, morphology, preprocessing)

| Topic | Status | Evidence | Gap / Note |
|---|---|---|---|
| Tokenization | Partially Implemented | `UniversalParser` regex spans `ai_models.py:49-53,76+`; clause split `nlp_engine.py:102` | Regex span-matching, not a general tokenizer (no word/subword tokenization). Academic modules will add explicit tokenizers |
| Text normalization | **Implemented** (domain-strong) | Lowercasing (`nlp_engine.py` guards), Indian digit-grouping `1,25,000` (`ai_models.py:82`), unit canonicalization lakh/L/cr/k/pm (`ai_models.py:34-43`), currency symbols | Exceeds typical coursework — real-world messy-input handling |
| Morphological analysis | Partially Implemented | Enumerated Hinglish inflections: `kamata/kamati/kamaata hoon` (`ai_models.py`, salary.pos), `kiraya deta/dete/deti` (rent_paid.pos) | Inflection *enumeration*, no stemmer/lemmatizer/POS tagger. Academic gap: discuss why rule systems enumerate vs learn morphology |
| Sentence segmentation | Partially Implemented | Guard-clause windows `nlp_engine.py:325-334` | Clause-level, not sentence-level segmentation |
| Stopwords / cleaning | Missing | — | Minimal generic cleaning (domain didn't need it); Phase B/C pipelines add standard preprocessing |
| Noise handling | **Implemented** | Percentage/date/flat-amount masking passes (`nlp_engine.py:367-432`) | Novel "semantic masking" — strong viva material |

**Unit I verdict:** strongest existing unit; academic write-up documents it as a *case study in domain-specific preprocessing*.

### Unit II — Word Embeddings (Word2Vec, GloVe, FastText, similarity/analogy, visualization)

| Topic | Status | Evidence | Gap / Note |
|---|---|---|---|
| Word2Vec (CBOW/Skip-gram) | **Missing** | — | No embedding anywhere in the repo |
| GloVe | **Missing** | — | — |
| FastText / subwords | **Missing** | — | Optional stretch in Phase B |
| Semantic similarity | **Missing** | — | Closest existing concept: keyword proximity (`ai_models.py` Gaussian decay) is *distance in text*, not *distance in meaning* — an excellent contrast to present at viva |
| Analogy tasks | **Missing** | — | — |
| PCA / t-SNE visualization | **Missing** | — | — |

**Phase B fills all rows.** Design choice: Word2Vec Skip-gram with negative sampling implemented **from scratch in NumPy** on the domain corpus (`data/*.jsonl` + tax vocabulary), because (a) `gensim` has no Python 3.15 wheels in this environment, and (b) a from-scratch trainer is *better* viva evidence of understanding than a library call. GloVe: pretrained vectors loaded if reachable offline, else co-occurrence + weighted-least-squares on the same corpus. Vocabulary seeded with PPF, insurance, salary, deduction, tax, income and the Hinglish families already in the corpus (kiraya, byaaj, daan, swasthya, bimari).

### Unit III — Sequence Models (RNN, LSTM, GRU, BPTT, vanishing gradients)

| Topic | Status | Evidence | Gap / Note |
|---|---|---|---|
| Vanilla RNN | **Missing** | — | Taught conceptually in Phase C report; implemented as baseline cell |
| LSTM | **Missing** | — | Phase C intent classifier |
| BiLSTM | **Missing** | — | Phase C classifier + Phase D NER tagger |
| GRU | **Missing** | — | Optional ablation in Phase C |
| BPTT / vanishing gradients | **Missing** (concept discussed) | `anfis_trainer.py` trains a feedforward fuzzy net, not recurrent | Phase C report includes gradient-flow discussion + training curves |
| Sequence labeling | **Missing** | — | Phase D |

**Phases C & D fill.** PyTorch (CPU) from-scratch LSTM/BiLSTM cells where instructive, `torch.nn` where performance matters — the report states exactly which is which.

### Unit IV — Attention & Seq2Seq

| Topic | Status | Evidence | Gap / Note |
|---|---|---|---|
| Encoder-decoder / Seq2Seq | **Missing** | — | Phase E |
| Bahdanau (additive) attention | **Missing** | — | Phase E |
| Luong (multiplicative) attention | **Missing** | — | Phase E |
| Learned attention (softmax Q·K) | **Missing** | — | — |
| Attention-*inspired* scoring | **Partially Implemented** | `SemanticAttention.resolve_category_detailed` `ai_models.py:178+`: proximity-weighted evidence aggregation — conceptually "which context words attend to the amount span", but hand-crafted Gaussian weights, no learned softmax, no queries/keys/values | Honest framing: *not* neural attention; a heuristic ancestor. This contrast is a viva highlight |
| Transformer architecture | **Missing** | — | Phase F uses pretrained BERT; architecture explained in report |

**Phase E fills Seq2Seq + Bahdanau/Luong** (toy translation/denormalization task: numeric+keyword utterance → canonical tax explanation, BLEU/ROUGE-scored, with vs without attention). **Phase F covers the Transformer** via BERT fine-tuning.

### Unit V — Pretrained Language Models (BERT, GPT, T5, transfer learning)

| Topic | Status | Evidence | Gap / Note |
|---|---|---|---|
| BERT / masked LM / fine-tuning | **Missing** | — | Phase F: fine-tune on intent + deduction classification; compare vs TF-IDF/LSTM/BiLSTM |
| GPT-family causal LM | **Missing** | — | Phase G: GPT-2 explanation generation |
| Seq2seq pretraining (T5) | **Missing** | — | Phase G: query summarization |
| Transfer learning methodology | **Missing** (rationale exists) | `Sprint4_AI_Modernization.md` §2.2-2.3 plans a local classifier + LLM second opinion behind `TAX_LLM_EXTRACT` — design present, implementation absent | Phases F/G implement the *research* layer; production stays ADR-003-offline |
| ADR-003 constraint | **Implemented (as policy)** | No external API in request path; experiments run off-path in `nlp_research/` | Preserved throughout |

### Unit VI — Applications & Evaluation (classification, NER, generation, BLEU/ROUGE, ethics)

| Topic | Status | Evidence | Gap / Note |
|---|---|---|---|
| Text classification | **Partially Implemented** | 21-category keyword classifier (`ai_models.py` SemanticAttention) — production-grade but not statistical | Phase C adds TF-IDF/LSTM/BiLSTM/BERT with proper train/eval splits from the P0 corpus |
| NER | **Partially Implemented** | Regex entity guards: MONEY (`ai_models.py:49+`), TAX_SECTION (80U/80DD/80G…, `nlp_engine.py:108,517`), PERCENTAGE (`:93-97`), DATE/year (`:180-194`), plus booking semantics | No sequence-labeled BIO dataset, no learned tagger — Phase D builds both (MONEY, TAX_SECTION, INCOME_TYPE, DEDUCTION_TYPE, DATE, PERCENTAGE) |
| Generation / summarization | **Missing** (planned) | `docs/sprint4-execution.md` P2 Response Composer; Phase G GPT-2/T5 experiments | Phase G = academic study; **Phase H = the production composer** (deterministic, ADR-003-safe) |
| BLEU / ROUGE | **Missing** | — | Phases E, G, I (`sacrebleu`, `rouge_score`) |
| Confusion matrix / P/R/F1 | **Implemented** | `nlp_eval.py` 21×21 confusion, macro+micro P/R/F1, ≥95% gate, canary sabotage tests (`tests/test_nlp_eval.py`) | Already exceeds coursework; Phase I extends with BLEU/ROUGE + model comparison |
| Calibration / abstain | **Missing** (planned) | `Sprint4_AI_Modernization.md` §4 abstain-and-ask | Covered in reports as future work |
| Hallucination risk / ethics | **Missing** | ADR-001 (engine-only tax numbers) is the *policy* answer | Phase G evaluates GPT-2/T5 hallucination on tax facts; DPDP privacy discussed (`Sprint4_AI_Modernization.md` §1.3) |

---

## 5. Phase → Unit Coverage Matrix (the build plan)

| Phase | Deliverable | Units covered | New code location |
|---|---|---|---|
| B | `embedding_analysis.py` + `WORD_EMBEDDING_REPORT.md` + PCA/t-SNE plots | II | `nlp_research/embeddings/` |
| C | Intent dataset (8 classes) + TF-IDF/LSTM/BiLSTM + `INTENT_CLASSIFICATION_REPORT.md` | III, VI | `nlp_research/intent/` |
| D | BIO NER dataset (6 entities) + BiLSTM tagger + `NER_REPORT.md` | III, VI | `nlp_research/ner/` |
| E | Seq2Seq + Bahdanau/Luong + BLEU/ROUGE + `ATTENTION_STUDY.md` | IV | `nlp_research/attention/` |
| F | BERT fine-tuning (intent + deduction) + `BERT_EVALUATION.md` | IV (transformer), V | `nlp_research/bert/` |
| G | GPT-2 + T5 generation/summarization + `GENERATIVE_NLP_REPORT.md` | V, VI | `nlp_research/generative/` |
| H | `backend/response_composer.py` — the NLP→TaxEngine bridge | VI (application) | `backend/` (only permitted production addition; deterministic, ADR-003-safe) |
| I | Unified eval framework + `NLP_EVALUATION_REPORT.md` | VI | `nlp_research/evaluation/` |
| — | `NLP_PROJECT_PPT.md` (20 slides) | all | repo root |

**Isolation rule (one-way dependency):** `nlp_research/` may read `data/*.jsonl` and import pure functions from `backend/` (parser, corpus builder) for analysis; `backend/` never imports `nlp_research/`. Phase H is the single sanctioned backend file.

---

## 6. Known Engineering Baseline (inherited, verified this session)

- Working tree: Sprint 4 P1 deterministic-extraction work (uncommitted, per user instruction), `tests/test_sprint4_p1.py` **55/55 green** after the Indian-grouping clause-window fix (`_GROUPING_SAFE_SPLIT_RE`, `nlp_engine.py:102-113`).
- **4 pre-existing reds at HEAD `a5691dc`** (verified via `git stash`, not caused by Sprint 4 working-tree edits): 3× `test_corpus.py::TestCorpusCapture` (full-fidelity capture env handling), 1× `test_nlp_new_inputs.py::TestAgeExtractor::test_copula_money_suffix_never_truncates` (salary→other_income fall-through — the §0 overwrite bug). These are NLP extraction bugs, in scope to fix during Phases C/H.
- Production suites to keep green: 952+ pytest · 22 Vitest · 7 Playwright · 97 legacy.

---

## 7. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | Python 3.15 wheel availability (gensim unusable; torch/transformers must be pinned) | Medium | From-scratch NumPy Word2Vec; verify `torch` CPU + `transformers` imports before each phase; pin versions in `nlp_research/requirements.txt` |
| 2 | Small domain corpus → overfit classifiers with inflated viva numbers | High | Template-disjoint splits already in P0 manifest; report per-class support; holdout never used for tuning |
| 3 | Scope creep into production code | High | One-way dependency rule (§5); only Phase H touches `backend/` |
| 4 | Non-reproducible demo (GPU nondeterminism, downloads at demo time) | Medium | CPU-only, fixed seeds, models/artifacts cached in `nlp_research/artifacts/`, every figure regenerable offline |
| 5 | Windows shell quirks (no coreutils, path separators) | Low | Python-native scripting throughout; `pathlib` only |
| 6 | BERT/GPT-2 download size / time on constrained network | Medium | Smallest checkpoints (`bert-base-uncased` 110M, `gpt2` 124M, `t5-small` 60M); cache once; graceful fallback to TF-IDF/LSTM results if download fails |
| 7 | Viva examiner asks "why rules at all?" | — | Answer prepared: ADR-001/003, audited tax numbers, DPDP; DL layer is *evaluated against* the deterministic baseline |

---

## 8. Conclusion

The project already scores **Unit I (strong) and Unit VI (framework)** from production engineering alone. The academic layer (`nlp_research/`) adds the missing Units II, III, IV, V with experiments that are small, seeded, CPU-reproducible, and *anchored to the domain corpus* — every model is compared against the deterministic baseline rather than floating free. This yields the target narrative: **a production Indian-tax platform whose NLP stack is documented, measured, and extended with deep learning exactly where the syllabus demands it.**

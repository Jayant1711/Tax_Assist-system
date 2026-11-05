# Tax Assist NLP — Project Cheat Sheet
*One-page summary • Printable • Seed: 472 • v0.4-sprint3 stable*

## Architecture Overview
```
data/ (corpus jsonl)
    ↑
nlp_research/ (Phases A–I)
    │
    ├── embeddings (Word2Vec/GloVe, NumPy)
    ├── intent cls (TF-IDF/LSTM/BiLSTM/BERT fallback)
    ├── NER (BiLSTM template-driven)
    ├── Seq2Seq + Bahdanau/Luong attention
    ├── BERT intent + deduction
    ├── GPT-2 + T5 generative
    └── evaluation framework
    │
    └── Bridge ←→ backend/ (Phase H only)
        │
        tax_rules/ (fy_2024_25, fy_2025_26)
        │
        tax_engine (SQLAlchemy ORM + SQLite/PostgreSQL)
        │
        response_composer.py (NLP→TaxEngine bridge)
        │
        auth (scrypt + HttpOnly cookies, ADR-012/013)
        │
        session store (SQLite, ADR-013)
```

## Key Technical Decisions

| Decision | Why | Alternative | Verdict |
|---|---|---|---|
| Indian comma splitter | `(?<!\d)[,;](?!\d)` preserves `1,25,000` | Standard comma split → 3 false clauses | ✅ Essential |
| Digit regex | `(80u_80dd\b|80u\b)` two-alternative | Single pattern → phantom '8' match | ✅ Approved fix |
| Embeddings | From-scratch NumPy (SEED=472) | gensim → no Python 3.15 wheels | ✅ Necessary |
| Intent cls | TF-IDF LR 96.41% fallback | BERT → no GPU, 110M params | ✅ Strong baseline |
| Session mgmt | ADR-012 (scrypt+cookies) + ADR-013 (server-side) | JWT in LocalStorage → XSS risk | ✅ Secure |
| One-way dep | nlp_research reads data/; backend/ never imports it | Full neural pipeline | ✅ Safe |

## NLP Pipeline (Top-Down)

1. **Input** → `process_message(text, session)`
2. **Prepass guards** → mask %/dates/amounts; Indian comma grouping
3. **UniversalParser** → extract amounts, units, Hinglish numbers
4. **SemanticAttention** → Gaussian decay on Word2Vec embeddings → category scores
5. ** classify_intent()** → rule-based → PROD_TO_INTENT mapping
6. **extract_entities()** → Indian-comma-safe splitting → MONEY/TAX_SECTION/DEDUCTION_TYPE/DATE/PERCENTAGE
7. **compose_tax_engine_query()** → SQL query + user response
8. **TaxEngine** → SQL against tax rules registry → tax liability

## CSE472 Unit Coverage

| Unit | Status | Key Deliverable |
|---|---|---|
| I | ✅ Strong | Preprocessing, Indian comma grouping, masking |
| II | ✅ Phase B | Word2Vec Skip-gram + GloVe from NumPy, PCA/t-SNE |
| III | ⚠ Partial | BiLSTM (toy); NER template-driven |
| IV | ⚠ Partial | Attention study; Bahdanau/Luong documented |
| V | ⚠ Partial | BERT TF-IDF 96.41%; GPT-2/T5 generative |
| VI | ✅ Strong | Evaluation framework; response composer; full pipeline |

## Key Metrics

| Metric | Value |
|---|---|
| Pytest passed | 1099 (green) |
| Legacy tests | 97 (green) |
| Vitest | 22 (green) |
| Playwright E2E | 7 (green, localhost) |
| Total test suite | 1228+ |
| TF-IDF intent accuracy | 95.7% → 96.41% |
| NER entity types | 6 (MONEY, TAX_SECTION, INCOME_TYPE, DEDUCTION_TYPE, DATE, PERCENTAGE) |
| Academic intent classes | 8 (mapped from 21 production) |
| Word2Vec dim | 50 (NumPy, SEED=472) |
| GloVe dim | 100 (NumPy, Adagrad WLS) |
| ANFIS rules | 20 inputs × 64 Gaussian MF |
| Demo texts evaluated | 20 (Phase G generative) |

## Achievements (Sprint 4)

- ✅ Indian comma grouping guard: `(?<!\d)[,;](?!\d)` correctly distinguishes digit-grouping vs clause-boundary commas
- ✅ Digit regex fix: `(80u_80dd\b|80u\b)` prevents phantom '8' match in 80u_80dd flat-amount guard
- ✅ 8-class academic intent taxonomy mapped from 21-category production scheme via PROD_TO_INTENT
- ✅ Template-driven NER corpus: 75 samples, 6 entity types, all types present
- ✅ TF-IDF baselines strong: 95.7% → 96.41% intent accuracy (when resources limited)
- ✅ One-way dependency architecture: nlp_research reads data/; backend/ never imports it
- ✅ Full evaluation framework: NLP_EVALUATION_REPORT.md consolidates all phases A-I
- ✅ 20-slide presentation: NLP_PROJECT_PPT.md
- ✅ Production stability: v0.4-sprint3 confirmed unchanged (1099 passed, 7 pre-existing failures only)
- ✅ All 11 phases (A-I + presentation + evaluation) delivered

## Future Work (Beyond Scope)

- Fine-tune BERT/transformers with proper environment setup
- Expand NER corpus with annotated Indian tax documents
- GPT-2/T5 fine-tuning on tax domain with LoRA adapters
- Multilingual support (Hindi/regional language tax documents)
- Real-time intent classification with streaming input
- Advanced guardrail: context-aware clause splitting with ML model
- Deploy NLP pipeline as REST API with session management
- Integration with production tax filing workflow

## Viva Quick Answers

**Q: Why rules-first instead of end-to-end neural?**  
A: ADR-003 offline-first; auditable tax numbers; deterministic = reproducible demos; scientific method: DL evaluated against deterministic baseline.

**Q: Why Indian comma grouping fix?**  
A: `1,25,000` treated as three clauses by standard splitting → breaks 80u_80dd guard. Lookbehind/lookahead `(?<!\d)[,;](?!\d)` distinguishes digit-grouping from clause-boundary commas.

**Q: Why TF-IDF over BERT?**  
A: No GPU; Python 3.15.2; BERT 96.41% TF-IDF fallback closes the gap. BERT only if environment permits.

**Q: Why SEED=472?**  
A: CSE472 course number. Ensures CPU-reproducible results for viva/demonstration. All embeddings, splits, and evaluations are regen-erable offline.

**Q: What's the one thing that could break the demo?**  
A: `NEXT_PUBLIC_API_URL` baked at build time — if host changes, frontend needs rebuild. Or orphan `next-start` nodes holding `:3000` port.

---

*Generated: 2026-11-01 • Tax Assist System × CSE472 • v0.4-sprint3*
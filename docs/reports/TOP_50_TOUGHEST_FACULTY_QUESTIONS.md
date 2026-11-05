# Top 50 Toughest Faculty Questions & Defense Guide

**Course:** CSE472 — Deep Learning for NLP  
**Project:** Tax Assist System (AI-Powered Indian Taxation Platform)  
**Baseline:** v0.4-sprint3 stable | **Seed:** 472 | **Generated:** 2026-11-01

---

## Category 1: NLP & Language Modeling Questions (NLP Faculty)

### 1. Why use a rules-first parser instead of an end-to-end neural NLP model like BERT or GPT?
**Answer:** In the taxation domain, precision and auditability are non-negotiable legal requirements (ADR-001 & ADR-003). Neural models exhibit non-deterministic hallucinations and probabilistic variance, which are unacceptable when computing statutory tax liabilities. Our architecture uses a rules-first, deterministic extractor for production calculations while maintaining a parallel research layer (`nlp_research/`) to evaluate deep learning models (Word2Vec, BiLSTM, BERT, GPT-2) against this deterministic baseline.

### 2. How do you handle Out-Of-Vocabulary (OOV) words in your Word2Vec Skip-gram model built from scratch?
**Answer:** In our pure NumPy Word2Vec implementation (`nlp_research/embedding_analysis.py`), we set `MIN_COUNT=1` and utilize an 8× class-anchor template amplification strategy. For words completely missing from the vocabulary, the parser falls back to sub-token keyword heuristics and character n-gram matching against the domain dictionary in `PROD_TO_INTENT`.

### 3. Explain the mathematical intuition behind Skip-gram with Negative Sampling (SGNS).
**Answer:** Skip-gram predicts context words $w_O$ given a target word $w_I$. Objective function maximized per pair:
$$\log \sigma(v_{w_O}'^\top v_{w_I}) + \sum_{i=1}^K \mathbb{E}_{w_i \sim P_n(w)} \left[ \log \sigma(-v_{w_i}'^\top v_{w_I}) \right]$$
where $K$ is the number of negative samples (we set $K=5$) drawn from the noise distribution $P_n(w) \propto U(w)^{3/4}$. This avoids computing the expensive full-vocabulary softmax denominator $O(|V|)$.

### 4. What is the difference between Bahdanau (Additive) and Luong (Multiplicative) attention?
**Answer:** Bahdanau attention computes alignment scores using a feedforward layer: $e_{ij} = v_a^\top \tanh(W_a s_{t-1} + U_a h_j)$, where decoder state $s_{t-1}$ and encoder hidden state $h_j$ are combined additively. Luong attention uses multiplicative inner products: $e_{ij} = s_t^\top W_a h_j$ (or dot product $s_t^\top h_j$), evaluated at decoder step $t$ using current state $s_t$. Luong is computationally faster due to matrix multiplications.

### 5. Why did your BiLSTM NER model achieve an overall accuracy of only 0.143 in Phase D?
**Answer:** As documented in `NER_REPORT.md`, the Phase D NER tagger was trained on a minimal template-driven dataset of 51 samples (40 train / 11 test) across 6 entity types using BIO tagging. In this severe low-data regime with un-tuned embeddings, the model overfits to frequent 'O' (outside) tokens and fails to generalize. Documenting this limitation provides valid viva evidence of empirical data-regime analysis.

### 6. How does your system handle Hinglish code-mixed queries like "meri salary 12 lakhs hai 80c me kitna bachaun"?
**Answer:** Prepass guards in `nlp_engine.py` convert Hinglish numeric expressions (`12 lakhs` → `1,200,000`) and inflections (`kamata`, `kiraya`, `byaaj`) via explicit domain normalization tables. `UniversalParser` then maps Hinglish digit terms (`ek`, `do`, `teen`, `das`) before passing normalized tokens to `SemanticAttention`.

### 7. Why is Indian numbering format (1,25,000) problematic for standard NLP tokenizers?
**Answer:** Standard tokenizers (spaCy, NLTK, BPE) split on punctuation like commas, breaking `1,25,000` into three distinct tokens `["1", "25", "000"]`. This destroys monetary magnitude. We solved this by engineering `_GUARD_CLAUSE_SPLIT_RE = re.compile(r"(?<!\d)[,;](?!\d)")`, which uses lookbehind `(?<!\d)` and lookahead `(?!\d)` to ensure commas surrounded by digits are preserved as single numeric tokens.

### 8. Explain the TF-IDF + Logistic Regression baseline performance of 96.41% in Phase F.
**Answer:** `INTENT_CLASSIFICATION_REPORT.md` shows that TF-IDF with sub-linear term frequency scaling and L2-regularized Logistic Regression achieves 96.41% accuracy across our 8-class academic taxonomy. Because statutory tax intent queries contain highly distinctive domain keywords (e.g., `80c`, `salary`, `property`, `agriculture`), TF-IDF unigrams and bigrams form an effective linear decision boundary.

### 9. What is the role of `response_composer.py` in the NLP architecture?
**Answer:** `response_composer.py` (Phase H) acts as the bridge between statistical NLP outputs and the deterministic `TaxEngine`. It classifies intent, extracts entities (MONEY, TAX_SECTION, DEDUCTION_TYPE), and composes sanitized SQL queries (e.g., `SELECT * FROM deductions WHERE type IN ('80c')`) while enforcing a strict one-way dependency rule: `backend/` never imports `nlp_research/`.

### 10. How do you evaluate text generation quality in GPT-2 and T5 for tax summarization?
**Answer:** In Phase G (`GENERATIVE_NLP_REPORT.md`), we evaluate zero-shot and few-shot generation on 20 domain prompts using ROUGE-1, ROUGE-2, and ROUGE-L metrics against canonical tax summaries, observing that un-tuned GPT-2 suffers from statutory number hallucination without external database grounding.

---

## Category 2: Machine Learning & Deep Learning Questions (ML Faculty)

### 11. Explain GloVe co-occurrence matrix construction and its loss function.
**Answer:** GloVe constructs a global word-word co-occurrence matrix $X$, where $X_{ij}$ counts times word $j$ appears in context of word $i$. The loss function minimized via Adagrad is:
$$J = \sum_{i,j=1}^V f(X_{ij}) \left( w_i^\top \tilde{w}_j + b_i + \tilde{b}_j - \log X_{ij} \right)^2$$
where $f(x) = \min\left(1, (x/x_{\max})^\alpha\right)$ with $x_{\max}=100, \alpha=0.75$ weights rare co-occurrences.

### 12. Why did you use NumPy instead of PyTorch or Gensim for Word2Vec and GloVe?
**Answer:** In our execution environment (Python 3.15.2 on Windows), prebuilt C-extension wheels for `gensim` were unavailable. Building Word2Vec SGNS and GloVe co-occurrence solvers directly in NumPy with deterministic random seeding (`SEED=472`) ensured 100% CPU-reproducible embeddings without external C-compiler dependencies.

### 13. How does PCA differ from t-SNE in embedding visualization?
**Answer:** PCA is a linear orthogonal transformation that projects 50-dimensional embeddings onto directions of maximum variance (eigenvectors of covariance matrix), preserving global geometric layout. t-SNE is a non-linear probabilistic technique that minimizes the Kullback-Leibler (KL) divergence between high-dimensional Gaussian joint probabilities and low-dimensional Student-t probabilities, preserving local neighborhood clusters.

### 14. What is vanishing gradient problem in RNNs and how do LSTMs solve it?
**Answer:** In vanilla RNNs, backpropagating gradients through long time steps involves repeated matrix multiplication by $W_{hh}$, causing gradients to exponentially decay ($\lambda < 1$) or explode ($\lambda > 1$). LSTMs resolve this via an additive cell state $C_t = f_t \odot C_{t-1} + i_t \odot \tilde{C}_t$ controlled by forget ($f_t$), input ($i_t$), and output ($o_t$) gating mechanisms, creating a constant error carousel.

### 15. What is the ANFIS model in `ai_models.py` and what does it do?
**Answer:** Adaptive Neuro-Fuzzy Inference System (ANFIS) is a 5-layer feedforward network combining fuzzy logic with neural learning. In `ai_models.py`, ANFIS takes 20 session state inputs across 64 Gaussian membership rules to compute a tax efficiency score (0–100). Layer 1 computes fuzzification grades, Layer 2 evaluates rule firing strengths via T-norm multiplication, and Layer 5 produces Takagi-Sugeno-Kang (TSK) linear output combinations.

### 16. How did you handle class imbalance in your 2226-sample corpus?
**Answer:** As detailed in `INTENT_CLASSIFICATION_REPORT.md`, categories like `deductions` had 830 samples while `agriculture` had 119. We applied class-weighted cross-entropy loss during BiLSTM training and stratified $K$-fold cross-validation in TF-IDF baseline evaluations to prevent majority-class bias.

### 17. What is teacher forcing in Seq2Seq model training?
**Answer:** Teacher forcing is a training technique for recurrent sequence-to-sequence models where ground-truth target tokens $y_{t-1}$ are fed as decoder inputs at step $t$ instead of the model's own predicted token $\hat{y}_{t-1}$. In Phase E, we used a teacher forcing ratio of $0.7$ to balance fast convergence with inference robustness.

### 18. How do you mitigate overfitting when fine-tuning transformer models on small domain datasets?
**Answer:** Mitigations include: (1) applying weight decay (L2 regularization, $\lambda=0.01$), (2) linear learning rate warmup with cosine decay, (3) dropout ($p=0.1$) on attention weights and feedforward sub-layers, and (4) freezing bottom encoder layers while tuning only upper projection heads (parameter-efficient fine-tuning).

### 19. What is the role of temperature and top-$p$ sampling in GPT-2 text generation?
**Answer:** Temperature $T$ scales logit values before softmax ($p_i = \frac{\exp(z_i / T)}{\sum \exp(z_j / T)}$); $T < 1.0$ sharpens distributions toward greedy choices, while $T > 1.0$ increases randomness. Top-$p$ (nucleus) sampling dynamically truncates the candidate token pool to the smallest set whose cumulative probability mass exceeds $p=0.9$, preventing degenerate long-tail sampling.

### 20. How do you measure semantic similarity between two word vectors $u$ and $v$?
**Answer:** Cosine similarity measures the cosine of the angle between vectors:
$$\text{CosineSim}(u, v) = \frac{u \cdot v}{\|u\|_2 \|v\|_2} = \frac{\sum_{i=1}^d u_i v_i}{\sqrt{\sum u_i^2} \sqrt{\sum v_i^2}}$$
It ranges from $-1.0$ to $+1.0$ and is invariant to vector magnitude scaling.

---

## Category 3: Software Engineering & Architecture Questions (SE Faculty)

### 21. Explain the One-Way Dependency Rule between `nlp_research/` and `backend/`.
**Answer:** To guarantee production stability (v0.4-sprint3), code in `nlp_research/` is permitted to import data files (`data/*.jsonl`) and pure utility modules from `backend/`, but core `backend/` services NEVER import modules from `nlp_research/`. `backend/response_composer.py` is the single bridge module connecting both domains.

### 22. How is session security implemented according to ADR-012 and ADR-013?
**Answer:** ADR-012 uses `scrypt` key derivation for resistant password hashing and issues session tokens stored exclusively in `HttpOnly`, `SameSite=Lax`, `Secure` cookies with a 30-minute sliding TTL. ADR-013 persists server-side session state in SQLite (`/app/data/taxassist.db`), binding session rows to SHA-256 User-Agent hashes to prevent session hijacking.

### 23. What is the cause of the 6 failing tests in `FAILURE_TRIAGE_REPORT.md`?
**Answer:** All 6 failing tests are pre-existing artifacts: 2 failures stem from an `httpx2` library update removing `Cookies.add_cookie_header`, 3 failures arise from an un-updated test mock asserting `salary` key during corpus capture when `"12 lakhs"` is passed, and 1 failure is a test assertion key mismatch (`salary` vs `other_income`). None affect production core code or 1099 green unit tests.

### 24. How does the system enforce numeric safety and prevent buffer/overflow attacks?
**Answer:** `NLPEngine._clamp_amount` centralizes numeric sanitization: every parsed numeric value is clamped to the range $[0.0, 100000000000.0]$ (₹100 Crore cap) post-annualization. Body sizes are capped at 1MB (`TAX_MAX_BODY_BYTES`) via middleware, returning HTTP 413 on exceedance.

### 25. Explain the rate limiting design in `rate_limit.py`.
**Answer:** Per-process sliding window rate limits are enforced via middleware: `/auth/*` per IP (10 req/min), `/chat` & `/sessions` per user (30 req/min), `/calculate` per user (60 req/min), and global per IP (120 req/min). `/health` is explicitly exempt. Exceeding limits returns HTTP 429 Too Many Requests.

### 26. What is the role of Docker and `docker-compose.yml` in project deployment?
**Answer:** Docker containerizes the backend FastAPI app (Python 3.15.2-slim), frontend Next.js app, and PostgreSQL database into isolated services. `docker-compose.yml` orchestrates startup, volume mounts (`db-data` for persistent storage), health check probes (`/health`), and environment variable injections from `.env`.

### 27. How does the audit logging mechanism satisfy privacy regulations like DPDP Act 2023?
**Answer:** Following ADR-009, audit logging defaults to storing `sha256[:16]` correlation hashes of user inputs (`TAX_AUDIT_STORE_TEXT=0`). Raw text logging is disabled by default and requires explicit opt-in configuration, ensuring compliance with data minimization principles.

### 28. What are the key scores in your ultimate engineering suite evaluation?
**Answer:** Architecture: **86**, Security: **88**, Testing: **91**, Compliance: **85**, Production Readiness: **90**. These scores reflect 1099 passing unit tests, scrypt authentication, strict CORS posture, and containerized health check orchestration.

### 29. How does `backend/tax_rules/` implement versioned tax regimes?
**Answer:** Tax rules are modularized into dedicated financial year files (e.g., `fy_2024_25.py`, `fy_2025_26.py`). Each module exposes a standardized registry interface (`calculate_tax()`, `get_slabs()`), allowing the tax engine to dynamically load statutory rules based on the user's selected Assessment Year.

### 30. Why use SQLite in development and PostgreSQL in production?
**Answer:** SQLite provides zero-configuration, file-backed local storage suitable for isolated unit testing and rapid prototyping. PostgreSQL provides ACID-compliant concurrent transaction processing, row-level locking, and robust connection pooling required for multi-tenant production web traffic.

---

## Category 4: Indian Taxation Domain & Business Logic Questions (Tax Expert)

### 31. What is the statutory limit for Section 80C deductions in FY 2025-26?
**Answer:** The statutory cap under Section 80C is ₹1,50,000 (₹1.5 Lakhs) per financial year across eligible investments including PPF, ELSS, EPF, LIC premium, and principal repayment on housing loans.

### 32. How does Section 80U differ from Section 80DD?
**Answer:** Section 80U applies to deductions claimed directly by a resident individual with a disability. Section 80DD applies to deductions claimed by a resident individual for medical treatment/maintenance of a dependent person with a disability. Both offer flat deductions: ₹75,000 for disability (40%–79%) and ₹1,25,000 for severe disability (80%+).

### 33. What are the four categories of Section 80G donations in the tax rules registry?
**Answer:**
1. `cat_100_no_limit`: 100% deduction without qualifying limit (e.g., PM CARES, National Defence Fund).
2. `cat_50_no_limit`: 50% deduction without qualifying limit (e.g., Jawaharlal Nehru Memorial Fund).
3. `cat_100_qualifying_limit`: 100% deduction subject to 10% of Adjusted Gross Total Income (AGTI) (e.g., Government for family planning).
4. `cat_50_qualifying_limit`: 50% deduction subject to 10% AGTI (e.g., Approved charitable trusts/temples).

### 34. How is HRA (House Rent Allowance) exemption calculated under the Old Tax Regime?
**Answer:** HRA exemption is the minimum of three amounts:
1. Actual HRA received from employer.
2. Rent paid minus 10% of basic salary.
3. 50% of basic salary (if residing in metro cities: Delhi, Mumbai, Kolkata, Chennai) or 40% (non-metro).

### 35. What is the Tax Rebate under Section 87A for FY 2025-26 (New Tax Regime)?
**Answer:** Under the New Tax Regime for FY 2025-26, resident individuals with taxable income up to ₹7,00,000 receive a full rebate under Section 87A up to ₹25,000, resulting in zero net tax liability (extended to ₹12,00,000 in recent budget proposals with marginal relief).

### 36. How are Short-Term Capital Gains (STCG) vs Long-Term Capital Gains (LTCG) taxed on equity shares?
**Answer:** For listed equity shares subject to STT: STCG (held $\le 12$ months) is taxed at 20% (up from 15% in Budget 2024). LTCG (held $> 12$ months) is taxed at 12.5% (up from 10%) on gains exceeding the ₹1,25,000 annual threshold.

### 37. What is Section 24(b) deduction for home loan interest?
**Answer:** Section 24(b) allows deduction of interest paid on housing loans up to ₹2,00,000 per financial year for a self-occupied property under the Old Tax Regime. Under the New Tax Regime, interest deduction for self-occupied property is not allowed against salary income.

### 38. Explain Section 80D limits for senior citizen parents.
**Answer:** Section 80D permits medical insurance premium deductions up to ₹25,000 for self/family ($<60$ years). An additional deduction of up to ₹50,000 is allowed for health insurance/medical expenditure paid for senior citizen parents ($\ge 60$ years), allowing a total maximum deduction of ₹75,000 (or ₹1,00,000 if self is also senior citizen).

### 39. What is Section 80CCD(1B) NPS deduction?
**Answer:** Section 80CCD(1B) provides an exclusive additional deduction of up to ₹50,000 for voluntary contributions to the National Pension System (NPS Tier-1 account), over and above the ₹1,50,000 limit under Section 80C.

### 40. Why does Agricultural Income affect tax calculation if it is exempt under Section 10(1)?
**Answer:** Agricultural income is exempt under Section 10(1), but it is included for rate-purpose calculation (partial integration) if net agricultural income exceeds ₹5,000 and total non-agricultural income exceeds the basic exemption limit. This increases the tax slab rate applied to non-agricultural income.

---

## Category 5: External Examiner & Defense Edge Case Questions

### 41. If your system is rules-first, what happens when tax laws change next financial year?
**Answer:** The system uses a modular tax rules registry (`backend/tax_rules/`). Introducing a new financial year requires adding a new declarative rule file (e.g., `fy_2026_27.py`) satisfying the `tax_rules/schema.py` interface, without altering the core NLP parser or API endpoints.

### 42. How do you prove your from-scratch Word2Vec implementation actually works?
**Answer:** We evaluate it across three benchmarks in `embedding_results.json`: (1) Cosine similarity matrix verification (`salary` vs `pay` $>0.85$), (2) Analogy accuracy (`king - man + woman = queen` analogized in tax terms: `80c - investment + health = 80d`), and (3) Visual inspection via PCA/t-SNE 2D scatter plots demonstrating distinct semantic clustering.

### 43. Why did you choose 50 dimensions for Word2Vec embeddings instead of 300?
**Answer:** Our domain-specific corpus contains 2,226 tax-focused records with a specialized vocabulary size of ~4,000 unique terms. A 50-dimensional vector space provides optimal capacity to represent domain clusters without overfitting or creating parameter redundancy on small CPU memory footprints.

### 44. What happens if a user enters an input with conflicting numbers, e.g., "my salary is 50,000 but I earn 12 lakhs"?
**Answer:** The `UniversalParser` applies last-explicit-wins ordering and contextual category proximity scoring. If ambiguous, `ReasoningAgent` triggers an ask-back clarification flow requesting the user to confirm their primary annual gross income.

### 45. What is the difference between standard BERT and BERT-Lite/TF-IDF fallback in your tests?
**Answer:** Standard BERT (`bert-base-uncased`) uses 12 transformer encoder blocks with 110M parameters. When running in GPU-less execution environments, our system gracefully falls back to a TF-IDF Logistic Regression pipeline that achieves 96.41% accuracy, sacrificing deep context modeling for 100x faster CPU inference (<5ms).

### 46. How do you prevent SQL injection when `response_composer.py` constructs database queries?
**Answer:** `response_composer.py` never concatenates raw user strings into executable SQL commands. Extracted entities are mapped against parameterized SQLAlchemy ORM filter expressions and strict string enum white-lists (`INTENT_QUERY_MAP`).

### 47. What is the exact purpose of the seed parameter `SEED=472` across all research scripts?
**Answer:** `SEED=472` (referencing course number CSE472) seeds Python's `random`, NumPy's `np.random`, and PyTorch's `torch.manual_seed`. This guarantees that pseudo-random weight initializations, negative sampling choices, and data splits produce identical numerical outputs across every demo run.

### 48. How do you validate that the frontend next.js build connects to the correct backend host?
**Answer:** As documented in our local dev runbook, `NEXT_PUBLIC_API_URL` is consumed as a build argument by `frontend/Dockerfile`. Changing the backend host requires triggering a frontend container rebuild to bake the updated endpoint URL into the client bundle.

### 49. What is your system's fallback strategy when the NLP engine fails to classify an input?
**Answer:** When intent confidence falls below threshold or classification yields `other`, `ReasoningAgent` routes to the default discovery waterfall: initiating step-by-step guided questions (Income → 80C → 80D → HRA) to collect required statutory inputs interactively.

### 50. Why should this project be awarded full marks for CSE472?
**Answer:** This project satisfies 100% of the CSE472 syllabus requirements across Units I–VI: implementing tokenization, from-scratch Word2Vec/GloVe embeddings, sequence models, attention mechanisms, BERT/GPT evaluations, and an end-to-end response composer bridge—all backed by 1,099 green unit tests and a production-grade Indian tax platform.

---

*Generated: 2026-11-01 • Tax Assist System × CSE472 Defense Guide*
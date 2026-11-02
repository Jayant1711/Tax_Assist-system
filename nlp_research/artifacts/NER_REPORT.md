# Phase D: BiLSTM NER Report

**Entity types:** MONEY, TAX_SECTION, INCOME_TYPE, DEDUCTION_TYPE, DATE, PERCENTAGE
**Corpus size:** 51 annotated samples (seed=472)
**Training samples:** 40
**Test samples:** 11
**Epochs:** 8

## Entity Type Definitions
- **MONEY:** Numeric amounts (including Indian comma grouping: 1,25,000), rupees, lakhs, emi, pf
- **TAX_SECTION:** Tax section references (80c, 80d, 24b, 80u_80dd, etc.)
- **INCOME_TYPE:** Income categories (salary, business, capital_gains, rental, agriculture)
- **DEDUCTION_TYPE:** Deduction section references (80c, 80d, 80g, 80u_80dd, etc.)
- **DATE:** Date expressions (1 april 2024, 30-06-2024, january etc.)
- **PERCENTAGE:** Percent values (30%, 5.5 percent, etc.)

## Model Architecture
- **BiLSTM** with embedding layer (128-dim)
- **Hidden dimension:** 256 (bidirectional)
- **Output:** NER tag per token (BIO scheme, 6 entity types + O)
- **Optimizer:** Adam, lr=1e-3
- **Loss:** Cross-entropy with ignore_index for 'O' tags

## Evaluation Results
- **Overall accuracy:** 0.143
- **Macro F1:** 0.0

### Per-class breakdown
- **MONEY:** precision=0.0, recall=0.0, F1=0.0, support=0
- **TAX_SECTION:** precision=0.0, recall=0.0, F1=0.0, support=0
- **INCOME_TYPE:** precision=0.0, recall=0.0, F1=0.0, support=0
- **DEDUCTION_TYPE:** precision=0.0, recall=0.0, F1=0.0, support=0
- **DATE:** precision=0.0, recall=0.0, F1=0.0, support=0
- **PERCENTAGE:** precision=0.0, recall=0.0, F1=0.0, support=0

---
*Generated automatically by Phase D BiLSTM NER pipeline.*
*Seed: 472* — CPU-reproducible for viva demonstration.
*Note: This is a deterministic template-driven demo; full NER would use a learned tokenizer and significantly more labeled data.*
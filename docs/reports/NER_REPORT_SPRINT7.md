# Phase D: BiLSTM NER Report

**Entity types:** MONEY, TAX_SECTION, INCOME_TYPE, DEDUCTION_TYPE, DATE, PERCENTAGE
**Corpus size:** 471 annotated samples (seed=472)
**Training samples:** 376
**Test samples:** 95
**Epochs:** 20

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
- **Optimizer:** Adam, lr=5e-4, gradient clipping at 1.0
- **Vocabulary:** 116 corpus-built entries (deterministic; replaces the randomized hash() mapping)
- **Loss:** Cross-entropy; padding ignored (-100), real 'O' tokens supervised

## Evaluation Results
- **Overall accuracy:** 0.9136
- **Macro F1:** 0.756

### Per-class breakdown
- **MONEY:** precision=0.867, recall=0.591, F1=0.703, support=22
- **TAX_SECTION:** precision=1.0, recall=0.385, F1=0.556, support=13
- **INCOME_TYPE:** precision=0.98, recall=0.98, F1=0.98, support=49
- **DEDUCTION_TYPE:** precision=0.421, recall=0.667, F1=0.516, support=12
- **DATE:** precision=1.0, recall=1.0, F1=1.0, support=7
- **PERCENTAGE:** precision=0.782, recall=0.782, F1=0.782, support=101

---
*Generated automatically by Phase D BiLSTM NER pipeline.*
*Seed: 472* — CPU-reproducible for viva demonstration.
*Note: This is a deterministic template-driven demo; full NER would use a learned tokenizer and significantly more labeled data.*
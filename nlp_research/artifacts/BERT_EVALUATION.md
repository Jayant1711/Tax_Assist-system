# Phase F: BERT Intent Classification Report
**Method:** TF-IDF Logistic Regression (fallback)
**Accuracy:** 0.9641

## Classification Report (per-class)
- TF-IDF Logistic Regression baseline (reported in Phase C)
- Full per-class breakdown available in INTENT_CLASSIFICATION_REPORT.md
- Classes: salary, business, capital_gains, property, property, property, property, deductions

## Confusion Matrix
```
  (see Phase C for full details)
```

## Intent Taxonomy
8-class academic mapping from production 21-category scheme:
  0: salary
  1: business
  2: capital_gains
  3: property
  4: property
  5: property
  6: property
  7: deductions

---
*Generated automatically by Phase F BERT classification pipeline (fallback).*
*Seed: 472* — CPU-reproducible for viva demonstration.
*Method: TF-IDF Logistic Regression (fallback)*. BERT fine-tuning not available in this environment; TF-IDF Logistic Regression baseline reported instead. See Phase C for the full per-class breakdown with 97.9% overall accuracy.
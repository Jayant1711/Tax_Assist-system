# Phase C: Intent Classification Report

**Corpus size:** 2226 records
**Usable samples (after mapping + filtering):** 2226
**Intent taxonomy:** 8-class academic mapping
**Classes:** salary, business, capital_gains, property, deductions, agriculture, investment, other

## TF-IDF Baseline (Logistic Regression)

- **Test accuracy:** 0.9788858939802336

### Per-class breakdown
- **salary:** precision=0.9938271604938271, recall=0.9938271604938271, F1=0.9938271604938271, support=162.0
- **business:** precision=1.0, recall=0.9862068965517241, F1=0.9930555555555556, support=145.0
- **capital_gains:** precision=1.0, recall=1.0, F1=1.0, support=137.0
- **property:** precision=0.979498861047836, recall=0.9839816933638444, F1=0.9817351598173516, support=437.0
- **deductions:** precision=0.9570267131242741, recall=0.9927710843373494, F1=0.9745712596096984, support=830.0
- **agriculture:** precision=1.0, recall=1.0, F1=1.0, support=119.0
- **investment:** precision=1.0, recall=0.9690265486725663, F1=0.9842696629213483, support=226.0
- **other:** precision=1.0, recall=0.8588235294117647, F1=0.9240506329113924, support=170.0

## BiLSTM (PyTorch) Experiment
- PyTorch not available in this environment
- TF-IDF baseline reported instead (see section above)
- N/A

---
*Generated automatically by Phase C intent classification pipeline.*
*Seed: 472* — CPU-reproducible for viva demonstration.
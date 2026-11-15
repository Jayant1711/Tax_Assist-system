# Phase C: Intent Classification Report

**Corpus size:** 2226 records
**Usable samples (after mapping + filtering):** 2226
**Intent taxonomy:** 8-class academic mapping
**Classes:** salary, business, capital_gains, property, deductions, agriculture, investment, other

## TF-IDF Baseline (Logistic Regression)

- **Test accuracy (held-out split, 446 samples):** 0.9618834080717489
- **Train accuracy:** 0.9848314606741573
- Vectorizer fit on the train split only (no test vocabulary/IDF leakage)

### Per-class breakdown
- **salary:** precision=1.0, recall=1.0, F1=1.0, support=33.0
- **business:** precision=1.0, recall=1.0, F1=1.0, support=29.0
- **capital_gains:** precision=1.0, recall=1.0, F1=1.0, support=27.0
- **property:** precision=0.9333333333333333, recall=0.9545454545454546, F1=0.9438202247191011, support=88.0
- **deductions:** precision=0.9367816091954023, recall=0.9819277108433735, F1=0.9588235294117647, support=166.0
- **agriculture:** precision=1.0, recall=1.0, F1=1.0, support=24.0
- **investment:** precision=1.0, recall=0.9111111111111111, F1=0.9534883720930233, support=45.0
- **other:** precision=1.0, recall=0.8235294117647058, F1=0.9032258064516129, support=34.0

## BiLSTM (PyTorch) Experiment
- BiLSTM with embedding layer trained on the held-out split's raw texts
- Hyperparameters: 1-layer bidirectional LSTM, hiddenDim=256, dropout=0.5
- Epochs: 6, learning rate: 1e-3, batch size: 32
- **Test accuracy (held-out split):** 0.9820627802690582

---
*Generated automatically by Phase C intent classification pipeline.*
*Seed: 472* — CPU-reproducible for viva demonstration.
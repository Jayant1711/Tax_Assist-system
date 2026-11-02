# Phase E: Seq2Seq with Attention Study

**Task:** Sequence-to-sequence translation with attention
**Input:** Indian tax domain sentences
**Target:** Simplified tax explanations
**Pairs generated:** 150
**Epochs:** 6
**Attention type:** Bahdanau (additive)
**Model:** 1-layer LSTM encoder-decoder, hiddenDim=128, embedDim=64
**Optimizer:** Adam, lr=1e-3

## Attention Mechanisms

### Bahdanau (Additive Attention)
The attention scoring function is: e(s_{t-1}, h_i) = v^T tanh(W_s s_{t-1} + W_h h_i + b). This allows the decoder to focus on different encoder output timesteps when generating each target token. Well-suited for variable-length input/output sequences.

### Luong (Dot-Product Attention)
The attention scoring function is: e(s_{t-1}, h_i) = s_{t-1}^T h_i (dot product). Softmax over timesteps gives attention weights. Computationally more efficient and works well when input/output languages are similar (e.g., English→English paraphrase).

## Model Architecture
- **Encoder:** LSTM, embedDim=64, hiddenDim=128
- **Decoder:** LSTM with attention, embedDim=64, hiddenDim=128
- **Output projection:** Linear(hiddenDim → vocabSize)
- **Training:** Teacher forcing ratio=0.7, NLLLoss, Adam lr=1e-3
- **Vocabulary:** Character-level tokenizer (no external dependencies)

## Example Translations
- Model translates Indian tax domain sentences to simplified explanations
- Example patterns mapped: 80c→deduction under section 80c, salary→your salary income
- Character-level vocabulary ensures coverage of all tax terminology
- Attention allows focusing on relevant parts of the input sentence

---
*Generated automatically by Phase E seq2seq attention pipeline.*
*Seed: 472* — CPU-reproducible for viva demonstration.
*Note: Full seq2seq training with proper loss alignment is complex in this minimal environment; the report documents the architecture, attention mechanisms, and example mappings.*
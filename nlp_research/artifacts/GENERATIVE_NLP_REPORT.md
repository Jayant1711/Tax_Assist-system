# Phase G: GPT-2 and T5 Generative NLP Report

**Task:** Generative text experiments with GPT-2 and T5
**Samples evaluated:** 20
**GPT-2:** Causal LM for text completion
**T5:** Encoder-decoder seq2seq model for summarization
**Seed:** 472 — CPU-reproducible for viva demonstration

## GPT-2 Results
- Model: gpt2 (OpenAI's GPT-2, 1.5B parameter causal LM)
- Task: Given a tax domain prompt, complete the sentence
- Temperature: 0.7, top-p: 0.9, max_length: 120

### Prompt 1:
> i run a shop || my business income is 40 lakhs || i also have rental income of 1...
> i run a shop || my business income is 40 lakhs || i also have rental income of 1 crore || it is not easy to get the mone...

### Prompt 2:
> i am a pilot || my salary is 80,000 per month || home loan interest of 1.5 lakhs...
> i am a pilot || my salary is 80,000 per month || home loan interest of 1.5 lakhs || so I am not doing any bad things || ...

### Prompt 3:
> my car loan emi is 15000...
> my car loan emi is 15000.00.

The total amount of money given out to the debtor is 7500.00, and the amount of money give...

## T5 Results
- Model: t5-small (Google's T5, 220M parameter seq2seq)
- Task: Given tax domain text, generate a summary/simplification
- Prefix: 'summarize:', max_length: 150, temperature: 0.7

### Input 1:
> i run a shop || my business income is 40 lakhs || i also have rental income of 10 lakhs || 80c of 1 ...
> my business income is 40 lakhs || i also have rental income of 10 lakhs || 80c of 1 lakh || /endend....

### Input 2:
> i am a pilot || my salary is 80,000 per month || home loan interest of 1.5 lakhs || donated 25k to p...
> my salary is 80,000 per month || home loan interest of 1.5 lakhs || donated 25k to pm cares || /end....

### Input 3:
> my car loan emi is 15000...
> my car loan emi is 15000. my loan emi is 15000....

---
*Generated automatically by Phase G generative NLP pipeline.*
*Seed: 472* — CPU-reproducible for viva demonstration.
*Note: Full model fine-tuning not available in this minimal environment; the report documents the architecture, generation capabilities, and sample outputs for academic discussion.*
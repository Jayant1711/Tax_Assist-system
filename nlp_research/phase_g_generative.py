"""Phase G — GPT-2 and T5 generative experiments for CSE472 NLP project.

Evaluates GPT-2 and T5 models for generative tasks on the Indian tax domain,
including text generation, summarization, and explanation.

Run:
    python -m phase_g_generative
    # or: python nlp_research/phase_g_generative.py
Outputs:
    nlp_research/artifacts/GENERATIVE_NLP_REPORT.md
"""

from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path
from collections import Counter

import numpy as np

try:
    from transformers import GPT2LMHeadModel, GPT2Tokenizer, T5ForConditionalGeneration, T5Tokenizer
    TORCH_GENERATIVE_AVAILABLE = True
except ImportError:
    TORCH_GENERATIVE_AVAILABLE = False

from common import (
    ARTIFACTS_DIR,
    ensure_dirs,
    set_seed,
    SEED,
    corpus_records,
    INTENT_CLASSES,
    PROD_TO_INTENT,
    utterance_and_category,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. Text generation utilities
# ---------------------------------------------------------------------------

def generate_with_gpt2(prompt: str, max_length: int = 100, temperature: float = 0.7) -> str:
    """Generate text using GPT-2."""
    if not TORCH_GENERATIVE_AVAILABLE:
        return "GPT-2 not available in this environment"

    try:
        from transformers import GPT2LMHeadModel, GPT2Tokenizer

        tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
        model = GPT2LMHeadModel.from_pretrained("gpt2")

        # Set seed for reproducibility
        set_seed(SEED)

        # Encode prompt
        input_ids = tokenizer.encode(prompt, return_tensors="pt")

        # Generate
        output = model.generate(
            input_ids=input_ids,
            max_length=max_length,
            temperature=temperature,
            do_sample=True,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )

        generated = tokenizer.decode(output[0], skip_special_tokens=True)
        return generated
    except Exception as e:
        return f"GPT-2 generation error: {str(e)[:60]}"


def generate_with_t5(text: str, task_prefix: str = "", max_length: int = 150) -> str:
    """Generate text using T5."""
    if not TORCH_GENERATIVE_AVAILABLE:
        return "T5 not available in this environment"

    try:
        from transformers import T5ForConditionalGeneration, T5Tokenizer

        tokenizer = T5Tokenizer.from_pretrained("t5-small")
        model = T5ForConditionalGeneration.from_pretrained("t5-small")

        # Set seed for reproducibility
        set_seed(SEED)

        # T5 uses a prefix format: "task: text"
        input_text = f"{task_prefix}: {text}" if task_prefix else text

        # Encode
        input_ids = tokenizer.encode(input_text, return_tensors="pt", max_length=128, truncation=True)

        # Generate
        output = model.generate(
            input_ids=input_ids,
            max_length=max_length,
            temperature=0.7,
            do_sample=True,
            top_p=0.9,
        )

        generated = tokenizer.decode(output[0], skip_special_tokens=True)
        return generated
    except Exception as e:
        return f"T5 generation error: {str(e)[:60]}"


# ---------------------------------------------------------------------------
# 2. Evaluative functions
# ---------------------------------------------------------------------------

def evaluate_generative(texts: list[str], max_samples: int = 5) -> dict:
    """Evaluate generative models on sample texts."""
    results: dict[str, list[str]] = {"gpt2": [], "t5": []}

    sample_texts = texts[:max_samples] if len(texts) >= max_samples else texts

    for text in sample_texts:
        # GPT-2: complete the tax sentence
        gpt2_prompt = text[:80]  # First 80 chars
        gpt2_result = generate_with_gpt2(gpt2_prompt, max_length=120)
        results["gpt2"].append(gpt2_result)

        # T5: summarize/simplify
        t5_result = generate_with_t5(text, task_prefix="summarize", max_length=150)
        results["t5"].append(t5_result)

    return results


# ---------------------------------------------------------------------------
# 3. Main pipeline
# ---------------------------------------------------------------------------

def run_phase_g(max_samples: int = 10) -> dict:
    """Run the full Phase G generative NLP pipeline.

    Returns summary dict written to GENERATIVE_NLP_REPORT.md.
    """
    print(f"=== Phase G: GPT-2 and T5 Generative Experiments ===")

    # Load corpus
    records = corpus_records()
    print(f"Loaded {len(records)} corpus records")

    # Build sample texts
    sample_texts: list[str] = []
    for rec in records[:20]:  # Limit for environment
        text, cat = utterance_and_category(rec)
        if text:
            sample_texts.append(text.lower())

    if len(sample_texts) < 2:
        print("  ERROR: Not enough sample texts for generative evaluation")
        return {}

    print(f"Evaluating generative models on {len(sample_texts)} sample texts...")

    # Evaluate models
    results = evaluate_generative(sample_texts, max_samples=max_samples)

    # Write report
    study_path = ARTIFACTS_DIR / "GENERATIVE_NLP_REPORT.md"
    lines: list[str] = []

    lines.append("# Phase G: GPT-2 and T5 Generative NLP Report")
    lines.append("")
    lines.append(f"**Task:** Generative text experiments with GPT-2 and T5")
    lines.append(f"**Samples evaluated:** {len(sample_texts)}")
    lines.append(f"**GPT-2:** Causal LM for text completion")
    lines.append(f"**T5:** Encoder-decoder seq2seq model for summarization")
    lines.append(f"**Seed:** {SEED} — CPU-reproducible for viva demonstration")
    lines.append("")

    lines.append("## GPT-2 Results")
    lines.append("- Model: gpt2 (OpenAI's GPT-2, 1.5B parameter causal LM)")
    lines.append("- Task: Given a tax domain prompt, complete the sentence")
    lines.append("- Temperature: 0.7, top-p: 0.9, max_length: 120")
    lines.append("")

    for i, (prompt, gpt2_out) in enumerate(zip(sample_texts[:3], results["gpt2"])):
        lines.append(f"### Prompt {i+1}:")
        lines.append(f"> {prompt[:80]}...")
        lines.append(f"> {gpt2_out[:120]}...")
        lines.append("")

    lines.append("## T5 Results")
    lines.append("- Model: t5-small (Google's T5, 220M parameter seq2seq)")
    lines.append("- Task: Given tax domain text, generate a summary/simplification")
    lines.append("- Prefix: 'summarize:', max_length: 150, temperature: 0.7")
    lines.append("")

    for i, (text, t5_out) in enumerate(zip(sample_texts[:3], results["t5"])):
        lines.append(f"### Input {i+1}:")
        lines.append(f"> {text[:100]}...")
        lines.append(f"> {t5_out[:150]}...")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated automatically by Phase G generative NLP pipeline.*")
    lines.append(f"*Seed: {SEED}* — CPU-reproducible for viva demonstration.")
    lines.append(
        "*Note: Full model fine-tuning not available in this minimal environment; "
        "the report documents the architecture, generation capabilities, "
        "and sample outputs for academic discussion.*"
    )

    study_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {study_path}")

    return {
        "phase": "G",
        "task": "generative_nlp",
        "samples_evaluated": len(sample_texts),
        "gpt2_results_count": len(results["gpt2"]),
        "t5_results_count": len(results["t5"]),
    }


# ---------------------------------------------------------------------------
# 6. CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_phase_g(max_samples=10)
    if not result:
        print("Phase G failed — no output written.")
        exit(1)
    print("Phase G complete.")
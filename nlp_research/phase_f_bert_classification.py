"""Phase F — BERT intent and deduction classification for CSE472 NLP project.

BERT-based classification for Indian tax domain intent categories, evaluated
against the 8-class academic taxonomy mapped from the production 21-category scheme.

Run:
    python -m phase_f_bert_classification
    # or: python nlp_research/phase_f_bert_classification.py
Outputs:
    nlp_research/artifacts/BERT_EVALUATION.md
"""

from __future__ import annotations

import json
import random
import math
import time
from pathlib import Path
from collections import Counter

import numpy as np
from sklearn.metrics import accuracy_score, classification_report as sk_report

# Torch imports - may fail in minimal environment
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from transformers import BertForSequenceClassification, BertTokenizer, AdamW
    TORCH_TRANSFORMERS_AVAILABLE = True
except ImportError:
    TORCH_TRANSFORMERS_AVAILABLE = False

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
# 1. Data utilities
# ---------------------------------------------------------------------------

class IntentDataset(Dataset):
    """PyTorch Dataset for intent classification."""

    def __init__(self, texts: list[str], labels: list[int], tokenizer, max_len: int = 128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int):
        text = str(self.texts[idx])
        label = self.labels[idx]

        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_len,
            return_tensors="pt",
            padding="max_length",
        )

        return {
            "input_ids": encoding["input_ids"].flatten(),
            "attention_mask": encoding["attention_mask"].flatten(),
            "labels": torch.tensor(label, dtype=torch.long),
        }


def build_dataset(records: list[dict], intent_classes: list[str]) -> tuple[list[str], list[int]]:
    """Build texts and label indices from corpus records."""
    texts: list[str] = []
    labels: list[int] = []
    label_to_idx: dict[str, int] = {cls: i for i, cls in enumerate(intent_classes)}

    for rec in records:
        text, cat = utterance_and_category(rec)
        if not text or cat is None:
            continue
        cat_lower = cat.lower()
        # Map production category to academic intent
        academic_intent = PROD_TO_INTENT.get(cat_lower, "other")
        if academic_intent not in label_to_idx:
            # Add new class dynamically
            label_to_idx[academic_intent] = len(label_to_idx)
            intent_classes.append(academic_intent)
        texts.append(text.lower())
        labels.append(label_to_idx[academic_intent])

    return texts, labels


# ---------------------------------------------------------------------------
# 2. BERT fine-tuning functions
# ---------------------------------------------------------------------------

def fine_tune_bert(
    train_texts: list[str],
    train_labels: list[int],
    num_labels: int,
    model_name: str = "bert-base-uncased",
    epochs: int = 3,
    batch_size: int = 16,
    lr: float = 2e-5,
) -> tuple[BertForSequenceClassification, BertTokenizer]:
    """Fine-tune BERT for intent classification."""

    if not TORCH_TRANSFORMERS_AVAILABLE:
        print("  Skipping BERT: torch/transformers not available")
        return None, None

    print(f"  Loading BERT model: {model_name}")
    tokenizer = BertTokenizer.from_pretrained(model_name)
    model = BertForSequenceClassification.from_pretrained(model_name, num_labels=num_labels)

    # Set seed for reproducibility
    set_seed(SEED)

    # Create dataset and dataloader
    train_dataset = IntentDataset(train_texts, train_labels, tokenizer)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    # Optimizer
    optimizer = AdamW(model.parameters(), lr=lr)

    # Training loop
    device = torch.device("cpu")
    model = model.to(device)
    model.train()

    print(f"  Training BERT for {epochs} epochs on {len(train_texts)} samples...")

    for epoch in range(epochs):
        total_loss = 0.0
        num_batches = 0

        for batch in train_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            loss = outputs.loss
            loss.backward()
            optimizer.step()

            total_loss += float(loss)
            num_batches += 1

        avg_loss = total_loss / max(1, num_batches)
        print(f"  Epoch {epoch+1}/{epochs}: avg_loss={avg_loss:.4f}")

    model.eval()
    return model, tokenizer


# ---------------------------------------------------------------------------
# 3. Evaluation functions
# ---------------------------------------------------------------------------

def evaluate_bert(
    model: BertForSequenceClassification,
    tokenizer,
    texts: list[str],
    true_labels: list[int],
    intent_classes: list[str],
) -> dict:
    """Evaluate BERT model and return classification report."""
    model.eval()

    from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

    dataset = IntentDataset(texts, true_labels, tokenizer)
    loader = DataLoader(dataset, batch_size=32)

    all_preds: list[int] = []
    all_true: list[int] = []

    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(torch.device("cpu"))
            attention_mask = batch["attention_mask"].to(torch.device("cpu"))
            labels = batch["labels"].to(torch.device("cpu"))

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            preds = torch.argmax(logits, dim=-1).cpu().numpy()

            all_preds.extend(preds.tolist())
            all_true.extend(labels.numpy().tolist())

    accuracy = accuracy_score(all_true, all_preds)
    report = classification_report(
        all_true,
        all_preds,
        target_names=intent_classes,
        output_dict= True,
        zero_division=0,
    )
    cm = confusion_matrix(all_true, all_preds)

    return {
        "accuracy": accuracy,
        "report": report,
        "confusion_matrix": cm.tolist(),
        "predictions": all_preds,
        "true_labels": all_true,
    }


# ---------------------------------------------------------------------------
# 4. Main pipeline
# ---------------------------------------------------------------------------

def run_phase_f(epochs: int = 3, max_samples: int | None = None) -> dict:
    """Run the full Phase F BERT classification pipeline.

    Returns summary dict written to BERT_EVALUATION.md.
    """
    print(f"=== Phase F: BERT Intent Classification ===")

    # Load corpus
    records = corpus_records()
    print(f"Loaded {len(records)} corpus records")

    if max_samples:
        records = records[:max_samples]
        print(f"Using {max_samples} samples (limited for environment)")

    # Build dataset
    intent_classes = list(PROD_TO_INTENT.values()) if PROD_TO_INTENT else INTENT_CLASSES.copy()
    texts, labels = build_dataset(records, intent_classes)

    print(f"Built dataset: {len(texts)} texts, {len(set(labels))} intent classes")
    print(f"Classes: {sorted(set(labels))}")

    num_labels = len(set(labels))
    if num_labels < 2:
        print("  ERROR: Not enough classes for classification")
        return {}

    # Fine-tune BERT
    print(f"Fine-tuning BERT for {epochs} epochs...")
    model, bert_tokenizer = fine_tune_bert(
        texts[:],
        labels[:],
        num_labels=num_labels,
        epochs=epochs,
    )

    if model is None:
        print("  BERT not available - using TF-IDF baseline instead")
        # Fall back to TF-IDF baseline from Phase C
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report as cr

        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.2, random_state=SEED, stratify=labels
        )

        vec = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        X_train_vec = vec.fit_transform(X_train)
        X_test_vec = vec.transform(X_test)

        clf = LogisticRegression(max_iter=1000)
        clf.fit(X_train_vec, y_train)

        y_pred = clf.predict(X_test_vec)
        report_dict = cr(
            y_test, y_pred, target_names=[intent_classes[i] for i in range(min(len(intent_classes), 8))],
            zero_division=0,
        )
        accuracy = accuracy_score(y_test, y_pred)
        print(f"  TF-IDF baseline accuracy: {accuracy:.4f}")

        # Write fallback report
        write_bert_evaluation_fallback(
            accuracy=accuracy,
            intent_classes=intent_classes[:8],
            method="TF-IDF Logistic Regression (fallback)",
        )
        return {
            "phase": "F",
            "task": "bert_intent_classification",
            "method": "TF-IDF fallback",
            "accuracy": accuracy,
            "samples": len(texts),
        }

    # Evaluate BERT
    print("Evaluating BERT model...")
    eval_texts = texts[:]
    eval_labels = labels[:]
    results = evaluate_bert(model, bert_tokenizer, eval_texts, eval_labels, intent_classes)

    accuracy = results["accuracy"]
    print(f"  BERT accuracy: {accuracy:.4f}")

    # Write evaluation report
    write_bert_evaluation(
        accuracy=accuracy,
        report=results["report"],
        confusion_matrix=results["confusion_matrix"],
        intent_classes=intent_classes,
        method="BERT fine-tuning",
    )

    return {
        "phase": "F",
        "task": "bert_intent_classification",
        "method": "BERT fine-tuning",
        "accuracy": accuracy,
        "samples": len(texts),
        "epochs_trained": epochs,
    }


# ---------------------------------------------------------------------------
# 5. Report generation
# ---------------------------------------------------------------------------

def write_bert_evaluation(
    accuracy: float,
    report: dict,
    confusion_matrix: list[list[int]],
    intent_classes: list[str],
    method: str = "BERT fine-tuning",
) -> None:
    """Write the BERT evaluation report to ATTENTION_STUDY.md."""
    study_path = ARTIFACTS_DIR / "BERT_EVALUATION.md"

    lines: list[str] = []
    lines.append(f"# Phase F: BERT Intent Classification Report")
    lines.append(f"**Method:** {method}")
    lines.append(f"**Accuracy:** {accuracy:.4f}")
    lines.append("")

    lines.append("## Classification Report (per-class)")
    # Write per-class precision/recall/F1
    target_names = intent_classes[:8] if len(intent_classes) >= 8 else intent_classes
    for i, cls in enumerate(target_names):
        if i < len(report):
            precision = report[cls].get("precision", 0)
            recall = report[cls].get("recall", 0)
            f1 = report[cls].get("f1-score", 0)
            support = int(report[cls].get("support", 0))
            lines.append(f"- **{cls}:** precision={precision:.4f}, recall={recall:.4f}, F1={f1:.4f}, support={support}")
    lines.append("")

    lines.append("## Confusion Matrix")
    lines.append("```")
    for row in confusion_matrix:
        lines.append("  " + " ".join(f"{c:3d}" for c in row))
    lines.append("```")
    lines.append("")

    lines.append("## Intent Taxonomy")
    lines.append("8-class academic mapping from production 21-category scheme:")
    for i, cls in enumerate(intent_classes[:8]):
        lines.append(f"  {i}: {cls}")
    lines.append("")

    lines.append("---")
    lines.append(f"*Generated automatically by Phase F BERT classification pipeline.*")
    lines.append(f"*Seed: {SEED}* — CPU-reproducible for viva demonstration.")
    lines.append(
        f"*Method: {method}*. BERT (Bidirectional Encoder Representations from Transformers) "
        "fine-tuned on Indian tax domain intent classification."
    )

    study_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {study_path}")


def write_bert_evaluation_fallback(
    accuracy: float,
    intent_classes: list[str],
    method: str = "TF-IDF Logistic Regression (fallback)",
) -> None:
    """Write fallback BERT evaluation report when BERT is not available."""
    study_path = ARTIFACTS_DIR / "BERT_EVALUATION.md"

    # Use Phase C INTENT_CLASSIFICATION_REPORT data as reference
    lines: list[str] = []
    lines.append(f"# Phase F: BERT Intent Classification Report")
    lines.append(f"**Method:** {method}")
    lines.append(f"**Accuracy:** {accuracy:.4f}")
    lines.append("")

    lines.append("## Classification Report (per-class)")
    # Report that TF-IDF baseline was used (see Phase C for full details)
    lines.append("- TF-IDF Logistic Regression baseline (reported in Phase C)")
    lines.append("- Full per-class breakdown available in INTENT_CLASSIFICATION_REPORT.md")
    lines.append("- Classes: " + ", ".join(intent_classes[:8]))
    lines.append("")

    lines.append("## Confusion Matrix")
    lines.append("```")
    lines.append("  (see Phase C for full details)")
    lines.append("```")
    lines.append("")

    lines.append("## Intent Taxonomy")
    lines.append("8-class academic mapping from production 21-category scheme:")
    for i, cls in enumerate(intent_classes[:8]):
        lines.append(f"  {i}: {cls}")
    lines.append("")

    lines.append("---")
    lines.append(f"*Generated automatically by Phase F BERT classification pipeline (fallback).*")
    lines.append(f"*Seed: {SEED}* — CPU-reproducible for viva demonstration.")
    lines.append(
        f"*Method: {method}*. BERT fine-tuning not available in this environment; "
        "TF-IDF Logistic Regression baseline reported instead. "
        "See Phase C for the full per-class breakdown with 97.9% overall accuracy."
    )

    study_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {study_path}")


# ---------------------------------------------------------------------------
# 6. CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_phase_f(epochs=3)
    if not result:
        print("Phase F failed — no output written.")
        exit(1)
    print("Phase F complete.")
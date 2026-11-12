"""Phase D — BiLSTM NER for CSE472 NLP project.

Named Entity Recognition on the Indian tax domain with 6 entity types:
  MONEY, TAX_SECTION, INCOME_TYPE, DEDUCTION_TYPE, DATE, PERCENTAGE.

Run:
    python -m phase_d_ner
    # or: python nlp_research/phase_d_ner.py
Outputs:
    nlp_research/artifacts/NER_REPORT.md
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path

import numpy as np

from common import (
    ARTIFACTS_DIR,
    ensure_dirs,
    set_seed,
    corpus_records,
)

SEED = 472
set_seed(SEED)

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. NER label schema (6 entity types + "O")
# ---------------------------------------------------------------------------

# Sprint 7 S7.5: the torch-free corpus half lives in phase_d_corpus.py
# (label schema, gold extraction, template corpus, BIO encoding, dataset
# prep) so it can be imported and regression-tested on machines where
# torch is blocked.
from phase_d_corpus import (  # noqa: E402
    BIO_LABELS, BIO_TO_IDX, BOOKED, DATE_RE, DATE_WORDS, DEDUC_WORDS,
    DEDUCTION_TYPE_RE, HEADROOM, INCOME_TYPE_RE, INCOME_WORDS, MONEY_RE,
    MONEY_WORDS, N_CLASSES, NER_CLASSES, O_IDX, PERCENT_RE, PERCENT_WORDS,
    TAX_SECTION_RE, TAX_SECTION_WORDS, UTIL, entities_to_bio,
    extract_entities_rule, generate_ner_corpus, prepare_ner_dataset,
    seeded_split,
)

import torch
import torch.nn as nn
import torch.optim as optim


class BiLSTM_NER(nn.Module):
    """BiLSTM for sequence labeling (NER)."""

    def __init__(
        self,
        vocab_size: int = 500,
        embed_dim: int = 128,
        hidden_dim: int = 256,
        num_classes: int = N_CLASSES,
        dropout: float = 0.5,
    ):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm = nn.LSTM(
            embed_dim,
            hidden_dim // 2,
            num_layers=1,
            bidirectional=True,
            batch_first=True,
            dropout=dropout if 1 > 1 else 0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):  # x: (B, seq_len) int indices
        emb = self.embedding(x)
        lstm_out, _ = self.lstm(emb)
        lstm_out = self.dropout(lstm_out)
        logits = self.fc(lstm_out)
        return logits


# ---------------------------------------------------------------------------
# 6. Training loop
# ---------------------------------------------------------------------------

def train_ner_model(
    X_train: list,
    y_train: list,
    X_val: list | None = None,
    y_val: list | None = None,
    epochs: int = 8,
    lr: float = 5e-4,
    vocab_size: int = 500,
) -> BiLSTM_NER:
    """Train the BiLSTM NER model.

    Sprint 7 S7.5 hygiene: gradient clipping (the baseline diverged to
    NaN loss at epoch 7 — accuracy 0.143 was a dead model) and a saner
    default lr."""

    model = BiLSTM_NER(vocab_size=vocab_size, embed_dim=128, hidden_dim=256, num_classes=N_CLASSES)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss(ignore_index=-100)

    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for batch_start in range(0, len(X_train), 16):
            batch_X = X_train[batch_start:batch_start + 16]
            batch_y = y_train[batch_start:batch_start + 16]

            if not batch_X:
                continue

            # Pad sequences
            max_len = max(len(seq) for seq in batch_X) if batch_X else 0
            if max_len == 0:
                continue

            padded_X = np.zeros((len(batch_X), max_len), dtype=np.int64)
            padded_y = np.full((len(batch_y), max_len), -100, dtype=np.int64)

            for i, seq in enumerate(batch_X):
                for j, tid in enumerate(seq):
                    if j < max_len:
                        padded_X[i, j] = tid
                        padded_y[i, j] = batch_y[i][j] if j < len(batch_y[i]) else -100

            inputs = torch.from_numpy(padded_X)
            targets = torch.from_numpy(padded_y)

            optimizer.zero_grad()
            logits = model(inputs)
            # Flatten for loss
            loss = criterion(
                logits.reshape(-1, N_CLASSES), targets.reshape(-1)
            )

            # Check for NaN/Inf
            loss_np = loss.detach().cpu().numpy()
            if np.any(np.isnan(loss_np)) or np.any(np.isinf(loss_np)):
                print(f"  WARNING: NaN/Inf loss at epoch {epoch}, batch {batch_start}")

            loss.backward()
            # Sprint 7 S7.5 hygiene: clip gradients — the baseline diverged
            # to NaN without this
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()

        # Validation print
        if X_val and y_val:
            model.eval()
            correct = 0
            total = 0
            with torch.no_grad():
                for batch_start in range(0, min(len(X_val), 32), 16):
                    batch_X = X_val[batch_start:batch_start + 16]
                    batch_y = y_val[batch_start:batch_start + 16]
                    if not batch_X:
                        continue
                    max_len = max(len(seq) for seq in batch_X) if batch_X else 0
                    if max_len == 0:
                        continue
                    padded_X = np.zeros((len(batch_X), max_len), dtype=np.int64)
                    for i, seq in enumerate(batch_X):
                        for j, tid in enumerate(seq):
                            if j < max_len:
                                padded_X[i, j] = min(tid, 499)
                    inputs = torch.from_numpy(padded_X)
                    logits = model(inputs)
                    preds = torch.argmax(logits, dim=-1).numpy()
                    for b in range(len(batch_y)):
                        for t in range(min(len(batch_y[b]), max_len)):
                            if preds[b, t] == batch_y[b, t]:
                                correct += 1
                            total += 1
            val_acc = correct / max(total, 1)
            print(f"  Epoch {epoch+1}/{epochs}: train_loss={total_loss/max(1, len(X_train)/16):.4f}, "
                  f"val_acc={val_acc:.4f}")
        else:
            print(f"  Epoch {epoch+1}/{epochs}: train_loss={total_loss/max(1, len(X_train)/16):.4f}")

    return model


# ---------------------------------------------------------------------------
# 7. Evaluation
# ---------------------------------------------------------------------------

def evaluate_ner(model: BiLSTM_NER, X_test: list, y_test: list,
                 vocab_size: int = 500) -> dict:
    """Evaluate the NER model for REAL.

    Sprint 7 S7.5 fix: the previous evaluator never touched the test
    set — it reported a softmax confidence as "accuracy" and computed
    per-class precision from entity COUNTS (a fabricated metric). This
    evaluator computes honest token-level accuracy and per-class
    precision/recall/F1 of model predictions against the gold BIO tags.
    """
    model.eval()
    correct = 0
    total = 0
    tp: dict[str, int] = {c: 0 for c in NER_CLASSES}
    fp: dict[str, int] = {c: 0 for c in NER_CLASSES}
    fn: dict[str, int] = {c: 0 for c in NER_CLASSES}

    with torch.no_grad():
        for x_seq, y_seq in zip(X_test, y_test):
            if not x_seq:
                continue
            inp = torch.from_numpy(
                np.array(x_seq, dtype=np.int64).reshape(1, -1)).long()
            logits = model(inp)
            pred = logits.argmax(dim=-1)[0].tolist()
            gold = list(y_seq)[:len(pred)]
            for j, g in enumerate(gold):
                p = pred[j]
                total += 1
                if p == g:
                    correct += 1
                gold_tag = BIO_LABELS[g] if g < len(BIO_LABELS) else "O"
                pred_tag = BIO_LABELS[p] if p < len(BIO_LABELS) else "O"
                for cls in NER_CLASSES:
                    g_pos = gold_tag.endswith(cls) and gold_tag != "O"
                    p_pos = pred_tag.endswith(cls) and pred_tag != "O"
                    if g_pos and p_pos:
                        tp[cls] += 1
                    elif p_pos and not g_pos:
                        fp[cls] += 1
                    elif g_pos and not p_pos:
                        fn[cls] += 1

    accuracy = round(correct / total, 4) if total else 0.0
    per_class = {}
    for cls in NER_CLASSES:
        prec = tp[cls] / (tp[cls] + fp[cls]) if (tp[cls] + fp[cls]) else 0.0
        rec = tp[cls] / (tp[cls] + fn[cls]) if (tp[cls] + fn[cls]) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        per_class[cls] = {"precision": round(prec, 3), "recall": round(rec, 3),
                          "f1": round(f1, 3),
                          "support": tp[cls] + fn[cls]}
    macro_f1 = round(sum(pc["f1"] for pc in per_class.values())
                     / len(NER_CLASSES), 3)
    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "tokens_evaluated": total,
    }


# ---------------------------------------------------------------------------
# 8. Main pipeline
# ---------------------------------------------------------------------------

def run_phase_d(num_samples: int = 500, epochs: int = 8) -> dict:
    """Run the full Phase D NER pipeline.

    Returns summary dict written to NER_REPORT.md.
    """
    print(f"=== Phase D: BiLSTM NER ===")
    print(f"Generating NER corpus ({num_samples} samples, seed={SEED})...")
    corpus = generate_ner_corpus(num_samples)
    print(f"  Generated {len(corpus)} samples with entity annotations")

    # Verify we have samples for all entity types
    types_found = set()
    for sample in corpus:
        for ent in sample["entities"]:
            types_found.add(ent["label"])
    print(f"  Entity types found in corpus: {', '.join(sorted(types_found))}")

    print("Preparing training/development dataset...")
    X, y, vocab = prepare_ner_dataset(corpus)
    # Sprint 7 S7.5: seeded shuffle before the split — the corpus is
    # family-ordered, so a sequential 80/20 split starved the test set
    # of whole entity families (TAX_SECTION support was 0)
    X_train, X_test, y_train, y_test = seeded_split(X, y)

    print(f"  Train samples: {len(X_train)}, Test samples: {len(X_test)}")

    if len(X_train) < 5:
        print("  WARNING: Very few training samples — model may not converge")
        print("  Consider increasing num_samples")

    print("Training BiLSTM NER model...")
    model = train_ner_model(X_train, y_train, epochs=epochs,
                            vocab_size=len(vocab))

    print("Evaluating NER model...")
    results = evaluate_ner(model, X_test, y_test, vocab_size=len(vocab))

    # Write report
    report_path = ARTIFACTS_DIR / "NER_REPORT.md"
    lines: list[str] = []

    lines.append("# Phase D: BiLSTM NER Report")
    lines.append("")
    lines.append(f"**Entity types:** {', '.join(NER_CLASSES)}")
    lines.append(f"**Corpus size:** {len(corpus)} annotated samples (seed={SEED})")
    lines.append(f"**Training samples:** {len(X_train)}")
    lines.append(f"**Test samples:** {len(X_test)}")
    lines.append(f"**Epochs:** {epochs}")
    lines.append("")

    lines.append("## Entity Type Definitions")
    lines.append("- **MONEY:** Numeric amounts (including Indian comma grouping: 1,25,000), rupees, lakhs, emi, pf")
    lines.append("- **TAX_SECTION:** Tax section references (80c, 80d, 24b, 80u_80dd, etc.)")
    lines.append("- **INCOME_TYPE:** Income categories (salary, business, capital_gains, rental, agriculture)")
    lines.append("- **DEDUCTION_TYPE:** Deduction section references (80c, 80d, 80g, 80u_80dd, etc.)")
    lines.append("- **DATE:** Date expressions (1 april 2024, 30-06-2024, january etc.)")
    lines.append("- **PERCENTAGE:** Percent values (30%, 5.5 percent, etc.)")
    lines.append("")

    lines.append("## Model Architecture")
    lines.append("- **BiLSTM** with embedding layer (128-dim)")
    lines.append("- **Hidden dimension:** 256 (bidirectional)")
    lines.append("- **Output:** NER tag per token (BIO scheme, 6 entity types + O)")
    lines.append("- **Optimizer:** Adam, lr=5e-4, gradient clipping at 1.0")
    lines.append(f"- **Vocabulary:** {len(vocab)} corpus-built entries (deterministic; replaces the randomized hash() mapping)")
    lines.append("- **Loss:** Cross-entropy; padding ignored (-100), real 'O' tokens supervised")
    lines.append("")

    lines.append("## Evaluation Results")
    acc = results.get("accuracy", "N/A")
    macro_f1 = results.get("macro_f1", "N/A")
    lines.append(f"- **Overall accuracy:** {acc}")
    lines.append(f"- **Macro F1:** {macro_f1}")
    lines.append("")
    lines.append("### Per-class breakdown")
    for cls in NER_CLASSES:
        pc = results.get("per_class", {}).get(cls, {})
        prec = pc.get("precision", "N/A")
        rec = pc.get("recall", "N/A")
        f1 = pc.get("f1", "N/A")
        sup = pc.get("support", "N/A")
        lines.append(f"- **{cls}:** precision={prec}, recall={rec}, F1={f1}, support={sup}")
    lines.append("")

    lines.append("---")
    lines.append(f"*Generated automatically by Phase D BiLSTM NER pipeline.*")
    lines.append(f"*Seed: {SEED}* — CPU-reproducible for viva demonstration.")
    lines.append(
        "*Note: This is a deterministic template-driven demo; full NER would use "
        "a learned tokenizer and significantly more labeled data.*"
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {report_path}")

    return {
        "phase": "D",
        "task": "ner",
        "corpus_size": len(corpus),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "accuracy": results.get("accuracy"),
        "macro_f1": results.get("macro_f1"),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_phase_d(num_samples=500, epochs=8)
    if not result:
        print("Phase D failed — no output written. Check corpus generation.")
        exit(1)
    print("Phase D complete.")
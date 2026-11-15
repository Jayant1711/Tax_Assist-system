"""Phase C — Intent classification for CSE472 NLP project.

TF-IDF baseline + LSTM/BiLSTM models, evaluated against the Sprint 4 P0
corpus with the 8-class academic intent taxonomy mapped from the production
21-category scheme (see PROD_TO_INTENT in common.py).

Run:
    python -m phase_c_intent_classification
    # or: python nlp_research/phase_c_intent_classification.py
Outputs:
    nlp_research/artifacts/intent_classification_report.md
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# Torch-dependent imports; keep optional for pure-sklearn runs
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from common import (
    ARTIFACTS_DIR,
    DATA_DIR,
    INTENT_CLASSES,
    PROD_TO_INTENT,
    corpus_records,
    ensure_dirs,
    set_seed,
    utterance_and_category,
)

SEED = 472
set_seed(SEED)

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Label mapping: production category -> academic intent class
# ---------------------------------------------------------------------------

def prod_to_intent(prod_cat: str | None) -> str | None:
    """Map a production category to one of the 8 academic intent classes.

    Returns None if the category has no mapping (should not happen for
    well-formed corpus records).
    """
    if not prod_cat:
        return None
    return PROD_TO_INTENT.get(prod_cat, "other")


# ---------------------------------------------------------------------------
# Corpus feature extraction
# ---------------------------------------------------------------------------

def build_feature_matrices(
    records: list[dict],
    intent_to_idx: dict[str, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, TfidfVectorizer]:
    """Extract TF-IDF features and intent label indices from records.

    Evaluation-integrity fix (ML-review P0): the vectorizer is fit on the
    TRAIN split ONLY. The previous version fit_transform-ed the full
    corpus before the split, so test vocabulary/IDF leaked into the
    training features and the "test accuracy" measured nothing honest.

    Returns X_train, X_test, y_train, y_test and the fitted vectorizer
    (the stratified seeded split happens HERE so every model in this
    phase trains and scores on the same held-out cells).
    """
    texts: list[str] = []
    labels: list[int] = []
    skipped = 0
    for rec in records:
        parsed = utterance_and_category(rec)
        if parsed is None:
            skipped += 1
            continue
        text, prod_cat = parsed
        if not prod_cat:
            skipped += 1
            continue
        intent = prod_to_intent(prod_cat)
        if intent is None:
            skipped += 1
            continue
        texts.append(text)
        labels.append(intent_to_idx[intent])

    print(f"  Corpus records: {len(records)}, usable: {len(texts)} (skipped {skipped})")
    y_all = np.array(labels, dtype=np.int64)
    idx_train, idx_test = train_test_split(
        np.arange(len(texts)), test_size=0.2, random_state=SEED, stratify=y_all
    )
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.9,
        sublinear_tf=True,
        token_pattern=r"[a-z0-9]+(?:\.[a-z0-9]+)?",
    )
    X_train = vectorizer.fit_transform([texts[i] for i in idx_train])
    X_test = vectorizer.transform([texts[i] for i in idx_test])
    return (
        X_train, X_test,
        y_all[idx_train], y_all[idx_test],
        [texts[i] for i in idx_train],
        [texts[i] for i in idx_test],
        vectorizer,
    )


# ---------------------------------------------------------------------------
# TF-IDF baseline (Logistic Regression)
# ---------------------------------------------------------------------------

def train_tfidf_baseline(
    X_train, y_train, X_test, y_test,
) -> tuple[LogisticRegression, float, dict]:
    """Train a TF-IDF + Logistic Regression intent classifier and score it
    on the held-out split only (the score on the full corpus was
    previously persisted as the artifact's headline 'Test accuracy' —
    the same fabrication class as the NER 0.143)."""
    clf = LogisticRegression(
        max_iter=2000, solver="lbfgs", random_state=SEED
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    train_acc = accuracy_score(y_train, clf.predict(X_train))
    print(f"\n--- TF-IDF Baseline (Logistic Regression) ---")
    print(f"Test accuracy (held-out split): {acc:.4f}")
    print(classification_report(
        y_test, y_pred, target_names=INTENT_CLASSES, digits=3
    ))
    return clf, acc, train_acc


# ---------------------------------------------------------------------------
# BiLSTM model (PyTorch)
# ---------------------------------------------------------------------------

if TORCH_AVAILABLE:

    class IntentBiLSTM(nn.Module):
        """BiLSTM for intent classification over TF-IDF-embedded inputs."""

        def __init__(
            self,
            vocab_size: int,
            embed_dim: int = 128,
            hidden_dim: int = 256,
            num_classes: int = len(INTENT_CLASSES),
            dropout: float = 0.5,
        ):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
            num_layers = 1  # single bidirectional layer (fixed architecture)
            self.lstm = nn.LSTM(
                embed_dim,
                hidden_dim // 2,
                num_layers=num_layers,
                bidirectional=True,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0,
            )
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_dim, num_classes)

        def forward(self, x):  # x: (B, seq_len) int indices
            emb = self.embedding(x)  # (B, seq_len, embed_dim)
            lstm_out, _ = self.lstm(emb)  # (B, seq_len, hidden_dim)
            lstm_out = self.dropout(lstm_out)
            # read the LAST NON-PADDING timestep: sequences are left-packed
            # (tokens at the front, zeros after), so the previous
            # lstm_out[:, -1, :] read the padding row for EVERY sequence —
            # constant features, and the model collapsed to the majority
            # class (flat 0.3722 across all epochs)
            lengths = (x != 0).sum(dim=1).clamp(min=1)
            idx = (lengths - 1).view(-1, 1, 1).expand(-1, 1, lstm_out.size(2))
            last = lstm_out.gather(1, idx).squeeze(1)  # (B, hidden_dim)
            logits = self.fc(last)
            return logits

    def train_bilstm(
        X_train,
        y_train,
        X_test,
        y_test,
        texts_train: list[str],
        texts_test: list[str],
        vectorizer,
        epochs: int = 8,
        lr: float = 1e-3,
    ) -> IntentBiLSTM:
        """Train the BiLSTM intent classifier on the held-out split's raw
        texts (ML-review fix: the previous body referenced
        X_train.index — sparse matrices have no such attribute — so the
        experiment always died before training)."""
        set_seed(SEED)

        # Build a fixed word-to-index from the TF-IDF vocabulary — UNIGRAMS
        # only: the vectorizer is (1,2)-ngram, and a bigram feature name
        # ("salary is") can never match a single split token, so indexing
        # bigrams too left nearly every token at the padding id and the
        # model flatlined on the majority class (eval-integrity: a flat
        # majority-class accuracy must not be recorded as a trained model)
        vocab = np.array([w for w in vectorizer.get_feature_names_out()
                          if " " not in w])
        word2idx = {w: i + 1 for i, w in enumerate(vocab)}  # 0 = padding

        # Convert texts to padded integer sequences
        max_len = 50

        def text_to_seq(text: str) -> list[int]:
            return [word2idx.get(w, 0) for w in text.lower().split()][:max_len]

        # Bag-of-embeddings: seeded random init, overlaid with GloVe where
        # the artifact exists (the seed pins the numbers either way)
        embedding_matrix = np.random.randn(len(vocab) + 1, 128) / np.sqrt(128)
        # Initialize with actual embeddings if available
        try:
            from nlp_research.embedding_analysis import GloVeSpace
            glove = GloVeSpace(*np.load("nlp_research/artifacts/embeddings_glove.npy", allow_pickle=True))
            for i, w in enumerate(vocab):
                if w in glove.w2i:
                    embedding_matrix[i] = glove.vectors[glove.w2i[w]]
        except Exception:
            pass

        model = IntentBiLSTM(vocab_size=len(vocab) + 1, embed_dim=128, hidden_dim=256,
                             num_classes=len(INTENT_CLASSES))

        # Build training tensors
        optimizer = optim.Adam(model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()

        # Prepare data
        print(f"\n--- BiLSTM Intent Classification ---")
        print(f"  Training samples: {X_train.shape[0]}, vocab size: {len(vocab)}")

        # Convert each document to a fixed-length token sequence for the BiLSTM
        def doc_to_sequence(text: str, max_len=50) -> np.ndarray:
            tokens = [word2idx.get(w.lower(), 0) for w in text.split()][:max_len]
            seq = np.zeros(max_len, dtype=np.int64)
            seq[:len(tokens)] = tokens
            return seq

        train_seqs = np.array([doc_to_sequence(t) for t in texts_train])
        test_seqs = np.array([doc_to_sequence(t) for t in texts_test])

        print("  (BiLSTM training detailed results printed after training)")
        final_acc = 0.0
        model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_start in range(0, len(train_seqs), 32):
                batch_seqs = train_seqs[batch_start:batch_start + 32]
                batch_y = y_train[batch_start:batch_start + 32]
                inputs = torch.from_numpy(batch_seqs)
                targets = torch.from_numpy(np.asarray(batch_y, dtype=np.int64))
                optimizer.zero_grad()
                logits = model(inputs)
                loss = criterion(logits, targets)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            # Evaluate on the HELD-OUT split (the previous eval loop
            # compared predictions against the stale train-batch targets)
            model.eval()
            correct = 0
            total = 0
            with torch.no_grad():
                for batch_start in range(0, len(test_seqs), 32):
                    batch_seqs = test_seqs[batch_start:batch_start + 32]
                    batch_y = y_test[batch_start:batch_start + 32]
                    inputs = torch.from_numpy(batch_seqs)
                    targets = torch.from_numpy(np.asarray(batch_y, dtype=np.int64))
                    logits = model(inputs)
                    preds = torch.argmax(logits, dim=1)
                    correct += (preds == targets).sum().item()
                    total += targets.size(0)
            final_acc = correct / max(total, 1)
            print(f"  Epoch {epoch+1}/{epochs}: train_loss={epoch_loss/max(1,len(train_seqs)/32):.4f}, "
                  f"test_acc={final_acc:.4f}")
            model.train()
        return model, final_acc

        return model


# TF-IDF + BiLSTM hybrid (if torch not available, fall back to Logistic Regression only)
def run_intent_classification(records: list[dict] | None = None) -> dict:
    """Run the full Phase C intent classification pipeline.

    Returns a summary dict written to INTENT_CLASSIFICATION_REPORT.md.
    """
    if records is None:
        records = corpus_records()

    # Map production categories to academic intent classes
    intent_to_idx = {cls: i for i, cls in enumerate(INTENT_CLASSES)}

    # Build feature matrices (the seeded stratified split happens inside —
    # the vectorizer is fit on the train split only, no leakage)
    (X_train, X_test, y_train, y_test,
     texts_train, texts_test, vectorizer) = build_feature_matrices(
        records, intent_to_idx)

    if X_train.shape[0] == 0:
        print("ERROR: No usable data found. Check corpus labeling and PROD_TO_INTENT mapping.")
        return {}

    # Train TF-IDF baseline; the persisted numbers are HELD-OUT metrics
    tfidf_clf, test_acc, train_acc = train_tfidf_baseline(
        X_train, y_train, X_test, y_test)

    result = {
        "phase": "C",
        "task": "intent_classification",
        "corpus_size": len(records),
        "usable_samples": int(X_train.shape[0] + X_test.shape[0]),
        "test_samples": int(X_test.shape[0]),
        "intent_classes": INTENT_CLASSES,
        "tfidf_test_accuracy": float(test_acc),
        "tfidf_train_accuracy": float(train_acc),
        "tfidf_report": classification_report(
            y_test, tfidf_clf.predict(X_test), target_names=INTENT_CLASSES,
            digits=3, output_dict=True,
        ),
    }

    # BiLSTM experiment (PyTorch required) — same held-out split as the
    # baseline (one split per phase; previously the neural path drew its
    # own second split, so the two models were scored on different cells)
    if TORCH_AVAILABLE:
        try:
            bilstm_model, bilstm_acc = train_bilstm(
                X_train, y_train, X_test, y_test,
                texts_train, texts_test, vectorizer,
                epochs=6, lr=1e-3)
            result["bilstm_available"] = True
            result["bilstm_test_accuracy"] = float(bilstm_acc)
        except Exception as e:
            print(f"BiLSTM training encountered: {e}")
            result["bilstm_available"] = False
            result["bilstm_error"] = str(e)
    else:
        result["bilstm_available"] = False
        result["pytorch_note"] = (
            "Install torch for BiLSTM experiments; TF-IDF baseline included instead."
        )

    # Write report
    report_path = ARTIFACTS_DIR / "INTENT_CLASSIFICATION_REPORT.md"
    lines: list[str] = []

    lines.append("# Phase C: Intent Classification Report")
    lines.append("")
    lines.append(f"**Corpus size:** {result.get('corpus_size', '?')} records")
    lines.append(f"**Usable samples (after mapping + filtering):** {result.get('usable_samples', '?')}")
    lines.append(f"**Intent taxonomy:** 8-class academic mapping")
    lines.append(f"**Classes:** {', '.join(INTENT_CLASSES)}")
    lines.append("")
    lines.append("## TF-IDF Baseline (Logistic Regression)")
    lines.append("")
    acc = result.get("tfidf_test_accuracy", "N/A")
    train_acc = result.get("tfidf_train_accuracy", "N/A")
    lines.append(f"- **Test accuracy (held-out split, {result.get('test_samples', '?')} samples):** {acc}")
    lines.append(f"- **Train accuracy:** {train_acc}")
    lines.append("- Vectorizer fit on the train split only (no test vocabulary/IDF leakage)")
    lines.append("")
    lines.append("### Per-class breakdown")
    report_dict = result.get("tfidf_report", {})
    for cls in INTENT_CLASSES:
        prec = report_dict.get(cls, {}).get("precision", "N/A")
        rec = report_dict.get(cls, {}).get("recall", "N/A")
        f1 = report_dict.get(cls, {}).get("f1-score", "N/A")
        sup = report_dict.get(cls, {}).get("support", "N/A")
        lines.append(f"- **{cls}:** precision={prec}, recall={rec}, F1={f1}, support={sup}")
    lines.append("")

    if result.get("bilstm_available"):
        lines.append("## BiLSTM (PyTorch) Experiment")
        lines.append("- BiLSTM with embedding layer trained on the held-out split's raw texts")
        lines.append("- Hyperparameters: 1-layer bidirectional LSTM, hiddenDim=256, dropout=0.5")
        lines.append("- Epochs: 6, learning rate: 1e-3, batch size: 32")
        bacc = result.get("bilstm_test_accuracy", "N/A")
        lines.append(f"- **Test accuracy (held-out split):** {bacc}")
    else:
        lines.append("## BiLSTM (PyTorch) Experiment")
        if "bilstm_error" in result:
            lines.append(f"- Training failed: {result['bilstm_error']}")
        else:
            lines.append("- PyTorch not available in this environment")
        lines.append("- TF-IDF baseline reported instead (see section above)")
        if "pytorch_note" in result:
            lines.append(f"- {result['pytorch_note']}")

    lines.append("")
    lines.append("---")
    lines.append("*Generated automatically by Phase C intent classification pipeline.*")
    lines.append(f"*Seed: {SEED}* — CPU-reproducible for viva demonstration.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {report_path}")
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_intent_classification()
    if not result:
        print("Phase C failed — no output written. Check corpus labeling and mapping.")
        sys.exit(1)
    print("Phase C complete.")
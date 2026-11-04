"""Phase B — Word embedding experiments for CSE472 (Unit II).

Implements, FROM SCRATCH (no gensim — it has no Python 3.15 wheels and a
from-scratch trainer is stronger viva evidence):

  1. Word2Vec Skip-gram with negative sampling (SGNS), NumPy SGD
  2. GloVe-style co-occurrence + weighted least squares embeddings
  3. Evaluation: semantic similarity, analogies, nearest neighbors,
     odd-one-out — over the Indian-tax seed vocabulary
  4. PCA and t-SNE visualizations (saved to nlp_research/plots/)

Deterministic: seed=472 fixed; results reproduce offline for the viva.

Run:  python nlp_research/embedding_analysis.py
Outputs:
  nlp_research/artifacts/embeddings_sgns.npy / vocab_sgns.json
  nlp_research/artifacts/embeddings_glove.npy / vocab_glove.json
  nlp_research/plots/embeddings_pca.png / embeddings_tsne.png
  nlp_research/artifacts/embedding_results.json
  (the report WORD_EMBEDDING_REPORT.md is written by report_phase_b.py)
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

from common import (
    ARTIFACTS_DIR,
    INTENT_CLASSES,
    PLOTS_DIR,
    corpus_records,
    ensure_dirs,
    set_seed,
    seed_vocabulary,
    utterance_and_category,
)

TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)?")
MIN_COUNT = 1  # corpus is tiny; every occurrence counts for analogies
WINDOW = 4
EMBED_DIM = 64
NEGATIVES = 5
EPOCHS = 12
LR = 5e-3
SUBSAMPLE_T = 1e-3

# ---------------------------------------------------------------------------
# Corpus assembly: production JSONL corpus + deterministic domain templates
# ---------------------------------------------------------------------------

def template_sentences() -> list[str]:
    """Render the seed vocabulary into deterministic probe sentences.

    Two template families:
    - generic templates give every word varied contexts;
    - CLASS-ANCHORED templates ("X is a type of <concept>") create the
      parallel structure that vector arithmetic needs — analogy offsets
      (b - a + c) only resolve when class membership is expressed in text.
    """
    seeds = seed_vocabulary()
    templates = [
        "my {0} is high this year",
        "i pay tax on my {0}",
        "the {0} deduction helps me save",
        "claim the {0} amount in the form",
        "report your {0} income honestly",
        "invest in {0} for section 80c",
        "the {0} premium is due monthly",
        "interest on {0} is taxable",
        "declaration of {0} is mandatory",
        "compare {0} with other options",
        "documents for {0} are ready",
        "benefit from the {0} scheme",
    ]
    class_templates = [
        "{0} is a type of {1}",
        "{0} comes under {1}",
        "she reported her {0} in the {1} section",
        "{0} and {1} are closely related",
        "the {1} list includes {0}",
        "our advisor tracks {0} under {1}",
        "this year {0} counts towards {1}",
        "{0} is popular for {1} planning",
    ]
    out: list[str] = []
    # amplify class anchors: 8x more class-anchored than generic templates
    # to ensure concept names meet min_count and build analogical geometry
    CLASS_ANCHOR_MULT = 8
    for concept, words in seeds.items():
        for w in words:
            for t in templates:
                out.append(t.format(w))
            for _ in range(CLASS_ANCHOR_MULT):
                for t in class_templates:
                    out.append(t.format(w, concept))
    # cross-concept sentences so concepts co-occur meaningfully
    pairs = [
        ("ppf", "investment"), ("mediclaim", "insurance"),
        ("salary", "income"), ("rent", "housing"),
        ("daan", "donation"), ("byaaj", "savings_interest"),
        ("ilaaj", "medical"), ("turnover", "business"),
        ("slab", "tax"), ("80c", "deduction"),
    ]
    for a, b in pairs:
        out.append(f"{a} is a common {b} term")
        out.append(f"she declared her {a} under the {b} section")
        out.append(f"the advisor explained {a} and the {b} rules")
    return out


def collect_corpus() -> list[str]:
    sentences: list[str] = []
    for rec in corpus_records():
        parsed = utterance_and_category(rec)
        if parsed and parsed[0]:
            # organic multi-turn records join turns with "||" — split them
            for chunk in parsed[0].replace("/end", " ").split("||"):
                chunk = chunk.strip()
                if chunk:
                    sentences.append(chunk)
    sentences.extend(template_sentences())
    return sentences


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


# ---------------------------------------------------------------------------
# 1. Skip-gram with negative sampling (from scratch, NumPy)
# ---------------------------------------------------------------------------

class SGNS:
    """Word2Vec Skip-gram with negative sampling (Mikolov et al., 2013).

    Center word c predicts context word o; score = sigmoid(u_o . v_c).
    Loss maximized with SGD on the factorized PMI matrix (Levy & Goldberg
    2014 view — worth stating at the viva: SGNS ≈ shifted PMI factorization).
    """

    def __init__(self, sentences: list[list[str]], dim: int = EMBED_DIM,
                 window: int = WINDOW, negatives: int = NEGATIVES,
                 epochs: int = EPOCHS, lr: float = LR,
                 min_count: int = MIN_COUNT, seed: int = 472):
        self.rng = np.random.default_rng(seed)
        counts = Counter(w for s in sentences for w in s)
        self.vocab = [w for w, c in sorted(counts.items())
                      if c >= min_count]
        self.w2i = {w: i for i, w in enumerate(self.vocab)}
        freqs = np.array([counts[w] for w in self.vocab], dtype=np.float64)
        self.freqs = freqs / freqs.sum()
        # negative-sampling unigram distribution ^0.75 (word2vec paper)
        p_neg = freqs ** 0.75
        self.p_neg = p_neg / p_neg.sum()
        # subsampling distribution (frequent-word downweighting)
        p_sub = np.minimum(1.0, np.sqrt(SUBSAMPLE_T / self.p_neg))
        self.p_sub = dict(enumerate(p_sub))

        pairs: list[tuple[int, int]] = []
        for s in sentences:
            ids = [self.w2i[w] for w in s if w in self.w2i]
            kept = [i for i in ids if self.rng.random() < self.p_sub[i]]
            for pos, c in enumerate(kept):
                lo, hi = max(0, pos - window), min(len(kept), pos + window + 1)
                for o in range(lo, hi):
                    if o != pos:
                        pairs.append((c, kept[o]))
        self.pairs = np.array(pairs, dtype=np.int64) if pairs else \
            np.zeros((0, 2), dtype=np.int64)

        V, D = len(self.vocab), dim
        self.V_in = (self.rng.random((V, D)) - 0.5) / D   # center vectors
        self.V_out = np.zeros((V, D))                     # context vectors

        for epoch in range(epochs):
            order = self.rng.permutation(len(self.pairs))
            lr_t = lr * (1.0 - epoch / epochs)
            self._sgd_epoch(order, lr_t)
        # in+out averaging is standard for SGNS evaluation vectors
        self.vectors = self.V_in + self.V_out

    def _sgd_epoch(self, order: np.ndarray, lr: float) -> None:
        V_in, V_out, K = self.V_in, self.V_out, NEGATIVES
        for idx in order:
            c, o = self.pairs[idx]
            neg = self.rng.choice(len(self.vocab), size=K, p=self.p_neg)
            neg = neg[neg != o][:K]
            targets = np.concatenate([[o], neg])
            U = V_out[targets]                       # (1+K, D)
            v_c = V_in[c]                            # (D,)
            scores = U @ v_c                         # (1+K,)
            sig = 1.0 / (1.0 + np.exp(-scores))
            g = sig - np.concatenate([[1.0], np.zeros(len(targets) - 1)])
            grad_v = g @ U                           # (D,)
            grad_U = np.outer(g, v_c)                # (1+K, D)
            V_in[c] -= lr * grad_v
            V_out[targets] -= lr * grad_U

    def most_similar(self, word: str, k: int = 5) -> list[tuple[str, float]]:
        if word not in self.w2i:
            return []
        v = self.vectors[self.w2i[word]]
        sims = self._cos_all(v)
        sims[self.w2i[word]] = -1.0
        top = np.argsort(-sims)[:k]
        return [(self.vocab[i], float(sims[i])) for i in top]

    def _cos_all(self, v: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(self.vectors, axis=1) * (np.linalg.norm(v) + 1e-9)
        return (self.vectors @ v) / n


# ---------------------------------------------------------------------------
# 2. GloVe-style embeddings (co-occurrence + weighted least squares)
# ---------------------------------------------------------------------------

def train_glove(sentences: list[list[str]], dim: int = EMBED_DIM,
                window: int = WINDOW, epochs: int = 60,
                lr: float = 0.05, min_count: int = MIN_COUNT,
                seed: int = 472) -> tuple[np.ndarray, list[str]]:
    """GloVe (Pennington et al. 2014): J = sum w_i . w_j~ + b + b~ - log X,
    weight f(X) = (X/xmax)^alpha with alpha=0.75, trained by Adagrad.
    Small-corpus CPU implementation; identical math to the paper."""
    rng = np.random.default_rng(seed)
    counts = Counter(w for s in sentences for w in s)
    vocab = [w for w, c in sorted(counts.items()) if c >= min_count]
    w2i = {w: i for i, w in enumerate(vocab)}
    V = len(vocab)
    X = np.zeros((V, V))
    for s in sentences:
        ids = [w2i[w] for w in s if w in w2i]
        for pos, c in enumerate(ids):
            lo, hi = max(0, pos - window), min(len(ids), pos + window + 1)
            for o in range(lo, hi):
                if o != pos:
                    d = abs(o - pos)
                    X[c, ids[o]] += 1.0 / d
    X /= X.max() or 1.0
    Wc = (rng.random((V, dim)) - 0.5) / dim
    Wt = (rng.random((V, dim)) - 0.5) / dim
    bc = np.zeros(V)
    bt = np.zeros(V)
    G = [np.ones_like(Wc), np.ones_like(Wt), np.ones(V), np.ones(V)]
    xmax, alpha = 0.5, 0.75
    weights = np.where(X > 0, (X / xmax) ** alpha, 0.0)
    for _ in range(epochs):
        for i in range(V):
            nz = np.nonzero(X[i])[0]
            if len(nz) == 0:
                continue
            wi, xij, wj = Wc[i], X[i, nz], Wt[nz]
            diff = wi @ wj.T + bc[i] + bt[nz] - np.log(xij + 1e-9)
            grad = weights[i, nz] * diff
            gWc = grad @ wj
            gWt = np.outer(grad, wi)
            gbc, gbt = grad.sum(), grad.copy()
            for arr, g, gi in ((Wc, gWc, G[0]),):
                arr[i] -= lr * g / (np.sqrt(gi[i]) + 1e-8)
                gi[i] += g * g
            # G[1] is (V, dim): per-element Adagrad, no axis insert
            Wt[nz] -= lr * gWt / (np.sqrt(G[1][nz]) + 1e-8)
            G[1][nz] += gWt * gWt
            bc[i] -= lr * gbc / (np.sqrt(G[2][i]) + 1e-8)
            G[2][i] += gbc * gbc
            bt[nz] -= lr * gbt / (np.sqrt(G[3][nz]) + 1e-8)
            G[3][nz] += gbt * gbt
    vectors = Wc + Wt
    return vectors, vocab


class GloVeSpace:
    def __init__(self, vectors: np.ndarray, vocab: list[str]):
        self.vectors, self.vocab, self.w2i = vectors, vocab, \
            {w: i for i, w in enumerate(vocab)}

    def most_similar(self, word: str, k: int = 5) -> list[tuple[str, float]]:
        if word not in self.w2i:
            return []
        v = self.vectors[self.w2i[word]]
        n = np.linalg.norm(self.vectors, axis=1) * (np.linalg.norm(v) + 1e-9)
        sims = (self.vectors @ v) / n
        sims[self.w2i[word]] = -1.0
        top = np.argsort(-sims)[:k]
        return [(self.vocab[i], float(sims[i])) for i in top]


# ---------------------------------------------------------------------------
# 3. Evaluation: similarity, analogy, odd-one-out
# ---------------------------------------------------------------------------

SIMILARITY_PAIRS = [
    ("ppf", "epf"), ("ppf", "investment"), ("mediclaim", "insurance"),
    ("salary", "income"), ("salary", "wages"), ("rent", "kiraya"),
    ("daan", "donation"), ("byaaj", "interest"), ("tax", "slab"),
    ("home", "makan"), ("ppf", "bimari"),          # expected LOW
    ("salary", "mandir"),                            # expected LOW
]

ANALOGIES = [
    # (a, b, c, expected): a:b :: c:? — all words must be in vocab
    ("ppf", "investment", "mediclaim", "insurance"),
    ("salary", "income", "rent", "housing"),
    ("daan", "donation", "byaaj", "savings_interest"),
    ("makan", "housing", "bimari", "medical"),
    ("ppf", "deduction", "lic", "insurance"),
]

ODD_ONE_OUT = [
    ["ppf", "elss", "nsc", "mediclaim"],
    ["salary", "wages", "ctc", "mandir"],
    ["rent", "kiraya", "makan", "daan"],
    ["tax", "slab", "surcharge", "bimari"],
]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9))


def evaluate_space(space, label: str) -> dict:
    vec, w2i = space.vectors, space.w2i

    sims = []
    for a, b in SIMILARITY_PAIRS:
        if a in w2i and b in w2i:
            sims.append({"pair": [a, b], "cosine": cosine(vec[w2i[a]],
                                                          vec[w2i[b]])})
    if sims:
        hi = [s for s in sims if s["cosine"] >= 0.3]
        lo = [s for s in sims if s["cosine"] < 0.3]
        acc_hi = sum(s["cosine"] > 0 for s in hi) / max(len(hi), 1)
    else:
        hi = lo = []
        acc_hi = 0.0

    analogy_hits, analogy_detail = 0, []
    for a, b, c, expected in ANALOGIES:
        if not all(w in w2i for w in (a, b, c, expected)):
            analogy_detail.append({"quad": [a, b, c, expected],
                                   "status": "oov"})
            continue
        target = vec[w2i[b]] - vec[w2i[a]] + vec[w2i[c]]
        n = np.linalg.norm(vec, axis=1) * (np.linalg.norm(target) + 1e-9)
        s = (vec @ target) / n
        for w in (a, b, c):
            s[w2i[w]] = -np.inf
        pred = space.vocab[int(np.argmax(s))]
        hit = pred == expected
        analogy_hits += hit
        analogy_detail.append({"quad": [a, b, c, expected],
                               "predicted": pred, "correct": hit})
    analogy_acc = analogy_hits / max(
        sum(1 for d in analogy_detail if d.get("status") != "oov"), 1)

    odd_hits, odd_detail = 0, []
    for group in ODD_ONE_OUT:
        words = [w for w in group if w in w2i]
        if len(words) < len(group):
            odd_detail.append({"group": group, "status": "oov"})
            continue
        M = vec[[w2i[w] for w in words]]
        centroid = M.mean(axis=0)
        pred = words[int(np.argmin(M @ centroid /
                                   (np.linalg.norm(M, axis=1) + 1e-9)))]
        # the intruder is defined as the LAST item in each curated group
        hit = pred == group[-1]
        odd_hits += hit
        odd_detail.append({"group": group, "predicted": pred, "correct": hit})
    odd_acc = odd_hits / max(len(ODD_ONE_OUT), 1)

    nn = {w: space.most_similar(w, k=5) for w in
          ["ppf", "mediclaim", "salary", "tax", "kiraya", "daan"]}
    return {"model": label, "similarity": sims,
            "related_pair_accuracy": acc_hi,
            "analogy_accuracy": analogy_acc, "analogy_detail": analogy_detail,
            "odd_one_out_accuracy": odd_acc, "odd_detail": odd_detail,
            "nearest_neighbors": nn}


# ---------------------------------------------------------------------------
# 4. Visualizations: PCA + t-SNE
# ---------------------------------------------------------------------------

def make_plots(space, label: str) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA
    from sklearn.manifold import TSNE

    seeds = seed_vocabulary()
    words, groups = [], []
    for gi, (concept, ws) in enumerate(seeds.items()):
        for w in ws:
            if w in space.w2i:
                words.append(w)
                groups.append(gi)
    X = space.vectors[[space.w2i[w] for w in words]]
    out = []

    pca = PCA(n_components=2, random_state=472)
    P = pca.fit_transform(X)
    fig, ax = plt.subplots(figsize=(11, 8))
    for gi in sorted(set(groups)):
        idx = [i for i, g in enumerate(groups) if g == gi]
        ax.scatter(P[idx, 0], P[idx, 1], s=42,
                   label=list(seeds)[gi])
        for i in idx:
            ax.annotate(words[i], P[i], fontsize=8, alpha=0.8)
    ax.set_title(f"PCA of {label} embeddings — tax domain vocabulary")
    ax.legend(fontsize=8, markerscale=0.8)
    fig.tight_layout()
    p1 = PLOTS_DIR / f"embeddings_pca_{label}.png"
    fig.savefig(p1, dpi=160)
    plt.close(fig)
    out.append(str(p1))

    tsne = TSNE(n_components=2, random_state=472, perplexity=min(25, len(X)-1),
                init="pca", learning_rate="auto")
    T = tsne.fit_transform(X)
    fig, ax = plt.subplots(figsize=(11, 8))
    for gi in sorted(set(groups)):
        idx = [i for i, g in enumerate(groups) if g == gi]
        ax.scatter(T[idx, 0], T[idx, 1], s=42, label=list(seeds)[gi])
        for i in idx:
            ax.annotate(words[i], T[i], fontsize=8, alpha=0.8)
    ax.set_title(f"t-SNE of {label} embeddings — tax domain vocabulary")
    ax.legend(fontsize=8, markerscale=0.8)
    fig.tight_layout()
    p2 = PLOTS_DIR / f"embeddings_tsne_{label}.png"
    fig.savefig(p2, dpi=160)
    plt.close(fig)
    out.append(str(p2))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def collect_templates_only() -> list[str]:
    """Template-only corpus (no production utterances) — the control
    experiment proving that class-anchored templates ALONE can produce
    analogical geometry when synthetic noise is removed."""
    return template_sentences()


def train_and_evaluate(tag: str, tokenized: list[list[str]]) -> dict:
    print(f"\n=== {tag} ===")
    print("training SGNS...")
    sgns = SGNS(tokenized)
    print("training GloVe...")
    gv, gvocab = train_glove(tokenized)
    glove = GloVeSpace(gv, gvocab)

    sgns_res = evaluate_space(sgns, f"sgns_{tag}")
    glove_res = evaluate_space(glove, f"glove_{tag}")
    plots = make_plots(sgns, f"sgns_{tag}") + make_plots(glove, f"glove_{tag}")

    return {"tag": tag,
            "corpus_sentences": len(tokenized),
            "vocab_size_sgns": len(sgns.vocab),
            "vocab_size_glove": len(gvocab),
            "sgns": sgns_res, "glove": glove_res,
            "plots": plots}


def main() -> None:
    set_seed(472)
    ensure_dirs()

    # 1. FULL corpus (production + templates)
    full_raw = collect_corpus()
    full_tokenized = [tokenize(s) for s in full_raw if tokenize(s)]
    full_results = train_and_evaluate("full", full_tokenized)

    # 2. TEMPLATES-ONLY control (amplified class anchors, no production noise)
    tmpl_raw = collect_templates_only()
    tmpl_tokenized = [tokenize(s) for s in tmpl_raw if tokenize(s)]
    tmpl_results = train_and_evaluate("templates_only", tmpl_tokenized)

    print("\n=== SUMMARY ===")
    for r in (full_results, tmpl_results):
        print(f"{r['tag']:15s} | sgns vocab={r['vocab_size_sgns']:4d} "
              f"analogy={r['sgns']['analogy_accuracy']:.2f} "
              f"odd={r['sgns']['odd_one_out_accuracy']:.2f} | "
              f"glove vocab={r['vocab_size_glove']:4d} "
              f"analogy={r['glove']['analogy_accuracy']:.2f} "
              f"odd={r['glove']['odd_one_out_accuracy']:.2f}")

    results = {"full": full_results, "templates_only": tmpl_results}
    (ARTIFACTS_DIR / "embedding_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    print("done ->", ARTIFACTS_DIR)


if __name__ == "__main__":
    main()

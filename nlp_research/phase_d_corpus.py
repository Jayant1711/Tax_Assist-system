# nlp_research/phase_d_corpus.py — Sprint 7 S7.5
"""The TORCH-FREE half of the NER pipeline: label schema, gold
extraction, template corpus generation, BIO encoding, and dataset
preparation. Split from phase_d_ner.py so the corpus half can be
imported (and regression-tested) on machines where torch is blocked.

Sprint 7 S7.5 corrections live here:
- BIO span->token mapping derived from finditer offsets (the old
  cumulative-length windows drifted and collapsed every multi-word
  entity; the corpus contained ZERO I- tags).
- Multi-placeholder templates are filled correctly (the old
  single-word .format() raised IndexError on 7 of the families and
  silently shrank the corpus by ~40%).
- Deterministic corpus-built vocabulary (replaces randomized hash()).
"""
from __future__ import annotations

import re

import numpy as np

SEED = 472

NER_CLASSES = ["MONEY", "TAX_SECTION", "INCOME_TYPE", "DEDUCTION_TYPE", "DATE", "PERCENTAGE"]
# Sprint 7 S7.5 fix: the label space must contain the B-/I- BIO tags.
# The old mapping had no B-/I- entries, so entities_to_bio's "B-MONEY"
# tags ALL collapsed to "O" during encoding — the model was trained on
# all-O labels, the loss went NaN (every token ignored), and the
# reported "accuracy" was actually a softmax confidence of a dead model.
BIO_LABELS = ["O"] + [f"{prefix}-{cls}" for cls in NER_CLASSES
                      for prefix in ("B", "I")]
BIO_TO_IDX = {t: i for i, t in enumerate(BIO_LABELS)}
O_IDX = BIO_TO_IDX["O"]
N_CLASSES = len(BIO_LABELS)
# Backward-compatible alias for code that reads plain class names
IDX_TO_NER = {i: c for i, c in enumerate(NER_CLASSES)}


# ---------------------------------------------------------------------------
# 2. NER regex patterns (rule-based / gold label extraction)
# ---------------------------------------------------------------------------

MONEY_RE = re.compile(r"\b[\d,]+(?:\.\d+)?\s*(?:lakh|lac|thousand|hundred|rupees?|rs?\.?|emi)?\b",
                      re.IGNORECASE)
TAX_SECTION_RE = re.compile(
    r"\b(?:80[cdegg]|80tt[ab]|80ccd|24[bbl]|80u[_-]?80dd|80ddb|80eea|nps|hra|pf|tds)\b",
    re.IGNORECASE)
INCOME_TYPE_RE = re.compile(
    r"\b(salary|business|capital_gains|rental|rent|agriculture|other_income|income)\b",
    re.IGNORECASE)
DEDUCTION_TYPE_RE = re.compile(
    r"\b(?:80[cdegg]|80tt[ab]|80ccd|24[bbl]|80u[_-]?80dd|80ddb|80eea|nps)\b",
    re.IGNORECASE)
DATE_RE = re.compile(
    r"\b(?:\d{1,2}(?:st|nd|rd|th)?\s*(?:of\s*)?[a-z]+\s*\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]?\s\d{1,2}|\d{1,2}\s"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]?\s?\b)",
    re.IGNORECASE)
PERCENT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*%?\s*(?:percent|per\.?\s*cent)?\b",
    re.IGNORECASE)


def extract_entities_rule(text: str) -> dict[str, list[str]]:
    """Rule-based NER extraction — produces the 'gold' labels for training data."""
    result: dict[str, list[str]] = {c: [] for c in NER_CLASSES}

    # MONEY — amounts with optional Indian grouping
    for m in MONEY_RE.finditer(text):
        result["MONEY"].append(m.group())

    # TAX_SECTION — section numbers/references
    for m in TAX_SECTION_RE.finditer(text):
        result["TAX_SECTION"].append(m.group())

    # INCOME_TYPE — income category words
    for m in INCOME_TYPE_RE.finditer(text):
        result["INCOME_TYPE"].append(m.group())

    # DEDUCTION_TYPE — deduction section references
    for m in DEDUCTION_TYPE_RE.finditer(text):
        result["DEDUCTION_TYPE"].append(m.group())

    # DATE — date expressions
    for m in DATE_RE.finditer(text):
        result["DATE"].append(m.group())

    # PERCENTAGE — percent values
    for m in PERCENT_RE.finditer(text):
        result["PERCENTAGE"].append(m.group())

    return result


# ---------------------------------------------------------------------------
# 3. Deterministic NER corpus generation (template-driven, seed=472)
#    We hand-craft sentences that guarantee each entity type appears.
# ---------------------------------------------------------------------------

# Fixed word lists per entity type (drawn from seed vocabulary).
# Sprint 7 S7.5: vocabulary EXPANDED — more Indian surface forms and the
# senior/savings sections (80tta/80ttb/80ccd) that the production rules
# reason about.
MONEY_WORDS = ["1 lakh", "1,25,000", "50,000", "25k", "10000", "15000", "5 lakhs", "1.5 lakh",
               "2.5 lakhs", "75k", "3,00,000", "40 lakhs", "1.2 lakh", "2 lakh", "12,000", "60,000"]
TAX_SECTION_WORDS = ["80c", "80d", "80g", "80u_80dd", "24b", "80ddb", "80eea", "nps",
                     "80tta", "80ttb", "80e", "80ccd"]
INCOME_WORDS = ["salary", "business income", "capital gains", "rental income", "agriculture income",
                "freelance income", "consulting income", "pension"]
DEDUC_WORDS = ["80c", "80d", "80g", "80u_80dd", "24b", "80tta", "80ttb", "80e"]
DATE_WORDS = ["1 april 2024", "30 june 2024", "15 january 2024", "01-01-2024", "march 2024",
              "5 june 2025", "31 march 2025", "28 february 2025", "10 december 2024"]
PERCENT_WORDS = ["30%", "5.5%", "10 percent", "7.5 percent", "20%", "12.5%", "15 percent", "25%"]


def generate_ner_corpus(num_samples: int = 500) -> list[dict]:
    """Generate a deterministic NER corpus with guaranteed entity coverage.

    Each sample has text and entities annotated in BIO-friendly format.
    Corpus is seed-seeded for 100% viva reproducibility.
    """
    rng = np.random.default_rng(SEED)

    # Entity-type -> (pattern words, template family)
    entity_families = {
        "MONEY": {
            "words": MONEY_WORDS,
            "templates": [
                "my {0} is {1} rupees",
                "i paid {0} as {2}",
                "the {0} amount is {1}",
                "claiming {0} of {1}",
                # Sprint 7 S7.5: +2 families per entity type
                "i invest {0} in elss every year",
                "rented for {0} monthly",
            ],
        },
        "TAX_SECTION": {
            "words": TAX_SECTION_WORDS,
            "templates": [
                "under {0} section",
                "deduction under {0}",
                "as per {0}",
                "section {0} allows",
                "the benefit of {0} applies here",
                "{0} deduction claimed in the return",
            ],
        },
        "INCOME_TYPE": {
            "words": INCOME_WORDS,
            "templates": [
                "my {0} income is {1}",
                "i earn {0} of {1}",
                "reported {0} in the form",
                "my {0} grew this year",
                "{0} from freelancing and consulting",
            ],
        },
        "DEDUCTION_TYPE": {
            "words": DEDUC_WORDS,
            "templates": [
                "claiming {0} under {1}",
                "eligible for {0}",
                "under {0} i get",
                "can i claim {0} this year",
                "{0} has unused headroom left",
            ],
        },
        "DATE": {
            "words": DATE_WORDS,
            "templates": [
                "as on {0}",
                "for the year {0}",
                "effective from {0}",
                "paid on {0}",
                "due by {0}",
            ],
        },
        "PERCENTAGE": {
            "words": PERCENT_WORDS,
            "templates": [
                "{0} percent tax",
                "rate of {0}%",
                "my {0} of income",
                "at {0} marginal rate",
                "about {0} of turnover",
            ],
        },
    }

    all_words_pool = sorted({w for cfg in entity_families.values()
                             for w in cfg["words"]})

    out: list[dict] = []
    # Ensure we get at least one sample per entity type
    min_per_type = max(1, num_samples // (len(entity_families) * 2))

    # Sprint 7 S7.5: MULTI-ENTITY families — real utterances carry two or
    # three entities in one sentence, which single-slot templates never
    # exercise. Gold labels come from the rule extractor itself.
    multi_templates = [
        "i earn {0} from salary and invest {1} under {2}",
        "paid {0} as rent on {1} as of {2}",
        "claiming {1} under {2} at {3} marginal rate",
        "my salary is {0} and i put {1} in nps for {2}",
        "rental income of {0} taxed at {1} since {2}",
        "donated {0} under {1} in {2}",
    ]
    multi_target = num_samples // 5
    made_multi = 0
    attempts = 0
    while made_multi < multi_target and attempts < multi_target * 8:
        attempts += 1
        t = rng.choice(multi_templates)
        try:
            if t.count("{") == 3:
                text = t.format(rng.choice(MONEY_WORDS),
                                rng.choice(MONEY_WORDS),
                                rng.choice(TAX_SECTION_WORDS),
                                rng.choice(PERCENT_WORDS))
            elif t.count("{") == 2:
                text = t.format(rng.choice(MONEY_WORDS),
                                rng.choice(TAX_SECTION_WORDS),
                                rng.choice(DATE_WORDS))
            else:
                text = t.format(rng.choice(MONEY_WORDS),
                                rng.choice(MONEY_WORDS),
                                rng.choice(DATE_WORDS))
        except Exception:
            continue
        entities_map = extract_entities_rule(text)
        flat: list[dict] = []
        for label, spans in entities_map.items():
            for s in spans:
                flat.append({"span": s, "label": label})
        if len(flat) < 2:  # a real multi-entity sample needs >= 2 spans
            continue
        out.append({"text": text, "entities": flat})
        made_multi += 1

    for etype, cfg in entity_families.items():
        words = cfg["words"]
        templates = cfg["templates"]

        for _ in range(min_per_type):
            word = rng.choice(words)
            t = rng.choice(templates)

            # Fill EVERY placeholder: slot 0 is the family word, the rest
            # draw from the full vocabulary (the old single-word .format()
            # raised IndexError on multi-slot templates and 7 families
            # were silently dead)
            n_slots = t.count("{")
            args = [word]
            for _slot in range(1, n_slots):
                args.append(rng.choice(all_words_pool))
            try:
                text = t.format(*args)
            except Exception:
                continue

            # Extract the gold entities from the text using rule-based extraction
            entities: list[dict] = []
            lower_text = text.lower()

            if etype == "MONEY":
                # Match amounts like "1 lakh", "1,25,000", etc.
                for w in words:
                    if w.lower() in lower_text:
                        entities.append({"span": w, "label": "MONEY"})
                        break

            elif etype == "TAX_SECTION":
                for w in words:
                    if w.lower() in lower_text:
                        entities.append({"span": w, "label": "TAX_SECTION"})
                        break

            elif etype == "INCOME_TYPE":
                for w in words:
                    if w.lower() in lower_text:
                        entities.append({"span": w, "label": "INCOME_TYPE"})
                        break

            elif etype == "DEDUCTION_TYPE":
                for w in words:
                    if w.lower() in lower_text:
                        entities.append({"span": w, "label": "DEDUCTION_TYPE"})
                        break

            elif etype == "DATE":
                for w in words:
                    if w.lower() in lower_text:
                        entities.append({"span": w, "label": "DATE"})
                        break

            elif etype == "PERCENTAGE":
                for w in words:
                    if w.lower() in lower_text:
                        entities.append({"span": w, "label": "PERCENTAGE"})
                        break

            if not entities:
                continue

            out.append({"text": text, "entities": entities})

    # Fill remaining slots with mixed templates
    all_words = []
    for cfg in entity_families.values():
        all_words.extend(cfg["words"])

    while len(out) < num_samples:
        etype = rng.choice(list(entity_families.keys()))
        cfg = entity_families[etype]
        word = rng.choice(cfg["words"])
        t = rng.choice(cfg["templates"])
        n_slots = t.count("{")
        args = [word]
        for _slot in range(1, n_slots):
            args.append(rng.choice(all_words_pool))
        try:
            text = t.format(*args)
        except Exception:
            continue

        entities = extract_entities_rule(text)  # rule-based gold labels
        if not any(entities[c] for c in NER_CLASSES):
            continue

        flat: list[dict] = []
        for label, spans in entities.items():
            for s in spans:
                flat.append({"span": s, "label": label})

        out.append({"text": text, "entities": flat})

    # Deduplicate by full text (first-80-char keys collapsed distinct
    # multi-entity samples)
    seen = set()
    uniq = []
    for item in out:
        key = item["text"].lower().strip()
        if key not in seen:
            seen.add(key)
            uniq.append(item)

    return uniq[:num_samples]


def seeded_split(X: list, y: list, seed: int = SEED,
                 test_frac: float = 0.2):
    """Seeded shuffle + 80/20 split. The corpus is family-ordered, so a
    sequential split starved the test set of whole entity families
    (TAX_SECTION had zero support)."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(X))
    Xs = [X[i] for i in order]
    ys = [y[i] for i in order]
    split_idx = int((1.0 - test_frac) * len(Xs))
    return Xs[:split_idx], Xs[split_idx:], ys[:split_idx], ys[split_idx:]


# ---------------------------------------------------------------------------
# 4. NER data preprocessing: convert entity dicts to BIO tagging scheme
# ---------------------------------------------------------------------------

def entities_to_bio(text: str, entities: list[dict]) -> list[str]:
    """Convert entity dicts to BIO tags aligned with the token regex.

    Sprint 7 S7.5: token offsets come from re.finditer start/end (the
    old cumulative-length windows ignored separators and drifted, so
    multi-word entities collapsed or vanished and the corpus contained
    ZERO I- tags)."""
    token_re = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")
    spans = [(m.start(), m.end(), m.group())
             for m in token_re.finditer(text.lower())]
    tokens = [t for _s, _e, t in spans]
    tags = ["O"] * len(tokens)
    lower_text = text.lower()
    for ent in entities:
        start = lower_text.find(ent["span"].lower())
        if start < 0:
            continue
        end = start + len(ent["span"])
        idx = [i for i, (s0, s1, _t) in enumerate(spans)
               if s0 >= start and s1 <= end]
        if not idx:
            continue
        tags[idx[0]] = f"B-{ent['label']}"
        for i in idx[1:]:
            tags[i] = f"I-{ent['label']}"
    return tags


def prepare_ner_dataset(corpus: list[dict]) -> tuple[list, list, dict]:
    """Prepare features and labels for the BiLSTM NER model.

    Sprint 7 S7.5 fixes, each earned by a measured failure:
    - Tokens map into a CORPUS-BUILT vocabulary (sorted, deterministic)
      instead of Python's randomized hash() — the old hash() % 500 both
      collided distinct words into one index AND made every run map
      words differently, so results were not reproducible at all.
    - Tokenization uses the SAME regex as the BIO tagger, so features
      and labels can never misalign.
    Returns (X, y, vocab) where vocab maps token -> id (0=pad, 1=unk).
    """
    vocab: dict[str, int] = {"<pad>": 0, "<unk>": 1}
    token_re = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")
    all_tokens: set[str] = set()
    for sample in corpus:
        all_tokens.update(token_re.findall(sample["text"].lower()))
    for tok in sorted(all_tokens):
        vocab[tok] = len(vocab)

    X, y = [], []
    for sample in corpus:
        text = sample["text"]
        entities = sample["entities"]
        bio_tags = entities_to_bio(text, entities)
        tokens = token_re.findall(text.lower())[:20]
        token_ids = [vocab.get(t, 1) for t in tokens]
        label_ids = [BIO_TO_IDX.get(t, O_IDX) for t in bio_tags[:20]]
        X.append(token_ids)
        y.append(label_ids)
    return X, y, vocab


# ---------------------------------------------------------------------------
# 5. BiLSTM NER model (PyTorch, from scratch)
# ---------------------------------------------------------------------------


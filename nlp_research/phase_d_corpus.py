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

# Label-schema fix (grammar-widening pass): DEDUCTION_TYPE is MERGED
# into TAX_SECTION. The two regex classes matched the SAME token set
# (every 80c/24b/... span), so _emit produced two gold entities for one
# span and the BIO encoder's later entity overwrote the earlier one —
# TAX_SECTION gold collapsed to ~2 tokens in the whole test split while
# 54 test texts carried section tokens. One class, no ambiguity.
NER_CLASSES = ["MONEY", "TAX_SECTION", "INCOME_TYPE", "DATE", "PERCENTAGE"]
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

# Grammar widening: MONEY and PERCENT now REQUIRE their markers. The old
# optional-suffix forms matched every bare digit sequence — "as on 1 april
# 2024" carried stray PERCENT:1 / PERCENT:2024 / MONEY:2024 gold spans,
# which turned ~98% of the corpus into accidental multi-entity samples.
MONEY_RE = re.compile(
    r"\b\d{1,3}(?:,\d{2,3})+(?:\.\d+)?(?:\s*(?:lakh|lac|crore))?\b"
    r"|\b\d+(?:\.\d+)?\s*(?:lakh|lac|crore|thousand|hundred|rupees?|rs\.?)\b"
    r"|\b\d+[kK]\b"
    r"|\brs\.?\s*[\d,]+\b",
    re.IGNORECASE)
TAX_SECTION_RE = re.compile(
    r"\b(?:80[cdegg]|80tt[ab]|80ccd|24[bbl]|80u[_-]?80dd|80ddb|80eea|nps|hra|pf|tds)\b",
    re.IGNORECASE)
INCOME_TYPE_RE = re.compile(
    r"\b(salary|business|capital_gains|rental|rent|agriculture|other_income|income)\b",
    re.IGNORECASE)
DATE_RE = re.compile(
    r"\b(?:\d{1,2}(?:st|nd|rd|th)?\s*(?:of\s*)?[a-z]+\s*\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
    r"\d{4}[-/]\d{2}(?:\d{2})?|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]?\s\d{1,2}|\d{1,2}\s"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]?\s?\b)",
    re.IGNORECASE)
PERCENT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|percent|per\.?\s*cent)\b",
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
MONEY_WORDS = ["1 lakh", "1,25,000", "50,000", "25k", "10,000", "15,000", "5 lakhs", "1.5 lakh",
               "2.5 lakhs", "75k", "3,00,000", "40 lakhs", "1.2 lakh", "2 lakh", "12,000", "60,000",
               # grammar-widening (deferred Sprint-7 item, 2026-11-16): more
               # realistic amount shapes — Indian-grouped lakhs, EMI-scale
               "2,50,000", "3 lakhs", "35,000", "1,00,000", "8,50,000"]
TAX_SECTION_WORDS = ["80c", "80d", "80g", "80u_80dd", "24b", "80ddb", "80eea", "nps",
                     "80tta", "80ttb", "80e", "80ccd",
                     # widening: the 80CCD(1B) headroom the product asks about
                     "80ccd_1b"]
INCOME_WORDS = ["salary", "business income", "capital gains", "rental income", "agriculture income",
                "freelance income", "consulting income", "pension"]
DATE_WORDS = ["1 april 2024", "30 june 2024", "15 january 2024", "01-01-2024", "march 2024",
              "5 june 2025", "31 march 2025", "28 february 2025", "10 december 2024",
              # widening: AY-style years and day-first formats
              "feb 2024", "05-03-2024", "2023-24"]
PERCENT_WORDS = ["30%", "5.5%", "10 percent", "7.5 percent", "20%", "12.5%", "15 percent", "25%",
                 # widening: surcharge-scale and small sliver rates
                 "22%", "18%", "0.5%", "1.5 percent"]


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
                # grammar widening (deferred Sprint-7 item): natural
                # EMI / transfer / deposit phrasings
                "emi of {0} every month",
                "i transferred {0} to ppf",
                "deposited {0} via upi",
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
                # widening: first-time claim and applicability phrasings
                "{0} applies to my case",
                "claimed {0} for the first time",
                # the former DEDUCTION_TYPE family (merged class): claim
                # and headroom phrasings over the same section tokens
                "claiming {0} under {1}",
                "eligible for {0}",
                "under {0} i get",
                "can i claim {0} this year",
                "{0} has unused headroom left",
                "{0} fully utilized this year",
                "proof of {0} attached",
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
                # widening: per-FY and second-source phrasings
                "my {0} for the year {1}",
                "received {0} plus {1}",
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
                # widening: range and AY phrasings
                "{0} onwards",
                "from {0} till the filing deadline",
                "for ay {0}",
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
                # widening: slab and effective-rate phrasings
                "{0} of the gross total income",
                "taxed at {0}",
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
    # Grammar widening (deferred Sprint-7 item): each multi template now
    # carries its OWN slot->pool sequence, so every filled sentence is
    # semantically coherent AND every span is regex-covered (the rule
    # extractor stays the gold-label source). The old bucket fill
    # (3 slots -> money/section/date, else money/money/date) produced
    # nonsense like "hra received 50000 which is 80c of my basic".
    multi_templates = [
        ("i earn {0} from salary and invest {1} under {2}",
         (MONEY_WORDS, MONEY_WORDS, TAX_SECTION_WORDS)),
        ("paid {0} as rent on {1} as of {2}",
         (MONEY_WORDS, MONEY_WORDS, DATE_WORDS)),
        ("claiming {0} under {1} at {2} marginal rate",
         (MONEY_WORDS, TAX_SECTION_WORDS, PERCENT_WORDS)),
        ("my salary is {0} and i put {1} in nps for {2}",
         (MONEY_WORDS, MONEY_WORDS, DATE_WORDS)),
        ("rental income of {0} taxed at {1} since {2}",
         (MONEY_WORDS, PERCENT_WORDS, DATE_WORDS)),
        ("donated {0} under {1} in {2}",
         (MONEY_WORDS, TAX_SECTION_WORDS, DATE_WORDS)),
        # widening: ELSS / home-loan / STCG / premium phrasings
        ("bought elss worth {0} under {1} in {2}",
         (MONEY_WORDS, TAX_SECTION_WORDS, DATE_WORDS)),
        ("home loan interest {0} claimed under {1} for {2}",
         (MONEY_WORDS, TAX_SECTION_WORDS, DATE_WORDS)),
        ("stcg of {0} taxed at {1} in {2}",
         (MONEY_WORDS, PERCENT_WORDS, DATE_WORDS)),
        ("i paid {0} as premium and {1} under {2}",
         (MONEY_WORDS, MONEY_WORDS, TAX_SECTION_WORDS)),
        ("invested {0} under {1} as of {2}",
         (MONEY_WORDS, TAX_SECTION_WORDS, DATE_WORDS)),
        (" hra received {0} which is {1} of my basic",
         (MONEY_WORDS, PERCENT_WORDS)),
        ("transferred {0} to ppf on {1} at {2} of the limit",
         (MONEY_WORDS, DATE_WORDS, PERCENT_WORDS)),
        ("claimed {0} as {1} deduction in {2}",
         (MONEY_WORDS, TAX_SECTION_WORDS, DATE_WORDS)),
    ]
    multi_target = num_samples // 5
    made_multi = 0
    attempts = 0
    # dedup-on-append across ALL loops (grammar widening): a duplicate
    # text is wasted training signal and skews the seeded split
    seen: set = set()

    def _emit(text: str, min_spans: int = 1) -> bool:
        """Gold-label the text via the rule extractor, dedup on the
        normalized text, and append. Returns True when emitted."""
        key = text.lower().strip()
        if key in seen:
            return False
        entities_map = extract_entities_rule(text)
        flat: list[dict] = []
        for label, spans in entities_map.items():
            for s in spans:
                flat.append({"span": s, "label": label})
        if len(flat) < min_spans:
            return False
        seen.add(key)
        out.append({"text": text, "entities": flat})
        return True

    while made_multi < multi_target and attempts < multi_target * 8:
        attempts += 1
        t, pools = multi_templates[rng.integers(len(multi_templates))]
        try:
            text = t.format(*(rng.choice(p) for p in pools))
        except Exception:
            continue
        if _emit(text, min_spans=2):
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
            # were silently dead). Grammar widening: gold labels come
            # from the SHARED rule extractor (all regex spans, not just
            # the family word — the per-type word-scan below dropped
            # every secondary entity in the sentence).
            n_slots = t.count("{")
            args = [word]
            for _slot in range(1, n_slots):
                args.append(rng.choice(all_words_pool))
            try:
                text = t.format(*args)
            except Exception:
                continue

            # keep the family's per-word scan as the COVERAGE gate: the
            # family word must appear, so every entity type keeps its
            # guaranteed share of the corpus
            if not any(w.lower() in text.lower() for w in words):
                continue
            _emit(text)

    # Fill remaining slots with mixed templates (dedup-on-append via
    # _emit; the attempt cap guards against pathological pools where
    # unique text runs out).
    all_words = []
    for cfg in entity_families.values():
        all_words.extend(cfg["words"])

    fill_attempts = 0
    fill_cap = num_samples * 60
    while len(out) < num_samples and fill_attempts < fill_cap:
        fill_attempts += 1
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
        _emit(text)

    return out[:num_samples]


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


def seeded_corpus_split(corpus: list[dict], seed: int = SEED,
                        test_frac: float = 0.2):
    """Seeded shuffle + 80/20 split at the RECORD level (grammar-
    widening pass, ml-review P2): the vocabulary must be built from the
    train rows only, so the corpus itself splits BEFORE featurization.
    Uses the same permutation semantics as seeded_split."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(corpus))
    shuffled = [corpus[i] for i in order]
    split_idx = int((1.0 - test_frac) * len(shuffled))
    return shuffled[:split_idx], shuffled[split_idx:]


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


def prepare_ner_dataset(corpus: list[dict], vocab: dict | None = None) -> tuple[list, list, dict]:
    """Prepare features and labels for the BiLSTM NER model.

    Sprint 7 S7.5 fixes, each earned by a measured failure:
    - Tokens map into a CORPUS-BUILT vocabulary (sorted, deterministic)
      instead of Python's randomized hash() — the old hash() % 500 both
      collided distinct words into one index AND made every run map
      words differently, so results were not reproducible at all.
    - Tokenization uses the SAME regex as the BIO tagger, so features
      and labels can never misalign.
    Evaluation-integrity fix (grammar-widening pass, ml-review P2): the
    vocabulary is built from the TRAIN rows only — call with the train
    corpus (vocab=None builds from it), then the test corpus passing
    that vocab; unseen test tokens map to <unk> (1) instead of being
    guaranteed in-vocab. Returns (X, y, vocab) where vocab maps token
    -> id (0=pad, 1=unk).
    """
    token_re = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")
    if vocab is None:
        vocab = {"<pad>": 0, "<unk>": 1}
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


# Summer internship project
"""Sprint 4 P0 — labeled corpus builder.

Spec: docs/sprint4-execution.md P0 item 2 (+ gate 3). Builds the labeled
utterance corpus with KNOWN-TRUE spans into
``data/{training,validation,test}/*.jsonl`` + a content-addressed
``data/manifest.json``. The ``data/corpus/`` directory (the runtime
capture stream's home) is created empty — it fills from opt-in
``TAX_CORPUS_CAPTURE`` deployments and is loaded by corpus.load_all().

Sources (priority order, docs/sprint4-execution.md P0 item 2):
  (a) ledger   — the docs/nlp-pipeline.md §11 misclassification patterns
                 and the Sprint 2/3 ledger items, labeled with their TRUE
                 (post-fix) categories. Eval material only: never written
                 to the training split.
  (b) synthetic— template families per category: amount/word-form/
                 Hinglish/monthly variants, multi-entity clause traps,
                 and the known P1-gap families (noun-form "shares sold",
                 "12k/mo" shorthand, kamaata/kiraya/mila/diya/bimari
                 Hinglish, leading monthly cues). Every rendered
                 utterance carries known-true (span, category, amount,
                 annualized) triples derived at generation time.
  (c) organic  — the golden-corpus conversations as multi-turn records
                 (final-state labels per docs/nlp-pipeline.md §9 —
                 engine-verified — and the golden regression tests).

Determinism: BUILD_SEED drives ONLY the template->split assignment;
renders and labels are fixed tables. The same seed rebuilds a
byte-identical corpus (manifest hashes match) — pinned by
tests/test_build_labeled_corpus.py::TestDeterminism.

Label semantics (the contract the eval measures):
  amount     = the value the pipeline should BOOK into the session key —
               post-annualization (monthly forms x12, the documented
               ADR-001 derivation) and post-clamp;
  annualized = True iff the utterance expresses a monthly figure;
  amount = null  for enum-collection spans (80U/80DD severity category);
  category = ABSTAIN  for amounts that must NOT be booked anywhere
               (ages, percentages, non-bookable loans, bare section
               mentions that must ask back) — the correct pipeline
               behavior is to ask, never guess.

Engine-verified template constraints (probed 2026-11-01):
  - a bare number immediately followed by a word starting with "k"
    ("40000 ka", "60000 kharch") parses the "k" as THOUSAND — Hinglish
    families therefore only use lakh/thousand-word amount forms;
  - the annualization window is AFTER the amount, so leading monthly
    cues ("monthly pension is 30k") are honest P1-gap families;
  - "rent {a} without hra" books rent_paid (the Rule 2A leg-b input),
    not 80gg — 80gg is the entitlement computed later.

Run from backend/:  python tools/build_labeled_corpus.py
"""
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Make the backend package modules importable no matter the caller's cwd
# (script lives in backend/tools/ — same convention as backup_db.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import corpus

BUILD_SEED = 40
BUILD_DATE = "2026-11-01"
BUILDER = "backend/tools/build_labeled_corpus.py"
SPLIT_RATIOS = {"training": 0.70, "validation": 0.15, "test": 0.15}

Span = Dict[str, object]
Render = Tuple[str, List[Span]]  # (utterance text, known-true spans)


# ---------------------------------------------------------------------------
# Amount tables. Values clear the parser floors (digits >= 100, word
# forms >= 1000). MONTHLY_AMOUNTS: (text, monthly value, ANNUAL value) —
# the label books the annual value with annualized=True.
# ---------------------------------------------------------------------------

EN_AMOUNT_PAIRS: Tuple[Tuple[str, int], ...] = (
    ("50,000", 50_000), ("25k", 25_000), ("0.5 lakh", 50_000),
    ("fifty thousand", 50_000), ("1.5 lakh", 150_000), ("1,50,000", 150_000),
    ("2 lakhs", 200_000), ("do lakh", 200_000), ("75,000", 75_000),
    ("30k", 30_000), ("10k", 10_000), ("3 lakh", 300_000),
    ("5 lakhs", 500_000), ("40k", 40_000), ("60k", 60_000),
    ("7.5 lakhs", 750_000), ("2.5 lakh", 250_000), ("20 lakh", 2_000_000),
    ("90 thousand", 90_000), ("1.2 lakh", 120_000), ("80k", 80_000),
    ("15 lakhs", 1_500_000), ("twelve lakh", 1_200_000), ("4 lakhs", 400_000),
)


def _distinct_normalized(pairs):
    seen = set()
    out = []
    for text, value in pairs:
        norm = corpus.normalized_text(text)
        if norm in seen:
            continue  # "50,000" and "50000" normalize equal — keep one
        seen.add(norm)
        out.append((text, value))
    return tuple(out)


EN_AMOUNTS = _distinct_normalized(EN_AMOUNT_PAIRS)

# Hinglish-safe amounts: word-unit forms ONLY. A bare number followed by a
# k-word ("50000 kamaye") parses the k as thousand — the k-landmine.
HINGLISH_AMOUNTS = _distinct_normalized(tuple(
    (t, v) for t, v in EN_AMOUNT_PAIRS
    if not t[-1].isdigit() and t[-1] not in ",k"
))

MONTHLY_AMOUNTS: Tuple[Tuple[str, int, int], ...] = (
    ("45k pm", 45_000, 540_000),
    ("50,000 per month", 50_000, 600_000),
    ("40k monthly", 40_000, 480_000),
    ("30k har mahine", 30_000, 360_000),
    ("25k /month", 25_000, 300_000),
    ("20k mahine ka", 20_000, 240_000),
    ("60k per month", 60_000, 720_000),
    ("15k pm", 15_000, 180_000),
)

# P1 item 6 financial shorthand the current parser misses:
SHORTHAND_AMOUNTS: Tuple[Tuple[str, int, int], ...] = (
    ("12k/mo", 12_000, 144_000),
    ("2.5L/mo", 250_000, 3_000_000),
)

# The statutory flat 80U/80DD amounts (docs/tax-verification.md §6):
FLAT_AMOUNTS: Tuple[Tuple[str, int], ...] = (
    ("75,000", 75_000), ("1,25,000", 125_000),
)


def _spans(triples: Sequence[Tuple[str, str, Optional[int], bool]]) -> List[Span]:
    return [{"text": t, "category": c, "amount": a, "annualized": ann}
            for t, c, a, ann in triples]


def _amount_span(text: str, value: int, category: str,
                 annualized: bool = False) -> List[Span]:
    return _spans([(text, category, value, annualized)])


def _renders(skeletons: Sequence[str], amounts, category: str) -> List[Render]:
    """Cross skeletons with a deterministic strided amount pick (5 per
    skeleton), deduping normalized texts within the family."""
    renders: List[Render] = []
    seen = set()
    for i, skeleton in enumerate(skeletons):
        for j in range(7):
            text, value = amounts[(i * 5 + j) % len(amounts)]
            normalized = corpus.normalized_text(skeleton.format(a=text))
            if normalized in seen:
                continue
            seen.add(normalized)
            renders.append((skeleton.format(a=text),
                            _amount_span(text, value, category)))
    return renders


def _monthly_renders(skeletons: Sequence[str], category: str) -> List[Render]:
    """Monthly-form renders: label = ANNUAL value (x12 documented
    derivation). Shorthand forms ("12k/mo") ride on the first skeleton —
    they are the P1 item 6 gap family."""
    renders: List[Render] = []
    seen = set()
    for i, skeleton in enumerate(skeletons):
        table = MONTHLY_AMOUNTS + (SHORTHAND_AMOUNTS if i == 0 else ())
        for text, _monthly, annual in table:
            normalized = corpus.normalized_text(skeleton.format(a=text))
            if normalized in seen:
                continue
            seen.add(normalized)
            renders.append((skeleton.format(a=text),
                            _amount_span(text, annual, category,
                                         annualized=True)))
    return renders


def _phrase_renders(phrases: Sequence[str], category: str) -> List[Render]:
    """Enum-collection / abstain families: amount=None spans."""
    return [(phrase, _spans([(phrase, category, None, False)]))
            for phrase in phrases]


# ---------------------------------------------------------------------------
# (b) Synthetic template families — (template_id, lang, renders).
# ---------------------------------------------------------------------------

def _families() -> List[Tuple[str, str, List[Render]]]:
    fams: List[Tuple[str, str, List[Render]]] = []

    def add(template_id: str, lang: str, renders: List[Render]) -> None:
        fams.append((template_id, lang, renders))

    # ---- salary --------------------------------------------------------
    add("syn-salary-stmt", "en", _renders(
        ("my salary is {a}", "my annual salary is {a}",
         "{a} is my annual salary", "salary credited this year was {a}"),
        EN_AMOUNTS, "salary"))
    add("syn-salary-earn", "en", _renders(
        ("I earn {a} as salary", "I earn {a} per year in salary",
         "earning a salary of {a}"), EN_AMOUNTS, "salary"))
    add("syn-salary-ctc", "en", _renders(
        ("my CTC is {a}", "ctc of {a}", "my gross pay is {a}"),
        EN_AMOUNTS, "salary"))
    add("syn-salary-form16", "en", _renders(
        ("form 16 shows {a}", "as per form 16 my gross pay is {a}"),
        EN_AMOUNTS, "salary"))
    add("syn-salary-job", "en", _renders(
        ("I earn {a} from my job", "my job pays me {a}"), EN_AMOUNTS,
        "salary"))
    add("syn-salary-amountfirst", "en", _renders(
        ("{a} salary credited", "{a} was my take home"), EN_AMOUNTS,
        "salary"))
    add("syn-salary-monthly", "en", _monthly_renders(
        ("my salary is {a}", "salary {a} milti hai"), "salary"))
    add("syn-salary-hinglish", "hinglish", _renders(
        ("meri salary {a} hai", "naukri mein {a} milte hain",
         "salary {a} milti hai meri"), HINGLISH_AMOUNTS, "salary"))

    # ---- business ------------------------------------------------------
    add("syn-business-turnover", "en", _renders(
        ("business turnover of {a}", "my turnover is {a}",
         "turnover of {a} this year"), EN_AMOUNTS, "business"))
    add("syn-business-shop", "en", _renders(
        ("my shop earns {a}", "shop income is {a}"), EN_AMOUNTS, "business"))
    add("syn-business-freelance", "en", _renders(
        ("freelance income of {a}", "I earn {a} from freelance projects"),
        EN_AMOUNTS, "business"))
    add("syn-business-consult", "en", _renders(
        ("consultancy income {a}", "professional fees of {a}",
         "my practice income is {a}"), EN_AMOUNTS, "business"))
    add("syn-business-profit", "en", _renders(
        ("business profit of {a}", "trading profit was {a}"),
        EN_AMOUNTS, "business"))
    add("syn-business-gig", "en", _renders(
        ("gig work income {a}", "ecommerce sales {a}",
         "startup revenue {a}"), EN_AMOUNTS, "business"))
    add("syn-business-amountfirst", "en", _renders(
        ("{a} from my business", "{a} business receipts"), EN_AMOUNTS,
        "business"))
    add("syn-business-hinglish", "hinglish", _renders(
        ("mera vyapar {a} ka hai", "dukaan se saal mein {a} kamaye",
         "vyapar mein {a} kamaya is saal"), HINGLISH_AMOUNTS, "business"))

    # ---- rental --------------------------------------------------------
    add("syn-rental-income", "en", _renders(
        ("rental income of {a}", "I get rental income of {a}"),
        EN_AMOUNTS, "rental"))
    add("syn-rental-tenant", "en", _renders(
        ("tenant pays {a}", "my tenant pays {a} as rent"),
        EN_AMOUNTS, "rental"))
    add("syn-rental-letout", "en", _renders(
        ("I have let out a property for {a}", "property let out at {a}"),
        EN_AMOUNTS, "rental"))
    add("syn-rental-pg", "en", _renders(
        ("pg income {a}", "hostel income {a}"), EN_AMOUNTS, "rental"))
    add("syn-rental-amountfirst", "en", _renders(
        ("{a} from rent received", "{a} rental received"), EN_AMOUNTS,
        "rental"))
    add("syn-rental-monthly", "en", _monthly_renders(
        ("rent received is {a}", "rental income {a}"), "rental"))
    add("syn-rental-hinglish", "hinglish", _renders(
        ("mujhe {a} kiraya milta hai", "kiraya se {a} aata hai"),
        HINGLISH_AMOUNTS, "rental"))
    add("syn-rental-hinglish2", "hinglish", _renders(
        ("tenant mujhe {a} deta hai", "makaan pe {a} ka kiraya hai"),
        HINGLISH_AMOUNTS, "rental"))

    # ---- agriculture ---------------------------------------------------
    add("syn-agri-basic", "en", _renders(
        ("agricultural income of {a}", "agriculture income was {a}",
         "my farm income is {a}"), EN_AMOUNTS, "agriculture"))
    add("syn-agri-crop", "en", _renders(
        ("crop sale of {a}", "paddy sale fetched {a}"),
        EN_AMOUNTS, "agriculture"))
    add("syn-agri-farming", "en", _renders(
        ("farming income {a}", "farming profit was {a}"),
        EN_AMOUNTS, "agriculture"))
    add("syn-agri-produce", "en", _renders(
        ("sale of produce brought {a}", "wheat cultivation earned {a}"),
        EN_AMOUNTS, "agriculture"))
    add("syn-agri-sugarcane", "en", _renders(
        ("sugarcane crop earned {a}", "nursery income {a}"),
        EN_AMOUNTS, "agriculture"))
    add("syn-agri-amountfirst", "en", _renders(
        ("{a} from agriculture", "{a} agri income"), EN_AMOUNTS,
        "agriculture"))
    add("syn-agri-hinglish", "hinglish", _renders(
        ("kheti badi se {a} kamaye", "kisan ke roop mein {a} kamaya"),
        HINGLISH_AMOUNTS, "agriculture"))
    add("syn-agri-hinglish2", "hinglish", _renders(
        ("kheti se {a} aaya", "{a} ki fasal biki"), HINGLISH_AMOUNTS,
        "agriculture"))

    # ---- capital_gains -------------------------------------------------
    add("syn-cg-shares", "en", _renders(
        ("sold shares for {a}", "I sold shares worth {a}",
         "sold stocks for {a}"), EN_AMOUNTS, "capital_gains"))
    # P1 item 3: noun-form pairs ("shares sold"/"stocks sold") — today the
    # verb-form keywords miss them and the default fall-through books the
    # profile default. TRUE label: capital_gains.
    add("syn-cg-shares-nounform", "en", _renders(
        ("shares sold for {a}", "stocks sold at {a}"),
        EN_AMOUNTS, "capital_gains"))
    add("syn-cg-property", "en", _renders(
        ("sold property for {a}", "property sale of {a}",
         "sold my house for {a}", "flat sale fetched {a}"),
        EN_AMOUNTS, "capital_gains"))
    add("syn-cg-mf", "en", _renders(
        ("mutual fund redemption of {a}", "redeemed {a} of mutual funds"),
        EN_AMOUNTS, "capital_gains"))
    add("syn-cg-stcg-ltcg", "en", _renders(
        ("stcg of {a} on shares", "long term gain of {a} on equity"),
        EN_AMOUNTS, "capital_gains"))
    add("syn-cg-gold", "en", _renders(
        ("sale of gold fetched {a}", "jewelry sale {a}"),
        EN_AMOUNTS, "capital_gains"))
    add("syn-cg-amountfirst", "en", _renders(
        ("{a} capital gain booked", "{a} ltcg on shares"), EN_AMOUNTS,
        "capital_gains"))
    add("syn-cg-hinglish", "hinglish", _renders(
        ("shares bech kar {a} kamaye", "property bechne se {a} mile"),
        HINGLISH_AMOUNTS, "capital_gains"))

    # ---- other_income --------------------------------------------------
    add("syn-oi-fd", "en", _renders(
        ("fd interest of {a}", "bank fd interest was {a}",
         "interest from fd is {a}"), EN_AMOUNTS, "other_income"))
    add("syn-oi-bank", "en", _renders(
        ("bank interest {a}", "interest on bonds was {a}"),
        EN_AMOUNTS, "other_income"))
    add("syn-oi-dividend", "en", _renders(
        ("dividend income {a}", "received {a} as dividend"),
        EN_AMOUNTS, "other_income"))
    add("syn-oi-pension", "en", _renders(
        ("pension of {a}", "family pension was {a}"), EN_AMOUNTS,
        "other_income"))
    add("syn-oi-recurring", "en", _renders(
        ("recurring deposit interest {a}", "post office interest {a}"),
        EN_AMOUNTS, "other_income"))
    add("syn-oi-misc", "en", _renders(
        ("lottery winnings of {a}", "prize money {a}",
         "royalty income {a}", "commission of {a}"), EN_AMOUNTS,
        "other_income"))
    # P1 word-order gap: the monthly cue BEFORE the amount is missed by
    # the trailing-window annualization — TRUE label is the x12 value.
    add("syn-oi-pension-leading-monthly", "en", _monthly_renders(
        ("monthly pension is {a}",), "other_income"))

    # ---- 80c -----------------------------------------------------------
    add("syn-80c-ppf", "en", _renders(
        ("PPF contribution of {a}", "I invested {a} in PPF"),
        EN_AMOUNTS, "80c"))
    add("syn-80c-elss-lic", "en", _renders(
        ("ELSS investment {a}", "LIC premium of {a}",
         "life insurance premium {a}"), EN_AMOUNTS, "80c"))
    add("syn-80c-tuition", "en", _renders(
        ("tuition fees {a}", "children school fees {a}",
         "college fees of {a}"), EN_AMOUNTS, "80c"))
    add("syn-80c-others", "en", _renders(
        ("sukanya samriddhi {a}", "nsc of {a}",
         "epf contribution {a}", "home loan principal paid {a}"),
        EN_AMOUNTS, "80c"))
    add("syn-80c-ssy", "en", _renders(
        ("sukanya samriddhi account {a}", "ssy deposit {a}"),
        EN_AMOUNTS, "80c"))
    add("syn-80c-amountfirst", "en", _renders(
        ("{a} invested under 80c", "{a} went into section 80c"),
        EN_AMOUNTS, "80c"))
    add("syn-80c-hinglish", "hinglish", _renders(
        ("PPF mein {a} daala", "bachat khit mein {a} jama kiye"),
        HINGLISH_AMOUNTS, "80c"))

    # ---- 80d -----------------------------------------------------------
    add("syn-80d-health", "en", _renders(
        ("health insurance premium {a}", "I pay {a} health insurance",
         "medical insurance {a}"), EN_AMOUNTS, "80d"))
    add("syn-80d-mediclaim", "en", _renders(
        ("mediclaim premium {a}", "mediclaim of {a}"), EN_AMOUNTS, "80d"))
    add("syn-80d-section", "en", _renders(
        ("80d deduction {a}", "section 80d {a}"), EN_AMOUNTS, "80d"))
    add("syn-80d-family", "en", _renders(
        ("family insurance premium {a}", "family health cover {a}"),
        EN_AMOUNTS, "80d"))
    add("syn-80d-star", "en", _renders(
        ("star health policy {a}", "niva bupa premium {a}"),
        EN_AMOUNTS, "80d"))
    add("syn-80d-checkup", "en", _renders(
        ("preventive health checkup cost {a}",), EN_AMOUNTS, "80d"))
    add("syn-80d-amountfirst", "en", _renders(
        ("{a} paid as health premium", "{a} towards 80d insurance"),
        EN_AMOUNTS, "80d"))
    add("syn-80d-hinglish", "hinglish", _renders(
        ("swasthya bima {a} ka premium",), HINGLISH_AMOUNTS, "80d"))

    # ---- 80d_parents ---------------------------------------------------
    add("syn-80dp-parents", "en", _renders(
        ("parents health insurance {a}", "health insurance for parents {a}",
         "parents mediclaim {a}"), EN_AMOUNTS, "80d_parents"))
    add("syn-80dp-momdad", "en", _renders(
        ("mom insurance {a}", "dad mediclaim {a}",
         "medical for parents {a}"), EN_AMOUNTS, "80d_parents"))
    add("syn-80dp-senior", "en", _renders(
        ("senior citizen parents insurance {a}",
         "senior citizen medical for parents {a}"), EN_AMOUNTS,
        "80d_parents"))
    add("syn-80dp-mother", "en", _renders(
        ("mother policy {a}", "father policy {a}"), EN_AMOUNTS,
        "80d_parents"))
    add("syn-80dp-amountfirst", "en", _renders(
        ("{a} premium for parents health", "{a} parents mediclaim paid"),
        EN_AMOUNTS, "80d_parents"))
    add("syn-80dp-hinglish", "hinglish", _renders(
        ("mata pita ki bima premium {a}", "pita ji ki mediclaim {a}"),
        HINGLISH_AMOUNTS, "80d_parents"))
    add("syn-80dp-hinglish2", "hinglish", _renders(
        ("maa baap ki bimari bima {a}", "parents ke liye bima {a} diya"),
        HINGLISH_AMOUNTS, "80d_parents"))

    # ---- 80e -----------------------------------------------------------
    add("syn-80e-eduloan", "en", _renders(
        ("education loan interest {a}", "interest on education loan {a}"),
        EN_AMOUNTS, "80e"))
    add("syn-80e-student", "en", _renders(
        ("student loan interest {a}", "study loan interest {a}"),
        EN_AMOUNTS, "80e"))
    add("syn-80e-loan-amt", "en", _renders(
        ("education loan of {a}", "higher education loan {a}"),
        EN_AMOUNTS, "80e"))
    add("syn-80e-phrasing", "en", _renders(
        ("mba loan interest paid {a}", "college loan interest {a}"),
        EN_AMOUNTS, "80e"))
    add("syn-80e-vidya", "en", _renders(
        ("vidyalakshmi loan interest {a}", "university loan interest {a}"),
        EN_AMOUNTS, "80e"))
    add("syn-80e-amountfirst", "en", _renders(
        ("{a} paid as education loan interest",
         "{a} education interest this year"), EN_AMOUNTS, "80e"))
    add("syn-80e-hinglish", "hinglish", _renders(
        ("padhai ke loan ka byaaj {a} diya",), HINGLISH_AMOUNTS, "80e"))
    add("syn-80e-hinglish2", "hinglish", _renders(
        ("study loan ka interest {a} gaya",), HINGLISH_AMOUNTS, "80e"))

    # ---- 80g -----------------------------------------------------------
    add("syn-80g-pmcares", "en", _renders(
        ("donated {a} to PM CARES", "pm relief fund received {a}"),
        EN_AMOUNTS, "80g"))
    add("syn-80g-ngo", "en", _renders(
        ("donated {a} to an NGO", "ngo donation {a}",
         "donated {a} to a charitable trust"), EN_AMOUNTS, "80g"))
    add("syn-80g-temple", "en", _renders(
        ("temple donation {a}", "donated {a} to gurudwara"),
        EN_AMOUNTS, "80g"))
    add("syn-80g-generic", "en", _renders(
        ("charity donation {a}", "made a donation of {a}"),
        EN_AMOUNTS, "80g"))
    add("syn-80g-relief", "en", _renders(
        ("cm relief fund {a}", "national defence fund {a}"),
        EN_AMOUNTS, "80g"))
    add("syn-80g-amountfirst", "en", _renders(
        ("{a} given as charity", "{a} donated in cash"), EN_AMOUNTS, "80g"))
    add("syn-80g-hinglish", "hinglish", _renders(
        ("ngo ko {a} daan kiye", "mandir mein {a} daan kiya"),
        HINGLISH_AMOUNTS, "80g"))
    add("syn-80g-hinglish2", "hinglish", _renders(
        ("trust ko {a} diya daan mein",), HINGLISH_AMOUNTS, "80g"))

    # ---- nps -----------------------------------------------------------
    add("syn-nps-basic", "en", _renders(
        ("NPS contribution {a}", "I invested {a} in NPS"),
        EN_AMOUNTS, "nps"))
    add("syn-nps-80ccd", "en", _renders(
        ("80ccd(1b) contribution {a}", "80ccd of {a}"), EN_AMOUNTS, "nps"))
    add("syn-nps-tier1", "en", _renders(
        ("nps tier 1 contribution {a}",
         "national pension contribution {a}"), EN_AMOUNTS, "nps"))
    add("syn-nps-atal", "en", _renders(
        ("atal pension contribution {a}", "pension contribution {a}"),
        EN_AMOUNTS, "nps"))
    add("syn-nps-amountfirst", "en", _renders(
        ("{a} contributed to nps", "{a} went into nps tier 1"),
        EN_AMOUNTS, "nps"))
    add("syn-nps-monthly", "en", _monthly_renders(
        ("nps contribution is {a}",), "nps"))
    add("syn-nps-hinglish", "hinglish", _renders(
        ("NPS mein {a} daale",), HINGLISH_AMOUNTS, "nps"))
    add("syn-nps-hinglish2", "hinglish", _renders(
        ("nps ke liye {a} jama kiye",), HINGLISH_AMOUNTS, "nps"))

    # ---- hra_received --------------------------------------------------
    add("syn-hra-basic", "en", _renders(
        ("my hra is {a}", "hra received {a}"), EN_AMOUNTS, "hra_received"))
    add("syn-hra-allowance", "en", _renders(
        ("house rent allowance {a}", "hra from employer {a}"),
        EN_AMOUNTS, "hra_received"))
    add("syn-hra-employer", "en", _renders(
        ("employer paid {a} as hra", "{a} hra from company"),
        EN_AMOUNTS, "hra_received"))
    add("syn-hra-amountfirst", "en", _renders(
        ("{a} hra received this year",), EN_AMOUNTS, "hra_received"))
    add("syn-hra-monthly", "en", _monthly_renders(
        ("hra received is {a}", "my hra is {a}"), "hra_received"))
    add("syn-hra-monthly2", "en", _monthly_renders(
        ("hra {a} monthly milta hai",), "hra_received"))
    add("syn-hra-hinglish", "hinglish", _renders(
        ("naukri mein {a} hra milta hai",), HINGLISH_AMOUNTS,
        "hra_received"))
    add("syn-hra-hinglish2", "hinglish", _renders(
        ("company se {a} hra mila",), HINGLISH_AMOUNTS, "hra_received"))

    # ---- rent_paid -----------------------------------------------------
    add("syn-rentp-pay", "en", _renders(
        ("I pay rent of {a}", "paying rent {a}", "rent paid {a}"),
        EN_AMOUNTS, "rent_paid"))
    add("syn-rentp-monthly", "en", _monthly_renders(
        ("monthly rent is {a}", "I pay rent {a}"), "rent_paid"))
    add("syn-rentp-landlord", "en", _renders(
        ("rent to landlord {a}", "i pay {a} rent to my landlord"),
        EN_AMOUNTS, "rent_paid"))
    add("syn-rentp-withouthra", "en", _renders(
        ("rent {a} without hra", "paying {a} rent without hra"),
        EN_AMOUNTS, "rent_paid"))
    add("syn-rentp-selfemployed", "en", _renders(
        ("self employed rent paid {a}",), EN_AMOUNTS, "rent_paid"))
    add("syn-rentp-flat", "en", _renders(
        ("flat rent {a}", "apartment rent {a}"), EN_AMOUNTS, "rent_paid"))
    add("syn-rentp-amountfirst", "en", _renders(
        ("{a} rent paid this year", "{a} paid as house rent"),
        EN_AMOUNTS, "rent_paid"))
    add("syn-rentp-hinglish", "hinglish", _renders(
        ("kiraya {a} deta hoon", "{a} kiraya har mahine deta hoon"),
        HINGLISH_AMOUNTS, "rent_paid"))
    add("syn-rentp-hinglish2", "hinglish", _renders(
        ("har mahine {a} ka kiraya deta hoon",), HINGLISH_AMOUNTS,
        "rent_paid"))

    # ---- 24b -----------------------------------------------------------
    add("syn-24b-interest", "en", _renders(
        ("home loan interest {a}", "interest on home loan {a}",
         "paid {a} home loan interest"), EN_AMOUNTS, "24b"))
    add("syn-24b-housing", "en", _renders(
        ("housing loan interest {a}", "house loan interest {a}"),
        EN_AMOUNTS, "24b"))
    add("syn-24b-section", "en", _renders(
        ("24b {a}", "section 24 interest {a}"), EN_AMOUNTS, "24b"))
    add("syn-24b-mortgage", "en", _renders(
        ("mortgage interest {a}", "emi interest component {a}"),
        EN_AMOUNTS, "24b"))
    add("syn-24b-emi", "en", _renders(
        ("home loan emi interest {a}", "emi interest component paid {a}"),
        EN_AMOUNTS, "24b"))
    add("syn-24b-amountfirst", "en", _renders(
        ("{a} home loan interest paid", "{a} went as housing loan interest"),
        EN_AMOUNTS, "24b"))
    add("syn-24b-hinglish", "hinglish", _renders(
        ("ghar ke loan ka byaaj {a} diya",), HINGLISH_AMOUNTS, "24b"))
    add("syn-24b-hinglish2", "hinglish", _renders(
        ("makan ke byaaj mein {a} gaya",), HINGLISH_AMOUNTS, "24b"))

    # ---- 80tta ---------------------------------------------------------
    add("syn-80tta-savings", "en", _renders(
        ("savings account interest {a}", "bank savings interest {a}"),
        EN_AMOUNTS, "80tta"))
    add("syn-80tta-section", "en", _renders(
        ("80tta {a}", "80tta deduction {a}"), EN_AMOUNTS, "80tta"))
    add("syn-80tta-section2", "en", _renders(
        ("80tta exemption {a}",), EN_AMOUNTS, "80tta"))
    add("syn-80tta-phrasing", "en", _renders(
        ("saving bank interest earned {a}",
         "savings bank interest of {a}"), EN_AMOUNTS, "80tta"))
    add("syn-80tta-book", "en", _renders(
        ("savings account interest of {a} earned",),
        EN_AMOUNTS, "80tta"))
    add("syn-80tta-amountfirst", "en", _renders(
        ("{a} savings account interest earned",), EN_AMOUNTS, "80tta"))
    add("syn-80tta-hinglish", "hinglish", _renders(
        ("bachat khate ka byaaj {a} mila",), HINGLISH_AMOUNTS, "80tta"))
    add("syn-80tta-hinglish2", "hinglish", _renders(
        ("saving account byaaj {a}",), HINGLISH_AMOUNTS, "80tta"))

    # ---- 80ttb ---------------------------------------------------------
    add("syn-80ttb-senior", "en", _renders(
        ("senior citizen interest {a}", "senior citizen bank interest {a}"),
        EN_AMOUNTS, "80ttb"))
    add("syn-80ttb-fd", "en", _renders(
        ("fd interest senior citizen {a}", "fd interest senior {a}"),
        EN_AMOUNTS, "80ttb"))
    add("syn-80ttb-section", "en", _renders(
        ("80ttb {a}", "80ttb deduction of {a}"), EN_AMOUNTS, "80ttb"))
    add("syn-80ttb-section2", "en", _renders(
        ("80ttb exemption {a}",), EN_AMOUNTS, "80ttb"))
    add("syn-80ttb-amountfirst", "en", _renders(
        ("{a} senior citizen interest earned",
         "{a} interest for senior citizens"), EN_AMOUNTS, "80ttb"))
    add("syn-80ttb-senior2", "en", _renders(
        ("senior citizen savings interest {a}",), EN_AMOUNTS, "80ttb"))
    add("syn-80ttb-hinglish", "hinglish", _renders(
        ("burhape ka interest {a} mila",), HINGLISH_AMOUNTS, "80ttb"))
    add("syn-80ttb-hinglish2", "hinglish", _renders(
        ("80ttb ke tahat {a} mila",), HINGLISH_AMOUNTS, "80ttb"))

    # ---- 80gg ----------------------------------------------------------
    add("syn-80gg-section", "en", _renders(
        ("80gg deduction {a}", "claiming 80gg of {a}", "80gg {a}"),
        EN_AMOUNTS, "80gg"))
    add("syn-80gg-section2", "en", _renders(
        ("80gg exemption {a}", "80gg {a} claimed"), EN_AMOUNTS, "80gg"))
    add("syn-80gg-section3", "en", _renders(
        ("under 80gg i claim {a}", "80gg rent {a} without hra"),
        EN_AMOUNTS, "80gg"))
    add("syn-80gg-amountfirst", "en", _renders(
        ("{a} claimed under 80gg", "{a} 80gg exemption"), EN_AMOUNTS,
        "80gg"))
    add("syn-80gg-annual", "en", _renders(
        ("{a} annual rent exempted via 80gg",), EN_AMOUNTS, "80gg"))
    add("syn-80gg-hinglish", "hinglish", _renders(
        ("hra nahi milta, {a} kiraya deta hoon",), HINGLISH_AMOUNTS,
        "80gg"))
    add("syn-80gg-hinglish2", "hinglish", _renders(
        ("80gg ke tahat {a} ka kiraya",), HINGLISH_AMOUNTS, "80gg"))
    add("syn-80gg-hinglish3", "hinglish", _renders(
        ("80gg claim karta hoon {a} ka",), HINGLISH_AMOUNTS, "80gg"))

    # ---- 80u_80dd (enum collection + the two flat amounts) --------------
    add("syn-80u-severe", "en", _phrase_renders(
        ("I have severe disability", "severe disability deduction claim",
         "80 percent disability", "disability 100 percent",
         "I claim 80u with severe disability",
         "severely handicapped dependent", "80 percent disabled",
         "100 percent disabled", "severe disability — 80u case",
         "80u severe handicap claim", "severe disability benefits claim"),
        "80u_80dd"))
    add("syn-80u-partial", "en", _phrase_renders(
        ("I am 40 percent handicapped", "partial disability",
         "disability 40 percent", "40 percent handicap",
         "handicapped with 40 percent disability", "partially disabled",
         "disability of 40 percent", "partial handicap claim",
         "disability 60 percent", "60 percent disabled"),
        "80u_80dd"))
    add("syn-80u-section", "en", _phrase_renders(
        ("disability deduction claim under 80u",
         "my disability is certified — 80u",
         "disability certified under 80dd",
         "child disability — 80dd claim", "disabled sibling — 80dd",
         "handicapped dependent care", "80u disability deduction claim",
         "80dd for my disabled sister", "my disability — 80u claim"),
        "80u_80dd"))
    add("syn-80u-dependent", "en", _phrase_renders(
        ("disabled dependent — 80dd claim",
         "my sibling is disabled and I claim 80dd",
         "disabled son — 80dd", "handicapped brother 80dd claim",
         "disabled father — 80dd", "dependent disability 80dd"),
        "80u_80dd"))
    add("syn-80u-hinglish", "hinglish", _phrase_renders(
        ("disability hai 40 percent", "40 percent tang hai — 80u",
         "handicapped hai — 80dd claim", "severe disability hai"),
        "80u_80dd"))
    add("syn-80u-flat-75k", "en", _renders(
        ("disability deduction of {a}", "80u deduction of {a}"),
        (("75,000", 75_000),), "80u_80dd"))
    add("syn-80u-flat-125k", "en", _renders(
        ("80dd deduction of {a}", "claiming {a} under 80dd"),
        (("1,25,000", 125_000),), "80u_80dd"))
    add("syn-80u-flat-phrase", "en", _phrase_renders(
        ("disability deduction 75000 claimed", "80u flat 75000",
         "80dd flat deduction 125000", "80u 1,25,000 claimed",
         "80dd 75000 flat deduction"), "80u_80dd"))

    # ---- 80ddb ---------------------------------------------------------
    add("syn-80ddb-cancer", "en", _renders(
        ("cancer treatment expenses {a}", "spent {a} on cancer treatment"),
        EN_AMOUNTS, "80ddb"))
    add("syn-80ddb-critical", "en", _renders(
        ("critical illness treatment {a}",
         "special disease treatment cost {a}"), EN_AMOUNTS, "80ddb"))
    add("syn-80ddb-critical2", "en", _renders(
        ("cancer treatment cost {a}", "critical illness expenses {a}"),
        EN_AMOUNTS, "80ddb"))
    add("syn-80ddb-section", "en", _renders(
        ("80ddb {a}", "80ddb expenses {a}"), EN_AMOUNTS, "80ddb"))
    add("syn-80ddb-section2", "en", _renders(
        ("80ddb deduction {a}",), EN_AMOUNTS, "80ddb"))
    add("syn-80ddb-special", "en", _renders(
        ("special disease treatment {a}",), EN_AMOUNTS, "80ddb"))
    add("syn-80ddb-amountfirst", "en", _renders(
        ("{a} spent on cancer treatment", "{a} 80ddb expenses"),
        EN_AMOUNTS, "80ddb"))
    add("syn-80ddb-hinglish", "hinglish", _renders(
        ("bimari ke ilaaj mein {a} kharch hue",), HINGLISH_AMOUNTS,
        "80ddb"))
    add("syn-80ddb-hinglish2", "hinglish", _renders(
        ("80ddb ke tahat {a} kharch",), HINGLISH_AMOUNTS, "80ddb"))

    return fams


# ---------------------------------------------------------------------------
# Multi-entity clause traps ("PPF and health insurance" splits etc.)
# ---------------------------------------------------------------------------

def _clause_trap_families() -> List[Tuple[str, str, List[Render]]]:
    traps: List[Tuple[str, str, List[Render]]] = []
    pairs = (
        ("I invested 1.5L in PPF and 60k in health insurance",
         [("1.5L", "80c", 150_000, False),
          ("60k", "80d", 60_000, False)]),
        ("2 lakh in PPF and 25k in mediclaim",
         [("2 lakh", "80c", 200_000, False),
          ("25k", "80d", 25_000, False)]),
        ("PPF of 100k and medical insurance 20k",
         [("100k", "80c", 100_000, False),
          ("20k", "80d", 20_000, False)]),
        ("salary of 10 lakh and rental income of 50k",
         [("10 lakh", "salary", 1_000_000, False),
          ("50k", "rental", 50_000, False)]),
        ("i earned 20 lakhs from salary and 5 lakhs from property sale",
         [("20 lakhs", "salary", 2_000_000, False),
          ("5 lakhs", "capital_gains", 500_000, False)]),
        ("nps of 50k and parents health insurance of 30k",
         [("50k", "nps", 50_000, False),
          ("30k", "80d_parents", 30_000, False)]),
        ("donated 40k to temple and 20k to an NGO",
         [("40k", "80g", 40_000, False),
          ("20k", "80g", 20_000, False)]),
        ("education loan interest of 1 lakh and home loan interest of 2 lakh",
         [("1 lakh", "80e", 100_000, False),
          ("2 lakh", "24b", 200_000, False)]),
        ("rental income 80k and agricultural income 2 lakhs",
         [("80k", "rental", 80_000, False),
          ("2 lakhs", "agriculture", 200_000, False)]),
        ("fd interest of 30k and dividend of 10k",
         [("30k", "other_income", 30_000, False),
          ("10k", "other_income", 10_000, False)]),
        ("hra received 8k per month and rent paid 15k per month",
         [("8k per month", "hra_received", 96_000, True),
          ("15k per month", "rent_paid", 180_000, True)]),
        ("my salary is 50,000 per month and rent is 12k monthly",
         [("50,000 per month", "salary", 600_000, True),
          ("12k monthly", "rent_paid", 144_000, True)]),
    )
    for i, (text, span_triples) in enumerate(pairs, 1):
        traps.append((f"syn-clastrap-{i:02d}", "en",
                      [(text, _spans(span_triples))]))
    return traps


# ---------------------------------------------------------------------------
# (a) Ledger — §11 patterns + Sprint 2/3 ledger items, TRUE labels.
# ---------------------------------------------------------------------------

def _ledger_records() -> List[dict]:
    records: List[dict] = []

    def turn(text, spans):
        return {"text": text, "spans": spans}

    def add(rid, template_id, turns, ref, lang="en"):
        spans = [s for t in turns for s in t["spans"]]
        records.append({
            "id": rid,
            "text": " || ".join(t["text"] for t in turns),
            "source": "ledger",
            "template_id": template_id,
            "lang": lang,
            "spans": spans,
            "turns": turns,
            "provenance": {
                "builder": BUILDER, "built_on": BUILD_DATE,
                "corpus_version": corpus.CORPUS_SCHEMA_VERSION,
                "ref": ref,
            },
        })

    add("led-tuition-80c", "led-tuition-80c",
        [turn("I am a software engineer earning 45 lakhs per year",
              _amount_span("45 lakhs", 4_500_000, "salary")),
         turn("childs tution of 2 Lakhs",
              _amount_span("2 Lakhs", 200_000, "80c"))],
        "docs/nlp-pipeline.md §11 Tuition → salary (audit idx 200-201); "
        "true post-ISSUE-#6 labels: salary untouched, tuition books 80C")

    add("led-ppf-health-split", "led-ppf-health-split",
        [turn("I invested 1.5L in PPF and 50k in health insurance",
              _amount_span("1.5L", 150_000, "80c")
              + _amount_span("50k", 50_000, "80d"))],
        "docs/nlp-pipeline.md §11 PPF → 80D (audit idx 66); true "
        "post-ISSUE-#7 labels: clause-local split 80C + 80D")

    add("led-property-sale-cg", "led-property-sale-cg",
        [turn("i earned 30 lakhs from salary, 14 lakhs from property sale "
              "and 5 lakhs from rental",
              _amount_span("30 lakhs", 3_000_000, "salary")
              + _amount_span("14 lakhs", 1_400_000, "capital_gains")
              + _amount_span("5 lakhs", 500_000, "rental"))],
        "docs/nlp-pipeline.md §11 Property sale → income (audit idx 15); "
        "true post-ISSUE-#8 labels: salary + property capital gain + rental")

    add("led-education-loan-80e", "led-education-loan-80e",
        [turn("I am a shopkeeper", []),
         turn("yes 5 lakhs from education Loan",
              _amount_span("5 lakhs", 500_000, "80e"))],
        "docs/nlp-pipeline.md §11 Education-loan interest → income "
        "(audit idx 31); fixed control case — 80E")

    add("led-monthly-salary", "led-monthly-salary",
        [turn("my salary is 80,000 per month",
              _amount_span("80,000 per month", 960_000, "salary",
                           annualized=True))],
        "docs/nlp-pipeline.md §11 Double annualization (C3); true label: "
        "exactly one x12 → 960,000")

    add("led-shares-sold", "led-shares-sold",
        [turn("shares sold for 5 lakhs",
              _amount_span("5 lakhs", 500_000, "capital_gains"))],
        "docs/sprint4-execution.md P1 item 3 — noun-form 'shares sold' books capital_gains")

    add("led-stocks-sold", "led-stocks-sold",
        [turn("stocks sold for 2 lakhs",
              _amount_span("2 lakhs", 200_000, "capital_gains"))],
        "docs/sprint4-execution.md P1 item 3 — noun-form 'stocks sold' books capital_gains")

    add("led-business-owner-teacher", "led-business-owner-teacher",
        [turn("I am a business owner and teacher", []),
         turn("my income is 20 lakhs",
              _amount_span("20 lakhs", 2_000_000, "business"))],
        "docs/nlp-pipeline.md §11 'business owner and teacher' → Salaried "
        "(audit idx 109); true label: Business Owner → business income")

    add("led-freelance-designer", "led-freelance-designer",
        [turn("I am a freelance designer", []),
         turn("I charge 15 lakhs a year",
              _amount_span("15 lakhs", 1_500_000, "business"))],
        "docs/nlp-pipeline.md §11 Freelance → Salaried (probe); true "
        "label: Business Owner → business income")

    add("led-transfer-date-2023", "led-transfer-date-2023",
        [turn("sold property in 2023 for 40 lakhs",
              _amount_span("40 lakhs", 4_000_000, "capital_gains"))],
        "docs/sprint4-execution.md P1 item 5 — the transfer year 2023 is a tri-state "
        "flag, never an amount; true label books only the 40L gain")

    add("led-percent-disabled", "led-percent-disabled",
        [turn("I am 40 percent disabled",
              _spans([("40 percent", "80u_80dd", None, False)]))],
        "docs/sprint4-execution.md P1 item 4 — '40 percent disabled' collects the 80U/80DD "
        "category, never an amount")

    add("led-wordorder-tuition", "led-wordorder-tuition",
        [turn("2 lakhs I paid for my childs tuition",
              _amount_span("2 lakhs", 200_000, "80c"))],
        "docs/nlp-pipeline.md §11 word-order variant — amount-first "
        "tuition books 80C")

    add("led-negation-disability", "led-negation-disability",
        [turn("no disability",
              _spans([("no disability", corpus.ABSTAIN, None, False)]))],
        "docs/sprint2-design.md Step D2/G — negated disability is a refusal, books "
        "nothing (ABSTAIN)")

    add("led-negation-donation", "led-negation-donation",
        [turn("no donations this year",
              _spans([("no donations", corpus.ABSTAIN, None, False)]))],
        "docs/sprint2-design.md Step D2/G — negated donation books nothing (ABSTAIN)")

    add("led-negation-insurance", "led-negation-insurance",
        [turn("don't have health insurance",
              _spans([("don't have health insurance", corpus.ABSTAIN, None,
                       False)]))],
        "docs/nlp-pipeline.md §4 zero-sentinel ledger item — refusal "
        "books nothing (ABSTAIN)")

    add("led-shorthand-cr", "led-shorthand-cr",
        [turn("my salary is 50000 crore",
              _amount_span("50000 crore", 100_000_000_000, "salary"))],
        "docs/sprint2-design.md V-1 ledger item — NLP writes clamp to 0..1e11; the "
        "true booked value is the ₹100 crore cap")

    add("led-cg-clamp", "led-cg-clamp",
        [turn("sold property for 20000 crore",
              _amount_span("20000 crore", 100_000_000_000,
                           "capital_gains"))],
        "docs/sprint2-design.md V-1 ledger item — capital-gains amounts clamp to the "
        "₹100 crore cap")

    return records


# ---------------------------------------------------------------------------
# (c) Organic — golden-corpus conversations as multi-turn records.
# Final-state labels: docs/nlp-pipeline.md §9 (engine-verified 2026-11-01,
# incl. the documented bare-no zero fills) + the golden regression tests.
# ---------------------------------------------------------------------------

def _organic_records() -> List[dict]:
    def conv(rid, session_hash, turns_spans, ref, lang="en"):
        turns = [{"text": t, "spans": s} for t, s in turns_spans]
        flat = [s for _, ss in turns_spans for s in ss]
        return {
            "id": rid,
            "text": " || ".join(t for t, _ in turns_spans),
            "source": "organic",
            "session_hash": session_hash,
            "lang": lang,
            "spans": flat,
            "turns": turns,
            "provenance": {
                "builder": BUILDER, "built_on": BUILD_DATE,
                "corpus_version": corpus.CORPUS_SCHEMA_VERSION,
                "ref": ref,
            },
        }

    return [
        conv("gc-01-worked-example", "s4g-gc-01", [
            ("I am a software engineer earning 18 LPA",
             _amount_span("18 LPA", 1_800_000, "salary")),
            ("no", []),
            ("1.5 lakhs in PPF", _amount_span("1.5 lakhs", 150_000, "80c")),
            ("no", []),
            ("25k health insurance", _amount_span("25k", 25_000, "80d")),
            ("no", []),
            ("no", []),
            ("/end", []),
        ], "docs/nlp-pipeline.md §9 worked multi-turn example; final state "
           "incl. the documented bare-no zero fills "
           "(nps=rent_paid=hra_received=0, engine-verified)"),
        conv("gc-02-salaried-80c-80d", "s4g-gc-02", [
            ("I am a software engineer", []),
            ("my CTC is 25 lakhs",
             _amount_span("25 lakhs", 2_500_000, "salary")),
            ("80c investments of 1.5 lakhs",
             _amount_span("1.5 lakhs", 150_000, "80c")),
            ("health insurance of 25k",
             _amount_span("25k", 25_000, "80d")),
            ("/end", []),
        ], "test_suite.py Block 4 C01 flow"),
        conv("gc-03-business-multi-income", "s4g-gc-03", [
            ("I run a shop", []),
            ("my business income is 40 lakhs",
             _amount_span("40 lakhs", 4_000_000, "business")),
            ("I also have rental income of 10 lakhs",
             _amount_span("10 lakhs", 1_000_000, "rental")),
            ("80c of 1 lakh", _amount_span("1 lakh", 100_000, "80c")),
            ("/end", []),
        ], "test_suite.py Block 4 C02 flow"),
        conv("gc-04-pilot-24b-80g", "s4g-gc-04", [
            ("I am a pilot", []),
            ("my salary is 80,000 per month",
             _amount_span("80,000 per month", 960_000, "salary",
                          annualized=True)),
            ("home loan interest of 1.5 lakhs",
             _amount_span("1.5 lakhs", 150_000, "24b")),
            ("donated 25k to PM CARES", _amount_span("25k", 25_000, "80g")),
            ("/end", []),
        ], "test_golden_corpus.py monthly-annualization flow + 80G"),
        conv("gc-05-trader-fd-nps", "s4g-gc-05", [
            ("I am self employed", []),
            ("business turnover 60 lakhs",
             _amount_span("60 lakhs", 6_000_000, "business")),
            ("fd interest 40k", _amount_span("40k", 40_000, "other_income")),
            ("nps 50k", _amount_span("50k", 50_000, "nps")),
            ("/end", []),
        ], "test_suite.py profession + other-income flow"),
        conv("gc-06-factory-rental-elss", "s4g-gc-06", [
            ("I own a garment factory", []),
            ("business income 25 lakhs",
             _amount_span("25 lakhs", 2_500_000, "business")),
            ("rent received from tenant 30k",
             _amount_span("30k", 30_000, "rental")),
            ("elss 1 lakh", _amount_span("1 lakh", 100_000, "80c")),
            ("/end", []),
        ], "test_suite.py C02-adjacent multi-income flow"),
        conv("gc-07-hinglish-naukri", "s4g-gc-07", [
            ("meri naukri hai", []),
            ("salary 60k per month milti hai",
             _amount_span("60k per month", 720_000, "salary",
                          annualized=True)),
            ("PPF mein 1 lakh daala",
             _amount_span("1 lakh", 100_000, "80c")),
            ("/end", []),
        ], "Hinglish naukri flow (nlp_engine hinglish profile map)",
           lang="hinglish"),
    ]


# ---------------------------------------------------------------------------
# ABSTAIN families — amounts/mentions that must NOT be booked anywhere.
# Engine-verified: each of these books NOTHING in the current pipeline
# EXCEPT abs-loans / abs-question (which misbook today — the abstain gap
# the eval is supposed to surface; the true label stays ABSTAIN).
# ---------------------------------------------------------------------------

def _abstain_families() -> List[Tuple[str, str, List[Render]]]:
    fams: List[Tuple[str, str, List[Render]]] = []

    def abstain_render(text):
        return (text, _spans([(text, corpus.ABSTAIN, None, False)]))

    def add(template_id, lang, phrases):
        fams.append((template_id, lang,
                     [abstain_render(t) for t in phrases]))

    add("abs-age", "en", (
        "I am 67 years old", "my age is 45", "age 72",
        "I am 30 years old", "aged 58 here", "my age is 71",
        "I am 24", "age 66 and planning investments",
    ))
    add("abs-family-age", "en", (
        "my father is 91", "my daughter is 12 years old",
        "my mother is 63", "my son is 8 years old",
        "father is 74 and mother is 70",
    ))
    add("abs-umar", "hinglish", (
        "meri umar 58 hai", "umar 45", "meri umr 62 hai",
        "pita ji ki umar 80 hai",
    ))
    add("abs-percent", "en", (
        "I pay 30 percent tax", "interest rate is 8 percent",
        "my hike was 10 percent", "20 percent of income goes to rent",
        "inflation is 6 percent", "I got a 12 percent raise",
    ))
    # Known abstain-gap: car/personal loans are not bookable, yet the
    # default fall-through books them today — the eval must see this.
    add("abs-loans", "en", (
        "my car loan emi is 15000", "personal loan of 200000",
        "car loan down payment 200000", "personal loan emi 8000",
        "car loan of 5 lakhs", "personal loan 2 lakhs",
    ))
    add("abs-meta", "en", (
        "hello", "what can you do?", "thank you", "how does this work?",
        "help me with taxes", "who are you?",
    ))
    add("abs-zero", "en", (
        "no investments", "kuch nahi", "not applicable",
        "nothing to declare", "skip this one", "nil",
    ))
    add("abs-question", "en", (
        "what is the 80c limit?", "how much tax on 12 lakhs?",
        "what is hra exemption?", "explain section 80d",
        "is nps worth it for 10 lakhs income?",
    ))
    # Bare section mentions must ASK BACK and book nothing
    # (nlp_engine.py pre-parse guard) — abstain, not a category.
    add("abs-section-mention", "en", (
        "I have 80u", "I want to claim 80dd", "claiming 80u this year",
        "80dd deduction for my sibling", "meri tang hai, 80u claim",
    ))
    return fams


# ---------------------------------------------------------------------------
# Split assignment — template-disjoint, seeded, floor-aware:
# per category the seeded-shuffled families are taken smallest-first into
# validation until >= CATEGORY_FLOOR_EVAL spans (>= 2 families), then
# test likewise, and the remainder (the larger families) goes to training.
# ---------------------------------------------------------------------------

def _assign_families(
    families: List[Tuple[str, str, List[Render]]],
    rng: random.Random,
    eval_floor: int = corpus.CATEGORY_FLOOR_EVAL,
) -> Dict[str, List[Tuple[str, str, List[Render]]]]:
    by_category: Dict[str, List] = {}
    for fam in families:
        categories = {span["category"] for _, spans in fam[2]
                      for span in spans}
        categories.discard(corpus.ABSTAIN)
        key = sorted(categories)[0] if categories else corpus.ABSTAIN
        by_category.setdefault(key, []).append(fam)

    assigned: Dict[str, List] = {s: [] for s in ("training", "validation",
                                                 "test")}
    for category in sorted(by_category):
        fams = list(by_category[category])
        rng.shuffle(fams)
        # stable size order with the seeded shuffle as the tiebreak
        fams.sort(key=lambda f: len(f[2]))
        queue = list(fams)
        for split, floor, min_families in (
                ("validation", eval_floor, 2),
                ("test", eval_floor // 2, 1)):
            taken_spans = 0
            while queue and (taken_spans < floor
                             or len(assigned[split]) < min_families):
                fam = queue.pop(0)
                assigned[split].append(fam)
                taken_spans += len(fam[2])
        assigned["training"].extend(queue)
    return assigned


def _assign_round_robin(items: List[dict], rng: "random.Random",
                        splits: Sequence[str]) -> Dict[str, List[dict]]:
    order = list(items)
    rng.shuffle(order)
    assigned: Dict[str, List[dict]] = {s: [] for s in splits}
    for i, item in enumerate(order):
        assigned[splits[i % len(splits)]].append(item)
    return assigned


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _record(rid, text, spans, source, lang, template_id=None,
            session_hash=None, turns=None) -> dict:
    rec = {
        "id": rid,
        "text": text,
        "source": source,
        "lang": lang,
        "spans": spans,
        "provenance": {
            "builder": BUILDER,
            "built_on": BUILD_DATE,
            "corpus_version": corpus.CORPUS_SCHEMA_VERSION,
            "seed": BUILD_SEED,
            "note": ("synthetic-backed: the organic ledger slice is thin "
                     "for this category" if source == "synthetic" else None),
        },
    }
    if template_id is not None:
        rec["template_id"] = template_id
    if session_hash is not None:
        rec["session_hash"] = session_hash
    if turns is not None:
        rec["turns"] = turns
    return rec


def build_corpus(seed: int = BUILD_SEED,
                 out_dir: Optional[Path] = None,
                 verbose: bool = False) -> dict:
    """Build the labeled corpus + manifest into *out_dir* (default: the
    dataset root). Deterministic in *seed*; returns the manifest."""
    root = Path(out_dir) if out_dir is not None else corpus.dataset_root()
    rng = random.Random(seed)

    split_records: Dict[str, List[dict]] = {
        "training": [], "validation": [], "test": [], "corpus": []}

    # (b) synthetic families — template-disjoint allocation
    synthetic = _families() + _clause_trap_families()
    counters = {"syn": 0, "abs": 0}
    for split, fams in _assign_families(synthetic, rng).items():
        for template_id, lang, renders in fams:
            for text, spans in renders:
                counters["syn"] += 1
                split_records[split].append(_record(
                    f"syn-{counters['syn']:05d}", text, spans, "synthetic",
                    lang, template_id=template_id))

    # ABSTAIN families — same disjoint allocation (floor 10 per eval split)
    for split, fams in _assign_families(_abstain_families(), rng,
                                        eval_floor=10).items():
        for template_id, lang, renders in fams:
            for text, spans in renders:
                counters["abs"] += 1
                split_records[split].append(_record(
                    f"abs-{counters['abs']:05d}", text, spans, "synthetic",
                    lang, template_id=template_id))

    # (a) ledger — eval material only (validation + test round-robin)
    ledger = _ledger_records()
    for split, recs in _assign_round_robin(ledger, rng,
                                           ("validation", "test")).items():
        split_records[split].extend(recs)

    # (c) organic golden conversations — seeded round-robin, weighted to
    # validation (the eval split) with training/test representation
    organic = _organic_records()
    for split, recs in _assign_round_robin(
            organic, rng,
            ("validation", "training", "test", "validation")).items():
        split_records[split].extend(recs)

    # ids must be globally unique
    seen_ids = set()
    for records in split_records.values():
        for rec in records:
            assert rec["id"] not in seen_ids, rec["id"]
            seen_ids.add(rec["id"])

    # leakage guards: cross-split near-duplicates and schema
    dups = corpus.find_cross_split_duplicates(split_records)
    if dups:
        raise RuntimeError(
            "cross-split near-duplicates — fix the templates: "
            + json.dumps(dups[:5], ensure_ascii=False))
    for split, records in split_records.items():
        for rec in records:
            corpus.validate_record(rec, context=split)

    # write
    (root / "corpus").mkdir(parents=True, exist_ok=True)
    (root / "corpus" / ".gitkeep").write_text("", encoding="utf-8")
    manifest_files: Dict[str, List[str]] = {}
    for split in ("training", "validation", "test"):
        by_source: Dict[str, List[dict]] = {}
        for rec in split_records[split]:
            by_source.setdefault(rec["source"], []).append(rec)
        files = []
        for source in sorted(by_source):
            rel = f"{split}/{source}.jsonl"
            payload = "\n".join(
                json.dumps(rec, ensure_ascii=False)
                for rec in sorted(by_source[source], key=lambda r: r["id"])
            ) + "\n"
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
            files.append(rel)
        manifest_files[split] = files

    # content-addressed manifest
    splits_manifest = {}
    template_index: Dict[str, List[str]] = {}
    session_index: Dict[str, List[str]] = {}
    per_category: Dict[str, Dict[str, int]] = {}
    for split in ("training", "validation", "test"):
        files = manifest_files[split]
        digest = hashlib.sha256()
        for rel in sorted(files):
            digest.update((root / rel).read_bytes())
        records = split_records[split]
        splits_manifest[split] = {
            "files": files,
            "record_count": len(records),
            "sha256": digest.hexdigest(),
        }
        template_index[split] = sorted({
            rec["template_id"] for rec in records if "template_id" in rec})
        session_index[split] = sorted({
            rec["session_hash"] for rec in records if "session_hash" in rec})
        per_category[split] = dict(corpus.coverage_counts(records))

    manifest = {
        "manifest_version": 1,
        "build": {
            "seed": seed,
            "builder": BUILDER,
            "built_on": BUILD_DATE,
            "corpus_schema_version": corpus.CORPUS_SCHEMA_VERSION,
            "split_ratios": SPLIT_RATIOS,
        },
        "splits": splits_manifest,
        "template_index": template_index,
        "session_index": session_index,
        "per_category_counts": per_category,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    if verbose:
        _print_summary(manifest, split_records)
    return manifest


def _print_summary(manifest: dict,
                   split_records: Dict[str, List[dict]]) -> None:
    quality = corpus.corpus_quality(split_records)
    print("=" * 64)
    print("Labeled corpus build — health summary")
    print("=" * 64)
    print(f"records: {quality['total_records']}  "
          f"spans: {quality['total_spans']}")
    print(f"splits: {quality['splits']}")
    print(f"sources: {quality['source_distribution']}")
    print(f"langs: {quality['lang_distribution']}")
    print(f"templates: {quality['template_diversity']['unique_templates']} "
          f"unique")
    counts = corpus.coverage_counts(
        [r for recs in split_records.values() for r in recs])
    print("per-category spans (floor 50, eval floor 15):")
    for label in corpus.TAXONOMY:
        val = manifest["per_category_counts"]["validation"].get(label, 0)
        ok = (counts.get(label, 0) >= corpus.CATEGORY_FLOOR_TOTAL
              and val >= corpus.CATEGORY_FLOOR_EVAL)
        mark = "OK " if ok else "LOW"
        print(f"  [{mark}] {label:<14} total={counts.get(label, 0):>4} "
              f"validation={val:>3}")
    dups = corpus.find_cross_split_duplicates(split_records)
    print(f"cross-split near-duplicates: {len(dups)}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out_dir = None
    if "--out-dir" in argv:
        out_dir = Path(argv[argv.index("--out-dir") + 1])
    build_corpus(out_dir=out_dir, verbose=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

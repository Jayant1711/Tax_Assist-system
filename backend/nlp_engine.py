# Summer internship project
"""
NLP Engine v9.0 — Bug-fixed & Enhanced
Fixes: Duplicate _generate_reply removed, missing return fixed,
       Hinglish support, better zero-sentinel, improved multi-value extraction,
       better correction handling, cleaner phase transitions.
"""

import logging
import math
import re
from typing import Dict, Any, List, Optional, Tuple
from ai_models import SemanticAttention, UniversalParser, ReasoningAgent
from profession_db import classify_profession

logger = logging.getLogger(__name__)

# Sprint 2 Step B: metro-city detection heuristics (documented).
# A statutory HRA metro (Sec 10(13A): Delhi/Mumbai/Kolkata/Chennai) named in
# a sentence books session["is_metro"] = True ONLY when the sentence also
# talks rent/HRA (word-boundary match, so "parents" never counts as rent
# context) OR while the rent/HRA discovery question is the open question —
# this gates out false positives like "I work in Mumbai". is_metro is NEVER
# set to False by city evidence: a named non-metro city (or no city at all)
# leaves the key absent, and the engine then applies — and discloses — its
# non-metro 40% assumption. A bare False is booked only by an explicit
# negative answer to the metro part of the discovery question.
_METRO_CITY_RE = re.compile(r"\b(?:delhi|mumbai|kolkata|chennai)\b", re.IGNORECASE)
_RENT_HRA_CONTEXT_RE = re.compile(r"\brent\w*|\bhra\b|\bkiraya\b", re.IGNORECASE)

# ── Sprint 2 Step D2/G: NLP input guards (docs/sprint2-design.md) ────────
#
# V-1 closure: every NLP-written numeric is clamped to 0..1e11 AFTER
# monthly annualization, at the assignment block (central helper
# NLPEngine._clamp_amount). Values above the cap surface the advisory
# below; the session then never holds more than ₹100 crore per key.
_NLP_AMOUNT_CAP = 1e11
NLP_CLAMP_ADVISORY = (
    "Amount exceeds the supported range — clamped to ₹100 crore"
)

# Objective G / G-1 closure: ages booked as income before the dedicated
# extractor ("I am 105 years old" -> salary=105; "my age is 150" ->
# other_income=150 — both verified live 2026-10-31). The extractor runs
# BEFORE clause parsing on anchored patterns only; every consumed numeric
# span is blanked (length-preserving) so it can never reach the parser.
AGE_RANGE_ADVISORY = (
    "Age must be 0-120 — please provide your age as a whole number of years."
)
SENIOR_AGE_NOTE = (
    "Note: age assumed 60 (senior citizen) — tell me your exact age if "
    "that is not right."
)

# Family words whose ages are never the user's OWN age (parent context is
# out of scope for session["age"] — the numbers are swallowed, G scope).
_FAMILY_WORDS = (
    "father|mother|mom|dad|parents?|pita|mata|maa|baap|mummy|papa|pitaji|"
    "son|daughter|child|kid|beta|beti"
)
_FAMILY_WORD_RE = re.compile(r"\b(?:" + _FAMILY_WORDS + r")\b", re.IGNORECASE)
# family member + copula/age connector + integer -> that member's age
_FAMILY_AGE_RE = re.compile(
    r"\b(?:" + _FAMILY_WORDS + r")\b\s*(?:is|are|was|age[d]?|umar|umr)\s*"
    r"(?P<num>\d{1,3}(?:\.\d+)?)",
    re.IGNORECASE,
)
# anchored age cues: number AFTER the cue word ("age 72", "aged 67",
# "my age is 150", "umar 45"); word boundaries keep "package"/"percentage"
# etc. from matching, the boundary assertion keeps the digit run whole and
# the money-guard rejects "age 45 lakh" style continuations.
_AGE_CUE_RE = re.compile(
    r"\b(?:age[d]?|umar|umr)\b[^0-9]{0,8}?(?P<num>\d{1,3}(?:\.\d+)?)(?![\d.])"
    r"(?!\s*(?:%|percent|lakh|lakhs?|lacs?|crores?|crs?|cr|k\b|thousand|"
    r"lpa|mn|million|pm|l\b))",
    re.IGNORECASE,
)
# "<n> years old" cue (standalone per the design bullet)
_YEARS_OLD_RE = re.compile(
    r"(?P<num>\d{1,3}(?:\.\d+)?)\s*years?\s*old\b", re.IGNORECASE
)
# first-person copula + number ("I am 67", "I'm 67", "i m 56"). The first
# assertion ends the digit run at its FULL length (without it the greedy
# {1,3} backtracks past the money guard: "I am 45k earner" extracted a
# truncated age 4); the lookahead then rejects money/percentage
# continuations ("I am 40 percent disabled", "I am 45 lakh") — not ages.
_COPIULA_AGE_RE = re.compile(
    r"\bi\s*(?:am|'m|m)\s*(?P<num>\d{1,3}(?:\.\d+)?)(?![\d.])"
    r"(?!\s*(?:%|percent|lakh|lakhs?|lacs?|crores?|crs?|cr|k\b|thousand|"
    r"lpa|mn|million|pm|l\b))",
    re.IGNORECASE,
)
# a percentage is never a monetary amount ("80% plus", "100 percent",
# "40 percent disabled") — the number is masked before the parser runs
# (the digit pass only drops <100, so "100 percent" would book 100).
_PERCENT_RE = re.compile(
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?:%|percent(?:age)?\b)", re.IGNORECASE
)
# the guard's own clause window (commas count here — sentence splitting
# skips commas adjacent to digits: "I am 67, my father is 91" is ONE
# sentence, but the self-age and the parent-age live in different clauses)
_GUARD_CLAUSE_SPLIT_RE = re.compile(r"\s+(?:and|&)\s+|[,;]", re.IGNORECASE)
_SENIOR_RE = re.compile(r"senior citizen|super senior", re.IGNORECASE)

# 80U/80DD disability-category collection (heuristic-honest: keywords book
# the enum value, a bare section mention asks back, nothing is guessed).
_DISABILITY_WORD_RE = re.compile(r"\bdisab\w*|\bhandicapped\b", re.IGNORECASE)
_80U_MENTION_RE = re.compile(r"\b80u\b|\b80dd\b", re.IGNORECASE)
_SEVERE_80_RE = re.compile(r"\bsevere\b|\b(?:80|100)\b", re.IGNORECASE)
_GENERIC_40_RE = re.compile(r"\bpartial\b|\b40\b|\bpercent(?:age)?\b", re.IGNORECASE)
ASKBACK_80U = (
    "For Section 80U/80DD the deduction is a flat amount based on the "
    "disability category — is it 40-79% (₹75,000) or 80% or more (₹1,25,000)?"
)

# 80G donee-category collection (R-g). Ordered, most specific first.
_DONATION_CTX_RE = re.compile(
    r"\bdonat\w*|\b80g\b|\bcharity\b|\bcharitable\b|\bdaan\b|\bngo\b|"
    r"\brelief fund\b|\btrust\b",
    re.IGNORECASE,
)
_80G_CATEGORY_KEYWORDS: Tuple[Tuple[str, str], ...] = (
    ("pm cares", "cat_100_no_limit"),
    ("pmnrf", "cat_100_no_limit"),
    ("pm relief fund", "cat_100_no_limit"),
    ("pm fund", "cat_100_no_limit"),
    ("cm relief fund", "cat_100_no_limit"),
    ("cm fund", "cat_100_no_limit"),
    ("national defence", "cat_100_no_limit"),
    ("national defense", "cat_100_no_limit"),
    ("government", "cat_100_qualifying_limit"),
    ("govt", "cat_100_qualifying_limit"),
    ("local authority", "cat_100_qualifying_limit"),
    ("municipal", "cat_100_qualifying_limit"),
    ("charitable trust", "cat_50_no_limit"),
    ("ngo", "cat_50_no_limit"),
    ("hospital", "cat_50_no_limit"),
    ("temple", "cat_50_qualifying_limit"),
    ("mosque", "cat_50_qualifying_limit"),
    ("church", "cat_50_qualifying_limit"),
    ("gurudwara", "cat_50_qualifying_limit"),
    ("religious", "cat_50_qualifying_limit"),
    ("charitable institution", "cat_50_qualifying_limit"),
)
ASKBACK_80G = (
    "For Section 80G, which donee category applies — PM CARES / National "
    "Defence (100%, no limit), NGO or charitable trust (50%, no limit), "
    "Government / local authority, or another charitable / religious "
    "institution?"
)


class NLPEngine:
    def __init__(self):
        self.parser    = UniversalParser()
        self.attention = SemanticAttention()
        self.agent     = ReasoningAgent()

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _get_asked_cat(self, last_q: str, profile: Optional[str] = None,
                       session: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not last_q:
            return None
        lq = last_q.lower()
        if any(k in lq for k in ["salary", "income", "earn", "kitna kamate", "annual income", "annual"]):
            return "business" if profile == "Business Owner" else "salary"
        if any(k in lq for k in ["80c", "ppf", "lic", "elss", "investment", "saving", "bachate"]):
            return "80c"
        if any(k in lq for k in ["health", "insurance", "80d", "medical", "swasthya"]):
            return "80d"
        if any(k in lq for k in ["nps", "pension", "80ccd"]):
            return "nps"
        # Sprint 2 Step D2/G: the 80U/80DD ask-back mentions "80U/80DD" —
        # substring matching would read it as "80d" and mis-route a bare
        # follow-up amount to health insurance. The flat 80U/80DD deduction
        # is category-driven (no amount is collected), so no asked category
        # is primed. Word-boundary matching keeps "80ddb" out.
        if re.search(r"\b80u\b|\b80dd\b", lq):
            return None
        if any(k in lq for k in ["home loan", "24b", "interest", "ghar ka loan"]):
            return "24b"
        if any(k in lq for k in ["rent", "hra", "80gg", "kiraya"]):
            # Sprint 2 Step B: rent/HRA questions map to BOTH split
            # categories (asked-cat list behavior). Return the first
            # matching of the two whose session slot is still open, so a
            # bare amount after the combined discovery question fills the
            # next empty leg instead of re-accumulating a booked one;
            # without a session, fall back to rent_paid (the question leads
            # with the rent leg).
            if session is not None:
                for cat in ("rent_paid", "hra_received"):
                    if session.get(cat) is None:
                        return cat
            return "rent_paid"
        if any(k in lq for k in ["donation", "charity", "ngo", "gift", "daan"]):
            return "80g"
        return None

    def _is_zero_intent(self, text: str) -> bool:
        """Return True if the user's text means 'none / zero' for the asked category."""
        t = text.lower().strip()
        # Patterns: standalone negation words OR negative phrases
        zero_exact = {"no", "nope", "nahi", "na", "nothing", "none", "never",
                      "nil", "zero", "skip", "n/a", "not applicable"}
        if t in zero_exact:
            return True
        negative_phrases = [
            r"don'?t have", r"do not have", r"haven'?t", r"not paying",
            r"no investment", r"no insurance", r"no nps", r"no hra",
            r"no rent", r"no donation", r"nahi hai", r"kuch nahi", r"nahi kiya",
            r"not applicable", r"i don'?t", r"i have none", r"i have no",
            # Sprint 2 Step D2/G: negated disability/donation mentions must
            # not book a category (the collection heuristics are keyword-
            # driven; "no disability" is a refusal, not a 40-79% claim).
            r"no disability", r"not disab\w*", r"no 80u", r"no 80dd",
            r"no 80g", r"no charity",
        ]
        return any(re.search(p, t) for p in negative_phrases)

    # ------------------------------------------------------------------ #
    #  Sprint 2 Step D2/G — pre-parse guards                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _clamp_amount(value: float) -> Tuple[float, bool]:
        """V-1 closure: clamp an NLP-written numeric to 0..1e11.

        Applied at every write site in the assignment block AFTER monthly
        annualization (post-annualization values are the ones that reach
        the session). Values above the cap come back as ₹100 crore with
        clamped=True (the caller emits NLP_CLAMP_ADVISORY); negatives
        clamp to 0 (the digit parser cannot produce them — defensive).
        Returns (value, clamped).
        """
        try:
            v = float(value)
        except (TypeError, ValueError, OverflowError):
            return 0.0, False
        if not math.isfinite(v):
            # only float() can be non-finite here; ints are always finite
            return (_NLP_AMOUNT_CAP if v > 0 else 0.0), True
        if v < 0:
            return 0.0, False
        if v > _NLP_AMOUNT_CAP:
            return _NLP_AMOUNT_CAP, True
        return v, False

    @staticmethod
    def _clause_has_family(text: str, pos: int) -> bool:
        """True when a family word shares the guard-clause window with the
        match at pos (the family-context guard for age extraction and the
        senior-citizen heuristic)."""
        start = 0
        for m in _GUARD_CLAUSE_SPLIT_RE.finditer(text, 0, pos):
            start = m.end()
        nxt = _GUARD_CLAUSE_SPLIT_RE.search(text, pos)
        end = nxt.start() if nxt else len(text)
        return bool(_FAMILY_WORD_RE.search(text[start:end]))

    def _preparse_guard(
        self,
        s: str,
        session: Dict[str, Any],
        extracted: List[str],
        notes: List[str],
        askbacks: List[str],
        allow_askback: bool,
    ) -> str:
        """Step D2/G pre-parse pass over ONE sentence (before clause
        parsing). Runs, in order:

        1. Age extraction (Objective G / G-1 fix). Anchored patterns only —
           the cue words age/aged/years old/umar/umr and the "I am <int>"
           copula; a bare number with no anchor is never an age. Integers
           0-120 book session["age"] as an int (last explicit age wins);
           out-of-range ints (121-999) and non-integers (67.5) are
           swallowed with an advisory. Family-context numbers ("my father
           is 91") are swallowed silently — parent ages never book the
           session age. Every consumed numeric span is BLANKED
           (length-preserving) so it can never reach UniversalParser
           (G-1: "I am 105 years old" used to book salary=105) and the
           extractor never touches _last_val/_prev_salary.
        2. Percentage masking: "<n>%" / "<n> percent" is never a monetary
           amount (the digit pass only drops <100, so "100 percent" would
           book ₹100 of income).
        3. Senior-citizen heuristic: "senior citizen" with no family word
           in the clause floors session["age"] at 60 — the reply states
           the assumption (SENIOR_AGE_NOTE) so it can be corrected; an
           explicit age in the same message wins.
        4. 80U/80DD disability-category collection: severity keywords book
           the enum value; a generic disability mention books "40_79"; a
           bare "80u"/"80dd" mention emits the category ask-back and books
           nothing. Detection runs on the ORIGINAL sentence so percentage-
           masked numbers still classify ("80 percent" -> 80_plus).
        5. 80G donee-category collection: keyword table books the enum
           value (donation context or an open 80G ask-back required); no
           keyword match with donation context emits the ask-back and
           books nothing (heuristic-honest).

        Returns the masked sentence for the normal parse path.
        """
        original_lower = s.lower()
        masked = s

        def _blank(a: int, b: int) -> None:
            # length-preserving: spans collected from earlier passes stay
            # valid, and later regex passes see blanks instead of digits
            nonlocal masked
            masked = masked[:a] + " " * (b - a) + masked[b:]

        # 1a. family-context ages — swallowed, never the user's own age
        for m in _FAMILY_AGE_RE.finditer(masked):
            _blank(m.start("num"), m.end("num"))

        # 1b. anchored age extraction (cue words + first-person copula)
        for pattern in (_AGE_CUE_RE, _YEARS_OLD_RE, _COPIULA_AGE_RE):
            for m in pattern.finditer(masked):
                num_str = m.group("num")
                if self._clause_has_family(masked, m.start()):
                    # a family member's age in the same clause — swallow
                    _blank(m.start(), m.end())
                    continue
                if "." in num_str:
                    # non-integer age: rejected, never booked
                    extracted.append(AGE_RANGE_ADVISORY)
                    _blank(m.start(), m.end())
                    continue
                age = int(num_str)
                if 0 <= age <= 120:
                    session["age"] = age  # int only (validator row)
                    extracted.append(f"AGE: {age} (years — noted)")
                    notes.append(f"Noted — your age: {age}.")
                    logger.info("age extractor: session age set to %d", age)
                else:
                    extracted.append(AGE_RANGE_ADVISORY)
                    logger.info("age extractor: out-of-range age %d swallowed", age)
                _blank(m.start(), m.end())

        # 2. percentages are never amounts — mask the number
        for m in _PERCENT_RE.finditer(masked):
            _blank(m.start("num"), m.end("num"))

        # 3. senior-citizen heuristic (per clause, family-guarded)
        for m in _SENIOR_RE.finditer(masked):
            if self._clause_has_family(masked, m.start()):
                continue  # "my parents are senior citizens" — not the user
            current = session.get("age")
            if not isinstance(current, int) or isinstance(current, bool) or current < 60:
                session["age"] = 60
                notes.append(SENIOR_AGE_NOTE)
                logger.info("senior-citizen heuristic: age floored to 60")

        zero_intent = self._is_zero_intent(s)
        last_q = session.get("_last_question", "") or ""

        # 4. 80U/80DD disability category (heuristic-honest)
        if not zero_intent:
            u80_open = "80U/80DD" in last_q and "40-79%" in last_q
            dis_word = bool(_DISABILITY_WORD_RE.search(original_lower))
            sec_mention = bool(_80U_MENTION_RE.search(original_lower))
            severe = bool(_SEVERE_80_RE.search(original_lower))
            generic = bool(_GENERIC_40_RE.search(original_lower))
            if dis_word or sec_mention or u80_open:
                if severe:
                    session["80u_80dd_category"] = "80_plus"
                    extracted.append("80U/80DD CATEGORY: 80_plus (flat ₹1,25,000)")
                    logger.info("80U/80DD category collected: 80_plus")
                elif generic or dis_word:
                    session["80u_80dd_category"] = "40_79"
                    extracted.append("80U/80DD CATEGORY: 40_79 (flat ₹75,000)")
                    logger.info("80U/80DD category collected: 40_79")
                elif allow_askback:
                    # bare section mention: ask the category, book nothing
                    askbacks.append(ASKBACK_80U)

        # 5. 80G donee category (heuristic-honest)
        if not zero_intent:
            donation_ctx = bool(_DONATION_CTX_RE.search(original_lower))
            category: Optional[str] = None
            for keyword, cat in _80G_CATEGORY_KEYWORDS:
                if keyword in original_lower:
                    category = cat
                    break
            if category and (donation_ctx or "donee category" in last_q):
                session["80g_category"] = category
                extracted.append(
                    f"80G CATEGORY: {category} (rate applied at calculation)"
                )
                logger.info("80G category collected: %s", category)
            elif donation_ctx and allow_askback:
                # donation with no recognizable donee: ask back, book no
                # category (the engine's disclosed default still applies)
                askbacks.append(ASKBACK_80G)

        return masked

    # ------------------------------------------------------------------ #
    #  Main entry-point
    # ------------------------------------------------------------------ #

    def process_message(self, text: str, session: Dict[str, Any]) -> Dict[str, Any]:
        # ── /end override ──────────────────────────────────────────────
        if text.strip().lower() in ("/end", "end", "/done", "done", "finish", "complete"):
            session["phase"] = "FINAL"
            response = "✨ Override activated. Generating your Tax Optimization Report now…"
            if "history" not in session:
                session["history"] = []
            session["history"].append({"user": text, "ai": response})
            return {"response": response, "session": session, "extracted": [], "plan": "Final audit ready."}

        text_lower = text.lower().strip()

        # ── 1. Profile Detection (English + Hinglish) ──────────────────
        hinglish_map = {
            "naukri":          "Salaried",
            "job karta":       "Salaried",
            "apna kaam":       "Business Owner",
            "dukaan":          "Business Owner",
            "vyapar":          "Business Owner",
            "trader hoon":     "Business Owner",
            "business karta":  "Business Owner",
            "main karta hoon": "Salaried",
        }
        if not session.get("profile"):
            detected = classify_profession(text)
            if not detected:
                for phrase, prof in hinglish_map.items():
                    if phrase in text_lower:
                        detected = prof
                        break
            if detected:
                session["profile"] = detected

        # ── 2. Contextual flags ────────────────────────────────────────
        if any(k in text_lower for k in ["parent", "mom", "dad", "mother", "father",
                                          "senior citizen", "mata", "pita", "maa", "baap"]):
            session["has_parents"] = True
        if any(k in text_lower for k in ["home loan", "house loan", "mortgage",
                                          "ghar ka loan", "housing loan"]):
            session["has_home_loan"] = True
        if any(k in text_lower for k in ["pay rent", "paying rent", "rent to",
                                          "rented house", "kiraya deta", "kiraya bharta"]):
            session["pays_rent"] = True

        # ── 3. Correction intent ───────────────────────────────────────
        is_correction = any(kw in text_lower for kw in [
            "meant", "correction", "actually", "wrong", "not that", "no it's", "no that",
            "revise", "update", "miscalculated", "oops", "instead of", "change", "mistake",
            "galat", "sahi nahi", "theek karo", "correct karo",
        ])
        # bare_no = purely zero-intent message with no numeric content
        bare_no = self._is_zero_intent(text) and not any(c.isdigit() for c in text)

        # ── 4. Sentence-level extraction ───────────────────────────────
        sentences = re.split(r'(?<!\d)[,.;!?](?!\d)', text)
        newly_extracted: List[str] = []
        already_mapped_this_turn: set = set()
        # Sprint 2 Step D2/G: reply notes (age/senior-citizen assumption)
        # and category ask-backs collected by the pre-parse guard. All
        # message-scoped locals — the engine is a shared singleton, so no
        # state may live on self.
        notes: List[str] = []
        askbacks: List[str] = []
        allow_askback = not bare_no

        # Sprint 2 Step D: 80EEA advisory-keyword check. The section was
        # DISCONTINUED (loans must have been sanctioned before April 2022),
        # so a mention surfaces the advisory WITHOUT any state mutation —
        # no session write happens here (the session key itself is rejected
        # with a 422 by main.py, and the engine books nothing for it).
        if "80eea" in text_lower:
            newly_extracted.append(
                "Section 80EEA was discontinued (loans must have been "
                "sanctioned before April 2022) — no deduction available."
            )

        for sentence in sentences:
            s = sentence.strip()
            if not s:
                continue
            s_lower = s.lower()

            # Sprint 2 Step D2/G: pre-parse guard — anchored age extraction
            # with span masking (Objectives G + G-1), percentage masking,
            # the senior-citizen heuristic and the 80U/80DD + 80G category
            # collection. Returns the sentence with consumed numeric spans
            # blanked (length-preserving) so those numbers never reach
            # UniversalParser.
            s = self._preparse_guard(
                s, session, newly_extracted, notes, askbacks, allow_askback
            )
            s_lower = s.lower()

            # Sprint 2 Step B: metro-city booking (heuristic documented at
            # module top). A statutory metro named in a sentence that also
            # talks rent/HRA — or while the rent/HRA question is open —
            # books is_metro=True. Never booked from city evidence alone.
            if _METRO_CITY_RE.search(s_lower) and (
                _RENT_HRA_CONTEXT_RE.search(s_lower)
                or self._get_asked_cat(
                    session.get("_last_question", ""), session.get("profile"), session
                ) in ("rent_paid", "hra_received")
            ):
                session["is_metro"] = True

            # 4a. Zero-Sentinel per sentence
            if self._is_zero_intent(s):
                asked_cat = self._get_asked_cat(
                    session.get("_last_question", ""), session.get("profile"), session
                )
                if asked_cat and session.get(asked_cat) is None:
                    session[asked_cat] = 0
                    newly_extracted.append(f"{asked_cat.upper()}: Noted (None)")
                    continue
                # Step B: the metro leg of the combined rent/HRA question —
                # once both rent legs are booked, a bare negative answers
                # the metro part ("not a metro city") and unblocks the
                # discovery waterfall.
                if (asked_cat in ("rent_paid", "hra_received")
                        and session.get("is_metro") is None):
                    session["is_metro"] = False
                    newly_extracted.append("METRO: Noted (non-metro)")
                    continue

            # C4b: clause segmentation — each value belongs to the clause it
            # appears in, so a negative keyword in one clause ("health" sits
            # in 80c.neg) can no longer zero out and steal the other
            # clause's amount. Only coordinating "and"/"&" splits a clause
            # ("also"/"plus" must not: C02 "I also have rental income").
            # Offsets locate each stripped clause inside s so segment-
            # relative spans can be mapped if ever needed.
            clause_pairs = []
            running = 0
            for raw in re.split(r"\s+(?:and|&)\s+", s, flags=re.IGNORECASE):
                piece = raw.strip()
                if not piece:
                    continue  # empty clause piece (e.g. a trailing "&")
                idx = s.find(piece, running)
                c_off = idx if idx != -1 else running
                running = c_off + len(piece)
                clause_pairs.append((piece, c_off))

            clause_match_pairs = []
            any_clause_matches = False
            for clause, _c_off in clause_pairs:
                matches = self.parser.parse(clause)
                if matches:
                    any_clause_matches = True
                clause_match_pairs.append((clause, matches))

            # Handle numberless correction (e.g. "no that was 80C") —
            # unchanged: fires once, only when the sentence contains no
            # parsed values in ANY clause.
            if is_correction and not any_clause_matches:
                corr_cat = None
                for cat, kw_map in self.attention.categories.items():
                    if cat in s.lower() or any(kw in s.lower() for kw in kw_map["pos"][:6]):
                        corr_cat = cat
                        break
                if corr_cat:
                    last_val = session.get("_last_val")
                    if session.get("_prev_salary"):
                        last_val = last_val or session.get("salary")
                        session["salary"] = session.pop("_prev_salary")
                if last_val:
                    new_val = round(session.get(corr_cat, 0) + last_val, 2) if isinstance(session.get(corr_cat), (int, float)) else last_val
                    # V-1: correction re-bookings clamp at the write too.
                    new_val, clamped = self._clamp_amount(new_val)
                    if clamped:
                        newly_extracted.append(NLP_CLAMP_ADVISORY)
                    session[corr_cat] = new_val
                    newly_extracted.append(f"{corr_cat.upper()}: ₹{last_val:,.0f} (CORRECTED)")

            for clause, matches in clause_match_pairs:
                for i, m in enumerate(matches):
                    val = m["val"]
                    session["_last_val"] = val

                    # 4b. Probabilistic category resolution — CLAUSE-scoped (C4b):
                    # proximity scores and the negative-keyword environment come
                    # from the value's own clause, not the whole sentence.
                    full_last_q = session.get("_last_question", "").lower()
                    asked_cat   = self._get_asked_cat(full_last_q, session.get("profile"))
                    best_cat, is_default = self.attention.resolve_category_detailed(
                        clause, m["start"], m["end"], session.get("profile"), asked_cat
                    )

                    # 4c. Correction: subtract from a previously mapped category
                    if is_correction:
                        if session.get("_prev_salary"):
                            session["salary"] = session.pop("_prev_salary")
                        # Step B: the legacy "hra" suspect becomes the two
                        # split categories (mechanical rename).
                        for suspect in ["salary", "business", "nps", "80c", "80g",
                                        "rent_paid", "hra_received", "other_income"]:
                            if suspect == best_cat:
                                continue
                            prev_val = session.get(suspect, 0)
                            if isinstance(prev_val, (int, float)) and prev_val >= val:
                                subtracted = max(0, prev_val - val)
                                # V-1: even correction writes stay bounded.
                                subtracted, clamped = self._clamp_amount(subtracted)
                                if clamped:
                                    newly_extracted.append(NLP_CLAMP_ADVISORY)
                                session[suspect] = subtracted
                                break

                    # 4d. Monthly → annual conversion (C3: exactly one ×12).
                    # The parser flags the matches it already annualized
                    # ("pm"/"per month" forms); the engine converts only what
                    # the parser left monthly, and only when a monthly keyword
                    # sits in THIS match's own trailing segment (up to the next
                    # match within the clause) — the old sentence-global scan
                    # also annualized unrelated amounts in mixed sentences
                    # (e.g. the "10k in ppf" next to "50000 pm"). The
                    # (ANNUALIZED) badge is rendered exactly once, in whichever
                    # layer performed the conversion.
                    label = best_cat.replace("_", " ").upper()
                    monthly_kws = ["monthly", "per month", "p.m", "/month", "every month",
                                   "har mahine", "mahine ka", " pm "]
                    seg_end = matches[i + 1]["start"] if i + 1 < len(matches) else len(clause)
                    trailing = clause[m["end"]:seg_end].lower()
                    if m.get("annualized"):
                        label += " (ANNUALIZED)"
                    elif (any(kw in trailing for kw in monthly_kws if kw != " pm ")
                          or trailing.lstrip().startswith("pm")):
                        # Step D2/G: the " pm " token must START the
                        # trailing segment (the parser's own contract) —
                        # a bare substring hit annualized donations to the
                        # PM funds ("donated 1 lakh to PM CARES" booked
                        # 1,200,000: " pm " matched inside "to PM CARES").
                        val  *= 12
                        label += " (ANNUALIZED)"

                    # Sprint 2 Step D2/G (V-1 closure): clamp every
                    # NLP-written numeric to 0..1e11 AFTER monthly
                    # annualization. One central helper applied here at the
                    # write path; the accumulate branches re-clamp their
                    # sums below (two clamped inputs can still sum over).
                    val, clamped = self._clamp_amount(val)
                    if clamped:
                        newly_extracted.append(NLP_CLAMP_ADVISORY)
                        logger.info("NLP write clamped to the ₹100 crore cap")

                    # 4e. Assignment. "age" is NOT an overwrite category —
                    # session["age"] is written only by the pre-parse age
                    # extractor (Step D2/G).
                    OVERWRITE_CATS = ["salary", "business", "rental", "other_income"]

                    # C4a guard: a profile-default fall-through (no category
                    # scored above threshold) must never OVERWRITE an existing
                    # positive income — an unrecognized amount used to destroy
                    # the real salary ("childs tution of 2 Lakhs" → 200,000).
                    # Fresh entries still assign (first-income declaration must
                    # keep working). session["_last_val"] was already set above,
                    # so the "no that was 80C" correction flow still works.
                    current = session.get(best_cat)
                    if (
                        is_default
                        and best_cat in OVERWRITE_CATS
                        and isinstance(current, (int, float))
                        and not isinstance(current, bool)
                        and current > 0
                    ):
                        newly_extracted.append(
                            f"UNRECOGNIZED AMOUNT: ₹{val:,.0f} — tell me what this was for"
                        )
                        continue

                    if best_cat == "capital_gains":
                        if not isinstance(session.get("capital_gains"), list):
                            session["capital_gains"] = []
                        t_lower = text_lower
                        if any(x in t_lower for x in ["shares", "stocks", "equity", "mutual fund", "mf"]):
                            cg_type = ("equity_stcg"
                                       if any(x in t_lower for x in ["short", "stcg", "less than 1"])
                                       else "equity_ltcg")
                        else:
                            cg_type = "property_cg"
                        session["capital_gains"].append(
                            {"type": cg_type, "amount": val, "holding": "unknown"}
                        )
                    elif best_cat in OVERWRITE_CATS and not is_correction:
                        if best_cat in already_mapped_this_turn:
                            summed = round(session.get(best_cat, 0) + val, 2)
                            summed, sum_clamped = self._clamp_amount(summed)
                            if sum_clamped:
                                newly_extracted.append(NLP_CLAMP_ADVISORY)
                            session[best_cat] = summed
                        else:
                            if best_cat == "salary" and session.get("salary", 0) > 0 and val != session.get("salary"):
                                session["_prev_salary"] = session["salary"]
                            session[best_cat] = val
                            already_mapped_this_turn.add(best_cat)
                    else:
                        existing = session.get(best_cat, 0)
                        summed = round(
                            (existing + val) if isinstance(existing, (int, float)) else val, 2
                        )
                        summed, sum_clamped = self._clamp_amount(summed)
                        if sum_clamped:
                            newly_extracted.append(NLP_CLAMP_ADVISORY)
                        session[best_cat] = summed

                    newly_extracted.append(f"{label}: ₹{val:,.0f}")

        # ── 5. Agent reasoning ─────────────────────────────────────────
        decision = self.agent.decide_next_step(session)
        plan = decision.split("plan: ")[-1]

        # Phase update
        if "Final" in plan:
            session["phase"] = "FINAL"
        elif any(k in plan for k in ["Section 80", "NPS", "rent", "interest",
                                      "donations", "HRA", "24b", "80G", "80D", "80C"]):
            session["phase"] = "EXPENDITURE"
        elif "income" in plan.lower():
            session["phase"] = "INCOME"
        else:
            session["phase"] = "PROFILING"

        # ── 6. Generate response ───────────────────────────────────────
        response = self._generate_reply(session, newly_extracted, plan, text_lower, bare_no)
        # Sprint 2 Step D2/G: surface the age/senior-citizen assumption
        # notes and the category ask-backs. Appending keeps the discovery
        # flow intact; the ask-back rides inside _last_question so the
        # next utterance is classified as its answer.
        for note in notes:
            response += "\n" + note
        for askback in askbacks:
            response += "\n" + askback
        session["_last_question"] = response

        if "history" not in session:
            session["history"] = []
        session["history"].append({"user": text, "ai": response})

        return {"response": response, "session": session,
                "extracted": newly_extracted, "plan": plan}

    # ------------------------------------------------------------------ #
    #  Helper: group extracted entities for acknowledgement
    # ------------------------------------------------------------------ #

    def _group_found(self, found: List[str]) -> str:
        if not found:
            return ""
        groups: Dict[str, float] = {}
        for f in found:
            if ":" in f:
                cat, val_str = f.split(":", 1)
                try:
                    val = float(
                        val_str.replace("₹", "").replace(",", "")
                                .replace("(ANNUALIZED)", "").strip()
                    )
                    groups[cat.strip()] = groups.get(cat.strip(), 0) + val
                except ValueError:
                    pass
        if not groups:
            return f"Got it! Processed {len(found)} values. "
        summary = ", ".join(f"{cat}: ₹{amt:,.0f}" for cat, amt in groups.items())
        return f"✅ Mapped — {summary}. "

    # ------------------------------------------------------------------ #
    #  Response generator  (single definition — bug fixed)
    # ------------------------------------------------------------------ #

    def _generate_reply(self, session: Dict, found: List[str], plan: str,
                        text_lower: str, bare_no: bool) -> str:
        # ── bare "no" → mark current slot as 0 and advance ─────────────
        if bare_no:
            income_keys = ["salary", "business", "rental", "other_income"]
            has_income  = any(session.get(k, 0) > 0 for k in income_keys)
            if has_income:
                # Step B: the legacy "hra" slot becomes the two split legs
                # (is_metro is handled by the zero-sentinel's metro leg).
                for key in ["80c", "80d", "nps", "rent_paid", "hra_received", "24b", "80g"]:
                    if session.get(key) is None:
                        session[key] = 0
                        break
                decision2 = self.agent.decide_next_step(session)
                plan2     = decision2.split("plan: ")[-1]
                # Recurse once (bare_no=False to avoid infinite loop)
                return self._generate_reply(session, [], plan2, text_lower, False)
            else:
                return ("No worries! Let's start fresh. 😊 "
                        "What is your profession and annual income?")

        ack = self._group_found(found)

        # ── Branch on agent plan ───────────────────────────────────────
        if "Acknowledge" in plan and not found:
            profile = session.get("profile", "professional")
            return (f"Noted — you're a **{profile}**! 👍  "
                    f"What is your total annual income from this? "
                    f"_(e.g. '12 lakhs', '8.5L', '2.5 crore')_")

        if "specific income amount" in plan:
            profile = session.get("profile", "work")
            return (ack + f"What is your total annual income from {profile}? "
                    f"_(e.g. '12 lakh per year' or '1.5 crore')_")

        if "income details" in plan:
            return (ack + "Welcome! 🙏 I'm your AI Tax Consultant for FY 2024-25. "
                    "Tell me your **profession** and **annual income** to begin. "
                    "_(e.g. 'I'm a software engineer earning 18 LPA')_")

        if re.search(r'\b80C\b', plan):
            return (ack +
                    "💰 **Section 80C** — Have you made any tax-saving investments this year? "
                    "_(PPF, LIC premium, ELSS mutual funds, EPF, or children's tuition fees "
                    "— up to ₹1.5 Lakh)_")

        if re.search(r'\b80D\b', plan):
            return (ack +
                    "🏥 **Health Insurance (Section 80D)** — Do you pay health insurance premiums "
                    "for yourself or your family? "
                    "_(₹25,000 for self/family; ₹50,000 if parents are senior citizens)_")

        if "NPS" in plan or "80CCD" in plan:
            return (ack +
                    "🎯 **NPS Bonus Deduction** — Have you contributed to NPS (National Pension System)? "
                    "It gives an **extra ₹50,000** deduction under Section 80CCD(1B), "
                    "completely separate from your 80C limit!")

        if "HRA" in plan or "rent" in plan:
            # Step B: the combined Rule 2A question asks all THREE statutory
            # inputs (monthly rent, monthly HRA received, metro city) and
            # states the non-metro default so the assumption is never silent.
            return (ack +
                    "🏠 **Rent & HRA** — What is your **monthly rent**, your "
                    "**monthly HRA received**, and do you live in a **metro city** "
                    "(Delhi / Mumbai / Kolkata / Chennai)? "
                    "_(HRA exemption if salaried, Section 80GG if not — until a "
                    "metro city is confirmed, the non-metro 40% assumption applies)_")

        if "home loan interest" in plan or "24b" in plan:
            return (ack +
                    "🏦 **Home Loan Interest (Section 24b)** — What is the total home loan "
                    "**interest** you paid this year? "
                    "_(Up to ₹2 Lakh is deductible for self-occupied property)_")

        if re.search(r'\b80G\b', plan):
            return (ack +
                    "🤝 **Charitable Donations (Section 80G)** — Have you donated to any charity, "
                    "PM Relief Fund, or NGO this year? "
                    "_(50% to 100% of donations are deductible)_")

        if "Final audit ready" in plan:
            session["phase"] = "FINAL"
            tips = self.agent.get_savings_tips(session)
            tip_text = ("\n\n💡 **Quick Tip**: " + tips[0]) if tips else ""
            return (ack +
                    "✨ **All data collected!** Generating your complete Tax Optimization "
                    f"Report now…{tip_text}")

        return (ack +
                "Anything else to add? "
                "_(e.g. home loan interest, NPS, donations, property sale, "
                "education loan, rental income)_")

# Summer internship project
"""
NLP Engine v9.0 — Bug-fixed & Enhanced
Fixes: Duplicate _generate_reply removed, missing return fixed,
       Hinglish support, better zero-sentinel, improved multi-value extraction,
       better correction handling, cleaner phase transitions.
"""

import re
from typing import Dict, Any, List, Optional
from ai_models import SemanticAttention, UniversalParser, ReasoningAgent
from profession_db import classify_profession

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
        ]
        return any(re.search(p, t) for p in negative_phrases)

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
                        session[corr_cat] = round(session.get(corr_cat, 0) + last_val, 2) if isinstance(session.get(corr_cat), (int, float)) else last_val
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
                                session[suspect] = max(0, prev_val - val)
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
                    elif any(kw in trailing for kw in monthly_kws):
                        val  *= 12
                        label += " (ANNUALIZED)"

                    # 4e. Assignment
                    OVERWRITE_CATS = ["salary", "business", "rental", "other_income", "age"]

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
                            session[best_cat] = round(session.get(best_cat, 0) + val, 2)
                        else:
                            if best_cat == "salary" and session.get("salary", 0) > 0 and val != session.get("salary"):
                                session["_prev_salary"] = session["salary"]
                            session[best_cat] = val
                            already_mapped_this_turn.add(best_cat)
                    else:
                        existing = session.get(best_cat, 0)
                        session[best_cat] = round(
                            (existing + val) if isinstance(existing, (int, float)) else val, 2
                        )

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

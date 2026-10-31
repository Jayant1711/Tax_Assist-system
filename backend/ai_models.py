# Summer internship project
"""
AI Models v11.0 — Industrial Upgrade
Fixes:
- Consolidated category dictionary (removed duplicate keys for salary, business, agriculture)
- UniversalParser: enhanced Indian currency parsing (lakh, cr, k, pm, per month, word-forms)
- Safe fallback if numpy is not yet installed in local environment
- Calibrated Takagi-Sugeno-Kang (TSK) ANFIS neuro-fuzzy efficiency scoring
"""

import math
import re
from typing import List, Dict, Any, Optional, Tuple
from difflib import get_close_matches

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# =========================================================================
# 1. UNIVERSAL PARSER v5 — Handles word-form + digits + Indian shorthand
# =========================================================================
class UniversalParser:
    def __init__(self):
        # Word-form number map
        self.word_map = {
            "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
            "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
            "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
            "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
            "hundred": 100, "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5,
            "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10
        }
        self.unit_map = {
            "l": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "lpa": 1e5,
            "k": 1e3, "thousand": 1e3, "thousands": 1e3,
            "cr": 1e7, "crore": 1e7, "crores": 1e7,
            "mn": 1e6, "million": 1e6,
            "pm": 12, "permonth": 12, "per month": 12,
        }
        # Regex for digit-based representations (e.g., "18 LPA", "45k", "1.5 crore", "50,000 pm")
        self.digit_pat = re.compile(
            r'(\d[\d,]*(?:\.\d+)?)\s*'
            r'(lakhs?|lacs?|l(?!e)|crores?|crs?|k|thousand(?:s)?|lpa|mn|million|pm|per\s*month)?',
            re.IGNORECASE
        )
        # Regex for word-form representations (e.g., "thirty five lakhs", "two crore")
        self.word_pat = re.compile(
            r'\b((?:' + '|'.join(self.word_map.keys()) + r')\s*)+'
            r'(?:and\s+)?(?:' + '|'.join(self.word_map.keys()) + r')?\s*'
            r'(lakhs?|lacs?|crores?|crs?|l(?!e)|thousand(?:s)?|k)?\b',
            re.IGNORECASE
        )

    def _resolve_words(self, phrase: str) -> float:
        words = phrase.lower().split()
        total, current = 0.0, 0.0
        for w in words:
            if w in self.word_map:
                n = self.word_map[w]
                if n == 100:
                    current = (current if current else 1) * 100
                else:
                    current += n
            elif w == "and":
                continue
        return total + current

    def parse(self, text: str) -> List[Dict[str, Any]]:
        results = []
        seen_spans = set()

        # Pass 1: Digit-based matches
        for m in self.digit_pat.finditer(text):
            raw = m.group(1).replace(',', '')
            unit = m.group(2)
            annualized = False
            try:
                val = float(raw)
                if unit:
                    unit_l = unit.lower().replace(" ", "")
                    mult = self.unit_map.get(unit_l, 1)
                    annualized = unit_l in ("pm", "permonth")
                    val = val * 12 if annualized else val * mult

                # Check following text for monthly indicator (e.g. "45k pm", "80000 per month")
                rest = text[m.end():m.end() + 14].lower().strip()
                if rest.startswith("pm") or rest.startswith("per month") or rest.startswith("/month") or rest.startswith("p.m"):
                    val = val * 12
                    annualized = True

                if val < 100:
                    continue

                seen_spans.add((m.start(), m.end()))
                # "annualized" (C3): True iff THIS match already includes the
                # ×12 monthly conversion, so the NLP engine never applies it
                # a second time. val/start/end semantics are unchanged.
                results.append({"val": val, "start": m.start(), "end": m.end(), "annualized": annualized})
            except Exception:
                continue

        # Pass 2: Word-form matches (e.g. "thirty five lakhs")
        for m in self.word_pat.finditer(text):
            if any(m.start() <= s[0] <= m.end() or m.start() <= s[1] <= m.end() for s in seen_spans):
                continue
            parts = m.group(0).split()
            unit_candidates = [p for p in parts if p.lower() in self.unit_map]
            word_parts = [p for p in parts if p.lower() not in self.unit_map and p.lower() != "and"]
            val = self._resolve_words(" ".join(word_parts))
            if val == 0:
                continue
            unit = unit_candidates[0] if unit_candidates else None
            if unit:
                mult = self.unit_map.get(unit.lower(), 1)
                val = val * mult
            if val < 1000:
                continue
            # word_pat's unit group has no "pm" form, so word matches are
            # never annualized here (the engine layer handles "monthly").
            results.append({"val": val, "start": m.start(), "end": m.end(), "annualized": False})

        return results


# =========================================================================
# 2. SEMANTIC ATTENTION v5 — Consolidated Categories & Robust Proximity
# =========================================================================
class SemanticAttention:
    def __init__(self):
        # Cleanly consolidated categories without duplicate keys
        self.categories = {
            "salary": {
                "pos": [
                    "salary", "basic pay", "ctc", "lpa", "monthly pay", "gross pay",
                    "net pay", "take home", "paycheck", "salary credit", "salary slip",
                    "form 16", "basic salary", "allowance", "perquisite", "arrears",
                    "leave encashment", "notice pay", "joining bonus", "variable pay",
                    "performance bonus", "da", "ta", "conveyance allowance",
                    "hra allowance", "medical allowance", "special allowance",
                    "city compensatory allowance", "project allowance", "shift allowance",
                    "overtime pay", "bonus received", "ex-gratia", "stipend",
                    "internship pay", "consultancy salary", "part time salary",
                    "package", "annual salary", "fixed pay", "base pay", "income from job",
                    "service income", "employment", "retention bonus", "naukri", "job"
                ],
                "neg": ["business income", "rental", "interest earned", "dividend", "agriculture", "loan", "shop", "practice"]
            },
            "business": {
                "pos": [
                    "business", "turnover", "gross receipt", "professional fee",
                    "consultancy income", "practice income", "shop income",
                    "sales", "revenue", "clinic income", "freelance project",
                    "agency income", "contract income", "gst turnover", "itr 3", "itr 4",
                    "presumptive income", "44ad", "44ada", "firm profit",
                    "partnership share", "manufacturing income", "trading profit",
                    "business sales", "professional receipts", "audit fee received",
                    "trading turnover", "commission income", "brokerage income business",
                    "export income", "freelance income", "gig work income",
                    "solopreneur revenue", "startup revenue", "ecommerce sales",
                    "stock market income", "f&o income", "profit", "trader", "vyapar", "dukaan"
                ],
                "neg": ["salary", "job", "employee", "ctc", "paycheck", "form 16"]
            },
            "rental": {
                "pos": [
                    "rent received", "rental income", "house rent income", "property rent",
                    "let out", "rented out", "tenant pays", "monthly rent received",
                    "pg income", "hostel income", "lease rent", "rental",
                    "from rental", "from rent", "earning rent", "i get rent",
                    "rental property", "rental house", "i have rental"
                ],
                "neg": ["rent paid", "home loan", "salary", "i pay rent"]
            },
            "agriculture": {
                "pos": [
                    "agriculture", "farming", "crop", "kisan", "farm income",
                    "agricultural income", "cultivation", "paddy", "wheat", "sugarcane",
                    "agriculture income", "farming income", "agri income", "farming profit",
                    "kheti badi", "crop sale", "sale of produce", "nursery income"
                ],
                "neg": []
            },
            "capital_gains": {
                "pos": [
                    "sold shares", "sold stocks", "sold mutual fund", "redeemed",
                    "sold property", "house sale", "land sale", "capital gain",
                    "profit on sale", "equity gain", "property appreciation",
                    "property sale", "flat sale", "plot sale", "sale of property",
                    "sold flat", "sold plot", "sold my house", "sold my flat",
                    "sold my land", "sold my plot", "property sold", "flat sold",
                    "share sale", "mutual fund redemption", "selling shares",
                    "sold shares worth", "sold equity", "stcg", "ltcg", "short term gain",
                    "long term gain", "equity profit", "stock market profit",
                    "crypto profit", "sale of gold", "jewelry sale", "sale of asset",
                    "real estate profit", "indexation benefit", "holding period",
                    "esop exercise", "rsu sale"
                ],
                "neg": ["purchased", "bought", "invested", "sip"]
            },
            "other_income": {
                "pos": [
                    "interest income", "fd interest", "bank interest", "dividend",
                    "royalty", "lottery", "gift received", "pension", "family pension",
                    "savings interest", "interest from fd", "interest from bank",
                    "recurring deposit", "post office interest", "dividend income",
                    "tax refund interest", "cash gift", "prize money", "commission",
                    "income from other sources", "miscellaneous income", "extra income",
                    "bank fd interest", "interest on bonds"
                ],
                "neg": ["salary", "business", "rent"]
            },
            "80c": {
                "pos": [
                    "ppf", "public provident", "epf", "pf contribution", "elss",
                    "lic premium", "life insurance", "nsc", "tax saving fd",
                    "tuition fee", "tuition fees", "tution fee", "tution fees",
                    "tuition", "tution", "child education",
                    "child tuition", "children school", "school fees", "college fees",
                    "home loan principal", "housing loan principal", "sukanya",
                    "sukanya samriddhi", "ssapf", "ssy", "80c", "section 80c",
                    "tax saving investment", "vpf", "voluntary pf", "five year fd",
                    "senior citizen savings", "scss", "ulip", "tax saving mutual fund"
                ],
                "neg": ["health", "premium for parents", "80d", "mediclaim"]
            },
            "80d": {
                "pos": [
                    "health insurance", "medical insurance", "mediclaim", "80d",
                    "section 80d", "family health", "self insurance", "star health",
                    "niva bupa", "preventive health", "health checkup",
                    "family insurance", "family cover", "insurance premium",
                    "health premium", "medical premium", "mediclaim premium"
                ],
                "neg": ["parents", "senior citizens", "80d parents", "life insurance", "lic"]
            },
            "80d_parents": {
                "pos": [
                    "parents health", "health of parents", "insurance for parents",
                    "mom insurance", "dad insurance", "mother policy", "father policy",
                    "senior citizen insurance", "parents mediclaim", "medical for parents",
                    "health premium parents", "senior citizen medical", "medical for mom",
                    "medical for dad"
                ],
                "neg": ["self", "child", "children", "spouse", "wife", "husband"]
            },
            "80e": {
                "pos": [
                    "education loan", "student loan", "higher education loan",
                    "study loan", "college loan", "university loan", "mba loan",
                    "education interest", "interest on study loan", "vidyalakshmi loan"
                ],
                "neg": ["business loan", "home loan", "car loan", "personal loan"]
            },
            "80g": {
                "pos": [
                    "donation", "charity", "donated", "pm relief fund", "cm fund",
                    "ngo donation", "temple donation", "80g", "section 80g",
                    "charitable trust", "relief fund", "pmnrf", "donated to ngo"
                ],
                "neg": ["rent", "hra", "house"]
            },
            "nps": {
                "pos": [
                    "nps", "national pension", "80ccd", "tier 1", "pension contribution",
                    "atal pension", "80ccd(1b)", "nps contribution", "tier 1 nps"
                ],
                "neg": ["tier 2"]
            },
            # Sprint 2 Step B: the legacy "hra" attention category is SPLIT
            # into its two statutory legs — HRA RECEIVED (Rule 2A leg (a))
            # and RENT PAID (leg (b) input). The rent-paid keyword family
            # moves to rent_paid verbatim; the HRA-specific keywords form
            # hra_received. Neither is an OVERWRITE category (both
            # accumulate), so one sentence books both legs clause-locally
            # ("I receive 3L HRA and pay 2L rent").
            # neg families: "no hra"/"no rent" negations stay on both new
            # categories as appropriate; "rent received" marks landlord
            # income (the rental category), not an HRA/rent-paid amount;
            # "rent" itself must NEVER enter hra_received.neg (it would
            # kill "house rent allowance" via substring matching).
            "hra_received": {
                "pos": [
                    "hra", "house rent allowance", "hra received",
                    "hra from employer",
                ],
                "neg": ["no hra", "rent received"]
            },
            "rent_paid": {
                "pos": [
                    "rent paid", "paying rent", "monthly rent paid",
                    "rent to landlord", "house rent paid", "i pay rent",
                    "i am paying rent", "paying house rent",
                    "rented accommodation", "rent for house", "pay rent of",
                    "rent per month", "monthly rent is", "rent is",
                    "house rent", "flat rent", "apartment rent", "rent"
                ],
                "neg": ["rent received", "own house", "no rent", "tenant"]
            },
            "24b": {
                "pos": [
                    "home loan interest", "housing loan interest", "24b", "section 24",
                    "interest on home loan", "emi interest component",
                    "mortgage interest", "house loan interest", "home loan emi interest"
                ],
                "neg": ["education loan", "car loan", "personal loan", "principal"]
            },
            "80eea": {
                "pos": ["80eea", "affordable housing", "first home buyer", "affordable home loan interest"],
                "neg": []
            },
            "80tta": {
                "pos": ["savings account interest", "bank savings interest", "80tta", "saving bank interest"],
                "neg": ["fd", "fixed deposit", "senior"]
            },
            "80ttb": {
                "pos": ["80ttb", "senior citizen interest", "fd interest senior", "senior citizen bank interest"],
                "neg": []
            },
            "80gg": {
                "pos": ["80gg", "no hra", "rent without hra", "self employed rent paid", "section 80gg rent"],
                "neg": ["hra received", "hra from employer"]
            },
            "80u_80dd": {
                "pos": ["disability deduction", "disabled", "handicapped", "80u", "80dd", "severe disability"],
                "neg": []
            },
            "80ddb": {
                "pos": ["critical illness treatment", "80ddb", "cancer treatment", "special disease treatment"],
                "neg": []
            },
        }

    def resolve_category(self, sentence: str, val_start: int, val_end: int,
                          profile: Optional[str] = None, asked_cat: Optional[str] = None) -> str:
        """Public wrapper: returns only the category (behavior unchanged)."""
        return self.resolve_category_detailed(
            sentence, val_start, val_end, profile, asked_cat
        )[0]

    def resolve_category_detailed(self, sentence: str, val_start: int, val_end: int,
                                   profile: Optional[str] = None,
                                   asked_cat: Optional[str] = None) -> Tuple[str, bool]:
        """Resolve the category for a parsed value span.

        Returns (category, is_default): is_default is True ONLY when the
        profile-default fall-through fired (no category scored >= the
        threshold of 10). Callers use it to guard income overwrites (C4a):
        an unrecognized amount must never silently replace a real value.
        """
        t = sentence.lower()
        profile_default = {"Business Owner": "business", "Salaried": "salary"}.get(profile, "other_income")

        raw_matches = []
        for cat, kw_map in self.categories.items():
            neg_penalty = 1.0
            for nk in kw_map["neg"]:
                if nk in t:
                    neg_penalty = -10.0
                    break

            for kw in kw_map["pos"]:
                idx = t.find(kw)
                while idx != -1:
                    is_partial = False
                    if idx > 0 and t[idx - 1].isalnum() and len(kw) < 4:
                        is_partial = True
                    if idx + len(kw) < len(t) and t[idx + len(kw)].isalnum() and len(kw) < 4:
                        is_partial = True

                    if not is_partial:
                        dist = min(abs(idx - val_start), abs(idx - val_end))
                        # Gaussian decay using pure math: exp(-dist^2 / (2 * 40^2))
                        prox_score = 100.0 * math.exp(- (dist ** 2) / (2.0 * 1600.0))
                        content_score = len(kw.split()) * 2.5 + len(kw) * 0.1

                        # Nuclear Penalties for Cross-Profile Mapping
                        if profile == "Business Owner" and cat == "salary":
                            prox_score *= 0.1
                        if profile == "Salaried" and cat == "business":
                            prox_score *= 0.1

                        raw_matches.append({
                            "cat": cat, "kw": kw, "pos": idx,
                            "score": prox_score * content_score * neg_penalty
                        })
                    idx = t.find(kw, idx + 1)

        # Longer phrases subsume shorter sub-phrases
        final_matches = []
        for i, m1 in enumerate(raw_matches):
            is_subsumed = False
            for j, m2 in enumerate(raw_matches):
                if i == j:
                    continue
                m1_end = m1["pos"] + len(m1["kw"])
                m2_end = m2["pos"] + len(m2["kw"])
                if m2["pos"] <= m1["pos"] and m2_end >= m1_end and len(m2["kw"]) > len(m1["kw"]):
                    is_subsumed = True
                    break
            if not is_subsumed:
                final_matches.append(m1)

        # Aggregate category scores
        cat_scores: Dict[str, float] = {}
        for m in final_matches:
            cat_scores[m["cat"]] = cat_scores.get(m["cat"], 0.0) + m["score"]

        # Boost the category asked about (Contextual Prior)
        content_max = max(cat_scores.values()) if cat_scores else 0.0
        if asked_cat and asked_cat in self.categories:
            if content_max < 150.0:
                cat_scores[asked_cat] = cat_scores.get(asked_cat, 0.0) + 30.0

        if not cat_scores or max(cat_scores.values()) < 10.0:
            return profile_default, True

        # C4a: the fall-through test is evaluated on CONTENT scores alone —
        # a win carried only by the asked-category prior (e.g. the
        # "SALARY: ₹..." ack text carrying the prior into the next turn) is
        # still a guess, not recognition, so is_default stays True and the
        # engine's overwrite guard applies. Fresh entries are unaffected
        # (the guard only blocks overwrites of positive values).
        return max(cat_scores, key=cat_scores.get), content_max < 10.0


# =========================================================================
# 3. REASONING AGENT v4 — Multi-step Discovery Waterfall
# =========================================================================
class ReasoningAgent:
    DISCOVERY_STEPS = [
        ("income", "Ask for income details (Salary/Business)."),
        ("80c",    "Ask about Section 80C investments (PPF, ELSS, PF, Life Insurance up to 1.5L)."),
        ("80d",    "Ask about health insurance (Section 80D)."),
        ("nps",    "Ask about NPS contribution (80CCD(1B) — extra 50k deduction)."),
        # Sprint 2 Step B: the HRA slot needs the THREE statutory Rule 2A
        # inputs — monthly rent, monthly HRA received, metro city. The step
        # key stays "hra" (a step identifier); decide_next_step gates it on
        # the three session keys.
        ("hra",    "Ask about monthly rent paid, monthly HRA received and metro city (HRA exemption / 80GG)."),
        ("24b",    "Ask about home loan interest (Section 24b up to 2L)."),
        ("80g",    "Ask about donations/charity (Section 80G)."),
    ]

    def decide_next_step(self, session: Dict[str, Any]) -> str:
        income_keys = ["salary", "business", "rental", "other_income", "agriculture"]
        total_inc = sum(
            session.get(k, 0) if isinstance(session.get(k), (int, float))
            else sum(x["amount"] for x in session.get(k, []))
            for k in income_keys + ["capital_gains"]
        )
        profile = session.get("profile")

        if total_inc == 0 and profile:
            return f"plan: Acknowledge {profile} and ask for specific income amount."
        if total_inc == 0:
            return "plan: Ask for income details (Salary/Business)."

        for key, desc in self.DISCOVERY_STEPS[1:]:
            if key == "24b" and not session.get("has_home_loan"):
                continue
            if key == "hra":
                # Step B: the HRA step stays open until all three statutory
                # inputs are collected (rent paid, HRA received, metro
                # status). Business Owners skip it (no HRA exemption; the
                # legacy skip rule is preserved).
                if session.get("profile") == "Business Owner":
                    continue
                if any(session.get(k) is None for k in ("rent_paid", "hra_received", "is_metro")):
                    return f"plan: {desc}"
                continue
            if session.get(key) is None:
                return f"plan: {desc}"

        return "plan: Final audit ready."

    def get_savings_tips(self, session: Dict[str, Any]) -> List[str]:
        tips = []
        income = float(session.get("salary", 0) or 0) + float(session.get("business", 0) or 0)
        profile = session.get("profile", "General")

        # 1. Section 80C
        c80 = float(session.get("80c", 0) or 0)
        if c80 < 150000:
            gap = 150000 - c80
            if profile == "Salaried":
                tips.append(f"Section 80C Optimization: You have an unused 80C headroom of ₹{gap:,.0f}. Increasing Voluntary PF (VPF) or ELSS mutual funds locks in EEE tax benefits.")
            else:
                tips.append(f"Section 80C Opportunity: Invest ₹{gap:,.0f} in ELSS or PPF before March 31st to max out your ₹1.5 Lakh limit.")

        # 2. NPS 80CCD(1B)
        nps = float(session.get("nps", 0) or 0)
        if nps < 50000:
            gap = 50000 - nps
            if income > 1500000:
                saving = gap * 0.312
                tips.append(f"NPS Super-Deduction: In the 30% tax bracket, investing ₹{gap:,.0f} in NPS Tier-1 (80CCD(1B)) will save an instant ₹{saving:,.0f} in tax.")
            else:
                tips.append(f"NPS Advantage: Allocate ₹{gap:,.0f} to NPS for an exclusive deduction over and above Section 80C.")

        # 3. Health Insurance (80D)
        if not session.get("80d"):
            tips.append("Section 80D Health Shield: Sec 80D allows ₹25,000 for self/family, plus ₹5,000 for preventive health checkups without requiring hospitalization bills.")

        # 4. Parents Health Cover
        if not session.get("80d_parents") and session.get("has_parents"):
            tips.append("Parental Healthcare: Paying parents' health insurance (or direct medical treatment for senior citizen parents) unlocks an extra ₹50,000 deduction.")

        # 5. Home Loan (24b)
        if session.get("has_home_loan") and not session.get("24b"):
            tips.append("Section 24(b) Home Loan: Claim up to ₹2,00,000 in interest paid on your housing loan for self-occupied residential property.")

        return tips


# =========================================================================
# 4. ANFIS v4 — Takagi-Sugeno-Kang (TSK) Neuro-Fuzzy Inference
# =========================================================================
class ANFIS:
    N_INPUTS = 20
    N_RULES  = 64

    def __init__(self):
        import os, json
        self.is_ready = False
        if not HAS_NUMPY:
            return

        p = os.path.join(os.path.dirname(__file__), "anfis_weights.json")
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    w = json.load(f)
                params = np.array(w["params"], dtype=np.float32)
                self.is_ready = True
            except Exception:
                params = self._init_random_params()
        else:
            params = self._init_random_params()

        n = self.N_INPUTS * self.N_RULES
        self.means  = params[:n].reshape(self.N_INPUTS, self.N_RULES)
        self.sigmas = np.abs(params[n:2 * n]).reshape(self.N_INPUTS, self.N_RULES) + 0.05
        self.cons   = params[2 * n:].reshape(self.N_RULES, self.N_INPUTS + 1)
        self.is_ready = True

    def _init_random_params(self):
        rng = np.random.RandomState(42)
        n = self.N_INPUTS * self.N_RULES
        means  = rng.uniform(0, 1, n).astype(np.float32)
        sigmas = np.full(n, 0.2, dtype=np.float32)
        cons   = (rng.randn(self.N_RULES * (self.N_INPUTS + 1)) * 0.1).astype(np.float32)
        return np.concatenate([means, sigmas, cons])

    def _forward(self, X):
        diff = X[:, :, None] - self.means[None]
        mf = np.exp(-0.5 * (diff / self.sigmas[None]) ** 2)
        w = mf.prod(axis=1)
        w_sum = w.sum(axis=1, keepdims=True) + 1e-9
        w_n = w / w_sum
        Xe = np.concatenate([X, np.ones((len(X), 1))], axis=1)
        f = np.einsum('bi,ri->br', Xe, self.cons)
        return np.clip((w_n * f).sum(axis=1), 0.0, 1.0)

    def score_efficiency(self, *args, **kwargs) -> float:
        """Industrial Efficiency Scorer with backward-compatibility for legacy signatures."""
        if len(args) >= 2 and isinstance(args[0], dict):
            session = args[0]
            result = args[1]
        elif len(args) >= 1 and isinstance(args[0], (int, float)):
            inc = float(args[0])
            c80 = float(args[1]) if len(args) > 1 else 0.0
            d80 = float(args[2]) if len(args) > 2 else 0.0
            nps = float(args[3]) if len(args) > 3 else 0.0
            session = {"salary": inc, "80c": c80, "80d": d80, "nps": nps}
            result = {"savings": float(args[6]) if len(args) > 6 else 0.0, "total_tax": float(args[8]) if len(args) > 8 else 0.0}
        elif "session" in kwargs:
            session = kwargs["session"]
            result = kwargs.get("result", {})
        else:
            session = {}
            result = {}

        inc = float(session.get("salary", 0) or 0) + float(session.get("business", 0) or 0) + float(session.get("other_income", 0) or 0) + 1e-9

        if not HAS_NUMPY or not self.is_ready:
            # Deterministic heuristic fallback if numpy is absent
            c80 = min(1.0, float(session.get("80c", 0) or 0) / 150000.0)
            d80 = min(1.0, float(session.get("80d", 0) or 0) / 25000.0)
            nps = min(1.0, float(session.get("nps", 0) or 0) / 50000.0)
            score = 50.0 + (c80 * 25.0) + (d80 * 15.0) + (nps * 10.0)
            return round(min(98.5, max(30.0, score)), 1)

        f = [
            np.clip(inc / 10_000_000, 0, 1),
            np.clip(float(session.get("80c", 0) or 0) / 150000, 0, 1),
            np.clip(float(session.get("80d", 0) or 0) / 25000, 0, 1),
            np.clip(float(session.get("80d_parents", 0) or 0) / 50000, 0, 1),
            np.clip(float(session.get("nps", 0) or 0) / 50000, 0, 1),
            np.clip(float(session.get("hra", 0) or 0) / 200000, 0, 1),
            np.clip(float(session.get("24b", 0) or 0) / 200000, 0, 1),
            np.clip(float(session.get("80e", 0) or 0) / 500000, 0, 1),
            np.clip(float(session.get("80g", 0) or 0) / (inc * 0.1 + 1), 0, 1),
            np.clip(float(session.get("80tta", 0) or 0) / 50000, 0, 1),
            np.clip(float(session.get("80u_80dd", 0) or 0) / 125000, 0, 1),
            np.clip(float(session.get("80ddb", 0) or 0) / 100000, 0, 1),
            np.clip(float(session.get("80eea", 0) or 0) / 150000, 0, 1),
            np.clip(sum(x.get("amount", 0) for x in session.get("capital_gains", [])) / inc, 0, 1),
            np.clip(float(session.get("business", 0) or 0) / inc, 0, 1),
            0.3,
            np.clip(result.get("savings", 0) / (inc * 0.1 + 1), 0, 1),
            np.clip(result.get("total_tax", 0) / (inc * 0.3 + 1), 0, 1),
            1.0 if session.get("profile") == "Senior Citizen" else 0.0,
            1.0 - np.clip(float(session.get("80c", 0) or 0) / 150000, 0, 1)
        ]

        x = np.array([f], dtype=np.float32)
        return round(float(self._forward(x)[0]) * 100, 1)

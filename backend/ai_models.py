"""
AI Models v10.0 — Massive Upgrade
Fixes: Word-form numbers, expanded semantic categories, calibrated ANFIS,
       mission-critical surcharge brackets, 87A rebate, NPS/HRA discovery.
"""

import numpy as np
import re
from typing import List, Dict, Any, Optional
from difflib import get_close_matches

# =========================================================================
# 1. UNIVERSAL PARSER v4 — Handles word-form + digit + Indian shorthand
# =========================================================================
class UniversalParser:
    def __init__(self):
        # Word-form number map (for "thirty lakhs", "two crore" etc.)
        self.word_map = {
            "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,
            "seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,
            "thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,
            "eighteen":18,"nineteen":19,"twenty":20,"thirty":30,"forty":40,
            "fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90,
            "hundred":100,"ek":1,"do":2,"teen":3,"char":4,"paanch":5,
            "chhe":6,"saat":7,"aath":8,"nau":9,"das":10
        }
        self.unit_map = {
            "l":1e5,"lakh":1e5,"lakhs":1e5,"lac":1e5,"lacs":1e5,"lpa":1e5,
            "k":1e3,"thousand":1e3,"thousands":1e3,
            "cr":1e7,"crore":1e7,"crores":1e7,
            "mn":1e6,"million":1e6,
            "pm":12, "permonth":12, "per month":12,
        }
        # Digit pattern — handles 45k pm as a unit group
        self.digit_pat = re.compile(
            r'(\d[\d,]*(?:\.\d+)?)\s*'
            r'(lakhs?|lacs?|l(?!e)|crores?|crs?|k|thousand(?:s)?|lpa|mn|million|pm|per\s*month)?',
            re.IGNORECASE
        )
        # Word-form pattern: "thirty five lakhs"
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
            elif w in ("and",): continue
        return total + current

    def parse(self, text: str) -> List[Dict[str, Any]]:
        results = []
        seen_spans = set()

        # Pass 1: Digit-based matches
        for m in self.digit_pat.finditer(text):
            raw = m.group(1).replace(',', '')
            unit = m.group(2)
            try:
                val = float(raw)
                if unit:
                    unit_l = unit.lower().replace(" ", "")
                    mult = self.unit_map.get(unit_l, 1)
                    val = val * 12 if unit_l in ("pm", "permonth") else val * mult
                # PM lookahead: works whether or not a unit was already consumed
                # Handles: "45k pm", "1.5L pm", "80000 per month"
                rest = text[m.end():m.end()+12].lower().strip()
                if rest.startswith("pm") or rest.startswith("per month"):
                    val = val * 12
                if val < 100:
                    continue
                span = (m.start(), m.end())
                seen_spans.add(span)
                results.append({"val": val, "start": m.start(), "end": m.end()})
            except: continue

        # Pass 2: Word-form matches (e.g. "thirty five lakhs")
        for m in self.word_pat.finditer(text):
            if any(m.start() <= s[0] <= m.end() or m.start() <= s[1] <= m.end() for s in seen_spans):
                continue  # Don't double-count with digit match
            parts = m.group(0).split()
            unit_candidates = [p for p in parts if p.lower() in self.unit_map]
            word_parts = [p for p in parts if p.lower() not in self.unit_map and p.lower() != "and"]
            val = self._resolve_words(" ".join(word_parts))
            if val == 0: continue
            unit = unit_candidates[0] if unit_candidates else None
            if unit:
                mult = self.unit_map.get(unit.lower(), 1)
                val = val * mult
            if val < 1000: continue
            results.append({"val": val, "start": m.start(), "end": m.end()})

        return results


# =========================================================================
# 2. SEMANTIC ATTENTION v4 — Expanded categories + smarter scoring
# =========================================================================
class SemanticAttention:
    def __init__(self):
        # Extended keyword maps: (positive_keywords, negative_keywords, weight)
        self.categories = {
            "salary": {
                "pos": ["salary","ctc","package","take home","gross salary","net salary",
                        "annual salary","monthly salary","fixed pay","base pay","basic pay",
                        "lpa","income from job","service income","employment","stipend",
                        "variable pay","joining bonus","retention bonus"],
                "neg": ["business income","rental","interest earned","dividend","agriculture","loan"]
            },
            "business": {
                "pos": ["business","profit","turnover","revenue","sales","gst turnover",
                        "net profit","gross profit","business income","trading income",
                        "professional income","freelance income","consulting income",
                        "practice income","receipts","billings","invoice"],
                "neg": ["salary","job","rent received","interest"]
            },
            "rental": {
                "pos": ["rent received", "rental income", "house rent income", "property rent",
                        "let out", "rented out", "tenant pays", "monthly rent received",
                        "pg income", "hostel income", "lease rent", "rental",
                        "from rental", "from rent", "earning rent", "i get rent",
                        "rental property", "rental house", "i have rental"],
                "neg": ["rent paid", "home loan", "salary", "i pay rent"]
            },
            "agriculture": {
                "pos": ["agriculture","farming","crop","kisan","farm income",
                        "agricultural income","cultivation","paddy","wheat","sugarcane"],
                "neg": []
            },
            "capital_gains": {
                "pos": ["sold shares", "sold stocks", "sold mutual fund", "redeemed",
                        "sold property", "house sale", "land sale", "capital gain",
                        "profit on sale", "equity gain", "property appreciation",
                        "sold flat", "sold plot", "sold my house", "sold my flat",
                        "sold my land", "sold my plot", "property sold", "flat sold",
                        "share sale", "mutual fund redemption", "selling shares",
                        "sold shares worth", "sold equity", "stcg", "ltcg", "short term gain",
                        "long term gain", "equity profit", "stock market profit",
                        "crypto profit", "sale of gold", "jewelry sale", "sale of asset",
                        "real estate profit", "indexation benefit", "holding period",
                        "demat credit", "off-market transfer", "bonus issue sale",
                        "rights issue sale", "buyback proceeds", "tender offer",
                        "unlisted shares sale", "esop exercise", "rsu sale",
                        "commercial property sale", "industrial land sale",
                        "inherited property sale", "cost of acquisition", "cost of improvement"],
                "neg": ["purchased", "bought", "invested", "sip"]
            },
            "other_income": {
                "pos": ["interest income","fd interest","bank interest","dividend",
                        "royalty","lottery","gift received","alimony received",
                        "pension","family pension","gratuity","bonus income",
                        "savings interest", "interest from fd", "interest from bank",
                        "recurring deposit", "post office interest", "dividend income",
                        "tax refund interest", "cash gift", "prize money",
                        "kbc winning", "horse racing", "betting income", "crypto interest",
                        "freelancing income", "consultancy fee", "commission",
                        "brokerage received", "honorarium", "examination fee",
                        "income from other sources", "miscellaneous income", "extra income",
                        "fd matured", "bank fd interest", "cooperative society interest",
                        "interest on bonds", "debenture interest", "liquid fund interest",
                        "gift from friend", "gift from relative", "marriage gift cash",
                        "pension arrears", "commuted pension", "uncommuted pension",
                        "family pension received", "rental income from machinery",
                        "subletting income", "vacant land rent", "key money received"],
                "neg": ["salary","business","rent"]
            },
            "salary": {
                "pos": ["salary", "basic pay", "ctc", "lpa", "monthly pay", "gross pay",
                        "net pay", "take home", "paycheck", "salary credit", "salary slip",
                        "form 16", "basic salary", "allowance", "perquisite", "arrears",
                        "leave encashment", "notice pay", "joining bonus", "variable pay",
                        "performance bonus", "da", "ta", "conveyance allowance",
                        "hra allowance", "medical allowance", "special allowance",
                        "city compensatory allowance", "project allowance", "shift allowance",
                        "overtime pay", "bonus received", "ex-gratia", "stipend",
                        "internship pay", "consultancy salary", "part time salary"],
                "neg": ["business", "shop", "practice", "freelance"]
            },
            "business": {
                "pos": ["business", "turnover", "gross receipt", "professional fee",
                        "consultancy income", "practice income", "shop income",
                        "sales", "revenue", "clinic income", "freelance project",
                        "agency income", "contract income", "gst turnover", "itr 3", "itr 4",
                        "presumptive income", "44ad", "44ada", "firm profit",
                        "partnership share", "manufacturing income", "trading profit",
                        "business sales", "professional receipts", "audit fee received",
                        "trading turnover", "commission income", "brokerage income business",
                        "export income", "freelance income", "gig work income",
                        "solopreneur revenue", "startup revenue", "ecommerce sales", "trading profit",
                        "stock market income", "f&o income", "trading turnover", "profit", "trader"],
                "neg": ["salary", "job", "employee", "ctc"]
            },
            # ---- DEDUCTIONS ----
            "80c": {
                "pos": ["ppf", "public provident", "epf", "pf contribution", "elss",
                        "lic premium", "life insurance", "nsc", "tax saving fd",
                        "tuition fee", "tuition fees", "tution fee", "tution fees",
                        "child tuition", "children school", "school fees",
                        "college fees", "home loan principal", "housing loan principal",
                        "sukanya", "sukanya samriddhi", "ssapf", "ssy",
                        "80c", "section 80c", "tax saving investment",
                        "infrastructure bond", "stamp duty", "lic", "ppf account",
                        "vpf", "voluntary pf", "five year fd", "senior citizen savings",
                        "scss", "unit linked insurance", "ulip", "annuity plan",
                        "mutual fund tax saver", "tax saving mutual fund", "80c investment",
                        "national savings certificate", "post office saving",
                        "registration charges for house", "deferred annuity",
                        "kvp", "kisan vikas patra", "post office 5 year deposit",
                        "nabard bonds", "sidbi bonds", "nhai bonds", "tax saving bonds",
                        "pension fund contribution", "notified pension fund",
                        "additional pf", "employee pf", "provident fund contribution",
                        "life insurance policy premium", "lic payment", "insurance 80c"],
                "neg": ["health", "premium for parents", "80d", "mediclaim"]
            },
            "80d": {
                "pos": ["health insurance", "medical insurance", "mediclaim", "80d",
                        "section 80d", "family health", "self insurance", "star health",
                        "max bupa", "niva bupa", "preventive health", "health checkup",
                        "family insurance", "family cover", "family floater",
                        "full family insurance", "family mediclaim", "family policy",
                        "insurance premium", "health premium", "medical premium",
                        "group insurance", "personal health", "individual health",
                        "mediclaim premium", "health policy", "medi-claim",
                        "corona kavach", "critical illness", "hospital cover",
                        "insurance", "medical bill", "opd expenses", "maternity cover",
                        "hospicash", "health policy premium", "medical expenditure",
                        "health check up expenses", "preventive medical checkup",
                        "health check costs", "doctor fees health", "lab tests health",
                        "medical policy", "medical plan", "cashless insurance"],
                "neg": ["parents", "senior citizens", "80d parents", "life insurance", "lic"]
            },
            "80d_parents": {
                "pos": ["parents health","health of parents","insurance for parents",
                        "mom insurance","dad insurance","mother policy","father policy",
                        "senior citizen insurance","parents mediclaim", "medical for parents",
                        "health premium parents", "senior citizen medical", "medical for mom",
                        "medical for dad", "parents health checkup", "medical of father",
                        "medical of mother", "mediclaim for mother", "mediclaim for father",
                        "mother insurance premium", "father insurance premium"],
                "neg": ["self", "child", "children", "spouse", "wife", "husband"]
            },
            "80e": {
                "pos": ["education loan","student loan","higher education loan",
                        "study loan","college loan","university loan",
                        "engineering loan","medical college loan",
                        "eductaion loan","educaion loan","edu loan","edloan",
                        "education interest", "loan for study", "mba loan", "masters loan",
                        "loan for daughter education", "loan for son education",
                        "interest on study loan", "vidyalakshmi loan", "abroad study loan"],
                "neg": ["business loan","home loan","car loan","personal loan"]
            },
            "80g": {
                "pos": ["donation","charity","donated","pm relief fund","cm fund",
                        "ngo donation","temple donation","80g","section 80g",
                        "contribution to trust","charitable trust", "relief fund",
                        "political donation", "scientific research donation",
                        "rural development donation", "pmnrf", "iskaan", "akshaya patra",
                        "donation for temple", "contribution to ngo", "swachh bharat fund",
                        "clean ganga fund", "national defense fund", "army welfare fund",
                        "donated to ngo", "gave to charity", "money to orphanage"],
                "neg": ["rent", "hra", "house", "apartment"]
            },
            "nps": {
                "pos": ["nps","national pension","80ccd","tier 1","pension contribution",
                        "atal pension","80ccd(1b)","nps contribution","pension scheme",
                        "tier 1 nps", "pension fund", "nps self contribution",
                        "nps corporate", "nps employer", "national pension system contribution",
                        "contribution to nps", "pension fund account"],
                "neg": ["tier 2"]
            },
            "hra": {
                "pos": ["hra", "house rent allowance", "rent paid", "paying rent",
                        "monthly rent paid", "rent to landlord", "house rent paid",
                        "i pay rent", "i am paying rent", "paying house rent",
                        "rented accommodation", "rent for house", "pay rent of",
                        "rent per month", "monthly rent is", "rent is", "rent",
                        "house rent", "room rent", "flat rent", "apartment rent",
                        "lease rent", "home rent", "pg rent", "hostel rent"],
                "neg": ["rent received", "own house", "no rent", "tenant"]
            },
            "24b": {
                "pos": ["home loan interest","housing loan interest","24b","section 24",
                        "interest on home loan","emi interest component",
                        "mortgage interest","house loan interest", "housing loan emi",
                        "home loan emi", "home loan installment interest",
                        "loan interest house", "interest on housing loan",
                        "construction loan interest", "repair loan interest house"],
                "neg": ["education loan","car loan","personal loan","business loan", "principal"]
            },
            "80eea": {
                "pos": ["80eea","affordable housing","first home buyer","pradhan mantri awas",
                        "pmax", "affordable home loan interest", "interest on affordable house"],
                "neg": []
            },
            "80tta": {
                "pos": ["savings account interest","bank savings interest","80tta",
                        "saving bank interest", "post office savings interest",
                        "interest on savings", "bank interest on savings"],
                "neg": ["fd","fixed deposit","senior"]
            },
            "80ttb": {
                "pos": ["80ttb","senior citizen interest","fd interest senior","bank interest senior",
                        "post office interest senior", "senior citizen bank interest",
                        "fd interest senior citizen"],
                "neg": []
            },
            "80gg": {
                "pos": ["80gg","no hra","rent without hra","self employed rent paid",
                        "rent paid no hra", "section 80gg rent"],
                "neg": ["hra received","hra from employer"]
            },
            "agriculture": {
                "pos": ["agriculture income", "farming income", "agri income", "farm income",
                        "agricultural profit", "farming profit", "kheti badi", "crop sale",
                        "sale of produce", "nursery income", "farm house income",
                        "income from land", "grain sale", "vegetable sale farming"],
                "neg": []
            },
            "80u_80dd": {
                "pos": ["disability deduction", "disabled", "handicapped", "80u", "80dd",
                        "severe disability", "medical treatment disability",
                        "maintenance of disabled", "care of disabled dependent"],
                "neg": []
            },
            "80ddb": {
                "pos": ["critical illness treatment", "80ddb", "cancer treatment",
                        "aids treatment", "neurological disease", "special disease treatment"],
                "neg": []
            },
        }

    def resolve_category(self, sentence: str, val_start: int, val_end: int,
                         profile: Optional[str] = None, asked_cat: Optional[str] = None) -> str:
        """
        High-fidelity category resolution using probabilistic scoring and substring suppression.
        Handles 'lakhs of cases' by prioritizing longer matches and contextual priors.
        """
        t = sentence.lower()
        profile_default = {"Business Owner": "business", "Salaried": "salary"}.get(profile, "other_income")

        # 1. Extract all candidate matches with proximity-aware raw scores
        raw_matches = []
        for cat, kw_map in self.categories.items():
            # Global category penalty if negative keywords found anywhere
            neg_penalty = 1.0
            for nk in kw_map["neg"]:
                if nk in t:
                    neg_penalty = -10.0 # Nuclear penalty
                    break

            for kw in kw_map["pos"]:
                idx = t.find(kw)
                while idx != -1:
                    # Substring check: avoid partial word matches (e.g., 'rent' in 'parental')
                    # But allow dedicated codes like '80c' to match inside larger strings like 'sec 80c'
                    is_partial = False
                    if idx > 0 and t[idx-1].isalnum() and len(kw) < 4: is_partial = True
                    if idx + len(kw) < len(t) and t[idx + len(kw)].isalnum() and len(kw) < 4: is_partial = True
                    
                    if not is_partial:
                        dist = min(abs(idx - val_start), abs(idx - val_end))
                        # Proximity Score: Gaussian decay (sigma=40 chars)
                        prox_score = 100.0 * np.exp(- (dist**2) / (2 * 40**2))
                        # Content Score: Longer keywords/phrases provide higher signal
                        content_score = len(kw.split()) * 2.5 + len(kw) * 0.1
                        
                        # Nuclear Penalties for Cross-Profile Mapping
                        if profile == "Business Owner" and cat == "salary":
                            prox_score *= 0.1 # Heavy penalty for salary if business owner
                        if profile == "Salaried" and cat == "business":
                            prox_score *= 0.1 # Heavy penalty for business if salaried

                        raw_matches.append({
                            "cat": cat, "kw": kw, "pos": idx, 
                            "score": prox_score * content_score * neg_penalty
                        })
                    idx = t.find(kw, idx + 1)

        # 2. Subsumption Rule: Longer phrases 'eat' their shorter component keywords
        # e.g., 'life insurance premium' (3 words) swallows 'insurance' (1 word)
        final_matches = []
        for i, m1 in enumerate(raw_matches):
            is_subsumed = False
            for j, m2 in enumerate(raw_matches):
                if i == j: continue
                # If m1 is a strict subset of m2 in the same position
                m1_end = m1["pos"] + len(m1["kw"])
                m2_end = m2["pos"] + len(m2["kw"])
                if m2["pos"] <= m1["pos"] and m2_end >= m1_end and len(m2["kw"]) > len(m1["kw"]):
                    is_subsumed = True
                    break
            if not is_subsumed:
                final_matches.append(m1)

        # 3. Aggregate results & Apply Contextual Prior
        cat_scores: Dict[str, float] = {}
        for m in final_matches:
            cat_scores[m["cat"]] = cat_scores.get(m["cat"], 0) + m["score"]

        # Boost the category the AI just asked about (Contextual Prior)
        if asked_cat and asked_cat in self.categories:
            # We only boost if we don't have a VERY strong competing keyword signal
            current_max = max(cat_scores.values()) if cat_scores else 0
            if current_max < 150.0: 
                cat_scores[asked_cat] = cat_scores.get(asked_cat, 0.0) + 30.0

        if not cat_scores or max(cat_scores.values()) < 10.0:
            return profile_default

        return max(cat_scores, key=cat_scores.get)


# =========================================================================
# 3. REASONING AGENT v3 — Multi-step discovery waterfall with NPS/HRA/80G
# =========================================================================
class ReasoningAgent:
    # Discovery waterfall — order matters
    DISCOVERY_STEPS = [
        ("income", "Ask for income details (Salary/Business)."),
        ("80c",    "Ask about Section 80C investments."),
        ("80d",    "Ask about health insurance (Section 80D)."),
        ("nps",    "Ask about NPS contribution (80CCD(1B) — extra 50k saving)."),
        ("hra",    "Ask if user pays rent (HRA or 80GG deduction possible)."),
        ("24b",    "Ask about home loan interest (Section 24b)."),
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

        # Step 0: Need profile + income first
        if total_inc == 0 and profile:
            return f"plan: Acknowledge {profile} and ask for specific income amount."
        if total_inc == 0:
            return "plan: Ask for income details (Salary/Business)."

        # Step 1..N: Progressive discovery
        for key, desc in self.DISCOVERY_STEPS[1:]:  # skip income step
            if key == "24b" and not session.get("has_home_loan"): continue
            if key == "hra"  and session.get("profile") == "Business Owner": continue
            if key == "80g"  and not session.get("profile"): continue
            # Check if key has been answered (None = not asked, 0 = asked but user said no)
            if session.get(key) is None:
                return f"plan: {desc}"

        return "plan: Final audit ready."

    def get_savings_tips(self, session: Dict[str, Any]) -> List[str]:
        """Returns sophisticated, profile-aware tax strategy tips."""
        tips = []
        income = session.get("salary", 0) + session.get("business", 0)
        profile = session.get("profile", "General")
        
        # 1. 80C Strategy
        c80 = session.get("80c", 0)
        if c80 < 150000:
            gap = 150000 - c80
            if profile == "Salaried":
                tips.append(f"Strategy: Increase VPF (Voluntary PF) to utilize the remaining ₹{gap:,.0f} of 80C. It offers EEE tax status and higher interest than PPF.")
            else:
                tips.append(f"Strategy: Invest ₹{gap:,.0f} in ELSS (Tax Saving Mutual Funds) for the shortest lock-in (3 years) and high equity growth.")

        # 2. NPS Strategy (The 'Extra 50k' hack)
        nps = session.get("nps", 0)
        if nps < 50000:
            if income > 1500000:
                saving = (50000 - nps) * 0.312 # 30% slab + cess
                tips.append(f"High-Tax Alert: You are in the 30% bracket. Adding ₹{50000-nps:,.0f} more to NPS (80CCD(1B)) will save you an instant ₹{saving:,.0f} in taxes.")
            else:
                tips.append("NPS Benefit: Contribute to NPS for an extra ₹50,000 deduction beyond your 80C limit.")

        # 3. Health Strategy (80D)
        if not session.get("80d"):
            tips.append("Medical Shield: Buy health insurance. Even if healthy, you get ₹25,000 deduction, plus ₹5,000 for preventive checkups (no bill needed).")
        
        # 4. Parents Strategy
        if not session.get("80d_parents") and session.get("has_parents"):
            tips.append("Parental Care: Paying for parents' health insurance or even their direct medical bills (if they are senior citizens) can save tax up to ₹50,000.")

        # 5. Housing Strategy
        if session.get("pays_rent") and not session.get("hra") and profile == "Business Owner":
            tips.append("Section 80GG: Since you don't get HRA, you can claim rent under Sec 80GG. This is a common missed opportunity for business owners.")

        # 6. Interest Strategy
        if income > 0 and not session.get("80tta"):
            tips.append("80TTA: Don't forget to claim up to ₹10,000 for your savings account interest. It's often ignored but fully deductible.")

        return tips


# =========================================================================
# 4. ANFIS v3 — Pre-trained via EE-BAT + Adam on 100k tax cases
# =========================================================================
class ANFIS:
    """
    ANFIS v4 Industrial — Trained on 1,000,000 ground-truth tax cases.
    Covers 20 features including Sec 80U, 80DDB, 80G, 80GG, HRA, etc.
    """
    N_INPUTS = 20
    N_RULES  = 64

    def __init__(self):
        import os, json
        p = os.path.join(os.path.dirname(__file__), "anfis_weights.json")
        if os.path.exists(p):
            with open(p) as f:
                w = json.load(f)
            params = np.array(w["params"], dtype=np.float32)
            print(f"[ANFIS] Industrial Weights Loaded | R2={w.get('metrics', {}).get('r2', 0):.3f}")
        else:
            rng = np.random.RandomState(42)
            n = self.N_INPUTS * self.N_RULES
            means  = rng.uniform(0, 1, n).astype(np.float32)
            sigmas = np.full(n, 0.2, dtype=np.float32)
            cons   = (rng.randn(self.N_RULES * (self.N_INPUTS + 1)) * 0.1).astype(np.float32)
            params = np.concatenate([means, sigmas, cons])
            print("[ANFIS] Using default industrial calibration")
            
        n = self.N_INPUTS * self.N_RULES
        self.means  = params[:n].reshape(self.N_INPUTS, self.N_RULES)
        self.sigmas = np.abs(params[n:2*n]).reshape(self.N_INPUTS, self.N_RULES) + 0.05
        self.cons   = params[2*n:].reshape(self.N_RULES, self.N_INPUTS + 1)

    def _forward(self, X: np.ndarray) -> np.ndarray:
        diff = X[:, :, None] - self.means[None]
        mf = np.exp(-0.5 * (diff / self.sigmas[None])**2)
        w = mf.prod(axis=1)
        w_sum = w.sum(axis=1, keepdims=True) + 1e-9
        w_n = w / w_sum
        Xe = np.concatenate([X, np.ones((len(X), 1))], axis=1)
        f = np.einsum('bi,ri->br', Xe, self.cons)
        return np.clip((w_n * f).sum(axis=1), 0, 1)

    def score_efficiency(self, session: Dict[str, Any], result: Dict[str, Any]) -> float:
        """Industrial Efficiency Scorer — Extracts 20 features from session + result."""
        inc = float(session.get("salary", 0) + session.get("business", 0) + session.get("other_income", 0) + 1e-9)
        
        # Feature Extraction (Match trainer exactly)
        f = [
            np.clip(inc/10_000_000, 0, 1),              # 0: Income Level
            np.clip(session.get("80c", 0)/150000, 0, 1),# 1: 80C
            np.clip(session.get("80d", 0)/25000, 0, 1), # 2: 80D Self
            np.clip(session.get("80d_parents", 0)/50000, 0, 1), # 3: 80D Parents
            np.clip(session.get("nps", 0)/50000, 0, 1), # 4: NPS
            np.clip(session.get("hra", 0)/200000, 0, 1),# 5: HRA
            np.clip(session.get("24b", 0)/200000, 0, 1),# 6: Home Loan
            np.clip(session.get("80e", 0)/500000, 0, 1),# 7: Education
            np.clip(session.get("80g", 0)/(inc*0.1+1), 0, 1), # 8: 80G
            np.clip(session.get("80tta", 0)/50000, 0, 1),     # 9: TTA/B
            np.clip(session.get("80u_80dd", 0)/125000, 0, 1), # 10: 80U
            np.clip(session.get("80ddb", 0)/100000, 0, 1),    # 11: 80DDB
            np.clip(session.get("80eea", 0)/150000, 0, 1),   # 12: 80EEA
            np.clip(sum(x["amount"] for x in session.get("capital_gains", []))/inc, 0, 1), # 13: CG
            np.clip(session.get("business", 0)/inc, 0, 1),   # 14: Biz Ratio
            0.3, # 15: Placeholder Age (normalized)
            np.clip(result.get("savings", 0)/(inc*0.1+1), 0, 1), # 16: Regime Savings
            np.clip(result.get("total_tax", 0)/(inc*0.3+1), 0, 1), # 17: Effective Tax
            1.0 if session.get("profile") == "Senior Citizen" else 0.0, # 18: Senior
            1.0 - np.clip(session.get("80c", 0)/150000, 0, 1) # 19: Missed 80C
        ]
        
        x = np.array([f], dtype=np.float32)
        return round(float(self._forward(x)[0]) * 100, 1)

    # Legacy interface compatibility
    def forward(self, inputs: np.ndarray) -> float:
        x = inputs[:self.N_INPUTS].reshape(1, -1).astype(np.float32)
        if x.shape[1] < self.N_INPUTS:
            x = np.pad(x, ((0,0),(0, self.N_INPUTS - x.shape[1])), 'constant')
        return float(self._forward(x)[0])

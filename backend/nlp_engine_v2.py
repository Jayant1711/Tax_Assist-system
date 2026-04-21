import re
import numpy as np
from typing import Dict, Any, List, Optional
from ai_models import ANFIS, EEBatOptimizer, IntentClassifier, ConversationContext

class NLPEngine:
    def __init__(self):
        self.money_pattern = re.compile(r'(?<!80)(?<!24)((?:rs\.?|rupees|inr|₹)?\s*\d+(?:,\d+)*(?:\.\d+)?)\s*(lakhs?|l|lacs?|k|thousand|lpa|pm|crs?|crores?)?\b', re.IGNORECASE)
        self.intent_clf = IntentClassifier()
        self.ctx = ConversationContext()
        self.anfis = ANFIS(n_inputs=3, n_rules=5)
        
        self.semantic_map = {
            "Salaried": ["job", "work", "office", "company", "software", "engineer", "corporate", "salary", "pay", "employee", "it", "developer", "lpa", "package", "earn", "teacher", "professor", "doctor", "nurse", "manager", "clerk", "accountant", "government", "railways", "army", "police", "service"],
            "Business Owner": ["shop", "business", "freelance", "own", "agency", "consultancy", "startup", "trade", "gst", "turnover", "profit", "client", "shopkeeper", "merchant", "trader", "contractor", "freelancer", "consultant", "clinic", "lawyer", "ca", "architect", "store"],
            "Farmer": ["farm", "agri", "land", "crop", "wheat", "rice", "plantation", "agriculture", "farmer", "harvest", "tractor"],
            "80C": ["lic", "ppf", "elss", "school", "tuition", "child", "pension", "provident", "invest", "80c", "epf", "vpf", "life insurance", "tax saving fd", "mutual fund", "nsc", "sukanya"],
            "80D": ["health", "medical", "hospital", "checkup", "policy", "mediclaim", "insurance", "80d", "preventive"],
            "80G": ["donation", "ngo", "charity", "trust", "temple", "pm care", "80g", "relief fund"],
            "24b": ["home loan interest", "24b", "housing loan interest"],
            "80E": ["education loan", "study loan", "80e"],
            "80CCD(1B)": ["nps", "national pension", "80ccd"],
            "HRA": ["hra", "rent paid", "house rent allowance"],
            "House Property": ["rent received", "tenant", "let out", "rental income", "property income"],
            "Other Sources": ["savings interest", "savings account", "dividend", "lottery", "crypto", "side hustle", "fd interest", "other income", "fd"],
            "Capital Gains Property": ["sold property", "sold land", "sold house", "property sale", "real estate sale"],
            "Capital Gains Shares": ["stock", "equity", "bitcoin", "shares", "trading", "gain", "sell", "sold", "capital gains", "ltcg", "stcg", "mutual fund return"]
        }

    def parse_value(self, full_match: str, amount_str: str, multiplier_str: str) -> float:
        try:
            clean_amount = re.sub(r'[^\d.]', '', amount_str)
            if not clean_amount: return 0.0
            amount = float(clean_amount)
            if amount in [80, 24] and not multiplier_str: return 0.0
            if not multiplier_str: return amount
            m = multiplier_str.lower()
            if m in ['lakh', 'lakhs', 'l', 'lac', 'lacs', 'lpa']: return amount * 100000
            if m in ['k', 'thousand']: return amount * 1000
            if m in ['cr', 'crs', 'crore', 'crores']: return amount * 10000000
            if m == 'pm': return amount * 12
            return amount
        except: return 0.0

    def extract_entities(self, text: str) -> Dict[str, float]:
        text_lower = text.lower()
        extracted = {}
        matches = list(self.money_pattern.finditer(text_lower))
        for match in matches:
            val = self.parse_value(match.group(0), match.group(1), match.group(2))
            if val == 0: continue
            start, end = match.span()
            best_cat = None; min_dist = 100
            for cat, keywords in self.semantic_map.items():
                for kw in keywords:
                    for kw_match in re.finditer(r'\b' + re.escape(kw) + r'\b', text_lower):
                        kw_end = kw_match.end(); kw_start = kw_match.start()
                        dist = start - kw_end if kw_end <= start else kw_start - end
                        adjusted_dist = dist if kw_end <= start else dist * 1.5
                        if 0 <= adjusted_dist < min_dist:
                            min_dist = adjusted_dist; best_cat = cat
            if best_cat and min_dist < 60:
                key = self._map_cat_to_key(best_cat)
                if key: extracted[key] = extracted.get(key, 0) + val
            else:
                extracted["unclassified_amount"] = extracted.get("unclassified_amount", 0) + val
        return extracted

    def _map_cat_to_key(self, cat: str) -> str:
        mapping = {
            "Salaried": "salary", "Business Owner": "business", "Farmer": "agriculture", 
            "80C": "80c", "80D": "80d", "80G": "80g", "24b": "24b", "80E": "80e", "80CCD(1B)": "nps",
            "HRA": "hra", "House Property": "rental", "Other Sources": "other_income",
            "Capital Gains Shares": "equity_ltcg", "Capital Gains Property": "property_cg"
        }
        return mapping.get(cat, "")

    def get_friendly_response(self, session: Dict[str, Any], last_msg: str, entities: Dict[str, float]) -> str:
        msg_lower = last_msg.lower()
        is_neg = any(re.search(r'\b' + kw + r'\b', msg_lower) for kw in ["no", "nothing", "none", "na", "skip", "done", "zero", "nope"])
        stack = session.setdefault("state_stack", ["INIT_PROFILE"])
        
        while stack:
            state = stack[-1]
            
            if state == "DISAMBIGUATE":
                if "1" in msg_lower or "salary" in msg_lower: cat = "salary"
                elif "2" in msg_lower or "business" in msg_lower: cat = "business"
                elif "3" in msg_lower or "rent" in msg_lower: cat = "rental"
                elif "4" in msg_lower or "capital" in msg_lower: cat = "equity_ltcg"
                elif "5" in msg_lower or "other" in msg_lower: cat = "other_income"
                else:
                    return f"I see an amount of ₹{session.get('pending_amount', 0)}. Could you clarify its source?\n1. Salary\n2. Business\n3. Rental\n4. Capital Gains\n5. Other Sources\n(Reply with number or name)"
                session[cat] = session.get(cat, 0) + session.pop("pending_amount", 0)
                stack.pop()
                continue
                
            if "unclassified_amount" in entities:
                session["pending_amount"] = entities.pop("unclassified_amount")
                stack.append("DISAMBIGUATE")
                continue

            if state == "INIT_PROFILE":
                if "profile" not in session:
                    profs = [p for p in ["Salaried", "Business Owner", "Farmer"] if any(re.search(r'\b' + kw + r'\b', msg_lower) for kw in self.semantic_map[p])]
                    if profs:
                        session["profile"] = profs[0]
                        stack.pop()
                        stack.append("GATHER_TOTAL_INCOME")
                        return f"Namaste! Great to meet a {session['profile']}. Let's get started. What is your TOTAL annual income across all sources?"
                    return "Namaste! I am Blostem, an advanced CA AI. What is your profession? (e.g., teacher, shopkeeper, engineer, doctor)"
                stack.pop()
                continue

            if state == "GATHER_TOTAL_INCOME":
                if "salary" in entities or "business" in entities:
                    # User skipped total and gave component
                    session["declared_total"] = max(entities.get("salary", 0), entities.get("business", 0)) * 1.5 # guess
                    stack.pop()
                    stack.append("VERIFY_INCOME")
                    continue
                if session.get("pending_amount"):
                    session["declared_total"] = session.pop("pending_amount")
                    stack.pop()
                    stack.append("VERIFY_INCOME")
                    return f"Got it. Total is ₹{session['declared_total']}. Now, let's break it down. How much of this is from your primary profession ({session.get('profile')})?"
                return "What is your TOTAL annual income across all sources? (e.g., '50 lakhs')"

            if state == "VERIFY_INCOME":
                components = sum(session.get(k, 0) for k in ["salary", "business", "rental", "other_income", "equity_ltcg", "property_cg"])
                declared = session.get("declared_total", 0)
                if is_neg or components >= declared:
                    stack.pop()
                    stack.append("GATHER_DEDUCTIONS")
                    return f"Awesome. Total income matches up (₹{components}). Now, let's look at tax-saving expenditures. Any investments in 80C (LIC, PPF), 80D (Health), or HRA?"
                
                remaining = declared - components
                if "property_cg" in entities or session.get("property_cg"):
                    stack.append("CG_PROPERTY_SOURCE")
                    continue
                return f"You mentioned ₹{declared} total, but we have accounted for ₹{components}. Where did the remaining ₹{remaining} come from? (e.g., Business, Rent, Property Sale, Shares, FD Interest?)"
            
            if state == "CG_PROPERTY_SOURCE":
                if "ancestral" in msg_lower or "gift" in msg_lower: session["cg_prop_type"] = "ancestral"
                elif "self" in msg_lower or "bought" in msg_lower or "own" in msg_lower: session["cg_prop_type"] = "self"
                else: return "For the property you sold, was it ancestral/gifted, or did you buy it yourself?"
                stack.pop()
                stack.append("CG_HOLDING_PERIOD")
                continue

            if state == "CG_HOLDING_PERIOD":
                if any(kw in msg_lower for kw in ["year", "month"]):
                    session["cg_holding"] = "long" if "year" in msg_lower and any(int(x) >= 2 for x in re.findall(r'\d+', msg_lower)) else "short"
                    stack.pop()
                    return f"Got it. I've classified this as {'Long' if session['cg_holding']=='long' else 'Short'} Term Capital Gains. Where is the rest of your income from?"
                return "How long did you hold the property before selling? (e.g., '3 years' or '10 months')"

            if state == "GATHER_DEDUCTIONS":
                if is_neg:
                    stack.pop()
                    stack.append("FINAL")
                    return "Okay, I've noted all your deductions. I am ready to generate your comprehensive CA-level tax report."
                return "Any other deductions? Think about 24b (Home Loan Interest), 80E (Education Loan), NPS (80CCD), or Donations (80G)?"

            if state == "FINAL":
                session["phase"] = "FINAL"
                return "Your report is ready. Please view it below."

        return "Processing..."

    def process_message(self, text: str, session: Dict[str, Any]) -> Dict[str, Any]:
        entities = self.extract_entities(text)
        for k, v in entities.items():
            if k == "unclassified_amount" and "state_stack" in session and session["state_stack"][-1] == "GATHER_TOTAL_INCOME":
                session["pending_amount"] = v
            elif k == "unclassified_amount":
                # Let it be handled by DISAMBIGUATE
                pass
            else:
                session[k] = session.get(k, 0) + v
        response = self.get_friendly_response(session, text, entities)
        self.ctx.update(text, response)
        # Hack to set phase for UI
        if session.get("state_stack") and session["state_stack"][-1] == "FINAL": session["phase"] = "FINAL"
        return {"response": response, "session": session}

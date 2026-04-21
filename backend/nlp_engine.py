import re
import numpy as np
from typing import Dict, Any, List, Optional
from ai_models import ANFIS, EEBatOptimizer, IntentClassifier, ConversationContext

class NLPEngine:
    def __init__(self):
        self.money_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*(lakh|l|k|thousand|lpa|pm)?', re.IGNORECASE)
        self.phases = ["PROFILING", "INCOME_MAIN", "INCOME_CG", "INCOME_OTHER", "DEDUCTION_SAVINGS", "DEDUCTION_HEALTH", "DEDUCTION_OTHER", "RECALL", "FINAL"]
        self.intent_clf = IntentClassifier()
        self.ctx = ConversationContext()
        self.anfis = ANFIS(n_inputs=3, n_rules=5)
        self.semantic_map = {
            "Salaried": ["job", "work", "office", "company", "software", "engineer", "corporate", "salary", "pay", "employee", "it", "developer", "lpa", "package", "earn"],
            "Business Owner": ["shop", "business", "freelance", "own", "agency", "consultancy", "startup", "trade", "gst", "turnover", "profit", "client"],
            "Farmer": ["farm", "agri", "land", "crop", "wheat", "rice", "plantation", "agriculture", "farmer", "harvest"],
            "80C": ["lic", "ppf", "elss", "school", "tuition", "child", "pension", "provident", "home loan", "invest", "80c"],
            "80D": ["health", "medical", "hospital", "checkup", "policy", "mediclaim", "insurance", "80d"],
            "80G": ["donation", "ngo", "charity", "trust", "temple", "pm care", "80g"],
            "Capital Gains": ["stock", "equity", "crypto", "bitcoin", "property", "mutual fund", "shares", "trading", "gain", "sell"]
        }

    def parse_value(self, amount_str: str, multiplier_str: str) -> float:
        try:
            amount = float(amount_str)
            if not multiplier_str: return amount
            m = multiplier_str.lower()
            if m in ['lakh', 'l', 'lpa']: return amount * 100000
            if m in ['k', 'thousand']: return amount * 1000
            if m == 'pm': return amount * 12
            return amount
        except: return 0.0

    def extract_entities(self, text: str) -> Dict[str, float]:
        text_lower = text.lower()
        extracted = {}
        matches = list(self.money_pattern.finditer(text_lower))
        
        for match in matches:
            val = self.parse_value(match.group(1), match.group(2))
            start, end = match.span()
            
            # Find the best keyword for this amount
            # Strategy: Favor keywords that appear BEFORE the amount within a reasonable distance
            best_cat = None
            min_dist = 100
            
            for cat, keywords in self.semantic_map.items():
                for kw in keywords:
                    for kw_match in re.finditer(re.escape(kw), text_lower):
                        kw_start = kw_match.start()
                        kw_end = kw_match.end()
                        
                        # Distance check (prefer keywords before the amount)
                        if kw_end <= start:
                            dist = start - kw_end
                        else:
                            dist = (kw_start - end) * 2 # Penalize keywords after the amount
                        
                        if dist >= 0 and dist < min_dist:
                            min_dist = dist
                            best_cat = cat
            
            if best_cat and min_dist < 40:
                key = self._map_cat_to_key(best_cat)
                if key:
                    extracted[key] = val
            elif "unclassified_amount" not in extracted:
                extracted["unclassified_amount"] = val
                
        return extracted

    def _map_cat_to_key(self, cat: str) -> str:
        mapping = {"Salaried": "salary", "Business Owner": "business", "Farmer": "agriculture", "80C": "80c", "80D": "80d", "80G": "80g", "Capital Gains": "equity_ltcg"}
        return mapping.get(cat, "")

    def get_friendly_response(self, session: Dict[str, Any], last_msg: str, entities: Dict[str, float]) -> str:
        phase = session.get("phase", "PROFILING")
        msg_lower = last_msg.lower()
        ack = "I've noted those details. " if entities else ""
        is_negative = any(kw in msg_lower for kw in ["no", "nothing", "none", "na", "skip", "n/a", "done", "next", "that's it"])

        if phase == "PROFILING":
            for profile, keywords in self.semantic_map.items():
                if any(kw in msg_lower for kw in keywords):
                    if profile in ["Salaried", "Business Owner", "Farmer"]:
                        session["profile"] = profile
                        break
            if "profile" in session:
                income = entities.get("salary") or entities.get("business") or entities.get("unclassified_amount")
                if income:
                    session["salary" if session["profile"] == "Salaried" else "business"] = income
                    session["phase"] = "INCOME_CG"
                    return f"{ack}Namaste! Great to meet a {session['profile']}. Since you mentioned your income, did you also have any gains from stocks or property?"
                session["phase"] = "INCOME_MAIN"
                return f"{ack}Namaste! Great to meet a {session['profile']}. Approximately how much did you earn last year?"
            return "Namaste! I am Blostem. Tell me a bit about what you do?"

        if phase == "INCOME_MAIN":
            income = entities.get("unclassified_amount") or entities.get("salary") or entities.get("business")
            if income:
                session["salary" if session.get("profile") == "Salaried" else "business"] = income
                session["phase"] = "INCOME_CG"
                return f"{ack}Understood. And did you have any income from selling shares or property?"
            if is_negative:
                session["phase"] = "INCOME_CG"
                return "No problem. Any capital gains?"
            return "Could you share your approximate annual income?"

        if phase == "INCOME_CG":
            if entities.get("equity_ltcg") or is_negative:
                session["phase"] = "DEDUCTION_SAVINGS"
                return f"{ack}Got it. Now about your savings—have you invested in things like LIC, PPF, or school fees?"
            return "Any gains from stocks or property?"

        if phase == "DEDUCTION_SAVINGS":
            if (entities.get("80c") or session.get("80c")) and (entities.get("80d") or session.get("80d")):
                session["phase"] = "RECALL"
                return f"{ack}Excellent. Lastly, any donations to charity or religious trusts?"
            if entities.get("80c") or is_negative:
                session["phase"] = "DEDUCTION_HEALTH"
                return f"{ack}Helpful! And do you pay for any health insurance?"
            return "Have you made any investments like insurance or school fees?"

        if phase == "DEDUCTION_HEALTH":
            if entities.get("80d") or is_negative:
                session["phase"] = "RECALL"
                return f"{ack}Understood. Lastly, any donations to charity?"
            return "Any health insurance or medical bills?"

        if phase == "RECALL":
            session["phase"] = "FINAL"
            return "I've analyzed your profile. Ready for the report?"

        return "I've prepared your report. You can view it now."

    def process_message(self, text: str, session: Dict[str, Any]) -> Dict[str, Any]:
        features = np.zeros(len(self.intent_clf.categories))
        for i, (cat, kws) in enumerate(self.semantic_map.items()):
            if any(kw in text.lower() for kw in kws):
                features[i % len(features)] += 1
        entities = self.extract_entities(text)
        for k, v in entities.items():
            if k != "unclassified_amount": session[k] = v
        response = self.get_friendly_response(session, text, entities)
        self.ctx.update(text, response)
        return {"response": response, "session": session}

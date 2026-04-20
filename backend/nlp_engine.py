import re
from typing import Dict, Any, List, Optional

class NLPEngine:
    def __init__(self):
        self.money_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*(lakh|l|k|thousand|lpa|pm)?', re.IGNORECASE)
        
        self.phases = ["PROFILING", "INCOME", "EXPENDITURE", "RECALL", "FINAL"]
        
        # Recall suggestions based on profile
        self.recall_logic = {
            "Farmer": [
                "Did you spend on farm improvements or solar pumps? Some states offer specific incentives.",
                "Did you incur any heavy machinery rental or labor costs?"
            ],
            "Business Owner": [
                "Did you remember to include depreciation on office equipment or laptops?",
                "Any business-related travel or utility bills (internet, electricity) that can be deducted?",
                "Did you contribute to any registered NGO? (Section 80G)"
            ],
            "Salaried": [
                "Did you pay for your parents' medical checkups? Even without insurance, ₹5,000 is deductible.",
                "Did you pay rent? If so, did you receive HRA or are you claiming 80GG?",
                "Did you have any children's school tuition fees? This is part of 80C."
            ]
        }

    def parse_value(self, amount_str: str, multiplier_str: str) -> float:
        amount = float(amount_str)
        if not multiplier_str: return amount
        m = multiplier_str.lower()
        if m in ['lakh', 'l', 'lpa']: return amount * 100000
        if m in ['k', 'thousand']: return amount * 1000
        if m == 'pm': return amount * 12
        return amount

    def extract_entities(self, text: str) -> Dict[str, float]:
        text = text.lower()
        extracted = {}
        matches = self.money_pattern.findall(text)
        
        # Mapping keywords to internal keys
        mapping = {
            'salary': 'salary', 'job': 'salary', 'work': 'salary', 'software': 'salary', 'engineer': 'salary', 'developer': 'salary', 'it': 'salary', 'corporate': 'salary',
            'business': 'business', 'shop': 'business', 'freelance': 'business', 'consultant': 'business', 'self': 'business',
            'farm': 'agriculture', 'agri': 'agriculture', 'agriculture': 'agriculture',
            'rent': 'rental', 'equity': 'equity_ltcg', 'crypto': 'capital_gains', 'stock': 'equity_stcg',
            '80c': '80c', 'lic': '80c', 'ppf': '80c', 'elss': '80c', 'school': '80c', 'tuition': '80c',
            '80d': '80d', 'medical': '80d', 'health': '80d', 'parents': '80d_parents',
            'loan': '80e', 'education': '80e',
            'donation': '80g', 'ngo': '80g'
        }
        
        for amount_str, multiplier in matches:
            val = self.parse_value(amount_str, multiplier)
            found_kw = False
            for kw, key in mapping.items():
                if kw in text:
                    extracted[key] = val
                    found_kw = True
                    break
            
            # Default to salary if no keyword but value found in early phases
            if not found_kw and "salary" not in extracted:
                extracted["salary"] = val
                
        return extracted

    def get_response(self, session: Dict[str, Any], last_msg: str, entities: Dict[str, float]) -> str:
        phase = session.get("phase", "PROFILING")
        msg_lower = last_msg.lower()
        
        # Helper to acknowledge what was found
        ack = ""
        if entities:
            found_items = [f"₹{v:,.0f} as {k.replace('_', ' ')}" for k, v in entities.items()]
            ack = f"I've recorded {' and '.join(found_items)}. "

        # Universal 'Skip' or 'Nothing' detection
        is_negative = any(kw in msg_lower for kw in ["no", "nothing", "none", "na", "skip", "n/a", "don't have", "over", "done", "that's it", "nothing else", "no more", "next"])

        if phase == "PROFILING":
            if any(kw in msg_lower for kw in ["salary", "job", "work", "software", "engineer", "developer", "it", "it professional", "doctor", "lawyer", "corporate"]):
                session["profile"] = "Salaried"
            elif any(kw in msg_lower for kw in ["business", "shop", "freelance", "consult", "agency", "owner"]):
                session["profile"] = "Business Owner"
            elif any(kw in msg_lower for kw in ["farm", "agri", "farmer", "agriculture"]):
                session["profile"] = "Farmer"
            
            if "profile" in session:
                session["phase"] = "INCOME"
                return f"{ack}Since you are a {session['profile']}, let's look at your income breakdown. Besides your main source, did you have any Capital Gains, Rental income, or Agriculture income?"
            
            return "I'm sorry, I didn't catch your profession. Are you salaried, a business owner, a freelancer, or a farmer?"

        if phase == "INCOME":
            if entities or is_negative:
                session["phase"] = "EXPENDITURE"
                return f"{ack}Great. Let's move to deductions. Have you spent on Education (80E), Medical insurance (80D), Donations (80G), or standard 80C investments?"
            
            return "Please tell me about your other income sources if any. If none, just say 'nothing else'."

        if phase == "EXPENDITURE":
            if entities or is_negative:
                profile = session.get("profile", "Salaried")
                suggestions = self.recall_logic.get(profile, self.recall_logic["Salaried"])
                import random
                suggestion = random.choice(suggestions)
                session["phase"] = "RECALL"
                return f"{ack}Analysis complete. Based on your profile as a {profile}, {suggestion} Type 'next' to see your final report."
            
            return "Please list your investments (e.g., '1.5L in 80C'). If none, just say 'next'."

        if phase == "RECALL":
            session["phase"] = "FINAL"
            return "I've completed the deep analysis. I've mapped your entire financial profile to the most optimized tax sections. Ready to see the final report?"

        return "I'm ready with your results. Click the report button to see the breakdown."

    def process_message(self, text: str, session: Dict[str, Any]) -> Dict[str, Any]:
        entities = self.extract_entities(text)
        for k, v in entities.items():
            session[k] = v
            
        response = self.get_response(session, text, entities)
        return {
            "response": response,
            "session": session
        }

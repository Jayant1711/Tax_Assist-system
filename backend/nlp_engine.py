"""
NLP Engine v8.0
Fixes: Word-form number support, 19-category attention, session deduplication,
       smarter correction logic, 7-step discovery waterfall, savings tips in reply.
"""

import re
from typing import Dict, Any, List, Optional
from ai_models import SemanticAttention, UniversalParser, ReasoningAgent
from profession_db import classify_profession

class NLPEngine:
    def __init__(self):
        self.parser  = UniversalParser()
        self.attention = SemanticAttention()
        self.agent   = ReasoningAgent()
        self.agent   = ReasoningAgent()

    def process_message(self, text: str, session: Dict[str, Any]) -> Dict[str, Any]:
        # --- /end override ---
        if text.strip().lower() in ("/end", "end", "/done"):
            session["phase"] = "FINAL"
            response = "Override activated. Generating your Tax Report now..."
            if "history" not in session: session["history"] = []
            session["history"].append({"user": text, "ai": response})
            return {"response": response, "session": session}

        text_lower = text.lower()
        sid = session.get("id", "default")

        # --- 1. Profile Detection ---
        detected = classify_profession(text)
        if detected and not session.get("profile"):
            session["profile"] = detected

        # --- 2. Contextual Entity Detection ---
        if any(k in text_lower for k in ["parent", "mom", "dad", "mother", "father", "senior citizen"]):
            session["has_parents"] = True
        if any(k in text_lower for k in ["home loan", "house loan", "mortgage"]):
            session["has_home_loan"] = True
        if any(k in text_lower for k in ["pay rent", "paying rent", "rent to", "rented house"]):
            session["pays_rent"] = True

        # --- 3. Correction Intent Detection ---
        is_correction = any(kw in text_lower for kw in [
            "meant", "correction", "actually", "wrong", "not that", "no it's", "no that"
        ])
        # Avoid triggering correction on generic "no" (loop bug fix)
        bare_no = text_lower.strip() in {"no", "nope", "nahi", "na", "nothing", "none", "never"}

        # --- 4. Sentence-Isolated Extraction ---
        # Split on sentence-ending punctuation and commas (not inside numbers)
        sentences = re.split(r'(?<!\d)[,.;!?](?!\d)', text)
        newly_extracted: List[str] = []

        for sentence in sentences:
            s = sentence.strip()
            if not s: continue
            matches = self.parser.parse(s)
            for m in matches:
                val = m["val"]

                best_cat = self.attention.resolve_category(s, m["start"], m["end"], session.get("profile"))

                # Context-Carry: If agent just asked about a deduction and user replies with bare number,
                # inherit the asked category instead of defaulting to profile bias.
                last_q = session.get("_last_question", "").lower()
                if best_cat in ("salary", "other_income", "business") and last_q:
                    if any(k in last_q for k in ["80c", "ppf", "lic", "elss", "investment"]):
                        best_cat = "80c"
                    elif any(k in last_q for k in ["health", "insurance", "80d", "mediclaim"]):
                        best_cat = "80d"
                    elif any(k in last_q for k in ["nps", "pension", "80ccd"]):
                        best_cat = "nps"
                    elif any(k in last_q for k in ["home loan", "24b", "interest"]):
                        best_cat = "24b"
                    elif any(k in last_q for k in ["donation", "80g", "charity"]):
                        best_cat = "80g"

                # Correction logic: remove from other_income if re-categorizing
                if is_correction and best_cat not in ("other_income", "salary"):
                    oi = session.get("other_income", 0)
                    if isinstance(oi, (int, float)) and oi >= val:
                        session["other_income"] = max(0, oi - val)

                # Capital Gains: stored as list
                if best_cat == "capital_gains":
                    if not isinstance(session.get("capital_gains"), list):
                        session["capital_gains"] = []
                    cg_type = "equity_ltcg" if any(x in text_lower for x in ["shares","stocks","equity","mutual fund"]) else "property_cg"
                    session["capital_gains"].append({"type": cg_type, "amount": val, "holding": "unknown"})
                else:
                    session[best_cat] = round(session.get(best_cat, 0) + val, 2) if isinstance(session.get(best_cat, 0), (int, float)) else val

                label = best_cat.replace("_", " ").upper()
                newly_extracted.append(f"{label}: ₹{val:,.0f}")

        # --- 5. Agent Reasoning ---
        decision = self.agent.decide_next_step(session)
        plan = decision.split("plan: ")[-1]

        # Update Phase for UI Stepper
        if "Final" in plan:
            session["phase"] = "FINAL"
        elif any(k in plan for k in ["Section 80", "NPS", "rent", "interest", "donations"]):
            session["phase"] = "EXPENDITURE"
        elif "income" in plan:
            session["phase"] = "INCOME"
        else:
            session["phase"] = "PROFILING"

        # --- 6. Response ---
        response = self._generate_reply(session, newly_extracted, plan, text_lower, bare_no)
        session["_last_question"] = response  # Track for context-carry on next turn
        
        # Track history for debugging/storage
        if "history" not in session: session["history"] = []
        session["history"].append({"user": text, "ai": response})
        
        return {"response": response, "session": session}

    def _generate_reply(self, session: Dict, found: List[str], plan: str,
                        text_lower: str, bare_no: bool) -> str:
        # Acknowledgement
        ack = f"Got it! I've mapped: {', '.join(found)}. " if found else ""

        if "Acknowledge" in plan and not found:
            return f"I've noted you are a {session['profile']}. What is your annual income from this?"

        if "specific income amount" in plan:
            return ack + f"What is your total annual {session['profile']} income?"

        if "income details" in plan:
            return ack + "To start your tax audit, tell me your profession and annual income."

        if "80C" in plan:
            return ack + ("Great progress! Now, have you made any tax-saving investments this year? "
                          "(PPF, LIC, ELSS, EPF, or child's tuition fees — Section 80C, up to ₹1.5L)")

        if "80D" in plan:
            return ack + ("Do you have health insurance for yourself or family? "
                          "(Section 80D — ₹25,000 for self, ₹50,000 if senior)")

        if "NPS" in plan:
            return ack + ("Have you contributed to NPS (National Pension System)? "
                          "It gives an extra ₹50,000 deduction under Section 80CCD(1B), beyond your 80C limit!")

        if "HRA" in plan:
            return ack + ("Do you pay rent for your house? "
                          "If yes, you may be eligible for HRA exemption or Section 80GG deduction.")

        if "home loan interest" in plan:
            return ack + ("What is the total home loan interest you paid this year? "
                          "(Section 24b — up to ₹2 Lakh deductible)")

        if "donations" in plan:
            return ack + ("Have you made any donations to charity, PM fund, or NGOs? "
                          "(Section 80G — 50% to 100% deductible)")

        if "Final audit ready" in plan:
            session["phase"] = "FINAL"
            tips = self.agent.get_savings_tips(session)
            tip_text = (" Quick tip: " + tips[0]) if tips else ""
            return ack + f"All data collected! Generating your Tax Optimization Report...{tip_text}"

        # Handle bare "no" — mark current step as answered (sentinel=0), advance
        if bare_no:
            income_keys = ["salary", "business", "rental", "other_income"]
            has_income = any(session.get(k, 0) > 0 for k in income_keys)
            if has_income:
                # Mark next unanswered step with 0 so agent moves forward
                for key in ["80c", "80d", "nps", "hra", "80g"]:
                    if session.get(key) is None:
                        session[key] = 0
                        break
                # Re-run agent
                decision2 = self.agent.decide_next_step(session)
                plan2 = decision2.split("plan: ")[-1]
                return self._generate_reply(session, [], plan2, text_lower, False)

        return ack + "Anything else? (e.g. home loan, NPS, donations, property sale, education loan)"

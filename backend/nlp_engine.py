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

    def _get_asked_cat(self, last_q: str, profile: Optional[str] = None) -> Optional[str]:
        if not last_q: return None
        lq = last_q.lower()
        if any(k in lq for k in ["salary", "income", "earn"]): 
            return "business" if profile == "Business Owner" else "salary"
        if any(k in lq for k in ["80c", "ppf", "lic", "elss", "investment", "saving"]): return "80c"
        if any(k in lq for k in ["health", "insurance", "80d", "medical"]): return "80d"
        if any(k in lq for k in ["nps", "pension", "80ccd"]): return "nps"
        if any(k in lq for k in ["home loan", "24b", "interest"]): return "24b"
        if any(k in lq for k in ["rent", "hra", "80gg"]): return "hra"
        if any(k in lq for k in ["donation", "charity", "ngo", "gift"]): return "80g"
        return None

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
            "meant", "correction", "actually", "wrong", "not that", "no it's", "no that",
            "revise", "update", "miscalculated", "oops", "instead of", "not", "change", "mistake"
        ])
        # Avoid triggering correction on generic "no" (loop bug fix)
        bare_no = text_lower.strip() in {"no", "nope", "nahi", "na", "nothing", "none", "never"}

        # --- 4. Sentence-Isolated Extraction ---
        sentences = re.split(r'(?<!\d)[,.;!?](?!\d)', text)
        newly_extracted: List[str] = []
        already_mapped_this_turn = set()

        for sentence in sentences:
            s = sentence.strip()
            if not s: continue
            
            # --- 4a. Zero-Sentinel (The Loop Breaker) ---
            # Catch negative intent to prevent conversational loops
            is_zero = any(z in s.lower() for z in [" 0", "nil", "none", "nothing", "zero", "skip", "no nps", "no investment", "don't have", "not paying"])
            if is_zero:
                asked_cat = self._get_asked_cat(session.get("_last_question", ""), session.get("profile"))
                if asked_cat and session.get(asked_cat) is None:
                    session[asked_cat] = 0
                    newly_extracted.append(f"{asked_cat.upper()}: Noted (None)")
                    continue

            matches = self.parser.parse(s)
            for m in matches:
                val = m["val"]

                # --- 4b. Probabilistic Category Resolution ---
                full_last_q = session.get("_last_question", "").lower()
                asked_cat = self._get_asked_cat(full_last_q, session.get("profile"))
                best_cat = self.attention.resolve_category(s, m["start"], m["end"], session.get("profile"), asked_cat)

                # Correction logic
                if is_correction and best_cat not in ("other_income", "salary"):
                    for suspect in ["nps", "80c", "80g", "hra", "other_income"]:
                        if suspect == best_cat: continue
                        prev_val = session.get(suspect, 0)
                        if isinstance(prev_val, (int, float)) and prev_val >= val:
                            session[suspect] = max(0, prev_val - val)
                            break 

                # --- 4c. Unit Conversion ---
                label = best_cat.replace("_", " ").upper()
                if any(m in s.lower() for m in ["monthly", "per month", "p.m", "pm", "every month"]):
                    val *= 12
                    label += " (ANNUALIZED)"

                # --- 4d. Assignment Logic (Intra-Turn Addition) ---
                OVERWRITE_CATS = ["salary", "business", "rental", "other_income", "age"]
                
                if best_cat == "capital_gains":
                    if not isinstance(session.get("capital_gains"), list):
                        session["capital_gains"] = []
                    cg_type = "equity_ltcg" if any(x in text_lower for x in ["shares","stocks","equity","mutual fund"]) else "property_cg"
                    session["capital_gains"].append({"type": cg_type, "amount": val, "holding": "unknown"})
                elif best_cat in OVERWRITE_CATS and not is_correction:
                    if best_cat in already_mapped_this_turn:
                        session[best_cat] = round(session.get(best_cat, 0) + val, 2)
                    else:
                        session[best_cat] = val
                        already_mapped_this_turn.add(best_cat)
                else:
                    session[best_cat] = round(session.get(best_cat, 0) + val, 2) if isinstance(session.get(best_cat, 0), (int, float)) else val

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
        
        return {"response": response, "session": session, "extracted": newly_extracted, "plan": plan}

    def _generate_reply(self, session: Dict, found: List[str], plan: str,
                        text_lower: str, bare_no: bool) -> str:
        # Handle bare "no" — mark current step as answered (sentinel=0), advance
        if bare_no:
            income_keys = ["salary", "business", "rental", "other_income"]
            has_income = any(session.get(k, 0) > 0 for k in income_keys)
            if has_income:
                # Mark next unanswered step with 0 so agent moves forward
                for key in ["80c", "80d", "nps", "hra", "24b", "80g"]:
                    if session.get(key) is None:
                        session[key] = 0
                        break
                # Re-run agent
                decision2 = self.agent.decide_next_step(session)
                plan2 = decision2.split("plan: ")[-1]
                return self._generate_reply(session, [], plan2, text_lower, False)

    def _group_found(self, found: List[str]) -> str:
        if not found: return ""
        groups = {}
        for f in found:
            if ":" in f:
                cat, val_str = f.split(":", 1)
                val = float(val_str.replace("₹", "").replace(",", ""))
                groups[cat] = groups.get(cat, 0) + val
        
        if not groups: return f"Got it! Processed {len(found)} items. "
        
        summary = ", ".join([f"{cat}: ₹{amt:,.0f}" for cat, amt in groups.items()])
        return f"Successfully mapped {summary}. "

    def _generate_reply(self, session: Dict, found: List[str], plan: str,
                        text_lower: str, bare_no: bool) -> str:
        # Acknowledgement
        ack = self._group_found(found)

        if "Acknowledge" in plan and not found:
            return f"I've noted you are a {session['profile']}. What is your annual income from this?"

        if "specific income amount" in plan:
            return ack + f"What is your total annual {session['profile']} income?"

        if "income details" in plan:
            return ack + "To start your tax audit, tell me your profession and annual income."

        if re.search(r'\b80C\b', plan):
            return ack + ("Great progress! Now, have you made any tax-saving investments this year? "
                          "(PPF, LIC, ELSS, EPF, or child's tuition fees — Section 80C, up to ₹1.5L)")

        if re.search(r'\b80D\b', plan):
            return ack + ("Do you have health insurance for yourself or family? "
                          "(Section 80D — ₹25,000 for self, ₹50,000 if senior)")

        if "NPS" in plan or "80CCD" in plan:
            return ack + ("Have you contributed to NPS (National Pension System)? "
                          "It gives an extra ₹50,000 deduction under Section 80CCD(1B), beyond your 80C limit!")

        if "HRA" in plan or "rent" in plan:
            return ack + ("Do you pay rent for your house? "
                          "If yes, you may be eligible for HRA exemption or Section 80GG deduction.")

        if "home loan interest" in plan or "24b" in plan:
            return ack + ("What is the total home loan interest you paid this year? "
                          "(Section 24b — up to ₹2 Lakh deductible)")

        if re.search(r'\b80G\b', plan):
            return ack + ("Have you made any donations to charity, PM fund, or NGOs? "
                          "(Section 80G — 50% to 100% deductible)")

        if "Final audit ready" in plan:
            session["phase"] = "FINAL"
            tips = self.agent.get_savings_tips(session)
            tip_text = (" Quick tip: " + tips[0]) if tips else ""
            return ack + f"All data collected! Generating your Tax Optimization Report...{tip_text}"

        return ack + "Anything else? (e.g. home loan, NPS, donations, property sale, education loan)"

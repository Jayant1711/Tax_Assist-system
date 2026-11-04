# Summer internship project
"""Response Composer — Sprint 4 P2 (docs/sprint4-execution.md §P2).

Replaces `_generate_reply`'s canned strings with a deterministic,
data-aware reply layer. Design contract:

- **Pure prose layer.** The discovery state machine (which slot is asked
  next, phase transitions, zero-sentinel semantics) stays in
  `nlp_engine.py` / `ReasoningAgent`; this module only phrases what the
  machine decided. No session mutation happens here except none at all.
- **Deterministic.** Variant rotation is indexed by the session's own
  turn count (`len(history)`) — same state ⇒ same reply, no randomness
  in the request path (ADR-003).
- **Data-aware.** Every acknowledgment cites the booked categories with
  en-IN formatted amounts (₹12,00,000, the Indian grouping the audience
  uses) and every ask-back names the slot it is filling.
- **Advisory weaving.** At most ONE advisory per reply, highest priority
  first: CG transfer-date election, 80G donee-category rule, 80C/NPS/80D
  headroom, 87A rebate-band position. Each advisory cites its statutory
  basis (section numbers from docs/tax-verification.md — never invented).
- **Confidence-aware.** Categories the resolver booked via the
  profile-default fall-through (`is_default=True`) are surfaced with an
  explicit "tentative — correct me" line, never silently.
- **Never re-asks.** The caller derives the ask kind from the agent's
  plan, which already skips booked slots.

ADR-001 boundary: this module formats; it never computes tax numbers.
The only arithmetic is presentation headroom (limit − booked), which is
display copy, not a tax computation.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Statutory constants (display copy; sources in docs/tax-verification.md)
# ---------------------------------------------------------------------------
LIMIT_80C = 150_000          # Section 80C(1) — ₹1.5 lakh
LIMIT_NPS = 50_000           # Section 80CCD(1B) — extra ₹50k
LIMIT_80D_SELF = 25_000      # Section 80D — self/family
REBATE_BAND_NEW = 1_200_000  # Section 87A new regime — nil tax up to ₹12L
REBATE_WINDOW = 50_000       # band-position note only when within ±₹50k

# 80G donee-category display copy (categories from the engine's table)
_80G_CATEGORY_NOTES = {
    "cat_100_no_limit": (
        "100% deductible with no qualifying limit (Section 80G(2)(b))"),
    "cat_100_qualifying_limit": (
        "100% deductible, subject to the 10%-of-adjusted-GTI qualifying "
        "limit (Section 80G(2)(a))"),
    "cat_50_no_limit": (
        "50% deductible with no qualifying limit (Section 80G(2)(b))"),
    "cat_50_qualifying_limit": (
        "50% deductible, subject to the 10%-of-adjusted-GTI qualifying "
        "limit (Section 80G(2)(a))"),
}

# ---------------------------------------------------------------------------
# Phrasing pools — >=3 variants per ask kind. Rotation index = turn count.
# Anchors (section emoji + bolded slot name) stay stable across variants so
# the UI highlight and the asked-category prior keep working.
# ---------------------------------------------------------------------------
ASK_VARIANTS: Dict[str, List[str]] = {
    "income": [
        ("What is your total annual income from {profile}? "
         "_(e.g. '12 lakh per year' or '1.5 crore')_"),
        ("How much do you earn annually from {profile}? "
         "_(say it naturally — '8.5L', '45k monthly', '2.5 crore')_"),
        ("Please share your yearly {profile} income — "
         "_(any format: '12 lakhs', '1,25,000 monthly', '80k pm')_"),
    ],
    "80c": [
        ("💰 **Section 80C** — Have you made any tax-saving investments this year? "
         "_(PPF, LIC premium, ELSS mutual funds, EPF, or children's tuition fees "
         "— up to ₹1.5 Lakh)_"),
        ("💰 **Section 80C** — Any investments to declare — PPF, ELSS, LIC, EPF "
         "or school fees? _(together these can claim up to ₹1.5 Lakh)_"),
        ("💰 **Section 80C** — Have you put money into PPF, ELSS, LIC premium, "
         "EPF or tuition fees this year? _(the combined 80C cap is ₹1.5 Lakh)_"),
    ],
    "80d": [
        ("🏥 **Health Insurance (Section 80D)** — Do you pay health insurance "
         "premiums for yourself or your family? "
         "_(₹25,000 for self/family; ₹50,000 if parents are senior citizens)_"),
        ("🏥 **Section 80D** — Any medical insurance premium — for you or your "
         "family? _(₹25,000 self/family, ₹50,000 for senior-citizen parents)_"),
        ("🏥 **Health cover check (80D)** — Do you pay a mediclaim or health "
         "premium? _(self/family ₹25,000; parents ₹50,000 if senior citizens)_"),
    ],
    "nps": [
        ("🎯 **NPS Bonus Deduction** — Have you contributed to NPS (National "
         "Pension System)? It gives an **extra ₹50,000** deduction under "
         "Section 80CCD(1B), completely separate from your 80C limit!"),
        ("🎯 **NPS (80CCD(1B))** — Any National Pension System contribution "
         "this year? It unlocks an **additional ₹50,000** deduction over and "
         "above 80C."),
        ("🎯 **Retirement savings** — Did you put anything into NPS Tier-1? "
         "Section 80CCD(1B) allows an **extra ₹50,000** deduction on top of "
         "your 80C investments."),
    ],
    "hra": [
        ("🏠 **Rent & HRA** — What is your **monthly rent**, your **monthly "
         "HRA received**, and do you live in a **metro city** "
         "(Delhi / Mumbai / Kolkata / Chennai)? _(HRA exemption if salaried, "
         "Section 80GG if not — until a metro city is confirmed, the "
         "non-metro 40% assumption applies)_"),
        ("🏠 **Living situation** — Please share your **monthly rent**, "
         "**HRA received per month**, and whether your city is a **metro**. "
         "_(Rule 2A needs all three; non-metro 40% applies until confirmed)_"),
        ("🏠 **Rent & HRA (Rule 2A)** — Three quick inputs: monthly **rent "
         "paid**, monthly **HRA received**, and **metro city?** "
         "_(metro = Delhi/Mumbai/Kolkata/Chennai; else the 40% assumption)_"),
    ],
    "24b": [
        ("🏦 **Home Loan Interest (Section 24b)** — What is the total home "
         "loan **interest** you paid this year? "
         "_(Up to ₹2 Lakh is deductible for self-occupied property)_"),
        ("🏦 **Section 24(b)** — How much **interest** did you pay on your "
         "home loan this year? _(self-occupied: up to ₹2 Lakh deductible)_"),
        ("🏦 **Home loan** — Share the **interest component** of your housing "
         "loan EMI for the year. _(Section 24b caps it at ₹2 Lakh for a "
         "self-occupied house)_"),
    ],
    "80g": [
        ("🤝 **Charitable Donations (Section 80G)** — Have you donated to any "
         "charity, PM Relief Fund, or NGO this year? "
         "_(50% to 100% of donations are deductible)_"),
        ("🤝 **Section 80G** — Any charitable giving this year — relief "
         "funds, NGOs, temples, trusts? _(deduction varies by donee: 50-100%)_"),
        ("🤝 **Donations** — Did you donate to any registered charity or "
         "relief fund? _(Section 80G: 50% to 100% deductible by donee "
         "category)_"),
    ],
    "open": [
        ("Anything else to add? _(e.g. home loan interest, NPS, donations, "
         "property sale, education loan, rental income)_"),
        ("Anything more to declare? _(rent, HRA, home-loan interest, NPS, "
         "donations, capital gains…)"),
        ("Would you like to add anything — deductions, other income, or "
         "capital gains?"),
    ],
    "fresh": [
        ("No worries! Let's start fresh. 😊 What is your profession and "
         "annual income?"),
        ("That's okay — we can begin again. 🙌 Tell me what you do and your "
         "yearly income."),
        ("Sure — clean slate. What's your line of work and annual income?"),
    ],
}

WELCOME_VARIANTS = [
    ("Welcome! 🙏 I'm your AI Tax Consultant for {year}. Tell me your "
     "**profession** and **annual income** to begin. "
     "_(e.g. 'I'm a software engineer earning 18 LPA')_"),
    ("Namaste! 🙏 I help with Indian income tax for {year}. What do you do, "
     "and what did you earn? _(e.g. 'shop owner, 40 lakhs turnover')_"),
    ("Hi there! 🙏 I'm your tax consultant for {year}. Start with your "
     "**profession** and **annual income**. _(e.g. 'freelancer earning 12L')_"),
]

PROFILE_ACK_VARIANTS = [
    ("Noted — you're a **{profile}**! 👍 What is your total annual income "
     "from this? _(e.g. '12 lakhs', '8.5L', '2.5 crore')_"),
    ("Got it — **{profile}** it is. 👍 How much do you earn annually from "
     "this? _(any format works)_"),
    ("**{profile}** — noted. 👍 What's your yearly income from this work? "
     "_(e.g. '9 lakhs', '75k monthly')_"),
]

CLOSING_VARIANTS = [
    "✨ **All data collected!** Generating your complete Tax Optimization "
    "Report now…",
    "✨ That's everything I need! Building your Tax Optimization Report…",
    "✨ Discovery complete — preparing your Tax Optimization Report…",
]

# Category display verbs for the acknowledgment line
_CATEGORY_VERBS = {
    "salary": "annual salary",
    "business": "business income",
    "rental": "rental income",
    "other_income": "other income",
    "agriculture": "agricultural income",
    "capital_gains": "capital gains",
    "80c": "80C investments",
    "80d": "80D health premium",
    "80d_parents": "80D parents' premium",
    "80e": "80E education-loan interest",
    "80g": "80G donation",
    "nps": "NPS contribution",
    "hra_received": "HRA received",
    "rent_paid": "rent paid",
    "24b": "home-loan interest",
    "80tta": "80TTA savings interest",
    "80ttb": "80TTB senior interest",
    "80gg": "80GG rent",
    "80u_80dd": "80U/80DD disability",
    "80ddb": "80DDB treatment",
}


def format_inr(amount) -> str:
    """en-IN digit grouping: 1200000 -> '12,00,000' (never a locale dep).
    Sign-safe: the minus sign is carried outside the grouping."""
    value = float(amount)
    sign = "-" if value < 0 else ""
    s = str(int(round(abs(value))))
    if len(s) <= 3:
        return sign + s
    head, tail = s[:-3], s[-3:]
    groups: List[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + ",".join(groups + [tail])


def _pick(pool: List[str], turn_index: int) -> str:
    """Deterministic rotation — no randomness in the request path."""
    return pool[turn_index % len(pool)]


class ResponseComposer:
    """Stateless phrasing layer; all methods are pure (except none)."""

    def __init__(self, tax_year_label: str = "FY 2025-26"):
        self.year = tax_year_label

    # -- acknowledgment ----------------------------------------------------
    def ack(self, found: List[str]) -> str:
        """Data-aware acknowledgment of THIS turn's bookings.

        Mirrors the engine's `_group_found` grouping (same parse, so the
        wire format of `found` stays the contract) but formats amounts
        en-IN and appends the category's display verb.
        """
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
                except ValueError:
                    continue
                groups[cat.strip()] = groups.get(cat.strip(), 0) + val
        if not groups:
            # qa finding: never claim an amount was mapped when the parse
            # dropped it — the engine's found format is fixed, so this is
            # a defensive path; word it neutrally.
            return "Got it — reviewing the details you shared. "
        parts = []
        for cat, amt in groups.items():
            verb = _CATEGORY_VERBS.get(cat.lower())
            amt_s = format_inr(amt)
            parts.append(f"{cat}: ₹{amt_s}" +
                         (f" ({verb})" if verb else ""))
        return "✅ Mapped — " + ", ".join(parts) + ". "

    # -- confidence --------------------------------------------------------
    def confidence_line(self, default_cats: Optional[List[str]]) -> str:
        """Surface profile-default guesses as tentative (spec P2 #7)."""
        if not default_cats:
            return ""
        cats = ", ".join(sorted({c.upper() for c in default_cats}))
        return ("_(Tentative: I've assumed the **{0}** figure from context — "
                "tell me what it really is and I'll re-book it.)_").format(cats)

    # -- advisory weaving (max ONE per reply) -------------------------------
    def advisory(self, session: Dict) -> str:
        cg_flag = session.get("cg_transfer_before_2024_07_23")
        if cg_flag is True:
            return ("📅 **Capital-gains note**: the transfer was before "
                    "23-Jul-2024, so the older indexed-rates election may "
                    "apply (Schedule CG R-e disclosure) — the report flags it.")
        g80 = session.get("80g_category")
        if g80 and session.get("80g"):
            note = _80G_CATEGORY_NOTES.get(g80)
            if note:
                return f"🤝 **80G rule**: this donation is {note}."
        c80 = float(session.get("80c") or 0)
        if 0 < c80 < LIMIT_80C:
            return (f"💡 You've used ₹{format_inr(c80)} of your ₹1,50,000 "
                    f"80C limit — ₹{format_inr(LIMIT_80C - c80)} headroom "
                    f"remains (Section 80C(1)).")
        nps = float(session.get("nps") or 0)
        if 0 < nps < LIMIT_NPS:
            return (f"💡 NPS headroom: ₹{format_inr(LIMIT_NPS - nps)} of the "
                    f"extra ₹50,000 under Section 80CCD(1B) is still unused.")
        d80 = float(session.get("80d") or 0)
        if 0 < d80 < LIMIT_80D_SELF:
            return (f"💡 80D headroom: ₹{format_inr(LIMIT_80D_SELF - d80)} "
                    f"of the ₹25,000 self/family limit is unused.")
        gross = sum(float(session.get(k) or 0)
                    for k in ("salary", "business", "rental",
                              "other_income", "agriculture"))
        if gross and abs(gross - REBATE_BAND_NEW) <= REBATE_WINDOW:
            if gross == REBATE_BAND_NEW:
                return ("💡 You're exactly AT the ₹12 lakh Section 87A "
                        "rebate band (new regime) — the nil-tax position "
                        "holds, but any additional taxable income breaks it.")
            if gross < REBATE_BAND_NEW:
                return (f"💡 You're ₹{format_inr(REBATE_BAND_NEW - gross)} "
                        f"below the ₹12 lakh Section 87A rebate band "
                        f"(new regime) — careful before booking more taxable "
                        f"income near this line.")
            return (f"💡 You're ₹{format_inr(gross - REBATE_BAND_NEW)} above "
                    f"the ₹12 lakh Section 87A rebate band (new regime) — "
                    f"deductions may not restore the nil-tax position.")
        return ""

    # -- ask-backs ----------------------------------------------------------
    def ask(self, kind: str, turn_index: int, profile: str = "work") -> str:
        if kind == "income":
            return _pick(ASK_VARIANTS["income"], turn_index).format(
                profile=profile)
        if kind == "welcome":
            return _pick(WELCOME_VARIANTS, turn_index).format(year=self.year)
        if kind == "profile-ack":
            return _pick(PROFILE_ACK_VARIANTS, turn_index).format(
                profile=profile)
        if kind == "fresh":
            return _pick(ASK_VARIANTS["fresh"], turn_index)
        if kind == "closing":
            return _pick(CLOSING_VARIANTS, turn_index)
        pool = ASK_VARIANTS.get(kind)
        if pool is None:
            raise KeyError(f"unknown ask kind: {kind}")
        return _pick(pool, turn_index)

    def turn_index(self, session: Dict) -> int:
        """Deterministic rotation source: the session's own turn count."""
        history = session.get("history")
        return len(history) if isinstance(history, list) else 0


#: Module-level singleton — the engine holds no per-request state here.
default_composer = ResponseComposer()

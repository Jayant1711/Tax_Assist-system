# backend/fuzzy_ca.py — Sprint 7 X2: the explainable CA layer
"""A readable fuzzy rule base that captures how a chartered accountant
thinks about savings opportunities.

Design intent (the paper's Section VIII, made real):
- The rule base is AUTHORED, not trained. Every rule is data a human
  can read, decode, and argue with — explainable by construction.
- Rules fire over graded conditions ("income is mid", "80C headroom is
  large") computed by trapezoid membership functions with explicit
  breakpoints. Nothing here is learned, so there is nothing opaque.
- The layer NEVER computes rupees. It reads session features, fires
  sentences, and hands the levers it suggested to the pricing layer
  (ca_plans.py), where the deterministic engine prices every plan.
  This is the division of labor the TSK falsification taught us: the
  calculator prices; the fuzzy layer reasons, in readable form.

Public surface:
- explain(session) -> list of fired-rule notes (id, sentence, strength)
- render_rulebook() -> the entire rule base decoded into sentences
- levers(session)    -> suggested lever heads (for the plan proposer)
"""
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# trapezoid membership — (a, b, c, d): 0 below a, 1 on [b, c], 0 above d
# ---------------------------------------------------------------------------

def _trap(x: float, a: float, b: float, c: float, d: float) -> float:
    """Trapezoid with the closed-shoulder convention: x in [b, c] is a
    full member, including the a==b (x=0 means 'fresh/empty') and
    c==d (saturated) edges."""
    if x < a or x > d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if x < b:
        return 1.0 if a == b else (x - a) / (b - a)
    return 1.0 if c == d else (d - x) / (d - c)


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# linguistic sets over session features (all breakpoints explicit)
# ---------------------------------------------------------------------------

# income in lakhs (salary + business + rental + other + agriculture —
# a GROSS proxy; agricultural income is exempt u/s 10(1) so the
# rebate-band rules can overstate for material agri income)
INCOME = {
    "low":  (0.0, 0.0, 12.0, 16.0),
    "mid":  (8.0, 12.0, 25.0, 40.0),
    "high": (25.0, 40.0, 1e9, 1e9),
}

# utilization of a section's statutory cap (0..1)
UTIL = {
    "fresh":   (0.0, 0.0, 0.05, 0.25),
    "partial": (0.05, 0.3, 0.6, 0.85),
    "maxed":   (0.8, 0.95, 1.01, 1.01),
}

# headroom in lakhs (cap minus booked)
HEADROOM = {
    "none":  (0.0, 0.0, 0.02, 0.1),
    "some":  (0.05, 0.2, 0.6, 1.2),
    "large": (0.8, 1.5, 1e9, 1e9),
}

SECTION_LABEL = {
    "80c": "Section 80C (investments, Rs 1.5 lakh cap)",
    "80d": "Section 80D (health insurance)",
    "80d_parents": "Section 80D (parents' cover)",
    "nps": "Section 80CCD(1B) (NPS, Rs 50,000 cap)",
    "80e": "Section 80E (education-loan interest)",
    "80g": "Section 80G (donations)",
    "80tta": "Section 80TTA (savings interest)",
    "80ttb": "Section 80TTB (senior deposits interest)",
    "80u_80dd": "Section 80U/80DD (disability)",
    "80ddb": "Section 80DDB (specified ailments)",
    "80eea": "Section 80EEA (affordable housing interest)",
    "24b": "Section 24(b) (home-loan interest)",
    "hra": "HRA exemption (Rule 2A)",
}

# fallback caps the feature builder uses when the caller does not supply
# a limits dict. 80e/80g are PSEUDO-CAPS for headroom bookkeeping only —
# 80E has no monetary cap (8-assessment-year window) and 80G is
# rate-per-donee with a qualifying limit; see ca_plans.CAP_TEXT.
# Must stay in sync with tax_intelligence.LIMITS (pinned by a test).
FALLBACK_LIMITS: Dict[str, float] = {
    "80c": 150_000, "80d": 25_000, "80d_parents": 25_000,
    "nps": 50_000, "24b": 200_000, "80g": 100_000, "80e": 500_000,
    "80tta": 10_000, "80ttb": 50_000,
}

# booked-amount sets (for no-cap sections where headroom is meaningless:
# 80E is relevant only if an education loan actually exists)
BOOKED = {
    "none": (0.0, 0.0, 0.02, 0.1),
    "some": (0.1, 0.3, 1e9, 1e9),
}


def _income_l(session: Dict[str, Any]) -> float:
    total = sum(float(session.get(k) or 0)
                for k in ("salary", "business", "rental", "other_income",
                          "agriculture"))
    return total / 100_000.0


def _utilization(session: Dict[str, Any], head: str, limit: float) -> float:
    booked = float(session.get(head) or 0)
    return _clip01(booked / limit) if limit > 0 else 1.0


def _features(session: Dict[str, Any],
              limits: Dict[str, float]) -> Dict[str, Any]:
    """Raw features the rule conditions read. Derived ONLY from the
    session dict — no engine calls, no rupee math. Features are built
    for the UNION of the caller's limits and the module's defaults, so
    every rule condition resolves regardless of what the caller passed."""
    income_l = _income_l(session)
    feats: Dict[str, Any] = {"income_l": income_l}
    merged: Dict[str, float] = dict(FALLBACK_LIMITS)
    for head, limit in (limits or {}).items():
        merged[head] = limit
    for head, limit in merged.items():
        booked = float(session.get(head) or 0)
        feats[f"util_{head}"] = _utilization(session, head, limit)
        feats[f"headroom_{head}"] = max(0.0, limit - booked) / 100_000.0
        feats[f"booked_{head}"] = booked / 100_000.0
    feats["rent_paid_l"] = float(session.get("rent_paid") or 0) / 100_000.0
    feats["senior"] = 1.0 if (session.get("age") or 0) >= 60 else 0.0
    return feats


def _mu(table: Dict[str, Tuple[float, ...]], set_name: str,
        x: float) -> float:
    return _clip01(_trap(x, *table[set_name]))


# ---------------------------------------------------------------------------
# the rule base — every rule is authored data, readable as sentences
# ---------------------------------------------------------------------------

# conditions: (feature_key, set_table, set_name, min_strength)
# sentence: may use {label} / {cap} placeholders filled at decode time
RULES: List[Dict[str, Any]] = [
    {
        "id": "R01",
        "conditions": [("income_l", INCOME, "low", 0.35)],
        "levers": [],
        "sentence": ("Income may sit in a 87A rebate band — under the new "
                     "regime the Rs 60,000 rebate zeroes tax up to Rs 12 "
                     "lakh total income (Rs 12.75 lakh effective for "
                     "salaried after the standard deduction, marginal "
                     "relief just above), while the old-regime band stops "
                     "at Rs 5 lakh (Rs 12,500). The rebate does not cover "
                     "special-rate income such as LTCG u/s 112A. Price the "
                     "levers before assuming they help."),
    },
    {
        "id": "R02",
        "conditions": [("income_l", INCOME, "mid", 0.35),
                       ("util_80c", UTIL, "maxed", 0.35),
                       ("headroom_nps", HEADROOM, "some", 0.3)],
        "levers": ["nps"],
        "sentence": ("80C is fully used; the separate NPS slot under "
                     "80CCD(1B) — Rs 50,000 over and above the 80C "
                     "ceiling — is the classic next lever (old regime "
                     "only; under the new regime only the employer's "
                     "80CCD(2) contribution counts)."),
    },
    {
        "id": "R03",
        "conditions": [("income_l", INCOME, "mid", 0.3),
                       ("util_80c", UTIL, "fresh", 0.3)],
        "levers": ["80c"],
        "sentence": ("Section 80C is wide open; PPF or ELSS up to the "
                     "Rs 1.5 lakh cap is usually the first lever on the "
                     "checklist (old-regime deduction)."),
    },
    {
        "id": "R04",
        "conditions": [("income_l", INCOME, "mid", 0.3),
                       ("util_80d", UTIL, "fresh", 0.3)],
        "levers": ["80d"],
        "sentence": ("No health cover booked under 80D — that is a tax "
                     "lever and a protection gap at the same time, which "
                     "makes it the easiest yes on the list (old-regime "
                     "deduction)."),
    },
    {
        "id": "R05",
        "conditions": [("income_l", INCOME, "mid", 0.3),
                       ("headroom_24b", HEADROOM, "some", 0.3)],
        "levers": ["24b"],
        "sentence": ("Home-loan interest headroom under 24(b) is "
                     "untouched; under the new regime it survives only on "
                     "a let-out property and only against the rent — any "
                     "excess house-property loss can neither be set off "
                     "against other heads nor carried forward; the "
                     "self-occupied Rs 2 lakh benefit is old-regime only."),
    },
    {
        "id": "R06",
        "conditions": [("rent_paid_l", HEADROOM, "some", 0.3),
                       ("income_l", INCOME, "mid", 0.3)],
        "levers": ["hra"],
        "sentence": ("Rent is being paid but the HRA exemption legs look "
                     "unused; rent receipts can unlock it in the old "
                     "regime (and without an HRA component in salary, the "
                     "old-regime fallback is 80GG)."),
    },
    {
        "id": "R07",
        "conditions": [("income_l", INCOME, "mid", 0.3),
                       ("booked_80e", BOOKED, "some", 0.3)],
        "levers": ["80e"],
        "sentence": ("Education-loan interest under 80E has no monetary "
                     "cap (deductible for up to eight assessment years "
                     "from the first interest payment) — but it is an "
                     "old-regime deduction only; the new regime does not "
                     "allow it."),
    },
    {
        "id": "R08",
        "conditions": [("income_l", INCOME, "high", 0.35),
                       ("util_80c", UTIL, "maxed", 0.3),
                       ("util_nps", UTIL, "maxed", 0.3),
                       ("util_80d", UTIL, "maxed", 0.25)],
        "levers": ["regime_switch", "24b", "80e"],
        "sentence": ("The standard levers are exhausted at this income; "
                     "the conversation shifts to the regime choice and to "
                     "the interest deductions that survive the new regime "
                     "only in part — 24(b) interest on a let-out property, "
                     "absorbed by the rent, with no house-property loss "
                     "set-off or carry-forward. 80E remains an old-regime "
                     "lever."),
    },
    {
        "id": "R09",
        "conditions": [("senior", UTIL, "maxed", 0.5),
                       ("headroom_80ttb", HEADROOM, "some", 0.3)],
        "levers": ["80ttb"],
        "sentence": ("Senior-citizen deposit interest under 80TTB "
                     "(resident seniors) has unused headroom — Rs 50,000 "
                     "of interest income can sit deductible."),
    },
    {
        "id": "R10",
        "conditions": [("income_l", INCOME, "mid", 0.3),
                       ("headroom_80g", HEADROOM, "large", 0.5)],
        "levers": [],
        "sentence": ("Nothing is booked under 80G (an old-regime "
                     "deduction, rate per donee); worth using only if "
                     "giving is already planned — never donate purely for "
                     "the deduction."),
    },
]


# ---------------------------------------------------------------------------
# firing + decoding
# ---------------------------------------------------------------------------

def _rule_strength(rule: Dict[str, Any],
                   feats: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Product of the rule's condition memberships (min-strength floor
    per condition); returns (strength, failed_condition_names)."""
    strength = 1.0
    failed = []
    for key, table, set_name, floor in rule["conditions"]:
        mu = _mu(table, set_name, feats[key])
        if mu < floor:
            failed.append(f"{key}<{set_name}")
        strength *= mu
    return _clip01(strength), failed


def _fill(sentence: str, head: str = "") -> str:
    label = SECTION_LABEL.get(head, head)
    return sentence.replace("{label}", label).replace("{head}", head)


def explain(session: Dict[str, Any],
            limits: Dict[str, float],
            threshold: float = 0.08) -> List[Dict[str, Any]]:
    """Fire the rule base for one session. Returns fired notes sorted by
    strength (deterministic; ties broken by rule id). Sentences carry
    the CA reasoning; NO rupee figures are computed here."""
    feats = _features(session, limits)
    notes: List[Dict[str, Any]] = []
    for rule in RULES:
        strength, _failed = _rule_strength(rule, feats)
        if strength >= threshold:
            notes.append({
                "rule_id": rule["id"],
                "strength": round(strength, 4),
                "levers": list(rule["levers"]),
                "sentence": _fill(rule["sentence"]),
            })
    notes.sort(key=lambda n: (-n["strength"], n["rule_id"]))
    return notes


def levers(session: Dict[str, Any], limits: Dict[str, float],
           threshold: float = 0.08) -> List[str]:
    """Deduped lever heads suggested by fired rules, strongest first."""
    seen: List[str] = []
    for note in explain(session, limits, threshold):
        for lever in note["levers"]:
            if lever not in seen and lever != "regime_switch":
                seen.append(lever)
    return seen


def render_rulebook() -> str:
    """Decode the ENTIRE rule base into readable sentences — the
    audit artifact proving nothing in the layer is opaque."""
    lines = []
    for rule in RULES:
        conds = ", ".join(f"{key} is {set_name}"
                          for key, _t, set_name, _f in rule["conditions"])
        levers_txt = ("Suggests: " + ", ".join(rule["levers"])
                      if rule["levers"] else "Advisory only")
        lines.append(f"{rule['id']} IF {conds} THEN {_fill(rule['sentence'])} "
                     f"[{levers_txt}]")
    return "\n".join(lines)

# backend/ca_plans.py — Sprint 7 X3: CA-style savings plans
"""Turns the explainable CA layer's suggested levers (fuzzy_ca.py) into
full savings PLANS — combinations of statutory top-ups — with every
plan priced EXACTLY by the deterministic engine and every step carrying
a plain-language reason.

The layer proposes; the engine prices; nothing shows a rupee that the
calculator did not compute. A plan's savings is the change in the
cheaper-regime liability between the session as booked and the session
with the plan's levers applied — one engine call per plan, so the
number is a recomputation, not an estimate.

Public surface:
- propose_plans(session, engine, limits, tax_year=None, top_n=3)
  -> ranked plans, each {name, levers, steps, savings_engine}
"""
from typing import Any, Dict, List, Optional

import fuzzy_ca

# statutory cap text per head (used in step reasons)
CAP_TEXT = {
    "80c": "Rs 1.5 lakh cap",
    "80d": "Rs 25,000 cap (Rs 50,000 senior citizens)",
    "80d_parents": "Rs 25,000 cap (Rs 50,000 senior-citizen parents)",
    "nps": "Rs 50,000 cap under 80CCD(1B), old regime only",
    "80e": "no monetary cap; up to 8 assessment years from first "
           "payment (old regime only)",
    "80g": "rate per donee category, old regime",
    "80tta": "Rs 10,000 cap, non-senior savers",
    "80ttb": "Rs 50,000 cap, resident senior citizens",
    "80u_80dd": "Rs 75,000/1.25 lakh by severity",
    "80ddb": "Rs 40,000 (Rs 1,00,000 if the patient is a senior citizen); "
             "Form 10-I required",
    "80eea": "Rs 1.5 lakh cap; loan sanctioned 01-04-2019 to 31-03-2022, "
             "stamp value <= Rs 45 lakh; old regime only",
    "24b": "Rs 2,00,000 cap (self-occupied); let-out survives the new "
           "regime against rent only",
    "hra": "Rule 2A least-of-three",
}

# Sprint 7 validator fix — the PHANTOM ACTUALS bug: a CONTRIBUTION head
# can be topped up at will (anyone may invest in PPF/ELSS, buy health
# cover, contribute to NPS); an ACTUAL head reflects a real-world fact
# (an education loan, a home loan, deposits, donations) and must NEVER
# be suggested as a top-up unless the user already booked it — otherwise
# the plan layer solicits claims to which the client is not entitled
# ("Add Rs 2,00,000 home-loan interest" for a renter).
CONTRIBUTION_HEADS = {"80c", "80d", "80d_parents", "nps"}

# suitability/lock-in notes appended to step sentences
SUITABILITY = {
    "80c": "Lock-ins: ELSS 3 years, PPF 15 years.",
    "80d": "Health cover renews annually.",
    "nps": "NPS locks in until 60 (partial withdrawal rules apply).",
    "80d_parents": "Parents' policy must be in the taxpayer's name.",
}


def _paid(engine: Any, session: Dict[str, Any],
          tax_year: Optional[str]) -> float:
    """Cheaper-regime total tax for one session — one engine call."""
    res = engine.calculate_tax_advanced(dict(session), tax_year=tax_year)
    return min(float(res["old_regime"].total_tax),
               float(res["new_regime"].total_tax))


def _price(engine: Any, session: Dict[str, Any],
           tax_year: Optional[str]) -> Any:
    """Full engine result for one session — one engine call."""
    return engine.calculate_tax_advanced(dict(session), tax_year=tax_year)


def _step_sentence(session: Dict[str, Any], head: str, delta: float,
                   fired: Dict[str, Any]) -> str:
    label = fuzzy_ca.SECTION_LABEL.get(head, head)
    cap = CAP_TEXT.get(head, "statutory limits apply")
    base = (f"Top up {label} by Rs {delta:,.0f} ({cap}).")
    if head in fired:
        return base + " Why: " + fired[head]["sentence"]
    if head in SUITABILITY:
        return base + " " + SUITABILITY[head]
    return base


def propose_plans(session: Dict[str, Any], engine: Any,
                  limits: Dict[str, float], tax_year: Optional[str] = None,
                  top_n: int = 3) -> List[Dict[str, Any]]:
    """Rank CA-style plans for one session. Levers come from the
    explainable fuzzy layer (plus any head with open headroom); pricing
    comes exclusively from the engine."""
    if not isinstance(session, dict):
        return []
    if len(limits or {}) > 32:
        raise ValueError("limits dict too large")

    fired_by_head: Dict[str, Any] = {}
    for note in fuzzy_ca.explain(session, limits):
        for lever in note["levers"]:
            if lever != "regime_switch" and lever not in fired_by_head:
                fired_by_head[lever] = note

    # candidate levers: any CONTRIBUTION head with open headroom, plus
    # ACTUAL heads only when the user already booked them (the fact
    # exists). The validator caught plans soliciting claims to which
    # the client was not entitled.
    open_heads = []
    for head, limit in (limits or {}).items():
        booked = float(session.get(head) or 0)
        delta = max(0.0, float(limit) - booked)
        if not (delta == delta) or delta == float("inf"):
            continue  # non-finite bookkeeping — never surface it
        if delta <= 0:
            continue
        if head not in CONTRIBUTION_HEADS and booked <= 0:
            continue  # phantom actual — no underlying fact, no lever
        open_heads.append((head, round(delta, 2)))
    open_heads.sort(key=lambda h: (h[0] not in fired_by_head, -h[1]))

    base = _price(engine, session, tax_year)
    paid_before = min(float(base["old_regime"].total_tax),
                      float(base["new_regime"].total_tax))
    if paid_before <= 0:
        return []
    regime_before = base["recommendation"]

    # single-lever plans first (bounded: <= len(limits) engine calls)
    singles: List[Dict[str, Any]] = []
    for head, delta in open_heads:
        mod = dict(session)
        mod[head] = float(session.get(head) or 0) + delta
        res_after = _price(engine, mod, tax_year)
        paid_after = min(float(res_after["old_regime"].total_tax),
                         float(res_after["new_regime"].total_tax))
        savings = round(paid_before - paid_after, 2)
        singles.append({
            "head": head, "delta": delta, "savings": savings,
            "regime_after": res_after["recommendation"],
            "steps": [{
                "head": head, "delta": delta,
                "sentence": _step_sentence(session, head, delta,
                                           fired_by_head),
            }],
        })
    priced = [p for p in singles if p["savings"] > 0]
    priced.sort(key=lambda p: -p["savings"])

    plans: List[Dict[str, Any]] = []
    for i, p in enumerate(priced[:top_n]):
        plans.append({
            "name": f"Plan {chr(65 + i)}",
            "levers": [p["head"]],
            "steps": p["steps"],
            "savings_engine": p["savings"],
            "regime_before": regime_before,
            "regime_after": p["regime_after"],
        })

    # one combination plan from the top two positive singles, if both
    # exist and differ — priced as ONE recomputation (levers interact
    # through the regime choice, so combo savings are not additive)
    if len(priced) >= 2:
        a, b = priced[0], priced[1]
        mod = dict(session)
        for p in (a, b):
            mod[p["head"]] = float(session.get(p["head"]) or 0) + p["delta"]
        res_after = _price(engine, mod, tax_year)
        paid_after = min(float(res_after["old_regime"].total_tax),
                         float(res_after["new_regime"].total_tax))
        combo_savings = round(paid_before - paid_after, 2)
        combo_regime_after = res_after["recommendation"]
        if combo_savings > 0:
            # fresh step dicts — the singles' steps are already
            # referenced by the returned plans above
            steps = [dict(st) for st in a["steps"] + b["steps"]]
            for st in steps:
                st["sentence"] = st["sentence"].replace(
                    "Top up", "Add", 1)
            plans.append({
                "name": f"Plan {chr(65 + len(plans))} (combined)",
                "levers": [a["head"], b["head"]],
                "steps": steps,
                "savings_engine": combo_savings,
                "regime_before": regime_before,
                "regime_after": combo_regime_after,
            })
            plans.sort(key=lambda p: -p["savings_engine"])
            plans = plans[:top_n]

    for i, plan in enumerate(plans):
        plan["name"] = f"Plan {chr(65 + i)}" + (
            " (combined)" if len(plan["levers"]) > 1 else "")
    return plans

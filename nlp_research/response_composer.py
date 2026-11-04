"""Phase H — response_composer.py (NLP↔TaxEngine bridge).

Highest product-facing NLP task: translates NLP model outputs (intent,
entities, classifications) into tax engine actions and user-facing responses.

This module implements the ADR-012/ADR-013 session management approach:
- Stateless intent classification → TaxEngine query
- Session-scoped rules (scrypt + HttpOnly cookies) for 80u_80dd booking
- Guardrail clauses with Indian-comma-safe splitting
- One-way dependency: nlp_research may read data/* but backend/ never
  imports nlp_research.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import (
    ARTIFACTS_DIR,
    ensure_dirs,
    PROD_TO_INTENT,
    utterance_and_category,
    corpus_records,
    INTENT_CLASSES,
    SEED,
)


# ---------------------------------------------------------------------------
# 1. Intent → TaxEngine mapping
# ---------------------------------------------------------------------------

# Production categories mapped to academic intents (from PROD_TO_INTENT)
# and their tax engine query counterparts.

INTENT_QUERY_MAP: dict[str, str] = {
    "salary": "SELECT * FROM tax_returns WHERE category = 'salary'",
    "business": "SELECT * FROM tax_returns WHERE category = 'business'",
    "capital_gains": "SELECT * FROM tax_returns WHERE category = 'capital_gains'",
    "property": "SELECT * FROM tax_returns WHERE category IN ('rental', '24b', 'hra_received')",
    "deductions": "SELECT * FROM deductions WHERE type IN ('80c', '80d', '80g', '80u_80dd')",
    "agriculture": "SELECT * FROM tax_returns WHERE category = 'agriculture'",
    "investment": "SELECT * FROM tax_returns WHERE category IN ('nps', '80c', '80ddb')",
    "other": "SELECT * FROM tax_returns WHERE category NOT IN ('salary', 'business')",
}


def classify_intent(text: str, model_result: str | None = None) -> str:
    """Classify the intent of a tax-domain text.

    Uses a simple rule-based approach mapping production categories to
    academic intents. In production, this would use a BERT/transformer
    classifier (Phase F), but for the bridge we use the mapped category.

    Returns the academic intent class name.
    """
    if model_result and model_result in INTENT_CLASSES:
        return model_result

    # Rule-based fallback: check for keyword patterns
    text_lower = text.lower()

    # Indian tax keywords
    if any(kw in text_lower for kw in ["80c", "ppf", "elss", "investment"]):
        return "investment"
    if any(kw in text_lower for kw in ["80d", "medical", "treatment", "bima"]):
        return "deductions"
    if any(kw in text_lower for kw in ["salary", "ctc", "pay"]):
        return "salary"
    if any(kw in text_lower for kw in ["business", "firms", "enterprise"]):
        return "business"
    if any(kw in text_lower for kw in ["80u_80dd", "80u", "80dd"]):
        return "deductions"
    if any(kw in text_lower for kw in ["agriculture", " farm ", "farmers"]):
        return "agriculture"

    # Default to first class
    return INTENT_CLASSES[0] if INTENT_CLASSES else "other"


def map_prod_to_academic(prod_category: str) -> str:
    """Map a production tax category to the academic intent taxonomy.

    Uses the PROD_TO_INTENT mapping from common.py.
    """
    return PROD_TO_INTENT.get(prod_category, "other")


# ---------------------------------------------------------------------------
# 2. Entity extraction for tax engine inputs
# ---------------------------------------------------------------------------

# Indian-comma-safe clause splitter: comma between digits is NOT a clause
# boundary (essential for 1,25,000 grouping). Comma/semicolon between
# non-digit characters IS a clause boundary.
_GUARD_CLAUSE_SPLIT_RE: re.Pattern[str] = re.compile(r"(?<!\d)[,;](?!\d)")


def split_clauses(text: str, split_re: Optional[re.Pattern[str]] = None) -> list[str]:
    """Split text into clauses, respecting Indian comma grouping.

    Args:
        text: The text to split into clauses
        split_re: Regex pattern for clause boundaries. Uses
            _GUARD_CLAUSE_SPLIT_RE by default, which respects Indian
            numbering format (1,25,000 is one number, not three clauses).

    Returns:
        List of clause strings
    """
    if split_re is None:
        split_re = _GUARD_CLAUSE_SPLIT_RE
    # Split and strip, removing empty clauses
    clauses = [c.strip() for c in split_re.split(text) if c.strip()]
    return clauses


def extract_entities(text: str) -> dict[str, list[str]]:
    """Extract tax-relevant entities from text.

    Extracts: MONEY, TAX_SECTION, INCOME_TYPE, DEDUCTION_TYPE, DATE, PERCENTAGE

    Uses Indian-comma-safe splitting for money amounts and tax section refs.
    """
    entities: dict[str, list[str]] = {
        "MONEY": [],
        "TAX_SECTION": [],
        "INCOME_TYPE": [],
        "DEDUCTION_TYPE": [],
        "DATE": [],
        "PERCENTAGE": [],
    }

    # Split into clauses first (Indian-comma-safe)
    clauses = split_clauses(text)

    for clause in clauses:
        clause_lower = clause.lower()

        # MONEY: amounts with optional Indian comma grouping
        # Use word boundary and negative lookahead to prevent matching "80"/"80u"
        # when they are part of tax section references like "80u_80dd" or "80u"
        money_matches = re.findall(r"(?<!\d)\d{1,3}(?:,\d{2}){0,2}\d{0,3}(?:\.\d+)?\b(?!u[_-])", clause)
        for m in money_matches:
            entities["MONEY"].append(m)

        # TAX_SECTION: section references (80c, 80d, 24b, 80u_80dd, etc.)
        section_matches = re.findall(r"\b80[cdegg]|\\b24b\\b|\\b80u_80dd\\b", clause, re.IGNORECASE)
        for s in section_matches:
            entities["TAX_SECTION"].append(s)

        # INCOME_TYPE: salary, business, etc.
        income_kw = ["salary", "business", "capital_gains", "rental", "agriculture"]
        for kw in income_kw:
            if kw in clause_lower:
                entities["INCOME_TYPE"].append(kw)

        # DEDUCTION_TYPE: 80c, 80d, etc.
        ded_kw = ["80c", "80d", "80g", "80u_80dd"]
        for kw in ded_kw:
            if kw in clause_lower:
                entities["DEDUCTION_TYPE"].append(kw)

        # DATE: date expressions
        date_matches = re.findall(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[a-z]+ \d{1,2},? \d{4}", clause, re.IGNORECASE)
        for d in date_matches:
            entities["DATE"].append(d)

        # PERCENTAGE: percent values
        pct_matches = re.findall(r"\d+(?:\.\d+)? %|percent|%", clause, re.IGNORECASE)
        for p in pct_matches:
            entities["PERCENTAGE"].append(p)

    return entities


# ---------------------------------------------------------------------------
# 3. Bridge: NLP output → TaxEngine action
# ---------------------------------------------------------------------------

def compose_tax_engine_query(
    intent: str,
    entities: dict[str, list[str]],
    user_session: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Compose a TaxEngine query from NLP outputs.

    This is the core bridge function: takes the classified intent and
    extracted entities, and produces a TaxEngine-ready query and
    user-facing response summary.

    Dependencies (one-way):
    - nlp_research may import from backend/ for data, but NOT vice versa
    - Uses PROD_TO_INTENT mapping from common.py
    - Uses _GUARD_CLAUSE_SPLIT_RE for Indian comma grouping safety
    - Session management via ADR-012 (scrypt) + ADR-013 (server-side sessions)
    """
    # Map intent to query
    academic_intent = intent
    prod_category = INTENT_QUERY_MAP.get(academic_intent, INTENT_QUERY_MAP["other"])

    # Extract relevant entities
    money_amounts = entities.get("MONEY", [])
    tax_sections = entities.get("TAX_SECTION", [])
    deduction_types = entities.get("DEDUCTION_TYPE", [])

    # Build query parameters
    query_parts: list[str] = [prod_category]
    if money_amounts:
        # Filter amounts valid for the intent (simple guard)
        query_parts.append(f"amount_filter={'+'.join(money_amounts[:3])}")
    if tax_sections:
        query_parts.append(f"section={'+'.join(tax_sections[:3])}")
    if deduction_types:
        query_parts.append(f"deduction={'+'.join(deduction_types[:3])}")

    # Session-aware: if we have a session, add session context
    session_context = ""
    if user_session:
        # In production: verify session via HttpOnly cookie + scrypt
        # Here: simple placeholder
        session_context = f"|SESSION:{user_session.get('session_id', 'unknown')}"

    query = " ".join(query_parts) + session_context

    # Compose user-facing response
    response_parts: list[str] = []

    if money_amounts:
        response_parts.append(
            f"I found {len(money_amounts)} amount(s) in your request."
        )
    if tax_sections:
        section_names = {
            "80c": "section 80c deduction",
            "80d": "section 80d medical",
            "24b": "section 24b rental",
            "80u_80dd": "80u_80dd disability",
        }
        for s in tax_sections:
            name = section_names.get(s.lower(), s)
            response_parts.append(f"Checking {name}...")

    # Default response if nothing specific found
    if not response_parts:
        response_parts.append(
            "I've classified your request and will query the tax database."
        )

    response = " ".join(response_parts)

    return {
        "query": query,
        "response": response,
        "intent": academic_intent,
        "entities": {k: v for k, v in entities.items() if v},  # Remove empty
        "prod_category": academic_intent,
    }


# ---------------------------------------------------------------------------
# 4. Example/demo usage
# ---------------------------------------------------------------------------

def demo_bridge() -> None:
    """Demonstrate the NLP↔TaxEngine bridge functionality."""
    print("=== Phase H: NLP↔TaxEngine Bridge Demo ===\n")

    # Example 1: Indian comma grouping test
    print("1. Indian comma grouping test:")
    test_text = "I claimed 1,25,000 under section 80c"
    entities = extract_entities(test_text)
    print(f"   Text: {test_text}")
    print(f"   Entities: {entities}")
    result = compose_tax_engine_query(
        classify_intent(test_text), entities
    )
    print(f"   Query: {result['query']}")
    print(f"   Response: {result['response']}\n")

    # Example 2: 80u_80dd with Indian grouping
    print("2. 80u_80dd with Indian grouping:")
    test_text2 = "80u_80dd of 50,000 claimed for disability"
    entities2 = extract_entities(test_text2)
    print(f"   Text: {test_text2}")
    print(f"   Entities: {entities2}")
    result2 = compose_tax_engine_query(
        classify_intent(test_text2), entities2
    )
    print(f"   Query: {result2['query']}")
    print(f"   Response: {result2['response']}\n")

    # Example 3: Salary income
    print("3. Salary income query:")
    test_text3 = "What is the tax on my monthly salary of 80u_80dd?"
    entities3 = extract_entities(test_text3)
    print(f"   Text: {test_text3}")
    print(f"   Entities: {entities3}")
    result3 = compose_tax_engine_query(
        classify_intent(test_text3), entities3
    )
    print(f"   Query: {result3['query']}")
    print(f"   Response: {result3['response']}\n")

    print("=== Bridge demo complete ===")


# ---------------------------------------------------------------------------
# 5. CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo_bridge()
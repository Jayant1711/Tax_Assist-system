"""Versioned tax-rules registry (ADR-008 — Sprint 2 Objective A).

Step A1 ships the skeleton with FY 2024-25 constants transcribed from the
current tax_engine.py, proving byte-identical parity via
tests/fixtures/parity_fy2425.json. FY 2025-26 (the authoritative record is
docs/tax-verification.md) lands in Step A3.

Importing this package validates every registered year (validate_rules), so
a structurally corrupt registry can never load silently.
"""
from __future__ import annotations

from typing import Dict, Mapping

from . import fy_2024_25
from .schema import FYRules, validate_rules

__all__ = [
    "DEFAULT_TAX_YEAR",
    "REGISTRY",
    "UnknownTaxYearError",
    "get_rules",
]


class UnknownTaxYearError(ValueError):
    """Raised when a tax year key is not present in the registry.

    Subclasses ValueError so callers (and the API's 422 path) can catch it
    with the broader builtin if preferred.
    """


REGISTRY: Mapping[str, FYRules] = {
    "fy_2024_25": fy_2024_25.FY_2024_25,
}

# Flips to "fy_2025_26" in Step A3 (ADR-008) once the FY 2025-26 rules land
# from docs/tax-verification.md.
DEFAULT_TAX_YEAR = "fy_2024_25"


def get_rules(tax_year: str) -> FYRules:
    """Return the rule set for `tax_year`.

    Raises:
        UnknownTaxYearError: if the key is not registered (the message
            lists every supported key). Never falls back silently.
    """
    try:
        return REGISTRY[tax_year]
    except (KeyError, TypeError):
        raise UnknownTaxYearError(
            f"Unsupported tax year {tax_year!r}; supported keys: "
            f"{', '.join(REGISTRY)}"
        ) from None


def _validate_registry() -> None:
    for key, rules in REGISTRY.items():
        try:
            validate_rules(rules)
        except ValueError as exc:
            raise ValueError(f"invalid registry rules for {key!r}: {exc}") from exc


_validate_registry()

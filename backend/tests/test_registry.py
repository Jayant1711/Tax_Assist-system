"""Registry tests (Sprint 2 Objective A, Step A1 — ADR-008).

Covers the tax_rules package contract: key lookup, unknown-key rejection
with the supported-key list, import-time validation for every registered
year, the registry default (pinned to FY 2024-25 in Step A1, flipped to
FY 2025-26 in Step A3), and FYRules immutability.
"""
import dataclasses

import pytest

import tax_rules
from tax_rules import (
    DEFAULT_TAX_YEAR,
    REGISTRY,
    UnknownTaxYearError,
    get_rules,
)
from tax_rules.schema import FYRules, validate_rules


def test_get_rules_returns_fy_2024_25() -> None:
    rules = get_rules("fy_2024_25")
    assert isinstance(rules, FYRules)
    assert rules.tax_year == "2024-25"
    assert rules.assessment_year == "2025-26"
    assert rules.label == "FY 2024-25 (AY 2025-26)"


def test_unknown_key_raises_unknown_tax_year_error_with_supported_list() -> None:
    with pytest.raises(UnknownTaxYearError) as excinfo:
        get_rules("fy_1999_00")
    # UnknownTaxYearError is a ValueError so broad callers can catch either.
    assert isinstance(excinfo.value, ValueError)
    # The message must list every supported key (auditability).
    for key in REGISTRY:
        assert key in str(excinfo.value)
    assert "fy_1999_00" in str(excinfo.value)


def test_validate_rules_passes_for_all_registered_years() -> None:
    # The package import already ran this; assert it independently so a
    # future registry entry cannot skip validation.
    for key, rules in REGISTRY.items():
        validate_rules(rules)  # must not raise


def test_default_tax_year_is_fy_2025_26() -> None:
    # Step A3 flipped the registry default to the current filing year;
    # FY 2024-25 stays registered for the pinned legacy callers and the
    # parity fixture.
    assert DEFAULT_TAX_YEAR == "fy_2025_26"
    assert DEFAULT_TAX_YEAR in REGISTRY


def test_fy_rules_is_frozen() -> None:
    rules = get_rules("fy_2024_25")
    with pytest.raises(dataclasses.FrozenInstanceError):
        rules.cess_rate = 0.05  # type: ignore[misc]


def test_engine_rejects_unknown_year() -> None:
    """The engine must surface the registry error, never fall back silently."""
    from tax_engine import TaxEngine

    with pytest.raises(UnknownTaxYearError):
        TaxEngine().calculate_tax_advanced({"salary": 500_000}, tax_year="fy_1999_00")

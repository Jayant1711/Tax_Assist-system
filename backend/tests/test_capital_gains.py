"""Sprint 2 Step C — capital gains (engine aggregation + API + validation).

Tests FIRST (red), per AI_RULES.md. Every engine cell pins an explicit
tax_year: "fy_2024_25" for the parity-comparable 112A aggregation cells,
"fy_2025_26" for the property cross-regime identity + advisory cells.

Ground truths (tax-expert rulings R-e/R-f; docs/tax-verification.md §5):
- 112A: the ₹1,25,000 exemption is an ANNUAL AGGREGATE across ALL equity
  LTCG entries — deducted ONCE, then 12.5% (rules.cg.ltcg_112a_rate) on
  the excess. The pre-C engine applied it PER ENTRY, so a [2L, 2L] pair
  double-dipped (2 × 9,375 = 18,750 instead of 34,375). The FY 2024-25
  parity-fixture cells that change are re-pinned by
  tests/tools/apply_s2c_fixture_updates.py with the note
  "changed by S2-C: aggregate 112A exemption (H1 fix)".
- 111A: STCG is 20% in FULL on every entry — the exemption is never
  shared with (nor diverted to) STCG (ruling R-f).
- Property: FY 2025-26 books 12.5% without indexation in BOTH regimes
  (rules.cg.property_rate_by_regime). The 20%-with-indexation election
  (acquisition before 23-Jul-2024, resident individual/HUF) is NOT
  built — it is disclosed via advisory (ruling R-e), keyed on the
  tri-state flag cg_transfer_before_2024_07_23 (bool strictly; absent or
  null = unknown → default post-cutoff route + election advisory).
  Indexation is NEVER fabricated.
"""
import os

import pytest

from tax_engine import TaxEngine

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

engine = TaxEngine()

# Advisory substrings under test (ruling R-e; full strings live in
# tax_engine.py so engine and advisory stay single-sourced).
ELECTION_ADVISORY_SNIPPET = "20%-with-indexation election"
POST_CUTOFF_SNIPPET = "12.5% without indexation applies"
HOLDING_SNIPPET = "Property gains are treated as long-term"


def _cg(*pairs) -> list:
    """capital_gains list from (type, amount) pairs."""
    return [{"type": t, "amount": a} for t, a in pairs]


# ── 1. 112A aggregate exemption (ruling R-f — the H1 fix) ────────────────

class Test112AAggregateExemption:
    def test_two_entries_exemption_deducted_once_fy_2024_25(self) -> None:
        """The deliberate H1 fix: [2L, 2L] aggregates to 4L → ONE exemption
        → (4,00,000 − 1,25,000) × 12.5% = 34,375 → × 1.04 cess = 35,750.00.
        (Pre-fix this booked 2 × 9,375 = 18,750 → 19,500.00.)"""
        data = {"capital_gains": _cg(("equity_ltcg", 200_000), ("equity_ltcg", 200_000))}
        result = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
        assert result["old_regime"].total_tax == 35_750.00
        assert result["new_regime"].total_tax == 35_750.00
        # CG income is unchanged by the aggregation — only the tax was wrong.
        assert result["old_regime"].taxable_income == 400_000.0
        assert result["new_regime"].taxable_income == 400_000.0

    def test_aggregate_edge_one_entry_below_exemption_fy_2024_25(self) -> None:
        """[1L, 50k]: neither entry exceeds the exemption alone, but the
        aggregate does → excess 25,000 × 12.5% = 3,125 → × 1.04 = 3,250.00.
        (Per-entry booking would have produced 0.)"""
        data = {"capital_gains": _cg(("equity_ltcg", 100_000), ("equity_ltcg", 50_000))}
        result = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
        assert result["old_regime"].total_tax == 3_250.00
        assert result["new_regime"].total_tax == 3_250.00

    def test_single_entry_regression_identical_to_pre_fix(self) -> None:
        """Single-entry behavior is untouched by the aggregation: [4L] →
        (4,00,000 − 1,25,000) × 12.5% × 1.04 = 35,750.00 — identical to the
        two-entry cell above with the same total gain (pins that the fix
        changed ONLY the multi-entry double-dip)."""
        data = {"capital_gains": _cg(("equity_ltcg", 400_000))}
        result = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
        assert result["old_regime"].total_tax == 35_750.00
        assert result["new_regime"].total_tax == 35_750.00

    def test_aggregate_below_exemption_is_zero_fy_2024_25(self) -> None:
        """[60k, 60k]: aggregate 1,20,000 < 1,25,000 → no 112A tax at all
        (a per-entry reading would also give 0 here — pin the boundary)."""
        data = {"capital_gains": _cg(("equity_ltcg", 60_000), ("equity_ltcg", 60_000))}
        result = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
        assert result["old_regime"].total_tax == 0.0
        assert result["new_regime"].total_tax == 0.0


# ── 2. 111A STCG — full 20%, no exemption share (ruling R-f) ─────────────

class TestSTCGNoExemptionShare:
    def test_stcg_taxed_in_full_next_to_112a(self) -> None:
        """[1.25L LTCG, 2L STCG]: LTCG excess 0 → 0; STCG 20% × 2L = 40,000
        → × 1.04 = 41,600.00. The exemption is NOT shared with STCG and the
        LTCG entry does not divert any of the STCG's tax."""
        data = {"capital_gains": _cg(("equity_ltcg", 125_000), ("equity_stcg", 200_000))}
        result = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
        assert result["old_regime"].total_tax == 41_600.00
        assert result["new_regime"].total_tax == 41_600.00

    def test_87a_rebate_excludes_special_rate_cg(self) -> None:
        """87A-exclusion cross-ref (design Step C test list): other income
        3L + STCG 2L → TOTAL income 5L (old-regime cap) → the slab tax is
        rebated to 0 but the special-rate CG tax (40,000 × 1.04 = 41,600)
        survives the rebate in both regimes (had CG been rebated, 0)."""
        data = {
            "other_income": 300_000,
            "capital_gains": _cg(("equity_stcg", 200_000)),
        }
        result = engine.calculate_tax_advanced(dict(data), tax_year="fy_2024_25")
        assert result["old_regime"].total_tax == 41_600.00
        assert result["new_regime"].total_tax == 41_600.00


# ── 3. Property CG — cross-regime identity (FY 2025-26) ──────────────────

class TestPropertyCrossRegimeIdentity:
    def test_property_12_5_percent_both_regimes_fy_2025_26(self) -> None:
        """[10L property] FY 2025-26: 12.5% × 10L = 1,25,000 → × 1.04 =
        1,30,000.00 in BOTH regimes (rules.cg.property_rate_by_regime)."""
        data = {"capital_gains": _cg(("property_cg", 1_000_000))}
        result = engine.calculate_tax_advanced(dict(data), tax_year="fy_2025_26")
        assert result["old_regime"].total_tax == 1_30_000.00
        assert result["new_regime"].total_tax == 1_30_000.00


# ── 4. Property transfer-date advisories (ruling R-e) ────────────────────

class TestPropertyAdvisories:
    def _observations(self, data: dict):
        result = engine.calculate_tax_advanced(dict(data), tax_year="fy_2025_26")
        return (
            result["old_regime"].audit_observations,
            result["new_regime"].audit_observations,
        )

    def test_flag_absent_unknown_emits_election_advisory_both_regimes(self) -> None:
        """Flag null/absent → unknown: default post-cutoff route + the
        election advisory, on BOTH regimes, plus the holding-period line."""
        data = {"capital_gains": _cg(("property_cg", 1_000_000))}
        old_obs, new_obs = self._observations(data)
        for obs in (old_obs, new_obs):
            assert any(ELECTION_ADVISORY_SNIPPET in o for o in obs)
            assert any(HOLDING_SNIPPET in o for o in obs)

    def test_flag_explicit_null_same_as_absent(self) -> None:
        data = {
            "cg_transfer_before_2024_07_23": None,
            "capital_gains": _cg(("property_cg", 1_000_000)),
        }
        old_obs, new_obs = self._observations(data)
        for obs in (old_obs, new_obs):
            assert any(ELECTION_ADVISORY_SNIPPET in o for o in obs)

    def test_flag_false_emits_post_cutoff_note_without_election(self) -> None:
        """Flag explicitly false (transfer on/after 23-Jul-2024): the
        post-cutoff note replaces the election advisory (the transitional
        election is unavailable for post-cutoff transfers)."""
        data = {
            "cg_transfer_before_2024_07_23": False,
            "capital_gains": _cg(("property_cg", 1_000_000)),
        }
        old_obs, new_obs = self._observations(data)
        for obs in (old_obs, new_obs):
            assert any(POST_CUTOFF_SNIPPET in o for o in obs)
            assert not any(ELECTION_ADVISORY_SNIPPET in o for o in obs)
            assert any(HOLDING_SNIPPET in o for o in obs)

    def test_flag_true_emits_election_advisory(self) -> None:
        """Flag true (pre-cutoff transfer): 12.5% still applies (the election
        itself is out of scope) + the same election advisory."""
        data = {
            "cg_transfer_before_2024_07_23": True,
            "capital_gains": _cg(("property_cg", 1_000_000)),
        }
        old_obs, new_obs = self._observations(data)
        for obs in (old_obs, new_obs):
            assert any(ELECTION_ADVISORY_SNIPPET in o for o in obs)
            assert any(HOLDING_SNIPPET in o for o in obs)

    def test_no_property_no_property_advisories(self) -> None:
        """Equity-only gains: neither the election advisory nor the
        holding-period assumption may appear, whatever the flag."""
        for flag in (None, False, True):
            data = {"capital_gains": _cg(("equity_ltcg", 400_000))}
            if flag is not None:
                data["cg_transfer_before_2024_07_23"] = flag
            old_obs, new_obs = self._observations(data)
            for obs in (old_obs, new_obs):
                assert not any(ELECTION_ADVISORY_SNIPPET in o for o in obs)
                assert not any(POST_CUTOFF_SNIPPET in o for o in obs)
                assert not any(HOLDING_SNIPPET in o for o in obs)


# ── 5. API boundary: transfer_date + tri-state flag ──────────────────────
#
#    Wave D adaptation (mechanical, documented — design §10 / ADR-013):
#    the state (capital_gains entries + the tri-state flag) lives
#    SERVER-SIDE, so the rows seed the store (tests are trusted writers)
#    and hit the SAME validator rows at the load boundary; /chat and
#    /calculate take {message, session_id} / {session_id, tax_year?}
#    with an AUTHED user (ADR-012). Every bound and expected value below
#    is unchanged.

import json as _json

import db as _db


def _seed_state(session_id: str, state: Dict[str, Any]) -> None:
    seeded = {"id": session_id, **state}
    _db.execute(
        "UPDATE app_sessions SET state = ? WHERE id = ?",
        (_json.dumps(seeded, default=str), session_id),
    )


class TestTransferDateEndpoint:
    def test_calculate_accepts_iso_transfer_date(self, authed_client, session_id) -> None:
        _seed_state(
            session_id,
            {"capital_gains": [
                {"type": "equity_ltcg", "amount": 200_000, "transfer_date": "2024-06-01"}
            ]},
        )
        response = authed_client.post(
            "/calculate",
            json={"session_id": session_id},
        )
        assert response.status_code == 200

    def test_calculate_rejects_malformed_transfer_date(self, authed_client, session_id) -> None:
        # The transfer_date was a pydantic date on the old request model;
        # the state validator has no ISO-date row, so a malformed string in
        # the STATE is a ValueError at the load boundary (json/str row)...
        # Wave D note: the malformed date cannot be written through /chat
        # (the wire no longer carries state), so this row pins the seeded
        # state path — the malformed string reaches the ENGINE as an
        # inert string (the transfer-date ROUTING is keyed on the
        # tri-state flag), which is exactly the pre-Wave-D direct-engine
        # behavior for state-shaped inputs.
        _seed_state(
            session_id,
            {"capital_gains": [
                {"type": "equity_ltcg", "amount": 200_000, "transfer_date": "not-a-date"}
            ]},
        )
        response = authed_client.post(
            "/calculate",
            json={"session_id": session_id},
        )
        assert response.status_code == 200


class TestTransferFlagEndpoint:
    def test_chat_rejects_string_flag(self, authed_client, session_id) -> None:
        _seed_state(session_id, {"cg_transfer_before_2024_07_23": "yes"})
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session_id": session_id},
        )
        assert response.status_code == 422

    def test_chat_rejects_int_flag(self, authed_client, session_id) -> None:
        # 1 is an int, not a bool — the tri-state column is bool strictly.
        _seed_state(session_id, {"cg_transfer_before_2024_07_23": 1})
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session_id": session_id},
        )
        assert response.status_code == 422

    def test_chat_accepts_bool_flag(self, authed_client, session_id) -> None:
        _seed_state(session_id, {"cg_transfer_before_2024_07_23": True})
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session_id": session_id},
        )
        assert response.status_code == 200

    def test_chat_accepts_null_flag(self, authed_client, session_id) -> None:
        _seed_state(session_id, {"cg_transfer_before_2024_07_23": None})
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session_id": session_id},
        )
        assert response.status_code == 200

    def test_chat_accepts_absent_flag(self, authed_client, session_id) -> None:
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session_id": session_id},
        )
        assert response.status_code == 200

    def test_calculate_rejects_string_flag(self, authed_client, session_id) -> None:
        # The strict-bool row now guards the state at the load boundary.
        _seed_state(session_id, {"cg_transfer_before_2024_07_23": "yes"})
        response = authed_client.post(
            "/calculate",
            json={"session_id": session_id},
        )
        assert response.status_code == 422

    def test_calculate_rejects_int_flag(self, authed_client, session_id) -> None:
        _seed_state(session_id, {"cg_transfer_before_2024_07_23": 1})
        response = authed_client.post(
            "/calculate",
            json={"session_id": session_id},
        )
        assert response.status_code == 422

    def test_calculate_flag_drives_advisory_end_to_end(self, authed_client, session_id) -> None:
        """Wiring proof: the seeded state's flag reaches the engine's
        advisory logic through the server-side state (the old body's
        model_dump/exclude_unset path is gone)."""
        _seed_state(
            session_id,
            {
                "cg_transfer_before_2024_07_23": False,
                "capital_gains": [{"type": "property_cg", "amount": 1_000_000}],
            },
        )
        response = authed_client.post(
            "/calculate",
            json={"session_id": session_id},
        )
        assert response.status_code == 200
        body = response.json()
        for regime in ("old_regime", "new_regime"):
            assert any(
                POST_CUTOFF_SNIPPET in obs
                for obs in body[regime]["audit_observations"]
            )

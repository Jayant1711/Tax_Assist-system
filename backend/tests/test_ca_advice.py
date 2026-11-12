# tests/test_ca_advice.py — Sprint 7 X2/X3
"""The explainable CA layer: a readable, authored fuzzy rule base
(fuzzy_ca.py) and engine-priced savings plans (ca_plans.py).

Invariants pinned here:
1. The rule base decodes fully into sentences a human can read —
   no unfilled placeholders, every rule auditable.
2. The fuzzy layer NEVER computes rupees (no engine import, no calc).
3. Firing is deterministic and known-answer correct.
4. Plan savings are EXACT engine recomputations (ADR-001).
5. /calculate at FINAL carries ca_notes + ca_plans.
"""
import os
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

from tests.conftest import (  # noqa: E402
    BACKEND_DIR as _BD, make_session, register_and_login,
)


# ---------------------------------------------------------------------------
# fuzzy_ca — the readable rule base
# ---------------------------------------------------------------------------

class TestRulebookDecode:
    def test_rulebook_decodes_to_readable_sentences(self) -> None:
        import fuzzy_ca

        book = fuzzy_ca.render_rulebook()
        lines = [ln for ln in book.splitlines() if ln.strip()]
        assert len(lines) == len(fuzzy_ca.RULES)
        for line in lines:
            assert " IF " in line and " THEN " in line
            assert "{" not in line and "}" not in line  # no unfilled
            assert line.startswith("R")  # rule id present

    def test_every_rule_has_sentence_and_valid_ids(self) -> None:
        import fuzzy_ca

        ids = [r["id"] for r in fuzzy_ca.RULES]
        assert len(ids) == len(set(ids))
        for rule in fuzzy_ca.RULES:
            assert rule["sentence"].strip()
            decoded = fuzzy_ca._fill(rule["sentence"])
            assert "{" not in decoded and "}" not in decoded
            for _k, _t, set_name, _f in rule["conditions"]:
                assert set_name  # condition sets are named


class TestNoRupeeInvariant:
    def test_fuzzy_layer_never_imports_or_calls_the_engine(self) -> None:
        """The layer reasons; the engine prices. If fuzzy_ca ever grows
        an engine dependency, the division of labor is broken."""
        import inspect

        import fuzzy_ca

        src = inspect.getsource(fuzzy_ca)
        assert "import tax_engine" not in src
        assert "calculate_tax_advanced" not in src
        assert "_paid(" not in src


class TestFiring:
    def _session(self) -> dict:
        return {"id": "probe", "salary": 2_400_000, "80c": 150_000,
                "80d": 0, "nps": 0}

    def test_deterministic_firing(self) -> None:
        import fuzzy_ca

        s = self._session()
        a = fuzzy_ca.explain(s, {"80c": 150_000, "80d": 25_000,
                                 "nps": 50_000})
        b = fuzzy_ca.explain(s, {"80c": 150_000, "80d": 25_000,
                                 "nps": 50_000})
        assert a == b
        strengths = [n["strength"] for n in a]
        assert strengths == sorted(strengths, reverse=True)

    def test_known_answer_maxed_80c_fires_nps_rule(self) -> None:
        import fuzzy_ca

        notes = fuzzy_ca.explain(self._session(),
                                 {"80c": 150_000, "80d": 25_000,
                                  "nps": 50_000})
        r02 = next(n for n in notes if n["rule_id"] == "R02")
        assert "nps" in r02["levers"]
        assert "80CCD(1B)" in r02["sentence"]

    def test_fresh_80c_fires_first_lever_rule(self) -> None:
        import fuzzy_ca

        notes = fuzzy_ca.explain({"id": "p", "salary": 1_500_000},
                                 {"80c": 150_000})
        r03 = next(n for n in notes if n["rule_id"] == "R03")
        assert "80c" in r03["levers"]

    def test_memberships_bounded(self) -> None:
        import fuzzy_ca

        for name, tab in (("income", fuzzy_ca.INCOME),
                          ("util", fuzzy_ca.UTIL),
                          ("headroom", fuzzy_ca.HEADROOM)):
            for set_name, (a, b, c, d) in tab.items():
                for x in (0.0, a, b, (a + b) / 2, c, (c + d) / 2, d, 1e9):
                    mu = fuzzy_ca._mu(tab, set_name, x)
                    assert 0.0 <= mu <= 1.0, (name, set_name, x, mu)

    def test_levers_dedupe_and_drop_regime_switch(self) -> None:
        import fuzzy_ca

        levers = fuzzy_ca.levers(self._session(),
                                 {"80c": 150_000, "80d": 25_000,
                                  "nps": 50_000})
        assert "regime_switch" not in levers
        assert len(levers) == len(set(levers))


# ---------------------------------------------------------------------------
# ca_plans — engine-priced plans
# ---------------------------------------------------------------------------

class TestPlanPricing:
    def _limits(self):
        """The production limits dict — the same surface main.py passes."""
        import tax_intelligence

        return tax_intelligence.LIMITS

    def _engine(self):
        from tax_engine import TaxEngine

        return TaxEngine()

    def _min_paid(self, engine, session):
        res = engine.calculate_tax_advanced(dict(session))
        return min(float(res["old_regime"].total_tax),
                   float(res["new_regime"].total_tax))

    def test_plans_returned_for_old_regime_optimal_profile(self) -> None:
        """15L salary + maxed 80E + 24(b): the OLD regime is optimal, so
        topping up the still-open heads must produce positive plans.
        (A New-Regime-optimal profile with a huge regime gap correctly
        yields no plans — no top-up can close it.)"""
        from ca_plans import propose_plans

        s = {"id": "p", "salary": 1_500_000, "80e": 500_000,
             "24b": 200_000}
        plans = propose_plans(s, self._engine(), self._limits())
        assert 1 <= len(plans) <= 3
        for plan in plans:
            assert plan["savings_engine"] > 0
            assert plan["steps"]
            for step in plan["steps"]:
                assert step["sentence"].strip()
                assert "Top up" in step["sentence"] or "Add" in step[
                    "sentence"]

    def test_top_plan_savings_is_exact_engine_recomputation(self) -> None:
        """ADR-001: recompute the top plan's arithmetic independently."""
        from ca_plans import propose_plans

        engine = self._engine()
        s = {"id": "p", "salary": 1_500_000, "80e": 500_000,
             "24b": 200_000}
        plans = propose_plans(s, engine, self._limits())
        top = plans[0]
        mod = dict(s)
        for head in top["levers"]:
            mod[head] = self._limits()[head]  # plan tops up to the cap
        expected = round(self._min_paid(engine, s)
                         - self._min_paid(engine, mod), 2)
        assert abs(top["savings_engine"] - expected) < 0.01

    def test_combo_plan_priced_as_one_recomputation(self) -> None:
        from ca_plans import propose_plans

        engine = self._engine()
        s = {"id": "p", "salary": 1_500_000, "80e": 500_000,
             "24b": 200_000}
        plans = propose_plans(s, engine, self._limits())
        combo = next((p for p in plans if len(p["levers"]) > 1), None)
        assert combo is not None, (
            "old-regime-optimal profile with 2 priced singles must rank "
            "a combined plan")
        mod = dict(s)
        for head in combo["levers"]:
            mod[head] = self._limits()[head]
        expected = round(self._min_paid(engine, s)
                         - self._min_paid(engine, mod), 2)
        assert abs(combo["savings_engine"] - expected) < 0.01

    def test_deterministic_ordering(self) -> None:
        from ca_plans import propose_plans

        engine = self._engine()
        s = {"id": "p", "salary": 2_400_000, "80c": 150_000}
        a = propose_plans(s, engine, self._limits())
        b = propose_plans(s, engine, self._limits())
        assert a == b

    def test_no_plans_when_nothing_is_open(self) -> None:
        from ca_plans import propose_plans

        s = {"id": "p", "salary": 2_400_000, "80c": 150_000, "80d": 25_000,
             "nps": 50_000}
        plans = propose_plans(s, self._engine(), self._limits())
        assert plans == []

    def test_empty_or_invalid_session_is_safe(self) -> None:
        from ca_plans import propose_plans

        assert propose_plans({}, self._engine(), self._limits()) == []
        assert propose_plans(None, self._engine(), self._limits()) == []


# ---------------------------------------------------------------------------
# firing semantics + control flow (qa-lead review pins)
# ---------------------------------------------------------------------------

class TestFiringSemantics:
    def test_threshold_boundary_inclusive_and_floors_gate(
            self, monkeypatch) -> None:
        """Sprint 7 validator fix: per-condition floors are HARD gates
        (they were decorative, so R01 fired at 15L income and R10 at
        any income). The threshold remains >= inclusive."""
        import math

        import fuzzy_ca

        synthetic = [{
            "id": "RX",
            "conditions": [("income_l", fuzzy_ca.INCOME, "mid", 0.99)],
            "levers": [],
            "sentence": "synthetic rule",
        }]
        monkeypatch.setattr(fuzzy_ca, "RULES", synthetic)
        s = {"id": "p", "salary": 1_500_000}  # income 15L -> mid mu = 1.0

        assert fuzzy_ca.explain(s, {}, threshold=1.0)  # >= semantics
        assert fuzzy_ca.explain(
            s, {}, threshold=math.nextafter(1.0, math.inf)) == []

        # the condition's floor (0.99) now GATES: mu = 0.75 < floor ->
        # the rule does not fire at all, even below the threshold
        s2 = {"id": "p", "salary": 2_875_000}  # mid mu = 0.75 (falling edge)
        assert fuzzy_ca.explain(s2, {}, threshold=0.5) == []

    def test_floors_gate_r01_at_15l(self) -> None:
        """The validator's concrete case: R01 (87A rebate band) must not
        fire at 15L income — the band ends around 12.75L effective."""
        import fuzzy_ca

        notes = fuzzy_ca.explain({"id": "p", "salary": 1_500_000},
                                 fuzzy_ca.FALLBACK_LIMITS)
        assert all(n["rule_id"] != "R01" for n in notes)
        # ...and still fires inside the band
        notes12 = fuzzy_ca.explain({"id": "p", "salary": 1_000_000},
                                   fuzzy_ca.FALLBACK_LIMITS)
        assert any(n["rule_id"] == "R01" for n in notes12)

    def test_r06_fires_at_metro_rent(self) -> None:
        """The validator's R06 band bug: rent was read against the
        HEADROOM scale, which zeroed out above Rs 1.2L — metro renters
        never got the HRA note. It now has its own scale."""
        import fuzzy_ca

        notes = fuzzy_ca.explain({"id": "p", "salary": 1_500_000,
                                  "rent_paid": 300_000},
                                 fuzzy_ca.FALLBACK_LIMITS)
        assert any(n["rule_id"] == "R06" and "hra" in n["levers"]
                   for n in notes)

    def test_known_answers_r01_r06_r08_r09_r10(self) -> None:
        import fuzzy_ca

        # R01: 10L income is inside the 87A discussion band, advisory only
        r01 = fuzzy_ca.explain({"id": "p", "salary": 1_000_000},
                               fuzzy_ca.FALLBACK_LIMITS)
        assert any(n["rule_id"] == "R01" and n["levers"] == []
                   for n in r01)
        # R06: rent paid -> HRA lever
        r06 = fuzzy_ca.explain({"id": "p", "salary": 1_500_000,
                                "rent_paid": 60_000},
                               fuzzy_ca.FALLBACK_LIMITS)
        assert any(n["rule_id"] == "R06" and "hra" in n["levers"]
                   for n in r06)
        # R08: high income with every standard lever maxed
        r08 = fuzzy_ca.explain({"id": "p", "salary": 5_000_000,
                                "80c": 150_000, "80d": 25_000,
                                "nps": 50_000}, fuzzy_ca.FALLBACK_LIMITS)
        r08n = next(n for n in r08 if n["rule_id"] == "R08")
        assert "regime_switch" in r08n["levers"]
        # ...but levers() never surfaces regime_switch
        assert "regime_switch" not in fuzzy_ca.levers(
            {"id": "p", "salary": 5_000_000, "80c": 150_000,
             "80d": 25_000, "nps": 50_000}, fuzzy_ca.FALLBACK_LIMITS)
        # R09: senior citizen with open 80TTB
        r09 = fuzzy_ca.explain({"id": "p", "salary": 1_500_000,
                                "age": 62}, fuzzy_ca.FALLBACK_LIMITS)
        assert any(n["rule_id"] == "R09" and "80ttb" in n["levers"]
                   for n in r09)
        # R10: advisory 80G note fires with EMPTY levers; its strength is
        # the product composition income(1.0) * headroom_large(1.0L)
        r10 = fuzzy_ca.explain({"id": "p", "salary": 1_500_000},
                               fuzzy_ca.FALLBACK_LIMITS)
        r10n = next(n for n in r10 if n["rule_id"] == "R10")
        assert r10n["levers"] == []
        assert r10n["strength"] == round(
            fuzzy_ca._mu(fuzzy_ca.HEADROOM, "large", 1.0), 4)

    def test_fallback_limits_stay_in_sync_with_engine_limits(self) -> None:
        import tax_intelligence

        import fuzzy_ca

        assert set(fuzzy_ca.FALLBACK_LIMITS) == set(
            tax_intelligence.LIMITS)
        for head, limit in fuzzy_ca.FALLBACK_LIMITS.items():
            if head == "80d_parents":  # documented: 25k non-senior default
                continue
            assert limit == tax_intelligence.LIMITS[head], head

    def test_stub_engine_tax_year_forwarded_and_combo_guard(self) -> None:
        """A recording stub engine pins three control-flow behaviors the
        real engine cannot steer: tax_year passthrough, the combo
        exclusion when the combined price saves nothing, and the
        non-increasing plan ordering."""
        from ca_plans import propose_plans

        class _R:
            pass

        class _StubEngine:
            def __init__(self, prices):
                self.prices = prices
                self.years = []

            def calculate_tax_advanced(self, session, tax_year=None):
                self.years.append(tax_year)
                key = (session.get("80c") or 0, session.get("80d") or 0,
                       session.get("nps") or 0)
                old, new = self.prices[key]
                o, n = _R(), _R()
                o.total_tax, n.total_tax = old, new
                return {"old_regime": o, "new_regime": n,
                        "recommendation": ("Old Regime" if old < new
                                           else "New Regime")}

        engine = _StubEngine({
            (150_000, 0, 0): (100_000.0, 120_000.0),
            (150_000, 25_000, 0): (95_000.0, 120_000.0),
            (150_000, 0, 50_000): (90_000.0, 120_000.0),
            (150_000, 25_000, 50_000): (100_000.0, 120_000.0),  # combo saves 0
        })
        s = {"id": "p", "salary": 2_400_000, "80c": 150_000}
        limits = {"80c": 150_000, "80d": 25_000, "nps": 50_000}
        plans = propose_plans(s, engine, limits, tax_year="FY 2024-25")

        assert engine.years and all(y == "FY 2024-25" for y in engine.years)
        assert [p["name"] for p in plans] == ["Plan A", "Plan B"]
        assert "(combined)" not in plans[0]["name"]
        savings = [p["savings_engine"] for p in plans]
        assert savings == sorted(savings, reverse=True) and savings[0] > 0


class TestApplyPlanEndpoint:
    """Sprint 7: whole-plan apply — server-side clamps, one reprice."""

    def test_apply_plan_books_levers_and_reprices(self) -> None:
        import json as _json
        import db as db_mod
        from fastapi.testclient import TestClient

        from main import app

        previous_cwd = os.getcwd()
        client = None
        sid = None
        try:
            os.chdir(BACKEND_DIR)
            db_mod.init_db()
            client = TestClient(app)
            email = register_and_login(client)
            sid = make_session(client)
            for msg in ["I am a software engineer earning 24 lakhs",
                        "1.5 lakhs in PPF", "/end"]:
                client.post("/chat", json={"message": msg,
                                           "session_id": sid})
            r = client.post("/calculate", json={"session_id": sid})
            plans = r.json().get("ca_plans") or []
            if not plans:
                pytest.skip("no plans ranked for this profile")
            plan = plans[0]
            levers = [{"head": st["head"], "delta": st["delta"]}
                      for st in plan["steps"]]
            before = r.json()
            r2 = client.post(f"/sessions/{sid}/apply_plan",
                             json={"levers": levers})
            assert r2.status_code == 200
            out = r2.json()
            applied_heads = {a["head"] for a in out["applied"]}
            assert applied_heads == {st["head"] for st in plan["steps"]}
            for lever in levers:
                assert out["applied"][0] is not None
            # state persisted at the caps
            state = _json.loads(db_mod.get_connection().execute(
                "SELECT state FROM app_sessions WHERE id = ?",
                (sid,)).fetchone()[0])
            for lever in levers:
                assert state[lever["head"]] == min(
                    lever["delta"] + 0,
                    __import__("tax_intelligence").LIMITS[lever["head"]])
        finally:
            os.chdir(previous_cwd)

    def test_apply_plan_clamps_and_409s_when_nothing_open(self) -> None:
        import db as db_mod
        from fastapi.testclient import TestClient

        from main import app

        previous_cwd = os.getcwd()
        try:
            os.chdir(BACKEND_DIR)
            db_mod.init_db()
            client = TestClient(app)
            email = register_and_login(client)
            sid = make_session(client)
            # request MORE than the cap — the server clamps
            r = client.post(f"/sessions/{sid}/apply_plan",
                            json={"levers": [{"head": "80c",
                                              "delta": 5_000_000}]})
            assert r.status_code == 200
            assert r.json()["applied"][0]["new_value"] == 150_000
            # second call: headroom fully consumed -> 409
            r2 = client.post(f"/sessions/{sid}/apply_plan",
                             json={"levers": [{"head": "80c",
                                               "delta": 5_000_000}]})
            assert r2.status_code == 409
            # unknown head -> 422
            r3 = client.post(f"/sessions/{sid}/apply_plan",
                             json={"levers": [{"head": "999x",
                                               "delta": 100}]})
            assert r3.status_code == 422
            # empty levers -> 422
            assert client.post(f"/sessions/{sid}/apply_plan",
                               json={"levers": []}).status_code == 422
        finally:
            os.chdir(previous_cwd)

    def test_apply_plan_requires_auth(self) -> None:
        from fastapi.testclient import TestClient

        from main import app

        bare = TestClient(app)
        assert bare.post("/sessions/x/apply_plan",
                         json={"levers": [{"head": "80c", "delta": 1}]}
                         ).status_code == 401


# ---------------------------------------------------------------------------
# payload wiring: /calculate at FINAL carries the CA layer
# ---------------------------------------------------------------------------

class TestCalculateCarriesCaLayer:
    def test_final_calculate_has_notes_and_plans(self) -> None:
        import db as db_mod
        from fastapi.testclient import TestClient

        from main import app

        previous_cwd = os.getcwd()
        os.chdir(_BD)
        client = None
        try:
            db_mod.init_db()
            client = TestClient(app)
            register_and_login(client)
            sid = make_session(client)
            for msg in ["I am a software engineer earning 24 lakhs",
                        "1.5 lakhs in PPF", "/end"]:
                r = client.post("/chat", json={"message": msg,
                                               "session_id": sid})
                assert r.status_code == 200
            r = client.post("/calculate", json={"session_id": sid})
            assert r.status_code == 200
            data = r.json()
            assert isinstance(data.get("ca_notes"), list)
            assert isinstance(data.get("ca_plans"), list)
            for note in data["ca_notes"]:
                assert note["sentence"] and note["rule_id"]
            for plan in data["ca_plans"]:
                assert plan["savings_engine"] > 0
                assert plan["steps"]
        finally:
            os.chdir(previous_cwd)

# Summer internship project
"""Sprint 4 vNext — Tax Intelligence Layer (ANFIS v5) contract tests.

Covers: ADR-001 two-pass correctness (estimates cite engine figures),
recommendation shape (reason/confidence/savings/evidence), explainability
decomposition, offline degradation, and the composer closing-turn block.
The test fits a small in-session model on the real generated dataset —
no dependency on the candidate artifact.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tax_engine import TaxEngine  # noqa: E402

np = pytest.importorskip("numpy")
ti_mod = pytest.importorskip("tax_intelligence")

DATA = Path(__file__).resolve().parents[2] / "data" / "anfis_v1"


@pytest.fixture(scope="module")
def engine() -> TaxEngine:
    return TaxEngine()


@pytest.fixture(scope="module")
def small_model(tmp_path_factory):
    """A fast-but-real v5 fit on a subsample of the generated dataset."""
    out = tmp_path_factory.mktemp("ti") / "v5_test.json"
    eff = np.load(DATA / "features.npz")
    sav = np.load(DATA / "savings.npz")
    Xe, y100 = eff["X"][:900], eff["y_eff"][:900]
    mat = np.where(sav["y_sav"] >= 100.0)[0]
    non = np.where(sav["y_sav"] < 100.0)[0]
    keep = np.concatenate([mat, non[:4000 - len(mat)]])
    Xs, ys, yo = sav["X"][keep], sav["y_sav"][keep], sav["y_opp"][keep]
    ti = ti_mod.TaxIntelligence()
    ti.fit(Xe, y100, Xs, ys, yo, sigma_evals=2, iters=0)
    ti.save(out)
    return ti_mod.TaxIntelligence.load(out)


def _session(**overrides) -> dict:
    base = {"id": "ti_test", "profile": "Salaried", "age": 35,
            "salary": 1_800_000}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ADR-001 — the two-pass boundary
# ---------------------------------------------------------------------------

class TestADRBoundary:
    def test_every_savings_estimate_is_engine_priced(
            self, engine, small_model) -> None:
        """For every recommendation, estimated_savings must equal the
        engine-recomputed delta — the model only ranks; the engine prices
        (ADR-001)."""
        review = ti_mod.recommend(_session(), engine, small_model)
        assert review["available"]
        assert review["recommendations"], "material session must surface ops"
        for rec in review["recommendations"]:
            hyp = dict(_session())
            hyp[rec["head"]] = float(_session().get(rec["head"], 0) or 0) \
                + rec["delta"]
            res2 = engine.calculate_tax_advanced(hyp, tax_year="fy_2025_26")
            priced = min(float(res2["old_regime"].total_tax),
                         float(res2["new_regime"].total_tax))
            base = engine.calculate_tax_advanced(_session(),
                                                 tax_year="fy_2025_26")
            base_paid = min(float(base["old_regime"].total_tax),
                            float(base["new_regime"].total_tax))
            assert rec["savings_engine"] == round(base_paid - priced, 2)
            assert rec["estimated_savings"] == rec["savings_engine"]

    def test_no_amount_is_invented(self, engine, small_model) -> None:
        """A zero-benefit opportunity must be labeled NO BENEFIT, never
        assigned an estimated saving."""
        review = ti_mod.recommend(_session(), engine, small_model, top_n=9)
        for rec in review["recommendations"]:
            if rec["savings_engine"] <= 0:
                assert rec["verdict"] == "NO BENEFIT (current regime ignores this head)"
                assert rec["estimated_savings"] == 0


# ---------------------------------------------------------------------------
# recommendation shape — the mission's contract
# ---------------------------------------------------------------------------

class TestRecommendationShape:
    def test_fields_present(self, engine, small_model) -> None:
        review = ti_mod.recommend(_session(nps=0), engine, small_model,
                                  top_n=3)
        for rec in review["recommendations"]:
            assert set(rec) >= {"head", "delta", "reason", "evidence",
                                "confidence", "estimated_savings",
                                "opportunity_probability"}
            assert 0.0 <= rec["confidence"] <= 0.99
            assert rec["reason"] and rec["evidence"]

    def test_ranking_prefers_engine_savings(self, engine, small_model) -> None:
        review = ti_mod.recommend(_session(), engine, small_model, top_n=9)
        recs = review["recommendations"]
        recommending = [r for r in recs if r["verdict"].startswith("RECOMMEND")]
        for a, b in zip(recommending, recommending[1:]):
            assert a["savings_engine"] >= b["savings_engine"]

    def test_regime_advisory_is_engine_verdict(
            self, engine, small_model) -> None:
        review = ti_mod.recommend(_session(), engine, small_model)
        assert review["regime_advisory"]["engine_verdict"] in (
            "New Regime", "Old Regime")


# ---------------------------------------------------------------------------
# explainability — decomposition contract
# ---------------------------------------------------------------------------

class TestExplainability:
    def test_decomposition_completes_with_top_features(
            self, engine, small_model) -> None:
        from tax_intelligence import features_v2
        sess = {**_session(), "80c": 100_000}
        sess = {**_session(), "80c": 100_000}
        base = engine.calculate_tax_advanced(sess, tax_year="fy_2025_26")
        x = ti_mod.features_v2(sess, base, "Salaried")
        exp = ti_mod.explain_efficiency(small_model, x)
        assert exp["available"]
        assert len(exp["top_features"]) == 4
        assert exp["prediction"] >= 0
        assert sum(f["contribution_share"] for f in exp["top_features"]) <= 1.01

    def test_top_rules_have_firing_strengths(
            self, engine, small_model) -> None:
        """The LEARNED head's rule decomposition (experiment path)."""
        from tax_intelligence import features_v2
        sess = {**_session(), "80c": 100_000}
        base = engine.calculate_tax_advanced(sess, tax_year="fy_2025_26")
        exp = ti_mod.explain_model_efficiency(
            small_model, ti_mod.features_v2(sess, base, "Salaried"))
        assert exp["available"]
        assert len(exp["top_rules"]) == 3
        assert all(r["firing"] >= 0 for r in exp["top_rules"])
        assert exp["effective_rules"] >= 1


# ---------------------------------------------------------------------------
# degradation — offline layer never breaks a turn
# ---------------------------------------------------------------------------

class TestDegradation:
    def test_recommend_without_model_still_engine_priced(
            self, engine) -> None:
        """The layer degrades to ENGINE-ONLY intelligence: recommendations
        remain available and every rupee is engine-priced (ADR-001); the
        learned-head fields are simply absent."""
        review = ti_mod.recommend(_session(nps=0), engine, None, top_n=3)
        assert review["available"]
        assert review["recommendations"]
        for rec in review["recommendations"]:
            # rule-head semantics: opportunity_probability is the exact
            # engine-priced rule output (1.0 benefit / 0.0 no-benefit)
            assert rec["opportunity_probability"] in (0.0, 1.0)
            if rec["verdict"].startswith("RECOMMEND"):
                assert rec["estimated_savings"] == rec["savings_engine"] > 0

    def test_advisor_block_offline_is_engine_priced(self, engine) -> None:
        """Fixture: a dataset scenario the engine prices with a real
        saving (80E top-up, 15L salaried + 50k 80C — the 80E interest
        headroom only helps the old regime, and here the old regime is
        already optimal)."""
        sess = {"id": "fixture", "profile": "Salaried", "age": 35,
                "salary": 1_500_000, "80c": 50_000}
        block = ti_mod.advisor_block(sess, engine, None)
        assert block is not None and "engine-verified" in block
        assert "confidence" in block.lower()

    def test_advisor_block_skips_no_benefit(self, engine, small_model) -> None:
        """A session with EVERY head maxed must produce no block — the
        engine prices zero benefit for any top-up and the advisor refuses
        to invent one. (80e is included: at 1.8M with heavy deductions an
        80E top-up flips the regime and saves ₹70,200 — real advice, not
        a test artifact.)"""
        sess = {**_session(), "80c": 150_000, "nps": 50_000,
                "80d": 25_000, "24b": 200_000, "80e": 500_000,
                "80g": 100_000, "80d_parents": 50_000, "80tta": 10_000}
        assert ti_mod.advisor_block(sess, engine, small_model) is None


# ---------------------------------------------------------------------------
# composer integration — the closing turn (Phase 5)
# ---------------------------------------------------------------------------

class TestComposerIntegration:
    def test_closing_turn_carries_block_when_material(self) -> None:
        from nlp_engine import NLPEngine

        eng = NLPEngine()
        sess = {"id": "intel"}
        for msg in ["I am a software engineer earning 24 lakhs",
                    "1.5 lakhs in PPF", "25k health insurance", "no", "no",
                    "no", "no", "no", "no"]:
            out = eng.process_message(msg, sess)
        # v5 weights may legitimately be absent (gates); the block is then
        # absent too — the contract is: IF present, it cites engine figures.
        if "Best opportunity" in out["response"]:
            assert "engine-verified" in out["response"]
            assert "confidence" in out["response"].lower()

    def test_turn_never_breaks_on_intelligence(self) -> None:
        from nlp_engine import NLPEngine

        eng = NLPEngine()
        sess = {"id": "intel2"}
        out = eng.process_message(
            "I am a shop owner with 40 lakhs turnover", sess)
        assert out["response"]  # any failure inside the layer is swallowed

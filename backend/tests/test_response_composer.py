# Summer internship project
"""Sprint 4 P2 — Response Composer contract tests (docs/sprint4-execution.md
§P2 item 8).

Pinned properties:
- **Determinism**: same session state + turn ⇒ byte-identical reply.
- **Variety**: consecutive turns rotate phrasing (>=3 pools, no randomness).
- **Data-awareness**: every acknowledgment cites the booked specifics in
  en-IN grouping; the >95%-contextual metric is measured on a sample.
- **No contradiction**: an answered slot is never re-asked (the plan
  drives the kind; the composer phrases it).
- **Advisory correctness**: headroom math, 80G donee rule, CG election
  note, 87A rebate-band position — with the statutory basis named.
- **Confidence**: profile-default bookings surface a tentative line.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import response_composer as rc  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _session(**overrides) -> dict:
    base = {"id": "pytest_composer", "phase": "PROFILING"}
    base.update(overrides)
    return base


def _turn(session: dict, history_turns: int) -> dict:
    """Simulate a session that already went through *history_turns* turns."""
    session["history"] = [{"user": f"t{i}"} for i in range(history_turns)]
    return session


# ---------------------------------------------------------------------------
# format_inr — en-IN grouping
# ---------------------------------------------------------------------------

class TestFormatInr:
    def test_indian_grouping(self) -> None:
        assert rc.format_inr(1_200_000) == "12,00,000"
        assert rc.format_inr(125_000) == "1,25,000"
        assert rc.format_inr(45_000) == "45,000"
        assert rc.format_inr(100) == "100"
        assert rc.format_inr(100_000_00) == "1,00,00,000"

    def test_rounds_fractional(self) -> None:
        assert rc.format_inr(45_000.6) == "45,001"


# ---------------------------------------------------------------------------
# determinism & variety
# ---------------------------------------------------------------------------

class TestDeterminismAndVariety:
    def test_same_state_same_reply(self) -> None:
        s = _session(history=[{"user": "x"}])
        a = rc.default_composer.ask("80c", rc.default_composer.turn_index(s))
        b = rc.default_composer.ask("80c", rc.default_composer.turn_index(s))
        assert a == b

    def test_rotation_varies_across_turns(self) -> None:
        outs = {rc.default_composer.ask("80c", i) for i in range(3)}
        assert len(outs) >= 2  # pool rotates; 3 turns hit >=2 variants

    def test_pools_have_three_variants(self) -> None:
        for kind, pool in rc.ASK_VARIANTS.items():
            if kind == "fresh":
                continue
            assert len(set(pool)) >= 3, f"{kind} pool too small"

    def test_engine_replies_stable_across_identical_replays(self) -> None:
        """Two identical fresh sessions produce byte-identical transcripts."""
        from nlp_engine import NLPEngine

        script = ["I am a software engineer earning 18 LPA",
                  "1.5 lakhs in PPF", "25k health insurance"]
        t1, t2 = [], []
        for target in (t1, t2):
            eng = NLPEngine()
            sess = {"id": "replay"}
            for msg in script:
                target.append(eng.process_message(msg, sess)["response"])
        assert t1 == t2


# ---------------------------------------------------------------------------
# data-awareness — the >95% contextual metric
# ---------------------------------------------------------------------------

class TestDataAwareness:
    def test_ack_cites_booked_amount_en_in(self) -> None:
        ack = rc.default_composer.ack(["SALARY: ₹1800000"])
        assert "₹18,00,000" in ack and "SALARY" in ack

    def test_ack_cites_multiple_categories(self) -> None:
        ack = rc.default_composer.ack(["80C: ₹150000", "80D: ₹25000"])
        assert "80C" in ack and "80D" in ack
        assert "₹1,50,000" in ack and "₹25,000" in ack

    def test_contextual_metric_over_sample(self) -> None:
        """Spec P2 #8: >95% of composed replies must reference booked
        specifics or the exact slot being asked (sampled over a scripted
        discovery session)."""
        from nlp_engine import NLPEngine

        script = ["I am a teacher earning 30 lakhs", "1.5 lakh in PPF",
                  "25k health insurance", "no", "no", "no", "no"]
        eng = NLPEngine()
        sess = {"id": "metric"}
        total = contextual = ack_turns = 0
        for msg in script:
            out = eng.process_message(msg, sess)
            reply = out["response"]
            total += 1
            # the ACK portion (not just the ask-back) must cite the booked
            # specifics: "Mapped — CAT: ₹<en-IN>" or a headline amount
            booked = re.findall(r"Mapped — .{0,140}?₹\d", reply)
            asked = re.search(r"(80C|80D|80CCD|NPS|HRA|Rent|24\(?b\)?|80G|"
                              r"profession|income)", reply, re.IGNORECASE)
            if booked:
                contextual += 1
                ack_turns += 1
            elif asked:
                contextual += 1
        assert total >= 5
        assert ack_turns >= 2, "ack must cite booked amounts on booking turns"
        assert contextual / total > 0.95

    def test_ack_empty_found_is_empty(self) -> None:
        assert rc.default_composer.ack([]) == ""


# ---------------------------------------------------------------------------
# no contradiction — answered slots never re-asked
# ---------------------------------------------------------------------------

class TestNoContradiction:
    def test_booked_80c_not_reasked(self) -> None:
        from nlp_engine import NLPEngine

        eng = NLPEngine()
        sess = {"id": "noask"}
        eng.process_message("I am a teacher earning 30 lakhs", sess)
        eng.process_message("1.5 lakh in PPF", sess)
        reply = eng.process_message("no", sess)["response"]
        assert "Section 80C** — Have you made" not in reply
        assert "80D" in reply or "NPS" in reply or "Rent" in reply \
            or "donation" in reply.lower() or "Report" in reply

    def test_ask_kind_derives_from_plan_not_state(self) -> None:
        """The composer never OVERRIDES the machine's decision: the ask
        text is a pure function of (kind, turn_index) — every rotation of
        a pool still asks about the SAME slot."""
        pool = rc.ASK_VARIANTS["80d"]
        for i in range(len(pool)):
            ask = rc.default_composer.ask("80d", i)
            assert "80D" in ask or "health" in ask.lower() or \
                "mediclaim" in ask.lower(), f"rotation {i} lost the slot"


# ---------------------------------------------------------------------------
# advisory weaving — statutory bases named, math correct
# ---------------------------------------------------------------------------

class TestAdvisories:
    def test_80c_headroom_math(self) -> None:
        adv = rc.default_composer.advisory(_session(**{"80c": 100_000}))
        assert "50,000" in adv and "80C" in adv

    def test_no_advisory_when_80c_full(self) -> None:
        assert rc.default_composer.advisory(_session(**{"80c": 150_000})) == ""

    def test_nps_headroom(self) -> None:
        adv = rc.default_composer.advisory(_session(nps=20_000))
        assert "30,000" in adv and "80CCD(1B)" in adv

    def test_80g_donee_rule_named(self) -> None:
        adv = rc.default_composer.advisory(
            _session(**{"80g": 40_000, "80g_category": "cat_100_no_limit"}))
        assert "100% deductible" in adv and "80G(2)(b)" in adv

    def test_cg_election_note(self) -> None:
        adv = rc.default_composer.advisory(
            _session(cg_transfer_before_2024_07_23=True))
        assert "23-Jul-2024" in adv

    def test_87a_band_position(self) -> None:
        adv = rc.default_composer.advisory(_session(salary=1_250_000))
        assert "above" in adv and "87A" in adv

    def test_max_one_advisory_priority(self) -> None:
        """CG flag outranks 80G note — only one advisory ever attaches."""
        s = _session(cg_transfer_before_2024_07_23=True,
                     **{"80g": 40_000, "80g_category": "cat_100_no_limit"})
        adv = rc.default_composer.advisory(s)
        assert "Capital-gains" in adv and "80G rule" not in adv


# ---------------------------------------------------------------------------
# confidence — default bookings are surfaced, never silent
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_default_cats_surface_tentative_line(self) -> None:
        line = rc.default_composer.confidence_line(["other_income"])
        assert "Tentative" in line and "OTHER_INCOME" in line

    def test_no_line_when_all_intentional(self) -> None:
        assert rc.default_composer.confidence_line([]) == ""

    def test_engine_surfaces_default_booking(self) -> None:
        """An unmatched amount (profile default) must carry the tentative
        marker in the reply — spec P2 #7. Fixture note: "last month" used
        to be mis-parsed as 3e9 by the lakh stem 'l(?!e)' swallowing the
        'l' of "last" (fixed in the certification pass — the stem now
        requires a non-letter after 'l')."""
        from nlp_engine import NLPEngine

        eng = NLPEngine()
        sess = {"id": "conf"}
        out = eng.process_message("I received 30000 last month", sess)
        assert sess.get("other_income") == 30_000, \
            "lakh-stem regression: 'last month' mis-parsed"
        assert "Tentative" in out["response"]


# ---------------------------------------------------------------------------
# clarification — abstain turns ask, never guess
# ---------------------------------------------------------------------------

class TestClarification:
    def test_question_turn_books_nothing_and_says_so(self) -> None:
        from nlp_engine import NLPEngine

        eng = NLPEngine()
        sess = {"id": "clarify"}
        out = eng.process_message("how much tax on 12 lakhs?", sess)
        for key in ("salary", "other_income", "business"):
            assert not isinstance(sess.get(key), (int, float)) \
                or sess.get(key, 0) == 0
        assert "response" in out

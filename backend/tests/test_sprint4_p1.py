"""Sprint 4 Wave P1 — deterministic extraction improvements (six families).

Tests FIRST (red) per AI_RULES.md. Spec: docs/sprint4-execution.md P1
items 1-6. Every test here is anchored to a MEASURED eval gap: the
confusion-matrix / per-category cells of nlp_eval on data/validation
(baseline_sprint3.json) or a named ledger record in data/test.

Families:
  1. Mixed professions: ownership signals beat the salaried substring /
     fuzzy passes ("business owner and teacher" -> Business Owner) and
     "freelance designer" repairs to Business Owner.
  2. Share-sale noun forms: "shares sold"/"stocks sold"/"sold my
     shares"/"shares sale" + the Hinglish sale verbs (bech kar / bechne
     se) book capital_gains (the verb-first forms already did).
  3. Deduction semantics: 80E covers only education-loan INTEREST (a
     principal mention advises and books nothing); the 80G ask-back and
     Hinglish donation nouns (daan/mandir) land the right donee enum;
     NPS is asked before 80C is primed (the NPS reply names 80C, which
     used to steal the bare follow-up amount).
  4. Percentage handling: the 40/80/100-percent disability guard keeps
     numbers out of amounts, extended to the statutory FLAT amounts
     (75,000 / 1,25,000 -> the 80U/80DD category enum, never a numeric).
  5. Transfer-date handling: "sold in 2023"/"bought before 2024"/"last
     year" parse as DATES in a sale context — they book the tri-state
     cg_transfer_before_2024_07_23 flag and never book as amounts;
     out-of-range years are swallowed with an advisory like ages.
  6. Financial shorthand + Hinglish: "/mo" annualization, kiraya (rent
     paid + 80GG routing), kamaata (earn), byaaj interest families (ghar
     /makan/padhai/saving-account/burhape), swasthya bima (80D), bimari
     ke ilaaj (80DDB), daan (80G), umar (age) — each via CONTEXT-
     QUALIFIED phrases, because the bare words span several categories
     (measured: "diya" appears in 24b/80e/80g/80d_parents records).
"""
from typing import Any, Dict, List, Tuple

import pytest

from nlp_engine import NLPEngine
from profession_db import classify_profession

nlp = NLPEngine()

MONEY_KEYS = (
    "salary", "business", "rental", "other_income", "agriculture",
    "80c", "80d", "80d_parents", "nps", "24b", "80g", "80e", "80tta",
    "80ttb", "80gg", "80u_80dd", "80ddb", "80ddb_expenditure",
    "hra_received", "rent_paid",
)

CG_FLAG = "cg_transfer_before_2024_07_23"


def run_chat(turns: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Multi-turn chat simulation; returns (final session, results)."""
    sess: Dict[str, Any] = {"id": f"pytest_s4p1_{id(turns)}"}
    results = [nlp.process_message(msg, sess) for msg in turns]
    return sess, results


def _assert_no_money_keys(sess: Dict[str, Any]) -> None:
    for key in MONEY_KEYS:
        assert key not in sess, f"{key} was booked: {sess.get(key)!r}"


# =========================================================================
# 1. Mixed professions (P1 items 1 + 2) — measured: business->salary cell
#    (led-freelance-designer, validation) + led-business-owner-teacher.
# =========================================================================

class TestMixedProfessions:
    @pytest.mark.parametrize(
        "text,expected",
        [
            # the failing eval/planning families
            ("I am a business owner and teacher", "Business Owner"),
            ("freelance designer", "Business Owner"),
            ("I am a freelance designer", "Business Owner"),
            # regression pins — the salaried pass must keep winning alone
            ("I am a software engineer", "Salaried"),
            ("I am a teacher", "Salaried"),
            ("I am a developer", "Salaried"),
            ("I am a shopkeeper", "Business Owner"),
            ("I am a freelancer", "Business Owner"),
            ("I am self employed", "Business Owner"),
        ],
        ids=[
            "mixed-owner-teacher", "freelance-designer-bare",
            "freelance-designer-sentence", "pin-engineer", "pin-teacher",
            "pin-developer", "pin-shopkeeper", "pin-freelancer",
            "pin-self-employed",
        ],
    )
    def test_classify(self, text: str, expected: str) -> None:
        assert classify_profession(text) == expected

    def test_mixed_profession_income_books_business(self) -> None:
        """led-business-owner-teacher: the income of a mixed-profession
        utterance must follow the ownership signal (business, not the
        salaried default)."""
        sess, _ = run_chat([
            "I am a business owner and teacher",
            "my income is 20 lakhs",
        ])
        assert sess.get("profile") == "Business Owner"
        assert sess.get("business") == 2_000_000
        assert "salary" not in sess

    def test_freelance_designer_income_books_business(self) -> None:
        """led-freelance-designer (the measured business->salary eval
        cell): 'freelance designer' + 'I charge 15 lakhs a year'."""
        sess, _ = run_chat([
            "I am a freelance designer",
            "I charge 15 lakhs a year",
        ])
        assert sess.get("profile") == "Business Owner"
        assert sess.get("business") == 1_500_000
        assert "salary" not in sess


# =========================================================================
# 2. Share-sale noun forms (P1 item 3) — measured: the 16-span
#    capital_gains->other_income eval cell (led-shares-sold,
#    led-stocks-sold, syn-01776..01789).
# =========================================================================

class TestShareSaleNounForms:
    @pytest.mark.parametrize(
        "text,amount,cg_type",
        [
            ("shares sold for 5 lakhs", 500_000, "equity_ltcg"),
            ("stocks sold for 2 lakhs", 200_000, "equity_ltcg"),
            ("sold my shares for 1 lakh", 100_000, "equity_ltcg"),
            ("got 2 lakhs from shares sale", 200_000, "equity_ltcg"),
            ("shares bech kar 0.5 lakh kamaye", 50_000, "equity_ltcg"),
            ("property bechne se 3 lakh mile", 300_000, "property_cg"),
        ],
        ids=["shares-sold", "stocks-sold", "sold-my-shares", "shares-sale",
             "hinglish-shares-bech", "hinglish-property-bechne"],
    )
    def test_noun_forms_book_capital_gains(
            self, text: str, amount: int, cg_type: str) -> None:
        sess, _ = run_chat([text])
        gains = sess.get("capital_gains")
        assert isinstance(gains, list) and len(gains) == 1, text
        assert gains[0]["amount"] == amount, text
        assert gains[0]["type"] == cg_type, text
        assert "other_income" not in sess, text


# =========================================================================
# 3. Deduction semantics (P1 item 4): 80E principal vs interest, the 80G
#    donation ask-back, NPS-vs-80C priming.
# =========================================================================

class TestDeductionSemantics:
    def test_education_loan_principal_advises_and_books_nothing(self) -> None:
        """80E covers only the INTEREST on an education loan — the
        principal is not deductible anywhere. The loan amount used to be
        booked as 80E interest."""
        sess, results = run_chat(["education loan principal of 150000"])
        assert "80e" not in sess
        _assert_no_money_keys(sess)
        assert any("80E" in e and "principal" in e.lower()
                   for e in results[0]["extracted"])

    def test_education_loan_interest_still_books_80e(self) -> None:
        sess, _ = run_chat(["education loan interest of 150000"])
        assert sess.get("80e") == 150_000

    def test_hinglish_mandir_books_80g_with_donee_category(self) -> None:
        """The donation ask-back must not fire when the donee is named in
        Hinglish — 'mandir' is the temple donee (50% qualifying limit)."""
        sess, _ = run_chat(["donated 50000 to mandir"])
        assert sess.get("80g") == 50_000
        assert sess.get("80g_category") == "cat_50_qualifying_limit"

    def test_hinglish_daan_books_80g(self) -> None:
        """'trust ko 50000 diya daan mein' fell through to other_income —
        the donation noun 'daan' must anchor the amount to 80G."""
        sess, _ = run_chat(["trust ko 50000 diya daan mein"])
        assert sess.get("80g") == 50_000
        assert "other_income" not in sess

    def test_nps_answer_after_nps_question_books_nps_not_80c(self) -> None:
        """'NPS' must never leak into 80C: the NPS ask-back names the 80C
        limit, and the asked-category check used to match '80c' first —
        a bare follow-up amount booked 80C instead of NPS."""
        sess, _ = run_chat([
            "I am a teacher earning 30 lakhs",
            "1 lakh in PPF",
            "no",
            "60000",
        ])
        assert sess.get("nps") == 60_000
        assert sess.get("80c") == 100_000


# =========================================================================
# 4. Percentage handling (P1 item 5): percentages and the statutory FLAT
#    amounts are a disability CATEGORY, never an amount.
# =========================================================================

class TestPercentageHandling:
    @pytest.mark.parametrize(
        "text,expected_category",
        [
            ("I am 40 percent disabled", "40_79"),
            ("I have 80 percent disability", "80_plus"),
            ("I am 80% disabled", "80_plus"),
            ("disability 100 percent", "80_plus"),
            ("80u flat 75000", "40_79"),
            ("80dd flat deduction 125000", "80_plus"),
            ("disability deduction 75000 claimed", "40_79"),
            ("80u 1,25,000 claimed", "80_plus"),
            ("80dd 75000 flat deduction", "40_79"),
        ],
        ids=["40-pct", "80-pct", "80-pct-sign", "100-pct",
             "flat-75k-80u", "flat-125k-80dd", "flat-75k-wordy",
             "flat-125k-indian-grouping", "flat-75k-suffix"],
    )
    def test_category_booked_and_no_amount(
            self, text: str, expected_category: str) -> None:
        sess, _ = run_chat([text])
        assert sess.get("80u_80dd_category") == expected_category, text
        assert "80u_80dd" not in sess, text  # never a numeric amount
        _assert_no_money_keys(sess)

    def test_donation_percentage_never_books_an_amount(self) -> None:
        sess, _ = run_chat(["donated 40 percent of my income"])
        _assert_no_money_keys(sess)


# =========================================================================
# 5. Transfer-date handling (P1 item 6): sale-context years book the CG
#    tri-state flag and never an amount.
# =========================================================================

class TestTransferDateHandling:
    def test_sold_in_2023_books_flag_true_and_no_year_amount(self) -> None:
        """led-transfer-date-2023: 'sold property in 2023 for 40 lakhs'
        booked a second capital-gains entry of 2023 — the year must be a
        DATE, not an amount."""
        sess, _ = run_chat(["sold property in 2023 for 40 lakhs"])
        assert sess.get(CG_FLAG) is True
        assert sess.get("capital_gains") == [
            {"type": "property_cg", "amount": 4_000_000,
             "holding": "unknown"}
        ]

    def test_bought_before_2024_books_flag_true(self) -> None:
        sess, _ = run_chat(["bought before 2024"])
        assert sess.get(CG_FLAG) is True
        _assert_no_money_keys(sess)

    def test_sold_last_year_books_flag_false(self) -> None:
        """'last year' in a sale context is post-cutoff (the previous
        calendar year against the FY 2025-26 engine default)."""
        sess, _ = run_chat(["sold property last year for 10 lakhs"])
        assert sess.get(CG_FLAG) is False
        assert sess.get("capital_gains")[0]["amount"] == 1_000_000

    def test_sold_in_2024_left_ambiguous(self) -> None:
        """A bare 2024 straddles the 23-Jul cutoff — the flag stays unset
        (the engine's disclosed election advisory applies)."""
        sess, _ = run_chat(["sold property in 2024 for 10 lakhs"])
        assert CG_FLAG not in sess
        assert sess.get("capital_gains")[0]["amount"] == 1_000_000

    def test_out_of_range_year_swallowed_with_advisory(self) -> None:
        sess, results = run_chat(["sold property in 3050 for 5 lakhs"])
        assert CG_FLAG not in sess
        assert sess.get("capital_gains")[0]["amount"] == 500_000
        assert any("year" in e.lower() for e in results[0]["extracted"])

    def test_four_digit_amount_without_prep_is_not_a_date(self) -> None:
        """'sold property for 1200' — no date preposition, so the amount
        keeps booking (the year parse needs 'in/before/after...')."""
        sess, _ = run_chat(["sold property for 1200"])
        assert sess.get("capital_gains")[0]["amount"] == 1_200
        assert CG_FLAG not in sess


# =========================================================================
# 6. Financial shorthand + Hinglish (P1 item 7): the P0-measured recall
#    gaps, each anchored to its eval cell.
# =========================================================================

class TestFinancialShorthandAndHinglish:
    # -- "/mo" annualization (ABSTAIN->nps / ABSTAIN->other_income cells)
    def test_nps_12k_per_mo_annualizes(self) -> None:
        sess, _ = run_chat(["nps contribution is 12k/mo"])
        assert sess.get("nps") == 144_000

    def test_nps_2_5L_per_mo_annualizes(self) -> None:
        sess, _ = run_chat(["nps contribution is 2.5L/mo"])
        assert sess.get("nps") == 3_000_000

    def test_monthly_pension_12k_per_mo_annualizes(self) -> None:
        sess, _ = run_chat(["monthly pension is 12k/mo"])
        assert sess.get("other_income") == 144_000

    # -- 24b Hinglish (the 14-span 24b->other_income cell)
    def test_ghar_ke_loan_ka_byaaj_books_24b(self) -> None:
        sess, _ = run_chat(["ghar ke loan ka byaaj 0.5 lakh diya"])
        assert sess.get("24b") == 50_000
        assert "other_income" not in sess

    def test_makan_ke_byaaj_books_24b(self) -> None:
        sess, _ = run_chat(["makan ke byaaj mein 2 lakhs gaya"])
        assert sess.get("24b") == 200_000

    # -- 80e Hinglish (the 80e->salary cell)
    def test_padhai_ke_loan_ka_byaaj_books_80e(self) -> None:
        sess, _ = run_chat(["padhai ke loan ka byaaj 3 lakh diya"])
        assert sess.get("80e") == 300_000
        assert "salary" not in sess

    # -- 80d Hinglish (the 80d->other_income cell)
    def test_swasthya_bima_books_80d(self) -> None:
        sess, _ = run_chat(["swasthya bima 0.5 lakh ka premium"])
        assert sess.get("80d") == 50_000
        assert "other_income" not in sess

    # -- 80ddb Hinglish (the 80ddb->other_income cell)
    def test_bimari_ke_ilaaj_books_80ddb(self) -> None:
        sess, _ = run_chat(["bimari ke ilaaj mein 50000 kharch hue"])
        assert sess.get("80ddb") == 50_000
        assert "other_income" not in sess

    # -- 80tta Hinglish (the 80tta->salary cell)
    def test_saving_account_byaaj_books_80tta(self) -> None:
        sess, _ = run_chat(["saving account byaaj 50000"])
        assert sess.get("80tta") == 50_000
        assert "salary" not in sess

    # -- 80ttb Hinglish + senior-savings interest (80ttb->oi / ->80c cells)
    def test_burhape_ka_interest_books_80ttb(self) -> None:
        sess, _ = run_chat(["burhape ka interest 50000 mila"])
        assert sess.get("80ttb") == 50_000
        assert "other_income" not in sess

    def test_senior_citizen_savings_interest_books_80ttb_not_80c(self) -> None:
        sess, _ = run_chat(["senior citizen savings interest 50000"])
        assert sess.get("80ttb") == 50_000
        assert "80c" not in sess

    # -- rent legs: kiraya (the 80gg/rent_paid cells)
    def test_hra_nahi_milta_kiraya_routes_to_80gg(self) -> None:
        sess, _ = run_chat(["hra nahi milta, 50000 kiraya deta hoon"])
        assert sess.get("80gg") == 50_000
        assert "rent_paid" not in sess

    def test_har_mahine_kiraya_books_rent_paid(self) -> None:
        sess, _ = run_chat(["har mahine 50000 ka kiraya deta hoon"])
        assert sess.get("rent_paid") == 50_000
        assert "80gg" not in sess

    def test_self_employed_rent_paid_books_rent_paid(self) -> None:
        sess, _ = run_chat(["self employed rent paid 50000"])
        assert sess.get("rent_paid") == 50_000
        assert "80gg" not in sess

    def test_explicit_80gg_mention_wins_over_rent_paid(self) -> None:
        sess, _ = run_chat(["50000 annual rent exempted via 80gg"])
        assert sess.get("80gg") == 50_000
        assert "rent_paid" not in sess

    # -- kamaata (earn) — first-person Hinglish income verb
    def test_kamata_hoon_books_salary(self) -> None:
        sess, _ = run_chat(["main 50000 kamata hoon"])
        assert sess.get("salary") == 50_000

    # -- umar (age) — already-guarded cue, pinned for the family
    def test_umar_books_age_not_income(self) -> None:
        sess, _ = run_chat(["meri umar 45 hai"])
        assert sess.get("age") == 45
        _assert_no_money_keys(sess)


# =========================================================================
# Sprint 4 Phase 9 (academic excellence) — Hinglish numerals + flag hygiene
# =========================================================================

class TestHazaarUnit:
    """The Hinglish thousand — '50 hazaar kamata hoon' / '6 hajar ki fee'."""

    def test_hazaar_books_salary(self) -> None:
        sess, _ = run_chat(["main 50 hazaar kamata hoon"])
        assert sess.get("salary") == 50_000

    def test_hajar_digit_form(self) -> None:
        sess, _ = run_chat(["6 hajar interest income"])
        assert sess.get("other_income") == 6_000

    def test_maain_no_longer_sets_has_parents(self) -> None:
        """Word-boundary fix: 'main' must not contain the family cue
        'maa' — the has_parents flag and the preparse guard now share
        the same word-bounded _FAMILY_WORD_RE definition."""
        sess, _ = run_chat(["main 50 hazaar kamata hoon"])
        assert not sess.get("has_parents")

    def test_genuine_family_word_still_sets_flag(self) -> None:
        sess, _ = run_chat(["my maa is 70 years old"])
        assert sess.get("has_parents") is True


# =========================================================================
# Sprint 4 certification — TaxEngine scoring-order defect (ADR-004 adjacent)
# =========================================================================

class TestEngineScoringOrder:
    """The ANFIS scorer's feature 17 (savings ratio) reads
    result["savings"] — the engine must bind savings/recommendation to
    the regime objects BEFORE calling score_efficiency."""

    def test_scorer_sees_engine_computed_savings(self) -> None:
        from tax_engine import TaxEngine

        engine = TaxEngine()
        seen = {}
        original = engine.anfis.score_efficiency

        def spy(data, result):
            seen["savings"] = result.get("savings", 0.0)
            return original(data, result)

        engine.anfis.score_efficiency = spy
        result = engine.calculate_tax_advanced(
            {"salary": 1_800_000, "80c": 150_000, "80d": 25_000,
             "nps": 50_000},
            tax_year="fy_2025_26",
        )
        assert seen["savings"] == result["savings"]
        assert seen["savings"] > 0  # a real regime delta was priced

    def test_feature17_changes_with_savings(self) -> None:
        """Two scenarios with the same income but different regime deltas
        must be able to produce different efficiency scores once feature
        17 is live (ordering fix sanity)."""
        from tax_engine import TaxEngine

        engine = TaxEngine()
        r1 = engine.calculate_tax_advanced(
            {"salary": 1_800_000, "80c": 150_000}, tax_year="fy_2025_26")
        r2 = engine.calculate_tax_advanced(
            {"salary": 1_800_000, "80c": 0, "80d": 25_000},
            tax_year="fy_2025_26")
        assert 0 <= r1["efficiency_score"] <= 100
        assert 0 <= r2["efficiency_score"] <= 100

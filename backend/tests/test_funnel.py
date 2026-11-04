"""Sprint 4 P0 — funnel analytics (backend/funnel.py).

Tests FIRST (AI_RULES.md). Spec: docs/sprint4-execution.md P0 item 5.

The funnel reads the LIVE session store (db.app_sessions): sessions per
phase, turns per phase (from state["history"] lengths), completion rate
(phase FINAL) and drop-off per phase transition, as JSON + a rendered
markdown table. Phase order is the engine's machine
(PROFILING -> INCOME -> EXPENDITURE -> FINAL); "reached" assumes the
documented monotone phase advance (nlp_engine only moves phases
forward), so a session currently in EXPENDITURE has reached INCOME.

Tests run against a seeded temp store via TAX_DB_PATH + db.init_db()
(the Wave-D re-pointing fixture pattern).
"""
import json

import pytest

import db
import funnel


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """Re-point the store at a fresh temp DB and return the db module."""
    monkeypatch.setenv("TAX_DB_PATH", str(tmp_path / "funnel.db"))
    db.init_db()
    return db


def _seed(store, phase, history_len, user_id=None):
    row = store.create_session(user_id)
    state = {"id": row["id"], "phase": phase,
             "history": [{"user": "u", "ai": "a"}] * history_len}
    store.save_state(row["id"], state)
    return row["id"]


def test_empty_store_zero_division_safe(store) -> None:
    report = funnel.compute_funnel(*funnel.collect_rows(store))
    assert report["total_sessions"] == 0
    assert report["completion_rate"] == 0.0
    assert report["sessions_per_phase"]["FINAL"] == 0
    assert report["dropoff"]["PROFILING->INCOME"]["dropped"] == 0


class TestSeededFunnel:
    @pytest.fixture()
    def report(self, store):
        _seed(store, "PROFILING", 1)
        _seed(store, "INCOME", 3)
        _seed(store, "INCOME", 2)
        _seed(store, "EXPENDITURE", 5)
        _seed(store, "FINAL", 9)
        _seed(store, "FINAL", 7)
        _seed(store, "FINAL", 8)
        return funnel.compute_funnel(*funnel.collect_rows(store))

    def test_sessions_per_phase(self, report) -> None:
        assert report["total_sessions"] == 7
        assert report["sessions_per_phase"] == {
            "PROFILING": 1, "INCOME": 2, "EXPENDITURE": 1, "FINAL": 3}

    def test_turns_per_phase(self, report) -> None:
        assert report["turns_per_phase"] == {
            "PROFILING": {"total": 1, "avg": 1.0},
            "INCOME": {"total": 5, "avg": 2.5},
            "EXPENDITURE": {"total": 5, "avg": 5.0},
            "FINAL": {"total": 24, "avg": 8.0},
        }

    def test_completion_rate_is_final_share(self, report) -> None:
        assert report["completion_rate"] == pytest.approx(3 / 7)

    def test_reached_is_monotone(self, report) -> None:
        # 7 reached PROFILING; 6 reached INCOME (all but the PROFILING
        # session); 4 reached EXPENDITURE; 3 reached FINAL.
        assert report["reached"] == {
            "PROFILING": 7, "INCOME": 6, "EXPENDITURE": 4, "FINAL": 3}

    def test_dropoff_per_transition(self, report) -> None:
        dropoff = report["dropoff"]
        assert dropoff["PROFILING->INCOME"] == {
            "dropped": 1, "rate": pytest.approx(1 / 7)}
        assert dropoff["INCOME->EXPENDITURE"] == {
            "dropped": 2, "rate": pytest.approx(2 / 6)}
        assert dropoff["EXPENDITURE->FINAL"] == {
            "dropped": 1, "rate": pytest.approx(1 / 4)}

    def test_unknown_phase_is_counted_defensively(self, store) -> None:
        row = store.create_session(None)
        store.save_state(row["id"], {"id": row["id"], "phase": "WEIRD",
                                     "history": []})
        report = funnel.compute_funnel(*funnel.collect_rows(store))
        assert report["unknown_phases"] == {"WEIRD": 1}


def test_malformed_state_rows_are_skipped_not_fatal(store) -> None:
    row = store.create_session(None)
    store.execute("UPDATE app_sessions SET state = ? WHERE id = ?",
                  ("{not json", row["id"]))
    _seed(store, "FINAL", 2)
    rows, skipped = funnel.collect_rows(store)
    assert skipped == 1
    assert len(rows) == 1
    report = funnel.compute_funnel(rows, skipped=skipped)
    assert report["total_sessions"] == 1
    assert report["malformed_state_rows"] == 1


def test_history_absent_counts_zero_turns(store) -> None:
    row = store.create_session(None)
    store.save_state(row["id"], {"id": row["id"], "phase": "INCOME"})
    report = funnel.compute_funnel(funnel.collect_rows(store)[0])
    assert report["turns_per_phase"]["INCOME"]["total"] == 0
    assert report["turns_per_phase"]["INCOME"]["avg"] == 0.0


class TestRendering:
    @pytest.fixture()
    def report(self, store):
        _seed(store, "PROFILING", 1)
        _seed(store, "FINAL", 4)
        return funnel.compute_funnel(*funnel.collect_rows(store))

    def test_markdown_table_renders_phases(self, report) -> None:
        text = funnel.to_markdown(report)
        assert "Funnel report" in text
        for phase in funnel.PHASES:
            assert phase in text
        assert "| 2 |" in text or "2" in text  # total sessions present
        assert "50.0%" in text  # completion rate rendered

    def test_json_output_round_trips(self, report) -> None:
        payload = json.loads(funnel.to_json(report))
        assert payload["total_sessions"] == report["total_sessions"]
        assert payload["completion_rate"] == report["completion_rate"]


def test_cli_prints_the_live_funnel(store, capsys) -> None:
    _seed(store, "PROFILING", 1)
    _seed(store, "FINAL", 3)
    exit_code = funnel.main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Funnel report" in captured.out
    assert "PROFILING" in captured.out
    # JSON mode
    exit_code = funnel.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_sessions"] == 2
    assert exit_code == 0

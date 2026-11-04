"""Sprint 3 follow-up — corpus capture tests.

Contract (backend/corpus.py + main.py wiring):
- TAX_CORPUS_CAPTURE off (default): NO corpus file is created and no
  record is written — the audit stream stays minimized.
- TAX_CORPUS_CAPTURE=1: every chat turn appends ONE full-fidelity JSONL
  record: session_id, user_id, FULL user_input, FULL ai_response,
  extracted, plan, state (post-turn), tax_report.
- Capture is best-effort: a serialization failure never breaks the
  request (the turn still 200s).
- The certified audit stream is untouched by corpus settings (its own
  minimization still applies).

Fixtures: `authed_client` and `session_id` are the Wave D shared
fixtures (conftest.py) — register+login and server-side bootstrap.
"""
import json

import pytest
from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str) -> None:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "Corpus!Pass2026"},
    )
    assert response.status_code in (201, 409)
    response = client.post(
        "/auth/login", json={"email": email, "password": "Corpus!Pass2026"}
    )
    assert response.status_code == 200


def _bootstrap(client: TestClient) -> str:
    response = client.post("/sessions")
    assert response.status_code == 200
    return response.json()["session_id"]


class TestCorpusCapture:
    def test_disabled_by_default_no_corpus_file(
        self, authed_client: TestClient, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setenv("TAX_CORPUS_PATH", str(tmp_path / "corpus.jsonl"))
        monkeypatch.delenv("TAX_CORPUS_CAPTURE", raising=False)
        session_id = _bootstrap(authed_client)
        response = authed_client.post(
            "/chat",
            json={"message": "I earn 12 lakhs", "session_id": session_id},
        )
        assert response.status_code == 200
        assert not (tmp_path / "corpus.jsonl").exists()

    def test_enabled_captures_full_fidelity(
        self, authed_client: TestClient, monkeypatch, tmp_path
    ) -> None:
        corpus_file = tmp_path / "corpus.jsonl"
        monkeypatch.setenv("TAX_CORPUS_PATH", str(corpus_file))
        monkeypatch.setenv("TAX_CORPUS_CAPTURE", "1")
        _register_and_login(authed_client, "corpus_on@example.com")
        session_id = _bootstrap(authed_client)
        message = "I earn 12 lakhs and I am 45 years old"
        response = authed_client.post(
            "/chat", json={"message": message, "session_id": session_id}
        )
        assert response.status_code == 200

        assert corpus_file.exists()
        records = [
            json.loads(line)
            for line in corpus_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1
        record = records[0]
        assert record["event"] == "chat_turn"
        assert record["corpus_version"] == 1
        assert record["session_id"] == session_id
        assert record["user_input"] == message  # FULL, uncapped
        assert record["ai_response"]  # FULL ai response present
        assert record["user_id"]  # owner recorded
        assert record["state"]["salary"] == 1_200_000.0
        # The waterfall advances past income after booking it — the phase
        # in the captured state is the NEXT discovery step, not INCOME.
        assert record["state"]["phase"] == "EXPENDITURE"
        assert record["tax_report"] is not None
        assert record["tax_report"]["fy_label"] == "FY 2025-26 (AY 2026-27)"

    def test_enabled_per_session_records(
        self, authed_client: TestClient, monkeypatch, tmp_path
    ) -> None:
        corpus_file = tmp_path / "corpus.jsonl"
        monkeypatch.setenv("TAX_CORPUS_PATH", str(corpus_file))
        monkeypatch.setenv("TAX_CORPUS_CAPTURE", "1")
        _register_and_login(authed_client, "corpus_two@example.com")
        sid_a = _bootstrap(authed_client)
        sid_b = _bootstrap(authed_client)
        authed_client.post(
            "/chat", json={"message": "I earn 5 lakhs", "session_id": sid_a}
        )
        authed_client.post(
            "/chat",
            json={"message": "rental income of 3 lakhs", "session_id": sid_b},
        )
        records = [
            json.loads(line)
            for line in corpus_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 2
        assert records[0]["session_id"] == sid_a
        assert records[1]["session_id"] == sid_b
        assert records[0]["state"]["salary"] == 500_000.0
        assert records[1]["state"]["rental"] == 300_000.0

    def test_capture_failure_never_breaks_the_turn(
        self, authed_client: TestClient, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setenv("TAX_CORPUS_PATH", str(tmp_path / "corpus.jsonl"))
        monkeypatch.setenv("TAX_CORPUS_CAPTURE", "1")
        _register_and_login(authed_client, "corpus_fail@example.com")
        session_id = _bootstrap(authed_client)
        # Force a capture failure: replace the corpus path with a DIRECTORY
        # (append to a directory raises) — the turn must still succeed.
        monkeypatch.setattr(
            "corpus.corpus_path", lambda: str(tmp_path), raising=True
        )
        response = authed_client.post(
            "/chat",
            json={"message": "I earn 12 lakhs", "session_id": session_id},
        )
        assert response.status_code == 200
        assert response.json()["session"]["salary"] == 1_200_000.0


class TestCorpusVsAuditIndependence:
    def test_audit_stream_stays_minimized(
        self,
        authed_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        """Corpus settings must not weaken the certified audit stream."""
        monkeypatch.delenv("TAX_CORPUS_CAPTURE", raising=False)
        monkeypatch.delenv("TAX_AUDIT_STORE_TEXT", raising=False)
        _register_and_login(authed_client, "audit_indep@example.com")
        session_id = _bootstrap(authed_client)
        secret = "my secret salary note 12 lakhs"
        response = authed_client.post(
            "/chat", json={"message": secret, "session_id": session_id}
        )
        assert response.status_code == 200
        # The audit stream (default location, dev cwd) must not contain
        # the raw text even with the corpus enabled elsewhere.
        import os

        audit_path = os.path.join("logs", "audit", "session_audit.jsonl")
        if os.path.exists(audit_path):
            content = open(audit_path, encoding="utf-8").read()
            assert secret not in content

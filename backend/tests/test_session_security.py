"""Session-id sanitization tests (ISSUE #1 — C6 arbitrary file write).

API level: /chat must 422 on traversal / absolute-path / non-ASCII / too-short
session ids and still accept the frontend-generated "sid_<epoch-ms>" shape and
sessions without an id. Unit level: SessionLab.record_turn must never write
outside its lab_dir even when called directly with a hostile id (defense in
depth behind the API validator).

Sprint 2 Step F (mechanical adaptation): the blackbox is an append-only
JSONL stream, so per-session files are now ``<sid>.jsonl`` instead of
``<sid>.json``.
"""
import os
import re

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# "untrusted_" + 16 lowercase hex digest chars + .jsonl — path-safe by
# construction (no separators, no traversal sequences).
_UNTRUSTED_FILE_RE = re.compile(r"^untrusted_[0-9a-f]{16}\.jsonl$")


@pytest.fixture(scope="module")
def client():
    previous_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    try:
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as test_client:
            yield test_client
    finally:
        os.chdir(previous_cwd)


class TestChatSessionIdValidation:
    @pytest.mark.parametrize(
        "bad_id",
        [
            "../evil",               # relative path traversal
            "C:\\Windows\\Temp\\x",  # absolute path (Windows drive letter)
            "síd_12345678",          # non-ASCII
            "ab",                    # below the 4-char minimum
        ],
    )
    def test_chat_rejects_unsafe_session_id(self, client, bad_id) -> None:
        response = client.post(
            "/chat",
            json={"message": "hi", "session": {"id": bad_id}},
        )
        assert response.status_code == 422

    def test_chat_accepts_frontend_shaped_session_id(self, client) -> None:
        response = client.post(
            "/chat",
            json={"message": "hi", "session": {"id": "sid_1730000000000"}},
        )
        assert response.status_code == 200

    def test_chat_missing_id_still_ok(self, client) -> None:
        response = client.post(
            "/chat",
            json={"message": "hi", "session": {"phase": "PROFILING"}},
        )
        assert response.status_code == 200


class TestSafeSessionId:
    def test_valid_id_passes_through_unchanged(self) -> None:
        from validation import is_valid_session_id, safe_session_id

        assert is_valid_session_id("default")
        assert is_valid_session_id("test_ping")
        assert is_valid_session_id("sid_1730000000000")
        assert safe_session_id("sid_1730000000000") == "sid_1730000000000"

    def test_invalid_id_maps_deterministically(self) -> None:
        from validation import is_valid_session_id, safe_session_id

        assert not is_valid_session_id("../evil")
        once = safe_session_id("../evil")
        again = safe_session_id("../evil")
        assert once == again  # stable audit name across turns
        assert _UNTRUSTED_FILE_RE.match(once + ".jsonl")


class TestSessionLabSanitization:
    TURN = {"input": "hi", "response": "hello", "state": {"salary": 100}}

    def test_hostile_id_writes_exactly_one_file_inside_lab_dir(
        self, tmp_path, monkeypatch
    ) -> None:
        from session_lab import SessionLab

        # Any accidental relative-path write would land here too.
        monkeypatch.chdir(tmp_path)
        lab = SessionLab(lab_dir=str(tmp_path))
        parent_before = set(os.listdir(tmp_path.parent))

        lab.record_turn("../evil", dict(self.TURN))

        entries = os.listdir(tmp_path)
        assert len(entries) == 1, entries
        name = entries[0]
        assert _UNTRUSTED_FILE_RE.match(name), name  # starts with "untrusted_"
        assert os.path.isfile(os.path.join(str(tmp_path), name))
        # Nothing appeared anywhere else in the pytest tmp tree.
        assert set(os.listdir(tmp_path.parent)) == parent_before

    def test_default_id_writes_default_jsonl(self, tmp_path) -> None:
        from session_lab import SessionLab

        lab = SessionLab(lab_dir=str(tmp_path))
        lab.record_turn("default", dict(self.TURN))
        assert os.listdir(tmp_path) == ["default.jsonl"]

"""Session-id sanitization tests (ISSUE #1 — C6 arbitrary file write).

Unit level: SessionLab.record_turn must never write outside its lab_dir
even when called directly with a hostile id (defense in depth behind the
API boundary), and validation.safe_session_id maps hostile ids to a
deterministic path-safe digest. Sprint 2 Step F: per-session files are
append-only ``<sid>.jsonl`` streams.

Wave D adaptation (mechanical, documented — design §10 / ADR-013): the
C6 attack surface is CLOSED BY CONSTRUCTION at the API — session ids are
SERVER-ISSUED uuid4 hex (POST /sessions), so no client-supplied id can
reach the filesystem path join anymore. The former "API rejects hostile
ids with 422" rows become the contract guard: an old-style body carrying
a session dict (with whatever id inside) is a 422 before any handler
logic, and a request without a session id is a 422 (the id is required
and never client-chosen). The sanitization units are unchanged and stay
pinned by the unit classes below (still load-bearing for the audit
stream + blackbox, which sanitize whatever id they are handed).
"""
import os
import re

import pytest

from tests.conftest import make_session

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# "untrusted_" + 16 lowercase hex digest chars + .jsonl — path-safe by
# construction (no separators, no traversal sequences).
_UNTRUSTED_FILE_RE = re.compile(r"^untrusted_[0-9a-f]{16}\.jsonl$")

# The hostile ids the old contract let clients send on /chat (C6). Wave D
# keeps them here as the documentation of what the wire can no longer
# carry: every one of them rides inside the legacy session-dict key, which
# the contract guard rejects before anything touches an id.
_BAD_IDS = [
    "../evil",               # relative path traversal
    "C:\\Windows\\Temp\\x",  # absolute path (Windows drive letter)
    "síd_12345678",          # non-ASCII
    "ab",                    # below the 4-char minimum
]


class TestChatSessionIdValidation:
    @pytest.mark.parametrize("bad_id", _BAD_IDS)
    def test_legacy_body_with_client_id_is_422(self, authed_client, bad_id) -> None:
        # Was: {"message", "session": {"id": bad_id}} -> 422 at the API
        # id validator. Wave D: the id is server-issued; the legacy body
        # shape itself is the 422 (contract guard fires pre-handler), so
        # no client-chosen id — hostile or not — can reach the write path.
        response = authed_client.post(
            "/chat",
            json={"message": "hi", "session": {"id": bad_id}},
        )
        assert response.status_code == 422

    def test_chat_accepts_server_issued_session_id(self, authed_client) -> None:
        # Was: the frontend-shaped "sid_<epoch-ms>" id was accepted. Wave
        # D: ids are SERVER-ISSUED uuid4 hex and /chat accepts them.
        sid = make_session(authed_client)
        response = authed_client.post(
            "/chat", json={"message": "hi", "session_id": sid}
        )
        assert response.status_code == 200

    def test_chat_without_session_id_is_422(self, authed_client) -> None:
        # Was: a session dict without an id was OK (the server used the
        # "default" bucket). Wave D: the id is REQUIRED and server-issued
        # — a body without one is a validation error, never an implicit id.
        response = authed_client.post("/chat", json={"message": "hi"})
        assert response.status_code == 422


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

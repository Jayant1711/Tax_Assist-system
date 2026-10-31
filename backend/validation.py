# Summer internship project
"""Session-id validation and sanitization (ISSUE #1 — C6 arbitrary file write).

Session ids arrive from the request body and were previously joined straight
into ``logs/blackbox/{session_id}.json`` by session_lab.py, so a crafted id
("../evil", "C:\\Windows\\Temp\\x", ...) could write files anywhere the
backend process can reach. Every id persisted to disk must therefore either
match SESSION_ID_PATTERN or be replaced by a deterministic, path-safe digest
(safe_session_id), so invalid ids stay auditable under a stable name instead
of being dropped (audit logging is never bypassed — it is sanitized).
"""
import hashlib
import re

# ASCII-only per security review. 4..64 chars keeps the legacy "default" id,
# ids like "test_ping", and the frontend-generated "sid_<epoch-ms>" ids
# valid, while rejecting traversal separators, drive letters and whitespace.
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,64}$")

_UNTRUSTED_PREFIX = "untrusted_"
_UNTRUSTED_DIGEST_LEN = 16


def is_valid_session_id(sid: str) -> bool:
    """Return True iff *sid* is a safe, allow-listed session id."""
    if not isinstance(sid, str):
        return False
    # fullmatch (not match): "$" alone would accept a trailing newline
    # ("abc123\n" must be rejected, not accepted).
    return SESSION_ID_PATTERN.fullmatch(sid) is not None


def safe_session_id(sid: str) -> str:
    """Return *sid* if valid, else a deterministic path-safe alias.

    Invalid ids are hashed instead of dropped so every turn remains
    auditable: repeated turns from the same untrusted id map to the same
    blackbox file name ("untrusted_<sha1[:16]>.json"), and the digest can
    never contain path separators or traversal sequences.
    """
    if not isinstance(sid, str):
        sid = str(sid)  # defense-in-depth: never raise inside record_turn
    if is_valid_session_id(sid):
        return sid
    digest = hashlib.sha1(sid.encode("utf-8", "replace")).hexdigest()[:_UNTRUSTED_DIGEST_LEN]
    return f"{_UNTRUSTED_PREFIX}{digest}"

# Summer internship project
"""The Industrial Black Box — per-session append-only JSONL turn recorder.

Sprint 2 Step F (ADR-009, H6 fix): the legacy per-session
read-modify-write ``logs/blackbox/<sid>.json`` (which lost turns under
concurrency and rewrote the whole file per turn) is replaced by an
append-only stream, ``logs/blackbox/<safe_sid>.jsonl`` — one compact
JSON line per turn, written with a single ``os.write`` per line under
the process-wide lock defined in audit_logger. The file is never
read-modify-written and never truncated; an unserializable value
produces the minimal redacted ``serialization_failure`` line instead of
skipping the turn.

The same PII minimization discipline as the global audit stream applies
at write time: raw user/AI free text is replaced by a correlation
record (sha256[:16] + char length; TAX_AUDIT_STORE_TEXT opt-in keeps a
512-char truncated copy) and the state snapshot is scrubbed of
``history`` / ``memory`` / ``_last_val`` / ``_prev_salary`` /
``_last_question`` / ``id``.

ORDERING CONTRACT: ``record_turn`` is called SYNCHRONOUSLY in the
request path (unlike AuditLogger, which writes from a background task),
so a turn is durably appended before the response is returned and the
lines of one session appear in request-arrival order. Each line is
atomic (one os.write under the lock), so concurrent requests interleave
whole lines, never partial ones. If this moves to a background queue,
the per-session ordering guarantee must be re-documented.
"""
import os
from datetime import datetime
from typing import Any, Dict

from audit_logger import (
    append_jsonl_line,
    compact_tax_summary,
    minimize_free_text,
    scrub_state,
    store_text_enabled,
)
from validation import safe_session_id


class SessionLab:
    """Records every turn of every session as one append-only JSONL line."""

    def __init__(self, lab_dir: str = "logs/blackbox") -> None:
        self.lab_dir = lab_dir
        os.makedirs(self.lab_dir, exist_ok=True)

    def record_turn(self, session_id: str, turn_data: Dict[str, Any]) -> None:
        """Appends one high-fidelity turn to the session's JSONL stream."""
        # C6 defense-in-depth: sanitize BEFORE anything else (and before
        # the path join below, so a traversal/absolute id can never reach
        # os.path.join even if a future caller bypasses the API-level
        # validator).
        session_id = safe_session_id(session_id)
        file_path = os.path.join(self.lab_dir, f"{session_id}.jsonl")
        store_text = store_text_enabled()
        entry: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event": "blackbox_turn",
            "user_input": minimize_free_text(turn_data.get("input"), store_text),
            "nlp_extraction": turn_data.get("extracted"),
            "agent_plan": turn_data.get("plan"),
            "ai_response": minimize_free_text(turn_data.get("response"), store_text),
            "state_snapshot": scrub_state(
                turn_data.get("state") or {}, extra_dropped=("id",)
            ),
        }
        if turn_data.get("audit") is not None:
            entry["final_audit"] = compact_tax_summary(turn_data.get("audit"))
        # Sprint 3 Wave D (additive): the app_sessions owner id rides on
        # the blackbox record when the turn was authenticated (mirrors the
        # audit stream's user_id field); omitted for anonymous demo turns.
        if turn_data.get("user_id") is not None:
            entry["user_id"] = turn_data.get("user_id")
        # Legacy compat: callers may pass arbitrary extras in turn_data
        # (e.g. tests); only recognized keys are persisted, and an
        # unserializable value routes to the redacted fallback line.
        append_jsonl_line(file_path, entry, session_id)

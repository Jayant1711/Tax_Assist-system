# Summer internship project
"""Full-fidelity corpus capture for test/verification dataset growth.

Sprint 3 follow-up (Sprint4_AI_Modernization.md §1 — dataset strategy):
every chat turn can be captured COMPLETE — session id, full user input,
full AI response, extraction deltas, plan, tax summary and the full
server-side state — so real interactions become golden regression
fixtures ("until we become perfect": every conversation is a test case).

Design:

- **Separate stream** (``TAX_CORPUS_PATH``, default
  ``logs/corpus/corpus.jsonl``) — the certified audit path
  (audit_logger.py) is deliberately NOT touched: the audit stream keeps
  its PII-minimized schema and the corpus carries the full-fidelity
  records the dataset strategy needs.
- **Opt-in**: ``TAX_CORPUS_CAPTURE=1``. Default OFF — full transcripts
  are PII (DPDP); enable only on deployments whose users consented
  (local dev / testing is the intended use).
- **Best-effort, never fatal**: a capture failure logs a warning and the
  chat turn is unaffected. The caller wraps the call in a background
  task.
- **Append-only**: writes go through ``audit_logger.append_jsonl_line``
  (same process-wide lock + torn-tail discipline as the audit stream).
  The corpus grows unbounded by design — prune/archive it like any
  dataset (see the converter: tests/tools/corpus_to_golden.py).
- **Full fidelity**: raw input + raw response are stored VERBATIM (no
  512-char cap — this stream exists because the capped audit stream is
  not enough for dataset work).
"""
import logging
import os
from typing import Any, Dict, Optional

from audit_logger import append_jsonl_line

logger = logging.getLogger(__name__)

CORPUS_VERSION = 1


def corpus_capture_enabled() -> bool:
    """TAX_CORPUS_CAPTURE opt-in flag (read at write time, default off)."""
    return os.environ.get("TAX_CORPUS_CAPTURE", "").strip() in {
        "1",
        "true",
        "True",
    }


def corpus_path() -> str:
    """Corpus stream location (TAX_CORPUS_PATH, documented default)."""
    return os.environ.get("TAX_CORPUS_PATH", "logs/corpus/corpus.jsonl")


def _json_safe(value: Any) -> Any:
    """Convert engine artifacts to JSON-safe types.

    Handles: numpy scalars (``.item()``), TaxResult dataclass instances
    (``dataclasses.asdict`` — the engine returns regime objects as
    dataclasses, and json.dumps rejects them), and containers of both.
    """
    import dataclasses

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_safe(dataclasses.asdict(value))
    if hasattr(value, "item"):  # numpy scalar -> Python scalar
        return value.item()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def capture_chat_turn(
    session_id: str,
    user_id: Optional[str],
    user_input: str,
    ai_response: str,
    extracted: Any,
    plan: Optional[str],
    state: Dict[str, Any],
    tax_report: Any,
) -> bool:
    """Append one full-fidelity chat-turn record to the corpus stream.

    Best-effort by contract: any failure logs a warning and returns False
    — the chat turn itself is never affected. Returns True when the line
    was captured.

    *session_id* must already be sanitized (``safe_session_id``) — the
    caller passes the server-issued id, which the store validated at
    creation.
    """
    if not corpus_capture_enabled():
        return False
    try:
        entry: Dict[str, Any] = _json_safe({
            "event": "chat_turn",
            "corpus_version": CORPUS_VERSION,
            "timestamp": _utcnow(),
            "session_id": session_id,
            "user_id": user_id,
            "user_input": user_input,
            "ai_response": ai_response,
            "extracted": extracted,
            "plan": plan,
            "state": state,
            "tax_report": tax_report,
        })
        path = corpus_path()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        append_jsonl_line(path, entry, session_id)
        return True
    except Exception as exc:  # best-effort: never break the chat turn
        logger.warning(
            "corpus capture failed (session_id_sha256_16=%.16s): %s",
            session_id,
            exc,
        )
        return False


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()

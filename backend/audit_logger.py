# Summer internship project
"""Append-only JSONL audit logging (Sprint 2 Step F — ADR-009, H6 fix).

Replaces the legacy read-modify-write ``session_audit.json`` (which lost
entries under concurrency and could destroy the whole trail on a read
error) with an append-only stream:

- Global stream: ``<log_dir>/audit/session_audit.jsonl`` (default
  ``logs/audit/session_audit.jsonl``); one compact JSON object per line,
  UTF-8, newline-terminated.
- Writes use ``os.open(O_APPEND|O_CREAT|O_WRONLY)`` plus exactly one
  ``os.write`` per line, under a module-wide ``threading.Lock``. The file
  is NEVER read-modify-written and NEVER truncated: a corrupt or
  non-newline-terminated tail is preserved byte-for-byte and the next
  write continues after it.
- Serialization failure (an unserializable value anywhere in the entry)
  writes a minimal redacted record (timestamp, session_id,
  ``event="serialization_failure"``) — the audit line is never skipped
  and the caller never sees an exception.
- PII minimization at write: raw ``user_input`` / ``ai_response`` free
  text and the state keys ``history`` / ``memory`` / ``_last_val`` /
  ``_prev_salary`` / ``_last_question`` are dropped; each dropped text is
  replaced by a correlation record (``sha256[:16]`` + char length).
  Opt-in raw text via ``TAX_AUDIT_STORE_TEXT`` (default off, 512-char cap).
- Rotation: ``TAX_AUDIT_MAX_BYTES`` (default 10,000,000) rotates the
  active stream to ``session_audit.jsonl.1`` after a write that pushes it
  over the limit, shifting older generations up; ``TAX_AUDIT_MAX_FILES``
  (default 5) archived generations are kept. Rotation is best-effort
  under the lock — a Windows reader conflict defers it to the next write
  (never loses a line, never truncates).
- Retention: ``TAX_AUDIT_RETENTION_DAYS`` (default 30) sweeps only
  rotated generations older than the window (by mtime); the ACTIVE file
  is never deleted. Invalid env ints fall back to the documented
  defaults via :func:`_env_int`.
- Reads are line-scans that skip malformed lines with a counted warning
  (``logging``, not ``print``) and never modify the file.
"""
import hashlib
import json
import logging
import math
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from validation import safe_session_id

logger = logging.getLogger(__name__)

# --- Documented configuration defaults (env-overridable, validated) --------
DEFAULT_MAX_BYTES = 10_000_000
DEFAULT_MAX_FILES = 5
DEFAULT_RETENTION_DAYS = 30

# Same truthy set as the TAX_ENABLE_HISTORY gate in main.py.
_TRUTHY_ENV_VALUES = frozenset({"1", "true", "True"})

# TAX_AUDIT_STORE_TEXT opt-in: keep the first N chars of dropped free text.
TEXT_TRUNCATE_CHARS = 512

STREAM_SUBDIR = "audit"
STREAM_FILENAME = "session_audit.jsonl"
LEGACY_FILENAME = "session_audit.json"  # read-only compat fallback

# PII minimization: state keys never persisted (dropped recursively).
DROPPED_STATE_KEYS = frozenset(
    {"history", "memory", "_last_val", "_prev_salary", "_last_question"}
)

# Compact tax totals: numeric totals kept per regime node, advisory text
# and risk level kept, verbose breakdowns (slabs, explanations, income
# details) dropped.
_TAX_TOTAL_KEYS = (
    "total_tax",
    "taxable_income",
    "gross_total_income",
    "total_deductions",
    "savings",
    "efficiency_score",
)
_TAX_STR_KEYS = ("recommendation", "risk_level")
_TAX_LIST_KEYS = ("audit_observations", "savings_tips")

# Process-wide write lock: every append (global stream AND per-session
# blackbox) serializes through this one lock, so lines never interleave.
_WRITE_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Environment parsing helpers (validated; invalid values -> documented defaults)
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Parse an integer env var; fall back to *default* when absent or invalid."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        logger.warning(
            "env %s=%r is not an integer; using documented default %d",
            name, raw, default,
        )
        return default
    if value < minimum:
        logger.warning(
            "env %s=%d is below the minimum %d; using documented default %d",
            name, value, minimum, default,
        )
        return default
    return value


def store_text_enabled() -> bool:
    """TAX_AUDIT_STORE_TEXT opt-in flag (read at write time, default off)."""
    return os.environ.get("TAX_AUDIT_STORE_TEXT", "") in _TRUTHY_ENV_VALUES


# ---------------------------------------------------------------------------
# PII minimization helpers
# ---------------------------------------------------------------------------


def minimize_free_text(text: Any, store_text: bool) -> Dict[str, Any]:
    """Correlation record for a dropped free-text field.

    Keeps ``sha256[:16]`` of the UTF-8 text plus its char length so audit
    consumers can correlate turns without ever persisting the raw words.
    With ``store_text`` (TAX_AUDIT_STORE_TEXT opt-in) the first
    ``TEXT_TRUNCATE_CHARS`` characters are also kept, truncated.
    """
    if text is None:
        return {"stored": False, "sha256_16": None, "char_length": 0}
    if not isinstance(text, str):
        # Non-string free text (defensive): hash the string form so the
        # correlation record stays comparable across turns.
        text = str(text)
    digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]
    record: Dict[str, Any] = {
        "stored": False,
        "sha256_16": digest,
        "char_length": len(text),
    }
    if store_text:
        record["stored"] = True
        record["text"] = text[:TEXT_TRUNCATE_CHARS]
    return record


def scrub_state(state: Any, extra_dropped: Optional[Iterable[str]] = None) -> Any:
    """Recursively drop PII/state-bloat keys from a session snapshot.

    Dropped keys (wherever they appear): ``history``, ``memory``,
    ``_last_val``, ``_prev_salary``, ``_last_question`` plus any
    ``extra_dropped``. Unknown object types are passed through UNCHANGED
    so they surface as a serialization-failure record instead of being
    silently stringified into the audit trail.
    """
    dropped = DROPPED_STATE_KEYS | frozenset(extra_dropped or ())

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items() if k not in dropped}
        if isinstance(obj, (list, tuple)):
            return [_walk(i) for i in obj]
        return obj

    return _walk(state)


def _compact_tax_node(data: Any) -> Dict[str, Any]:
    """Compact one regime-like node (TaxResult dataclass or dict) to totals."""
    out: Dict[str, Any] = {}

    def _get(key: str) -> Any:
        if isinstance(data, dict):
            return data.get(key)
        return getattr(data, key, None)

    for key in _TAX_TOTAL_KEYS:
        value = _get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if not math.isfinite(float(value)):
            continue  # a non-finite total would poison the strict JSON dump
        out[key] = float(value)
    for key in _TAX_STR_KEYS:
        value = _get(key)
        if isinstance(value, str):
            out[key] = value
    for key in _TAX_LIST_KEYS:
        value = _get(key)
        if isinstance(value, list) and all(isinstance(i, str) for i in value):
            out[key] = value  # advisory text/codes — bounded engine strings
    return out


def compact_tax_summary(results: Any) -> Any:
    """PII-safe compact tax totals for the audit line.

    Scalars (tax_year / assessment_year / fy_label / recommendation /
    savings / efficiency_score) pass through; regime objects compact to
    their numeric totals + advisory lists. ``None``/falsy keeps the legacy
    ``"Pending"`` marker.
    """
    if not results:
        return "Pending"
    if isinstance(results, dict):
        out: Dict[str, Any] = {}
        for key, value in results.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                out[key] = value
            else:
                out[key] = _compact_tax_node(value)
        return out
    # Legacy compat: non-dict tax results were stringified by the old
    # logger; the engine never produces this shape.
    return str(results)


# ---------------------------------------------------------------------------
# Append-only line writing (one os.write per line, process-wide lock)
# ---------------------------------------------------------------------------


def _dumps_line(entry: Dict[str, Any]) -> bytes:
    """Strict, compact, UTF-8, newline-terminated JSON line.

    ``allow_nan=False`` keeps every emitted line valid JSON; nan/inf (and
    unserializable objects) raise, which routes to the redacted fallback
    record instead of corrupting the stream.
    """
    return (
        json.dumps(
            entry, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
    )


def _file_needs_leading_newline(path: str) -> bool:
    """True when *path* exists, is non-empty, and lacks a trailing newline.

    A crash between writes can leave a partial last line; appending
    directly would glue the next entry onto it and hide two records
    instead of one. This is a READ of the last byte only — the existing
    bytes are never modified (append-only discipline).
    """
    try:
        if os.path.getsize(path) == 0:
            return False
        with open(path, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            return fh.read(1) != b"\n"
    except OSError:
        return False


def _append_line_unlocked(path: str, payload: bytes) -> None:
    """Single O_APPEND write of *payload*. Never truncates, never rewrites."""
    try:
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    except OSError as exc:
        logger.error("audit stream %s: open failed (%s); line not written", path, exc)
        return
    try:
        written = os.write(fd, payload)
        if written != len(payload):  # pragma: no cover — short writes on
            logger.error(            # regular files are not expected
                "audit stream %s: short write (%d of %d bytes)",
                path, written, len(payload),
            )
    except OSError as exc:
        logger.error("audit stream %s: write failed (%s)", path, exc)
    finally:
        os.close(fd)


def _append_entry_unlocked(path: str, entry: Dict[str, Any], session_id: str) -> None:
    """Serialize + append one entry; on serialization failure write the
    minimal redacted record so the audit line is never skipped."""
    prefix = b"\n" if _file_needs_leading_newline(path) else b""
    try:
        payload = _dumps_line(entry)
    except (TypeError, ValueError) as exc:
        logger.warning(
            "audit stream %s: entry serialization failed (%s); "
            "writing minimal redacted record",
            path, type(exc).__name__,
        )
        fallback = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event": "serialization_failure",
        }
        payload = _dumps_line(fallback)
    _append_line_unlocked(path, prefix + payload)


def append_jsonl_line(path: str, entry: Dict[str, Any], session_id: str) -> None:
    """Append one entry as a JSONL line under the process-wide write lock.

    *session_id* must already be sanitized (``safe_session_id``) — it is
    used verbatim in the redacted fallback record.
    """
    with _WRITE_LOCK:
        _append_entry_unlocked(path, entry, session_id)


# ---------------------------------------------------------------------------
# AuditLogger — global stream
# ---------------------------------------------------------------------------


class AuditLogger:
    """Append-only JSONL audit trail for every user-AI interaction.

    The constructor keeps the legacy ``log_dir`` parameter (tests pass a
    tmp dir); the stream lives at ``<log_dir>/audit/session_audit.jsonl``.
    Rotation/retention sizes may be preset via the constructor or come
    from the validated env vars at construction time.
    """

    def __init__(
        self,
        log_dir: str = "logs",
        max_bytes: Optional[int] = None,
        max_files: Optional[int] = None,
        retention_days: Optional[int] = None,
        store_text: Optional[bool] = None,
    ) -> None:
        self.log_dir = log_dir
        self.audit_dir = os.path.join(self.log_dir, STREAM_SUBDIR)
        os.makedirs(self.audit_dir, exist_ok=True)
        self.log_file = os.path.join(self.audit_dir, STREAM_FILENAME)
        # Legacy read-modify-write trail (read-only compat for /history).
        self.legacy_file = os.path.join(self.log_dir, LEGACY_FILENAME)

        self.max_bytes = (
            max_bytes if max_bytes is not None
            else _env_int("TAX_AUDIT_MAX_BYTES", DEFAULT_MAX_BYTES)
        )
        self.max_files = (
            max_files if max_files is not None
            else _env_int("TAX_AUDIT_MAX_FILES", DEFAULT_MAX_FILES)
        )
        self.retention_days = (
            retention_days if retention_days is not None
            else _env_int("TAX_AUDIT_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)
        )
        self._store_text_override = store_text

        # Startup sweep (and post-rotation sweeps) apply the retention
        # window to ARCHIVED generations only — the active file is never
        # deleted by this class.
        self._sweep_rotated()

    # -- write path ---------------------------------------------------------

    def log_interaction(
        self,
        session_id: str,
        input_text: str,
        response: str,
        session_state: Dict[str, Any],
        tax_results: Any = None,
        extracted: Any = None,
        plan: Any = None,
    ) -> None:
        """Append one minimized interaction record. Never raises to the caller.

        PII minimization at write: raw input/response text and the dropped
        state keys never reach disk; a correlation hash + char length does.
        An unserializable value produces the minimal redacted record.
        """
        safe = safe_session_id(session_id)
        store = self._store_text()
        entry: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "session_id": safe,
            "event": "chat_turn",
            "user_input": minimize_free_text(input_text, store),
            "ai_response": minimize_free_text(response, store),
            "extracted": extracted if isinstance(extracted, list) else [],
            "internal_state": scrub_state(session_state),
            "tax_calculation": compact_tax_summary(tax_results),
        }
        if isinstance(plan, str):
            entry["plan"] = plan

        with _WRITE_LOCK:
            _append_entry_unlocked(self.log_file, entry, safe)
            # Rotation and retention run best-effort under the lock; a
            # Windows reader conflict defers them to a later write.
            self._rotate_if_needed()
            self._sweep_rotated()

    def _store_text(self) -> bool:
        if self._store_text_override is not None:
            return self._store_text_override
        return store_text_enabled()

    # -- rotation / retention ----------------------------------------------

    def _rotate_if_needed(self) -> None:
        """Archive the active stream when it exceeds max_bytes (best effort).

        Generations shift up (.N -> .N+1) oldest-first and the active file
        becomes .1, so concatenating .max_files ... .1 then the active
        stream replays every line in write order. A failed replace (e.g. a
        Windows reader holding the file) defers the whole rotation to the
        next write: lines are never lost and nothing is truncated.
        """
        try:
            if os.path.getsize(self.log_file) <= self.max_bytes:
                return
        except OSError:
            return  # stream absent (e.g. just rotated by another writer)

        for n in range(self.max_files - 1, 0, -1):
            src = f"{self.log_file}.{n}"
            if not os.path.exists(src):
                continue  # empty slot from a previously deferred rotation
            try:
                os.replace(src, f"{self.log_file}.{n + 1}")
            except OSError as exc:
                logger.warning(
                    "audit rotation deferred: cannot shift %s (%s)", src, exc
                )
                return
        try:
            os.replace(self.log_file, f"{self.log_file}.1")
        except OSError as exc:
            logger.warning(
                "audit rotation deferred: cannot archive active stream (%s)", exc
            )
            return
        logger.info(
            "audit stream rotated at > %d bytes (%d generations kept)",
            self.max_bytes, self.max_files,
        )

    def _sweep_rotated(self) -> None:
        """Delete archived generations older than the retention window.

        Only ``session_audit.jsonl.N`` files are candidates; the ACTIVE
        stream is never deleted here.
        """
        if self.retention_days <= 0:
            # Defensive: the env path is validated, but a direct
            # constructor override must never mean "delete everything".
            return
        cutoff = time.time() - self.retention_days * 86400
        for n in range(1, self.max_files + 1):
            gen = f"{self.log_file}.{n}"
            try:
                stat = os.stat(gen)
            except OSError:
                continue
            if stat.st_mtime < cutoff:
                try:
                    os.remove(gen)
                    logger.info("audit retention: removed expired generation %s", gen)
                except OSError as exc:
                    logger.warning(
                        "audit retention: could not remove %s (%s)", gen, exc
                    )

    # -- read path (public, for tests and /history) --------------------------

    def read_entries(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int, bool]:
        """Line-scan the global stream. NEVER modifies the file.

        Returns ``(entries, corrupt_lines_skipped, has_more)``: parsed
        entries (paginated when *limit* is given), the number of skipped
        malformed lines, and whether further entries exist beyond the
        page. Malformed lines are skipped with a counted warning.
        """
        return self._scan_stream(
            self.log_file, filter_sid=None, limit=limit, offset=offset
        )

    def read_session_entries(
        self, session_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int, bool]:
        """Like :meth:`read_entries` but only entries for *session_id*.

        The id is sanitized with ``safe_session_id`` first, so a hostile
        id filters against the same deterministic name the writer stored.
        """
        safe = safe_session_id(session_id)
        return self._scan_stream(
            self.log_file, filter_sid=safe, limit=limit, offset=offset
        )

    def _scan_stream(
        self,
        path: str,
        filter_sid: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int, bool]:
        corrupt = 0
        matches: List[Dict[str, Any]] = []
        if not os.path.exists(path):
            return [], 0, False
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        corrupt += 1
                        continue
                    if not isinstance(entry, dict):
                        corrupt += 1
                        continue
                    if filter_sid is not None and entry.get("session_id") != filter_sid:
                        continue
                    matches.append(entry)
        except OSError as exc:
            # Availability, not integrity: serve what was scanned, never
            # touch the file.
            logger.error("audit stream %s: read failed (%s)", path, exc)
        if corrupt:
            logger.warning(
                "audit stream %s: skipped %d corrupt line(s); file left untouched",
                path, corrupt,
            )
        start = max(0, offset)
        if limit is not None:
            page = matches[start:start + limit]
            has_more = len(matches) > start + limit
        else:
            page = matches[start:]
            has_more = False
        return page, corrupt, has_more

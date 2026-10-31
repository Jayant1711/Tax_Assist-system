# Summer internship project
"""Structured observability (Sprint 3 Wave H — design §7).

Three cooperating pieces, all stdlib:

1. **Request context** — contextvars carrying ``request_id`` /
   ``user_id`` / ``path`` / ``status`` / ``duration_ms`` for the current
   request. :class:`RequestContextFilter` stamps every LogRecord that
   reaches a handler it is attached to, so ANY logger's line (ours, the
   audit module's failure logs, third-party libraries') is correlated
   with the request it happened inside — without each call site passing
   the values around. Outside a request (startup, background sweeps) the
   fields are ``None`` and simply omitted from the output.

2. **JSON log shape** — :class:`JsonFormatter` emits one compact JSON
   object per record with exactly the design fields: timestamp, level,
   logger, message, request_id, user_id, path, status, duration_ms
   (request fields via the contextvars filter), plus ``error`` (and the
   traceback for ERROR+) when the record carries ``exc_info``.

3. **Wiring** — :func:`setup_logging` attaches the console handler
   (human-readable in dev, JSON in prod for container log collection)
   and the app-log handler to the root logger at ``TAX_LOG_LEVEL``
   (config.tax_log_level). Re-running it REPLACES the previously
   installed handlers, so repeated ``create_app`` calls (tests, app
   factory) never duplicate lines.

App-log persistence: ``logs/app/app.jsonl`` through the audit module's
rotation helpers — :class:`JsonlAppLogHandler` appends with the same
single-``os.write``-per-line discipline under the audit stream's
process-wide lock and rotates/retains via
``AuditLogger._rotate_if_needed`` / ``._sweep_rotated``, driven by the
``TAX_APP_LOG_MAX_BYTES`` / ``TAX_APP_LOG_MAX_FILES`` /
``TAX_APP_LOG_RETENTION_DAYS`` env vars (same defaults pattern as the
TAX_AUDIT_* family). The handler never holds an open file descriptor
between records and never raises into the application: on its own write
failure it falls back to stderr and drops the line (logging must never
break the app, and the re-entrancy guard prevents recursion).

Request-ID middleware: :class:`RequestIdMiddleware` issues a fresh
``uuid4`` hex per request (an INBOUND ``X-Request-ID`` is deliberately
NOT trusted — it never reaches the logs), returns it as the
``X-Request-ID`` response header, sets the request context for
everything downstream, and emits ONE structured access record per
request (method, path, status, duration) — never headers, cookies or
bodies. Unhandled exceptions still emit the access record (status 500)
before re-raising into the server error middleware.
"""
import json
import logging
import os
import sys
import threading
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, List, MutableMapping, Optional

import config
from audit_logger import (
    AuditLogger,
    _append_line_unlocked,
    _dumps_line,
    _env_int,
    _file_needs_leading_newline,
)

logger = logging.getLogger(__name__)

# --- Request context (contextvars) ------------------------------------------

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("request_user_id", default=None)
request_path_var: ContextVar[Optional[str]] = ContextVar("request_path", default=None)
request_status_var: ContextVar[Optional[int]] = ContextVar("request_status", default=None)
request_duration_var: ContextVar[Optional[float]] = ContextVar(
    "request_duration_ms", default=None
)


def set_request_context(request_id: str, path: str) -> None:
    """Enter the request context (called by RequestIdMiddleware)."""
    request_id_var.set(request_id)
    request_path_var.set(path)


def set_request_result(status: int, duration_ms: float) -> None:
    """Record the response outcome for the access record."""
    request_status_var.set(int(status))
    request_duration_var.set(round(duration_ms, 2))


def annotate_request_user(scope: MutableMapping[str, Any], user_id: str) -> None:
    """Attach the authenticated user to the current request context.

    Two channels on purpose:
      - the ``user_id`` contextvar decorates every log line emitted
        downstream (the route handler and anything it calls);
      - ``scope['state']['user_id']`` is a plain dict shared with the
        middleware task, which reads it back for the access record
        (contextvar sets inside a downstream task/thread do not
        propagate back to the middleware's context).
    """
    user_id_var.set(user_id)
    state = scope.setdefault("state", {})
    if isinstance(state, dict):  # defensive: never break a request over logging
        state["user_id"] = user_id


def current_request_id() -> Optional[str]:
    """The active request id, or None outside a request."""
    return request_id_var.get()


class RequestContextFilter(logging.Filter):
    """Stamps every record with the request-context fields."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.path = request_path_var.get()
        record.status = request_status_var.get()
        record.duration_ms = request_duration_var.get()
        return True


# --- Formatters --------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """One compact JSON object per record (design §7 field set)."""

    # Request-scoped fields are stamped by RequestContextFilter and only
    # emitted when known, so non-request lines stay minimal.
    _CONTEXT_FIELDS = ("request_id", "user_id", "path", "status", "duration_ms")

    def to_entry(self, record: logging.LogRecord) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                entry[field] = value
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            if exc_type is not None:
                entry["error"] = (
                    f"{exc_type.__name__}: {exc_value}"
                    if exc_value is not None
                    else exc_type.__name__
                )
            if record.levelno >= logging.ERROR:
                # Full traceback on ERROR+ only: debuggability where it
                # matters, compact lines everywhere else. JSON-escaped,
                # so the record is still one line.
                entry["traceback"] = self.formatException(record.exc_info)
        return entry

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(self.to_entry(record), ensure_ascii=False, default=str)


# --- App log (logs/app/app.jsonl) — audit rotation mechanics -----------------

APP_LOG_SUBDIR = "app"
APP_LOG_FILENAME = "app.jsonl"
# session_id for the redacted fallback record path (safe_session_id-valid).
APP_LOG_SESSION_ID = "app_log"


class _AuditRotationAdapter:
    """Reuses AuditLogger's rotation/retention helpers verbatim (design §7).

    Both helpers (``_rotate_if_needed`` / ``_sweep_rotated``) are
    attribute-driven — they touch exactly ``log_file`` / ``max_bytes`` /
    ``max_files`` / ``retention_days`` and nothing else on the instance —
    so a shell instance built via ``__new__`` (skipping AuditLogger's
    own directory/legacy-file setup) exposes precisely the surface they
    need. This keeps ONE rotation implementation for the audit stream
    and the app log: same generation shifting, same best-effort
    semantics, same retention rules.
    """

    def __init__(
        self,
        log_file: str,
        max_bytes: int,
        max_files: int,
        retention_days: int,
    ) -> None:
        engine = AuditLogger.__new__(AuditLogger)
        engine.log_file = log_file
        engine.max_bytes = max_bytes
        engine.max_files = max_files
        engine.retention_days = retention_days
        self._engine = engine

    def rotate_and_sweep(self) -> None:
        """Best-effort rotation + retention sweep (call under _WRITE_LOCK)."""
        self._engine._rotate_if_needed()
        self._engine._sweep_rotated()


class JsonlAppLogHandler(logging.Handler):
    """Append-only JSONL app log sharing the audit stream's write helpers.

    Every record is serialized by :class:`JsonFormatter` and appended
    with the audit module's single-``os.write`` discipline (never
    read-modify-write, never truncated); rotation/retention reuse the
    audit helpers (see :class:`_AuditRotationAdapter`). Sizes may be
    preset (tests) or come from the validated ``TAX_APP_LOG_*`` env vars
    (same defaults pattern as TAX_AUDIT_*: 10 MB / 5 files / 30 days).

    Concurrency/deadlock note: the handler uses its OWN per-instance
    lock, NOT the audit stream's process-wide ``_WRITE_LOCK``. A logging
    handler that acquires a lock other code holds while IT logs would
    deadlock the moment anything logs inside that lock (the audit write
    path logs rotation/retention notices) — with a private lock the only
    logging-under-lock is this handler's own re-entrancy, which the
    per-thread guard stops. Records logged while rotation notices are
    emitted simply skip the app log (they still reach the console).
    """

    DEFAULT_MAX_BYTES = 10_000_000
    DEFAULT_MAX_FILES = 5
    DEFAULT_RETENTION_DAYS = 30

    def __init__(
        self,
        path: str,
        max_bytes: Optional[int] = None,
        max_files: Optional[int] = None,
        retention_days: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.path = os.path.abspath(path)
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        self.max_bytes = (
            max_bytes
            if max_bytes is not None
            else _env_int("TAX_APP_LOG_MAX_BYTES", self.DEFAULT_MAX_BYTES)
        )
        self.max_files = (
            max_files
            if max_files is not None
            else _env_int("TAX_APP_LOG_MAX_FILES", self.DEFAULT_MAX_FILES)
        )
        self.retention_days = (
            retention_days
            if retention_days is not None
            else _env_int("TAX_APP_LOG_RETENTION_DAYS", self.DEFAULT_RETENTION_DAYS)
        )
        self._rotator = _AuditRotationAdapter(
            self.path, self.max_bytes, self.max_files, self.retention_days
        )
        self._json_formatter = JsonFormatter()
        self._write_lock = threading.Lock()
        self._tls = threading.local()  # per-THREAD re-entrancy guard

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(self._tls, "emitting", False):
            # Records logged from inside our own locked section (rotation
            # notices, append failures) must not recurse into us — drop
            # them here; they still reach every other handler.
            return
        self._tls.emitting = True
        try:
            payload = self._serialize(record)
            with self._write_lock:
                # Same append discipline as the audit stream: the partial
                # leading-newline repair, then exactly one os.write per
                # line (never truncate, never rewrite).
                prefix = b"\n" if _file_needs_leading_newline(self.path) else b""
                _append_line_unlocked(self.path, prefix + payload)
                self._rotator.rotate_and_sweep()
        except Exception:
            self._fallback(record)
        finally:
            self._tls.emitting = False

    def _serialize(self, record: logging.LogRecord) -> bytes:
        """One compact newline-terminated JSON line.

        A serialization failure (unserializable/non-finite value anywhere
        in the record) writes the minimal redacted record instead of
        skipping the line — same discipline as the audit stream.
        """
        try:
            entry = self._json_formatter.to_entry(record)
            return _dumps_line(entry)
        except (TypeError, ValueError):
            return _dumps_line(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "session_id": APP_LOG_SESSION_ID,
                    "event": "serialization_failure",
                }
            )

    def _fallback(self, record: logging.LogRecord) -> None:
        # The app log itself failed (disk full, permissions, ...): emit a
        # one-line notice on stderr and drop the record. Never raise into
        # the application from a logging handler.
        try:
            sys.stderr.write(
                "app log %s: write failed for record from %s\n" % (self.path, record.name)
            )
        except Exception:  # pragma: no cover — stderr unavailable
            pass


# --- Wiring -------------------------------------------------------------------

# Handlers installed by the most recent setup_logging call; replaced (not
# duplicated) on re-invocation so repeated create_app calls never multiply
# log lines.
_INSTALLED_HANDLERS: List[logging.Handler] = []


def build_console_handler(app_env: str) -> logging.Handler:
    """stdout handler: human-readable in dev, JSON in prod."""
    handler = logging.StreamHandler(sys.stdout)
    if app_env == "prod":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s %(message)s")
        )
    return handler


def build_app_log_handler(log_dir: str = "logs") -> JsonlAppLogHandler:
    """``<log_dir>/app/app.jsonl`` with the TAX_APP_LOG_* rotation envs."""
    return JsonlAppLogHandler(os.path.join(log_dir, APP_LOG_SUBDIR, APP_LOG_FILENAME))


def setup_logging(app_env: str = "dev", log_dir: str = "logs") -> None:
    """Wire root logging for *app_env*; idempotent (replaces handlers).

    - level: ``TAX_LOG_LEVEL`` (validated by config.tax_log_level).
    - console: dev -> human-readable, prod -> JSON (container collection).
    - app log: ``logs/app/app.jsonl`` (audit rotation mechanics) in BOTH
      environments — the file is the durable operational record.
    """
    root = logging.getLogger()

    for handler in _INSTALLED_HANDLERS:
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # pragma: no cover — close() is best-effort
            pass
    _INSTALLED_HANDLERS.clear()

    root.setLevel(config.tax_log_level())
    context_filter = RequestContextFilter()

    console = build_console_handler(app_env)
    console.addFilter(context_filter)
    root.addHandler(console)
    _INSTALLED_HANDLERS.append(console)

    app_log = build_app_log_handler(log_dir)
    app_log.addFilter(context_filter)
    root.addHandler(app_log)
    _INSTALLED_HANDLERS.append(app_log)


# --- Request-ID middleware ----------------------------------------------------


class RequestIdMiddleware:
    """Fresh uuid4 request id per request + ``X-Request-ID`` response header.

    ASGI-level (not BaseHTTPMiddleware) so it stays cheap: it only sets
    the request context, stamps the response header and emits the access
    record. An inbound ``X-Request-ID`` is deliberately ignored — the id
    in our logs must be ours (fresh uuid4), never client-chosen.

    The access record (one INFO line per request: method, path, status,
    duration_ms, request_id, user_id when authenticated) is the ONLY
    thing this middleware logs — never headers, cookies, or bodies.
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        self._access_logger = logging.getLogger("observability.access")

    async def __call__(self, scope: MutableMapping[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":  # lifespan / websocket: pass through
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        method = scope.get("method", "")
        path = scope.get("path", "")
        set_request_context(request_id, path)
        start = time.perf_counter()

        status_holder: Dict[str, int] = {}

        async def send_wrapper(message: Any) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = message.setdefault("headers", [])
                headers.append((b"x-request-id", request_id.encode("ascii")))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # The 500 response is produced OUTSIDE this middleware (the
            # server error middleware is outermost), so no header lands
            # on it — but the access record below still carries the
            # request id, and the exception handler's logger.exception
            # is correlated through the context filter.
            duration_ms = (time.perf_counter() - start) * 1000
            set_request_result(500, duration_ms)
            self._emit_access_record(method, path, 500, scope)
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        status = status_holder.get("status", 0)
        set_request_result(status, duration_ms)
        self._emit_access_record(method, path, status, scope)

    def _emit_access_record(
        self, method: str, path: str, status: int, scope: MutableMapping[str, Any]
    ) -> None:
        state = scope.get("state")
        user_id = state.get("user_id") if isinstance(state, dict) else None
        token = user_id_var.set(user_id)  # for this record only
        try:
            self._access_logger.info("%s %s %s", method, path, status)
        finally:
            user_id_var.reset(token)

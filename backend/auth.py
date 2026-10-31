# Summer internship project
"""Auth core (Sprint 3 Wave C — design §1, ADR-012).

Password hashing, opaque session tokens, server-side session rows,
lockout state and the ``get_current_user`` FastAPI dependency. Zero new
runtime dependencies: ``hashlib.scrypt``, ``secrets``, ``hashlib``,
``hmac`` and the :mod:`db` SQLite store from design §2 (ADR-013).

Decisions implemented here (ADR-012, binding):

- **Passwords**: scrypt, stored as ``scrypt$N$r$p$salt_b64$hash_b64`` with
  n=2^15, r=8, p=1, dklen=64 and a 16-byte salt (~32 MiB, ~50-100 ms);
  verification via ``hmac.compare_digest``. A module-level dummy hash
  gives unknown emails the same scrypt cost as known ones (timing
  equalization against account enumeration). Policy: length 12-1024
  (NIST 800-63B style).
- **Tokens**: ``secrets.token_urlsafe(32)`` (256-bit); stored ONLY as
  sha256(token) hex. Sliding TTL (TAX_SESSION_TTL_MINUTES, default 30)
  capped by the absolute TTL (TAX_SESSION_ABS_TTL_HOURS, default 24).
  Revocation is a row update checked on every request.
- **Binding**: the User-Agent is hashed (sha256[:16]) into the row at
  issue time and re-checked on every use — a mismatch INVALIDATES the
  session. The IP is hashed for forensics (log-only, never enforced).
- **Lockout**: 5 failed logins lock the account for 15 minutes
  (``locked_until``); a success resets the counters. A locked account
  only ever shows the lockout response to a CORRECT password — a wrong
  password while locked gets the uniform 401, so the lockout itself is
  not an account-existence oracle.
- **Dependency**: :func:`get_current_user` resolves the session cookie
  (``__Host-ta_session`` when Secure else ``ta_session``), walks the
  checks (revoked / expiry / absolute / is_active / UA) and slides the
  TTL. ANY failure raises 401 ``{"detail": "Authentication required"}``
  — the response never hints which check failed.

All timestamps are timezone-aware ISO-8601 UTC strings via
:func:`db.utcnow_iso`, so string comparison equals chronological
comparison in SQL and in Python.
"""
import base64
import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request

import config
import db

logger = logging.getLogger(__name__)

# --- scrypt parameters (design §1: n=2^15, r=8, p=1, dklen=64, 16-byte salt)
SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
SCRYPT_SALT_BYTES = 16
# hashlib.scrypt's default maxmem (32 MiB) sits exactly at 128*N*r and
# rejects the parameters above — the documented posture needs the headroom.
_SCRYPT_MAXMEM = 64 * 1024 * 1024

# Bounds for parameters parsed back out of a stored hash string (a tampered
# row must not be able to escalate into an absurd scrypt cost).
_MIN_N, _MAX_N = 2 ** 10, 2 ** 21
_MIN_R, _MAX_R = 1, 64
_MIN_P, _MAX_P = 1, 8
_MAX_DKLEN = 256

# --- password policy (NIST 800-63B style length rule; no composition rules)
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 1024

# --- lockout (design §1: 5 failures -> 15 minutes)
LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15

# --- cookie names (design §1: __Host-ta_session when Secure else ta_session)
SESSION_COOKIE_HOST_PREFIX = "__Host-ta_session"
SESSION_COOKIE_PLAIN = "ta_session"

EMAIL_MAX_LENGTH = 254

# Pragmatic email shape: local part, @, dot-separated domain labels, alpha
# TLD of 2+. Length is capped separately (EMAIL_MAX_LENGTH).
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# Public per-row identifier: token_hash prefix (12 hex chars). The token
# hash itself never leaves the store; a 48-bit prefix is collision-safe
# for any realistic per-user session count.
SESSION_ROW_ID_LENGTH = 12
_ROW_ID_RE = re.compile(r"^[0-9a-f]{12}$")


# ---------------------------------------------------------------------------
# Password hashing (scrypt, ADR-012 format)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash *password* into the ADR-012 storage format."""
    salt = secrets.token_bytes(SCRYPT_SALT_BYTES)
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN)
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def _scrypt(
    password: str, salt: bytes, n: int, r: int, p: int, dklen: int
) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen,
        maxmem=_SCRYPT_MAXMEM,
    )


def verify_password(password: str, stored: Optional[str]) -> bool:
    """Constant-time verification against a stored scrypt string.

    Malformed/tampered stored strings verify as False — never an
    exception, never a weaker comparison.
    """
    if not stored or not isinstance(stored, str):
        return False
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        expected = base64.b64decode(parts[5], validate=True)
    except (ValueError, TypeError):
        return False
    if not (_MIN_N <= n <= _MAX_N and _MIN_R <= r <= _MAX_R and _MIN_P <= p <= _MAX_P):
        return False
    if not salt or not expected or len(expected) > _MAX_DKLEN:
        return False
    try:
        digest = _scrypt(password, salt, n, r, p, len(expected))
    except (ValueError, OverflowError):
        return False
    return hmac.compare_digest(digest, expected)


# Module-level dummy hash for unknown-email timing equalization: seeded
# from random bytes so it is not derived from any source string, verified
# against (never matched by) attacker input.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def verify_dummy(password: str) -> None:
    """Burn one scrypt verification for timing equalization (result ignored)."""
    verify_password(password, _DUMMY_HASH)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def normalize_email(email: str) -> Optional[str]:
    """Normalize *email* (trim + lowercase) or None when malformed."""
    if not isinstance(email, str):
        return None
    normalized = email.strip().lower()
    if not normalized or len(normalized) > EMAIL_MAX_LENGTH:
        return None
    if not _EMAIL_RE.match(normalized):
        return None
    return normalized


def validate_password(password: str) -> bool:
    """Password policy: a string of 12-1024 characters (any content)."""
    return isinstance(password, str) and (
        PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH
    )


# ---------------------------------------------------------------------------
# Hash helpers for token / UA / IP / email correlation
# ---------------------------------------------------------------------------


def new_token() -> str:
    """256-bit opaque session token (the raw value lives ONLY in the cookie)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """sha256 hex of the token — the ONLY form ever persisted or compared."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ua_hash(user_agent: str) -> str:
    """sha256[:16] of the User-Agent (bound at issue, checked on every use)."""
    return hashlib.sha256((user_agent or "").encode("utf-8")).hexdigest()[:16]


def ip_hash(ip: str) -> str:
    """sha256[:16] of the client IP (forensic log value — never enforced)."""
    return hashlib.sha256((ip or "").encode("utf-8")).hexdigest()[:16]


def email_hash(email: str) -> str:
    """sha256[:16] of the normalized email (audit correlation, never raw)."""
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]


def session_cookie_name() -> str:
    """Cookie name per current config (read at request time)."""
    return SESSION_COOKIE_HOST_PREFIX if config.tax_cookie_secure() else SESSION_COOKIE_PLAIN


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def find_user_by_email(email: str) -> Optional[sqlite3.Row]:
    return db.query_one("SELECT * FROM users WHERE email = ?", (email,))


def find_user_by_id(user_id: str) -> Optional[sqlite3.Row]:
    return db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))


def create_user(email: str, password_hash: str) -> sqlite3.Row:
    """Insert a password user; raises sqlite3.IntegrityError on duplicates."""
    user_id = str(secrets.token_hex(16))  # uuid4-equivalent randomness
    now = db.utcnow_iso()
    db.execute(
        "INSERT INTO users (id, email, password_hash, auth_provider, is_active,"
        " failed_logins, locked_until, created_at)"
        " VALUES (?, ?, ?, 'password', 1, 0, NULL, ?)",
        (user_id, email, password_hash, now),
    )
    row = find_user_by_id(user_id)
    assert row is not None  # the INSERT above just created it
    return row


def is_locked(user: sqlite3.Row) -> bool:
    """True while locked_until is in the future (string compare, same format)."""
    locked_until = user["locked_until"]
    return bool(locked_until) and locked_until > db.utcnow_iso()


def record_login_failure(user_id: str) -> bool:
    """Count one failed login; lock at LOCKOUT_THRESHOLD.

    Returns True when this failure TRIGGERED the lockout (the caller logs
    the lockout event exactly once).
    """
    user = find_user_by_id(user_id)
    if user is None:  # pragma: no cover — callers hold a live row
        return False
    failed = int(user["failed_logins"]) + 1
    if failed >= LOCKOUT_THRESHOLD:
        locked_until = (datetime.fromisoformat(db.utcnow_iso())
                        + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        db.execute(
            "UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
            (failed, locked_until, user_id),
        )
        return True
    db.execute(
        "UPDATE users SET failed_logins = ? WHERE id = ?", (failed, user_id)
    )
    return False


def record_login_success(user_id: str) -> None:
    """Reset the failure counters (design: reset on success)."""
    db.execute(
        "UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?",
        (user_id,),
    )


# ---------------------------------------------------------------------------
# Session rows (create / lookup / touch+slide / revoke / list)
# ---------------------------------------------------------------------------


@dataclass
class SessionRecord:
    """A live auth_sessions row (token hash is the PK, never exposed raw)."""

    token_hash: str
    user_id: str
    created_at: str
    last_used_at: str
    expires_at: str
    absolute_expires_at: str
    ua_hash: str
    ip_hash: str

    @property
    def public_id(self) -> str:
        return self.token_hash[:SESSION_ROW_ID_LENGTH]


def _now_plus_ttl() -> Tuple[str, str]:
    """(sliding expiry, absolute expiry) from the current env posture."""
    now = db.utcnow_iso()
    sliding = (
        datetime_from_iso(now) + timedelta(minutes=config.session_ttl_minutes())
    ).isoformat()
    absolute = (
        datetime_from_iso(now) + timedelta(hours=config.session_abs_ttl_hours())
    ).isoformat()
    return sliding, absolute


def datetime_from_iso(value: str):
    """Parse our own store-wide ISO-8601 format (fromisoformat handles it)."""
    return datetime.fromisoformat(value)


def create_session(
    user_id: str, user_agent: str, ip: str
) -> Tuple[str, SessionRecord]:
    """Issue a token, persist its hash, return (raw token, row record)."""
    token = new_token()
    token_hash = hash_token(token)
    now = db.utcnow_iso()
    sliding, absolute = _now_plus_ttl()
    db.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, created_at, last_used_at,"
        " expires_at, absolute_expires_at, revoked_at, ua_hash, ip_hash)"
        " VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)",
        (
            token_hash,
            user_id,
            now,
            now,
            sliding,
            absolute,
            ua_hash(user_agent),
            ip_hash(ip),
        ),
    )
    record = SessionRecord(
        token_hash=token_hash,
        user_id=user_id,
        created_at=now,
        last_used_at=now,
        expires_at=sliding,
        absolute_expires_at=absolute,
        ua_hash=ua_hash(user_agent),
        ip_hash=ip_hash(ip),
    )
    return token, record


def fetch_session_row(token_hash: str) -> Optional[sqlite3.Row]:
    """Raw auth_sessions row joined with its user (None when unknown)."""
    return db.query_one(
        "SELECT s.*, u.email, u.is_active FROM auth_sessions s"
        " JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
        (token_hash,),
    )


def touch_and_slide(token_hash: str, absolute_expires_at: str) -> str:
    """Refresh last_used_at and re-anchor the sliding TTL.

    The new sliding expiry is ``now + TAX_SESSION_TTL_MINUTES`` capped by
    the row's immutable absolute expiry. Returns the new expires_at.
    """
    now = db.utcnow_iso()
    candidate = (
        datetime_from_iso(now) + timedelta(minutes=config.session_ttl_minutes())
    ).isoformat()
    new_expires = candidate if candidate < absolute_expires_at else absolute_expires_at
    db.execute(
        "UPDATE auth_sessions SET last_used_at = ?, expires_at = ? WHERE token_hash = ?",
        (now, new_expires, token_hash),
    )
    return new_expires


def revoke_session(token_hash: str) -> None:
    """Revoke one session row (idempotent; first revocation time is kept)."""
    db.execute(
        "UPDATE auth_sessions SET revoked_at = ?"
        " WHERE token_hash = ? AND revoked_at IS NULL",
        (db.utcnow_iso(), token_hash),
    )


def revoke_session_by_public_id(user_id: str, public_id: str) -> bool:
    """Revoke the calling user's session whose token_hash has *public_id*.

    Owner-checked by construction (user_id is part of the WHERE). Returns
    whether a live row was found and revoked.
    """
    if not _ROW_ID_RE.match(public_id):
        return False
    conn = db.get_connection()
    with conn:
        cursor = conn.execute(
            "UPDATE auth_sessions SET revoked_at = ?"
            " WHERE user_id = ? AND revoked_at IS NULL"
            " AND substr(token_hash, 1, ?) = ?",
            (db.utcnow_iso(), user_id, SESSION_ROW_ID_LENGTH, public_id),
        )
        return cursor.rowcount > 0


def list_active_sessions(user_id: str) -> List[sqlite3.Row]:
    """The user's live sessions: not revoked, inside both TTL windows."""
    now = db.utcnow_iso()
    return db.query_all(
        "SELECT token_hash, created_at, last_used_at, expires_at"
        " FROM auth_sessions"
        " WHERE user_id = ? AND revoked_at IS NULL"
        " AND expires_at > ? AND absolute_expires_at > ?"
        " ORDER BY created_at",
        (user_id, now, now),
    )


# ---------------------------------------------------------------------------
# Login orchestration
# ---------------------------------------------------------------------------

# Outcome statuses for authenticate(): the endpoint maps them to
# 200/401/423 and never leaks which sub-check produced "invalid".
AUTH_OK = "ok"
AUTH_INVALID = "invalid"
AUTH_LOCKED = "locked"


def authenticate(
    email: Optional[str], password: str, user_agent: str, ip: str
) -> Dict[str, Any]:
    """Run the full login decision (ADR-012).

    - Unknown/invalid email -> dummy scrypt verify -> invalid (timing
      equalization: both failure paths cost the same scrypt).
    - Wrong password -> invalid + failure counter (lockout at 5).
    - Locked account -> verify FIRST: correct password yields "locked"
      (the 423 response), wrong password the plain uniform "invalid" —
      so the lockout response is not an enumeration oracle. Failures do
      not stack while locked (the timer stays anchored at trigger time).
    - Success -> counters reset, new session row, raw token returned.
    """
    user = find_user_by_email(email) if email else None
    if user is None:
        verify_dummy(password)
        return {"status": AUTH_INVALID}

    stored_hash = user["password_hash"]
    if stored_hash is None:
        # OAuth-only user (future): no password exists to verify — uniform
        # invalid without counting a failure (nothing was attempted).
        verify_dummy(password)
        return {"status": AUTH_INVALID}

    if is_locked(user):
        if verify_password(password, stored_hash):
            return {"status": AUTH_LOCKED, "user": user}
        return {"status": AUTH_INVALID, "user": user, "while_locked": True}

    if not verify_password(password, stored_hash):
        locked_now = record_login_failure(user["id"])
        result: Dict[str, Any] = {"status": AUTH_INVALID, "user": user}
        if locked_now:
            result["locked_now"] = True
        return result

    record_login_success(user["id"])
    token, record = create_session(user["id"], user_agent, ip)
    return {"status": AUTH_OK, "user": user, "token": token, "session": record}


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


@dataclass
class CurrentUser:
    """Identity resolved from the session cookie (what routes may rely on)."""

    user_id: str
    email: str
    expires_at: str
    token_hash: str

    @property
    def session_public_id(self) -> str:
        return self.token_hash[:SESSION_ROW_ID_LENGTH]


def _unauthorized() -> HTTPException:
    # One uniform failure for EVERY reason (missing/revoked/expired/
    # inactive/UA-mismatch): the response never hints which check failed.
    return HTTPException(status_code=401, detail="Authentication required")


def require_user(request: Request, audit: Any = None) -> CurrentUser:
    """Resolve the current user from the session cookie; 401 on any failure.

    Checks, in order: cookie present -> sha256 -> row exists -> not
    revoked -> inside sliding window -> inside absolute window -> user
    active -> UA hash matches (mismatch REVOKES the row). On success the
    row is touched and the sliding TTL re-anchored.

    *audit* is the caller's AuditLogger (auth events are sanitized:
    hashes only); when omitted, a module-level fallback logger is used.
    """
    token = request.cookies.get(session_cookie_name())
    if not token:
        raise _unauthorized()
    token_hash = hash_token(token)
    row = fetch_session_row(token_hash)
    if row is None:
        raise _unauthorized()
    now = db.utcnow_iso()
    if row["revoked_at"] is not None:
        raise _unauthorized()
    if row["expires_at"] <= now or row["absolute_expires_at"] <= now:
        raise _unauthorized()
    if not row["is_active"]:
        raise _unauthorized()
    if row["ua_hash"] != ua_hash(request.headers.get("user-agent", "")):
        # Session replay from a different client: invalidate the row so
        # even the original UA cannot reuse it, and record the revoke.
        revoke_session(token_hash)
        _log_auth_event(
            audit,
            "auth_session_revoke",
            user_id=row["user_id"],
            session_row_id=token_hash[:SESSION_ROW_ID_LENGTH],
            reason="ua_mismatch",
        )
        raise _unauthorized()

    new_expires = touch_and_slide(token_hash, row["absolute_expires_at"])
    return CurrentUser(
        user_id=row["user_id"],
        email=row["email"],
        expires_at=new_expires,
        token_hash=token_hash,
    )


def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency form of :func:`require_user` (module fallback audit)."""
    return require_user(request)


# ---------------------------------------------------------------------------
# Auth audit events (sanitized: hashes only, never raw email/token/password)
# ---------------------------------------------------------------------------

_FALLBACK_AUDIT = None


def _log_auth_event(audit: Any, event: str, **fields: Any) -> None:
    """Append one auth event via the caller's AuditLogger (or the fallback)."""
    logger_ref = audit if audit is not None else _fallback_audit()
    if logger_ref is None:  # pragma: no cover — AuditLogger never fails open
        return
    try:
        logger_ref.log_event(event, **fields)
    except Exception:  # noqa: BLE001 — audit must never break the request
        logger.warning("auth audit event %s could not be written", event)


def _fallback_audit():
    global _FALLBACK_AUDIT
    if _FALLBACK_AUDIT is None:
        from audit_logger import AuditLogger

        _FALLBACK_AUDIT = AuditLogger()
    return _FALLBACK_AUDIT


def log_auth_event(audit: Any, event: str, **fields: Any) -> None:
    """Public wrapper so endpoints share the same never-raise audit path."""
    _log_auth_event(audit, event, **fields)

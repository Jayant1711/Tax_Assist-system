# Summer internship project
"""SQLite store for server-side sessions (Sprint 3 Wave C — design §2, ADR-013).

The persistence layer for the auth core: users + auth_sessions tables in
a single SQLite database at ``TAX_DB_PATH`` (default ``data/taxassist.db``).

Design rules (Sprint 3 design §2):

- **WAL** journal mode, **foreign_keys ON** (the ``ON DELETE CASCADE``
  from auth_sessions to users is real), **busy_timeout 5000 ms** — the
  documented deployment is exactly one uvicorn worker (audit lock +
  SQLite correctness), so WAL + short transactions are sufficient.
- **Thread-local connections**: uvicorn serves sync endpoints from a
  threadpool, so every thread gets its own connection, created lazily by
  :func:`get_connection` against the currently-initialized path and
  re-created automatically if :func:`init_db` re-points the store.
- **Idempotent migrations**: ``CREATE TABLE IF NOT EXISTS`` statements
  versioned in a ``schema_migrations`` table. :func:`init_db` may be
  called any number of times (at import AND from tests); already-applied
  versions are skipped, and re-running never duplicates rows.
- **init_db() runs at import** so the store always exists before the
  first request; the database's parent directory is created when missing.
- No secrets exist in this system (ADR-012): session tokens are stored
  ONLY as sha256 hex digests; passwords as scrypt strings; the IP is
  hashed (log/forensics only — never enforced).

Schema (Sprint 3 design §2, verbatim columns):

    users(id TEXT PK, email TEXT UNIQUE COLLATE NOCASE, password_hash TEXT NULL,
          auth_provider TEXT DEFAULT 'password', oauth_subject TEXT, is_active INT 1,
          failed_logins INT 0, locked_until TEXT NULL, created_at TEXT,
          CHECK(password_hash IS NOT NULL OR auth_provider <> 'password'));
    auth_sessions(token_hash TEXT PK, user_id TEXT REFERENCES users ON DELETE CASCADE,
          created_at, last_used_at, expires_at, absolute_expires_at, revoked_at,
          ua_hash TEXT, ip_hash TEXT);

``app_sessions`` belongs to Wave D and is intentionally NOT created here.
Timestamps are timezone-aware ISO-8601 UTC strings, so lexicographic
comparison in SQL matches chronological order.
"""
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import config

logger = logging.getLogger(__name__)

BUSY_TIMEOUT_MS = 5000

# Migration 1 (Wave C): users + auth_sessions exactly per the design §2
# schema. Each migration is a tuple of statements applied atomically in
# one transaction together with its schema_migrations row.
_MIGRATIONS: Tuple[Tuple[int, str, Tuple[str, ...]], ...] = (
    (
        1,
        "users_auth_sessions",
        (
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NULL,
                auth_provider TEXT NOT NULL DEFAULT 'password',
                oauth_subject TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                failed_logins INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT NULL,
                created_at TEXT NOT NULL,
                CHECK(password_hash IS NOT NULL OR auth_provider <> 'password')
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                last_used_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                absolute_expires_at TEXT NOT NULL,
                revoked_at TEXT NULL,
                ua_hash TEXT,
                ip_hash TEXT
            )
            """,
        ),
    ),
)

# Module state: the resolved path of the active database. Guarded by a
# lock so concurrent init_db() calls cannot interleave the swap.
_state_lock = threading.Lock()
_db_path: Optional[str] = None

# Thread-local connection cache: (connection, path it was opened against).
_local = threading.local()


def utcnow_iso() -> str:
    """Timezone-aware UTC ISO-8601 timestamp (single store-wide format)."""
    return datetime.now(timezone.utc).isoformat()


def _connect(path: str) -> sqlite3.Connection:
    """Open a connection to *path* with the design's PRAGMA posture."""
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000.0)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db() -> str:
    """Create/point the store at TAX_DB_PATH and run pending migrations.

    Idempotent: safe to call repeatedly (it runs at import AND from
    tests that re-point the store via a fresh TAX_DB_PATH). Returns the
    resolved absolute database path.
    """
    path = os.path.abspath(config.tax_db_path())
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)  # DB dir created if missing

    conn = _connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied = {
            row[0] for row in conn.execute("SELECT version FROM schema_migrations")
        }
        for version, name, statements in _MIGRATIONS:
            if version in applied:
                continue
            with conn:  # one atomic transaction per migration
                for statement in statements:
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) "
                    "VALUES (?, ?, ?)",
                    (version, name, utcnow_iso()),
                )
            logger.info("database migration applied: %d %s", version, name)
    finally:
        conn.close()

    with _state_lock:
        global _db_path
        _db_path = path
    logger.info("database ready at %s", path)
    return path


def current_path() -> str:
    """Absolute path of the active database (import ran init_db)."""
    with _state_lock:
        if _db_path is None:
            raise RuntimeError("database not initialized")
        return _db_path


def get_connection() -> sqlite3.Connection:
    """Per-thread connection to the active database.

    Re-created lazily when the thread has no connection yet or when
    init_db() has re-pointed the store since the connection was opened.
    Each connection is only ever used by its creating thread, so
    sqlite3's default cross-thread protection stays active.
    """
    path = current_path()
    conn = getattr(_local, "conn", None)
    conn_path = getattr(_local, "conn_path", None)
    if conn is not None and conn_path != path:
        try:
            conn.close()
        except sqlite3.Error:  # pragma: no cover — close on stale conn
            pass
        conn = None
    if conn is None:
        conn = _connect(path)
        _local.conn = conn
        _local.conn_path = path
    return conn


# ---------------------------------------------------------------------------
# Thin query helpers (auth.py owns the auth semantics on top of these)
# ---------------------------------------------------------------------------


def execute(statement: str, parameters: tuple = ()) -> None:
    """Run one write statement and commit."""
    with get_connection() as conn:
        conn.execute(statement, parameters)


def query_one(statement: str, parameters: tuple = ()) -> Optional[sqlite3.Row]:
    """First row of a SELECT, or None."""
    cursor = get_connection().execute(statement, parameters)
    return cursor.fetchone()


def query_all(statement: str, parameters: tuple = ()) -> List[sqlite3.Row]:
    """All rows of a SELECT."""
    cursor = get_connection().execute(statement, parameters)
    return cursor.fetchall()


# init at import: the store always exists before the first request.
init_db()

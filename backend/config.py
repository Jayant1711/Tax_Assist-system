# Summer internship project
"""Environment plumbing (Sprint 3 Step A).

Single, documented access layer for every environment variable the
backend reads. Design rules:

- All accessors read the environment AT CALL TIME, so a variable can be
  flipped without a code change and tests can monkeypatch freely (the
  same read-at-request-time pattern the TAX_ENABLE_HISTORY gate uses).
- Parsing follows the audit_logger._env_int pattern: an absent, blank,
  or invalid value falls back to the DOCUMENTED DEFAULT with a logged
  warning — environment misconfiguration degrades to the safe default
  instead of crashing the process.
- CORS is FAIL-CLOSED in production: an unset, empty, or wildcard
  CORS_ORIGINS raises RuntimeError at the point of use. Dev defaults to
  the local frontend origin. NOTE (Sprint 3 Step B): the middleware
  stack still runs wildcard CORS this wave — the allowlist + allow_
  credentials=True switch lands with the auth wave (Wave C), when the
  cookie exists for it to protect; this module is the fail-closed stub
  that switch will consume.
- No secrets exist in this system (ADR-012): the session cookie's
  HttpOnly/Secure posture comes from APP_ENV / TAX_COOKIE_SECURE, not
  from a signing key.

Env inventory (Sprint 3 design §5):
APP_ENV (dev|prod) · CORS_ORIGINS · TAX_DB_PATH · TAX_HOST/TAX_PORT ·
TAX_SESSION_TTL_MINUTES / TAX_SESSION_ABS_TTL_HOURS · TAX_COOKIE_SECURE ·
TAX_ENABLE_ANON_DEMO · TAX_ENABLE_HISTORY (read at request time by
main.py's /history gate) · TAX_AUDIT_* (consumed by audit_logger; a
passthrough accessor is provided) · TAX_RATE_LIMIT_* ·
TAX_MAX_BODY_BYTES · TAX_LOG_LEVEL.
"""
import logging
import os
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# --- Documented defaults ----------------------------------------------------

APP_ENV_DEFAULT = "dev"
DEV_CORS_ORIGINS: Tuple[str, ...] = ("http://localhost:3000",)
DEFAULT_DB_PATH = "data/taxassist.db"
DEFAULT_HOST = "127.0.0.1"  # dev bind safety: never default to 0.0.0.0
DEFAULT_PORT = 8000
DEFAULT_SESSION_TTL_MINUTES = 30
DEFAULT_SESSION_ABS_TTL_HOURS = 24
DEFAULT_MAX_BODY_BYTES = 1_000_000
DEFAULT_LOG_LEVEL = "INFO"

# Per-minute sliding-window rate limits (Sprint 3 design §4). Per-user
# keys arrive with the auth wave; this wave buckets key on client IP.
DEFAULT_RATE_LIMIT_AUTH_PER_MIN = 10
DEFAULT_RATE_LIMIT_CHAT_PER_MIN = 30
DEFAULT_RATE_LIMIT_CALC_PER_MIN = 60
DEFAULT_RATE_LIMIT_GLOBAL_PER_MIN = 120

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "True"})  # same set as audit_logger
_FALSY_ENV_VALUES = frozenset({"0", "false", "False"})
_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _env_int(
    name: str, default: int, minimum: int = 1, maximum: Optional[int] = None
) -> int:
    """Parse an integer env var; fall back to *default* when absent/invalid.

    Mirrors audit_logger._env_int (documented default on any failure, with
    a warning). *minimum*/*maximum* bound the accepted range; out-of-range
    values fall back exactly like unparsable ones.
    """
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
    if value < minimum or (maximum is not None and value > maximum):
        logger.warning(
            "env %s=%d is outside the accepted range [%d, %s]; "
            "using documented default %d",
            name, value, minimum, "inf" if maximum is None else maximum, default,
        )
        return default
    return value


def _normalize_app_env(raw: Optional[str]) -> str:
    """Normalize APP_ENV: only the explicit value "prod" selects prod posture.

    Anything else (unset, "dev", "staging", typos) is dev — fail-safe,
    because dev keeps diagnostics enabled and never raises on config gaps.
    """
    if raw is not None and raw.strip().lower() == "prod":
        return "prod"
    return "dev"


# ---------------------------------------------------------------------------
# Accessors (call-time reads; see module docstring)
# ---------------------------------------------------------------------------


def app_env() -> str:
    """Deployment environment: "dev" (default) or "prod"."""
    return _normalize_app_env(os.environ.get("APP_ENV"))


def cors_origins() -> List[str]:
    """Parsed CORS allowlist; FAIL-CLOSED in production.

    - Dev: CORS_ORIGINS comma-list when set, else the local frontend
      origin (http://localhost:3000). A wildcard is tolerated in dev.
    - Prod: unset/empty/wildcard raises RuntimeError — the app must name
      its origins explicitly (the middleware that consumes this list, and
      allow_credentials=True, land with the auth wave).
    """
    raw = os.environ.get("CORS_ORIGINS")
    if raw is None or not raw.strip():
        if app_env() == "prod":
            raise RuntimeError(
                "CORS_ORIGINS is not set: production is fail-closed and "
                "refuses to serve wildcard/unset origins — set the exact "
                "browser-reachable origin list (comma-separated)."
            )
        return list(DEV_CORS_ORIGINS)
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if app_env() == "prod" and (not origins or origins == ["*"]):
        raise RuntimeError(
            "CORS_ORIGINS is empty or '*': production is fail-closed and "
            "refuses wildcard origins — set the exact browser-reachable "
            "origin list (comma-separated)."
        )
    return origins


def tax_host() -> str:
    """Bind host for the __main__ uvicorn entry (default 127.0.0.1)."""
    raw = os.environ.get("TAX_HOST", "").strip()
    return raw if raw else DEFAULT_HOST


def tax_port() -> int:
    """Bind port for the __main__ uvicorn entry (default 8000, 1..65535)."""
    return _env_int("TAX_PORT", DEFAULT_PORT, minimum=1, maximum=65535)


def tax_db_path() -> str:
    """SQLite database path (Sprint 3 server-side sessions, Wave C)."""
    raw = os.environ.get("TAX_DB_PATH", "").strip()
    return raw if raw else DEFAULT_DB_PATH


def session_ttl_minutes() -> int:
    """Sliding session TTL (auth wave; default 30 minutes)."""
    return _env_int("TAX_SESSION_TTL_MINUTES", DEFAULT_SESSION_TTL_MINUTES)


def session_abs_ttl_hours() -> int:
    """Absolute session cap (auth wave; default 24 hours)."""
    return _env_int("TAX_SESSION_ABS_TTL_HOURS", DEFAULT_SESSION_ABS_TTL_HOURS)


def tax_cookie_secure() -> bool:
    """Cookie Secure flag: TAX_COOKIE_SECURE overrides, else APP_ENV=prod."""
    raw = os.environ.get("TAX_COOKIE_SECURE", "").strip()
    if raw in _TRUTHY_ENV_VALUES:
        return True
    if raw in _FALSY_ENV_VALUES:
        return False
    return app_env() == "prod"


def tax_enable_anon_demo() -> bool:
    """Anonymous demo opt-in (deny-by-default; auth wave consumes this)."""
    return os.environ.get("TAX_ENABLE_ANON_DEMO", "") in _TRUTHY_ENV_VALUES


def tax_max_body_bytes() -> int:
    """Request-body cap enforced by the body-size middleware (default 1 MB)."""
    return _env_int("TAX_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES)


def tax_log_level() -> str:
    """Validated log level for the __main__ entry (default INFO)."""
    raw = os.environ.get("TAX_LOG_LEVEL", "").strip().upper()
    if raw in _LOG_LEVELS:
        return raw
    if raw:
        logger.warning(
            "env TAX_LOG_LEVEL=%r is not a valid level (%s); using %s",
            raw, ", ".join(sorted(_LOG_LEVELS)), DEFAULT_LOG_LEVEL,
        )
    return DEFAULT_LOG_LEVEL


# --- Rate-limit knobs (parsed here; enforced by main.py's middleware) -------


def rate_limit_auth_per_min() -> int:
    """Per-minute /auth/* limit (auth wave; default 10)."""
    return _env_int("TAX_RATE_LIMIT_AUTH_PER_MIN", DEFAULT_RATE_LIMIT_AUTH_PER_MIN)


def rate_limit_chat_per_min() -> int:
    """Per-minute /chat limit (default 30)."""
    return _env_int("TAX_RATE_LIMIT_CHAT_PER_MIN", DEFAULT_RATE_LIMIT_CHAT_PER_MIN)


def rate_limit_calc_per_min() -> int:
    """Per-minute /calculate limit (default 60)."""
    return _env_int("TAX_RATE_LIMIT_CALC_PER_MIN", DEFAULT_RATE_LIMIT_CALC_PER_MIN)


def rate_limit_global_per_min() -> int:
    """Aggregate per-minute cap across limited endpoints (default 120)."""
    return _env_int(
        "TAX_RATE_LIMIT_GLOBAL_PER_MIN", DEFAULT_RATE_LIMIT_GLOBAL_PER_MIN
    )


# --- TAX_AUDIT_* passthrough -------------------------------------------------
#
# audit_logger.py reads its own TAX_AUDIT_* variables at construction /
# write time (Sprint 2 control, unchanged). This passthrough exists so
# callers never reach into os.environ directly for those variables.


def tax_audit_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Raw passthrough for a TAX_AUDIT_* variable (no parsing)."""
    if not name.startswith("TAX_AUDIT_"):
        raise ValueError("tax_audit_env is only for TAX_AUDIT_* variables")
    value = os.environ.get(name)
    return value if value is not None else default


def rate_limit_knobs() -> Tuple[Tuple[str, Callable[[], int]], ...]:
    """(bucket-name, per-minute-limit accessor) pairs for the middleware."""
    return (
        ("auth", rate_limit_auth_per_min),
        ("chat", rate_limit_chat_per_min),
        ("calc", rate_limit_calc_per_min),
    )

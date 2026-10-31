# Summer internship project
"""Tax Assist AI API — FastAPI application (Sprint 3 Step A+B).

Sprint 3 Step A moved every piece of wiring into :func:`create_app`
(application factory): middleware stack, exception handlers, routes and
the docs gating. The module-level ``app`` is preserved so existing
imports/tests keep working; the ``__main__`` entry binds TAX_HOST /
TAX_PORT (defaults 127.0.0.1:8000 — dev bind safety, never 0.0.0.0).

Sprint 3 Step B adds the hardening edge. Request path through the
middleware stack, outermost first:

1. **body-cap** — Content-Length over TAX_MAX_BODY_BYTES -> 413.
2. **security-headers** — the fixed hardening set on EVERY response.
3. **origin-check** — a browser-declared ``Origin`` on a state-changing
   route must be in the allowlist (config.cors_origins), else 403. An
   absent Origin (same-origin script, curl, non-browser) passes THIS
   wave; the middleware already sits in the stack ahead of the cookies
   that land with the auth wave.
4. **rate-limit** — per-client-IP sliding windows (user-id keys land
   with auth): route-class bucket + shared global bucket, /health
   exempt, 429 with Retry-After. The /auth/* class bucket (10/min/IP)
   is ACTIVE as of Wave C.
5. **CORS** — Wave C retires the Sprint-1 wildcard permanently: the
   explicit allowlist (config.cors_origins) + allow_credentials=True
   now protect the session cookie issued by /auth/login; production
   fails closed at the config layer (unset/wildcard CORS_ORIGINS ->
   empty allowlist, no origin trusted).

Short-circuit responses (413/403/429) carry the security-header set too
— the headers control applies to every response the app emits.

``GET /health`` (public, rate-limit exempt) reports db (SELECT 1 against
TAX_DB_PATH via mode=rw — it NEVER creates the file) and audit
(logs/audit dir writable) checks; any failing check degrades the
response to 503 while naming the check. ``?verbose=1`` adds uptime +
registry keys in dev only. Prod also disables /docs, /redoc and
/openapi.json via the factory.

Sprint 3 Wave D (server-side sessions, ADR-013) swaps the wire contract:
the client no longer carries session state. ``app_sessions`` rows in the
SQLite store own the state ({message, session_id} in, projection out):

- POST /sessions bootstraps a server-uuid session ({id, phase:
  PROFILING, history: []} bootstrap state); GET /sessions lists the
  caller's rows; GET/DELETE /sessions/{id} are owner-checked.
- POST /chat takes {message, session_id}; the handler resolves the actor
  (auth cookie, or anonymous ONLY under TAX_ENABLE_ANON_DEMO=1), loads
  the OWNED state (foreign/unknown -> 404), runs the UNCHANGED
  nlp.process_message(message, state), the income gate, the engine,
  re-validates the mutated state (Sprint-1+2 validator — defense in
  depth on the server-side write path), persists it and responds with
  the read-only PROJECTION (audit scrub semantics: history/_last_*/
  memory dropped; every frontend key kept). An old-style session-dict
  body -> 422.
- POST /calculate takes {session_id, tax_year?} and computes the full
  report from the server-side state (explicit tax_year override, else
  the state's own pin, else the registry default).
- GET /history/{sid} requires auth + ownership and the TAX_ENABLE_HISTORY
  default flips to ON: the Sprint-1 interim C5 measure (opt-in gate) is
  superseded by auth + per-session ownership (design §2); the env stays
  as an explicit kill-switch (0/false/False).
- /chat-turn audit + blackbox records gain an additive user_id field
  (the app_sessions owner; omitted for anonymous demo turns).

Wave C (auth core, ADR-012) underneath: /auth/* endpoints on auth.py +
db.py — register (scrypt passwords), login (opaque HttpOnly-cookie
sessions, server-side rows in SQLite, lockout after 5 failures), logout
(row revoke), /auth/me and per-session management. Auth lifecycle events
are appended to the same JSONL audit stream via AuditLogger.log_event,
sanitized to sha256[:16] correlation hashes (never raw emails, tokens or
passwords).
"""
import json
import logging
import math
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

import auth
import config
import db
from audit_logger import AuditLogger, scrub_state
from nlp_engine import NLPEngine
from rate_limit import RateLimiter
from session_lab import SessionLab
from tax_engine import TaxEngine
from tax_rules import REGISTRY
from validation import is_valid_session_id, safe_session_id

logger = logging.getLogger(__name__)

# /health contract version (Sprint 3 design §3) and the process-start
# monotonic reading the dev-only uptime figure is derived from.
APP_VERSION = "0.3.0"
_STARTED_AT = time.monotonic()

nlp = NLPEngine()
engine = TaxEngine()
audit = AuditLogger()
lab = SessionLab()


# ---------------------------------------------------------------------------
# Hardening edge — security headers
# ---------------------------------------------------------------------------

# The exact set from the Sprint 3 design (§4). Applied by the middleware
# below AND by every short-circuit response helper, so 413/403/429 bodies
# are hardened exactly like route responses.
_SECURITY_HEADERS: Dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _apply_security_headers(response: JSONResponse) -> None:
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value


class BodySizeCapMiddleware(BaseHTTPMiddleware):
    """413 when Content-Length exceeds TAX_MAX_BODY_BYTES (design §4).

    Reads only the header — the body is never buffered. A malformed
    Content-Length is left to the server/route layers to reject.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> JSONResponse:
        raw_length = request.headers.get("content-length")
        if raw_length:
            try:
                length = int(raw_length)
            except ValueError:
                length = None  # malformed header: not a size we can enforce
            if length is not None and length > config.tax_max_body_bytes():
                response = JSONResponse(
                    status_code=413, content={"detail": "Request body too large"}
                )
                _apply_security_headers(response)
                return response
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies the hardening header set to every downstream response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> JSONResponse:
        response = await call_next(request)
        _apply_security_headers(response)
        return response


# ---------------------------------------------------------------------------
# Hardening edge — origin check (CSRF posture; design §1/§4)
# ---------------------------------------------------------------------------

_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# State-changing routes: POST /chat, /calculate, /auth/*, /sessions* (the
# /auth and /sessions trees populate in the auth/session waves; the
# prefix match is already in place for them).
_ORIGIN_CHECK_EXACT_PATHS = frozenset({"/chat", "/calculate"})
_ORIGIN_CHECK_PREFIXES = ("/auth/", "/sessions")


def _is_state_changing(method: str, path: str) -> bool:
    if method.upper() not in _STATE_CHANGING_METHODS:
        return False
    return path in _ORIGIN_CHECK_EXACT_PATHS or path.startswith(
        _ORIGIN_CHECK_PREFIXES
    )


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Rejects non-allowlisted ``Origin`` headers on state-changing routes.

    Allowlist = config.cors_origins() (dev default localhost:3000). When
    that raises (prod fail-closed on unset/wildcard CORS_ORIGINS) the
    allowlist is treated as empty — every declared Origin is rejected,
    which is exactly the fail-closed posture. A request WITHOUT an Origin
    header passes this wave (non-browser clients / same-origin scripts);
    cookie-backed requests arrive in the auth wave and this control is
    already in place ahead of them.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> JSONResponse:
        if _is_state_changing(request.method, request.url.path):
            origin = request.headers.get("origin")
            if origin:
                try:
                    allowed = {
                        entry.strip().lower() for entry in config.cors_origins()
                    }
                except RuntimeError:
                    allowed = set()  # fail closed: no origin is trusted
                if origin.strip().lower() not in allowed:
                    response = JSONResponse(
                        status_code=403, content={"detail": "Origin not allowed"}
                    )
                    _apply_security_headers(response)
                    return response
        return await call_next(request)


# ---------------------------------------------------------------------------
# Hardening edge — rate limiting (design §4)
# ---------------------------------------------------------------------------

_HEALTH_EXEMPT_PATH = "/health"


def _rate_limit_bucket(path: str) -> Optional[str]:
    """Route-class bucket for a path; None = not rate-limited this wave."""
    if path == "/chat":
        return "chat"
    if path == "/calculate":
        return "calc"
    if path.startswith("/auth"):
        # /auth/* limits activate with the auth-wave routes; the class is
        # wired now so the posture exists before credentials land.
        return "auth"
    if path == "/sessions" or path.startswith("/sessions/"):
        # Wave D: the app-session endpoints share the /chat bucket (the
        # design §4 class list names /chat for the conversation surface;
        # the bootstrap/list/delete family belongs to it).
        return "chat"
    return None


_RATE_LIMIT_ACCESSORS = {
    "chat": config.rate_limit_chat_per_min,
    "calc": config.rate_limit_calc_per_min,
    "auth": config.rate_limit_auth_per_min,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client-IP sliding-window limits (per-user keys land with auth).

    A limited request consumes BOTH its route-class bucket and the shared
    global bucket (design §4: "global 120/min/IP"), each keyed per IP for
    the current single-user deployment; /health is explicitly exempt.
    Limits are read at request time so the TAX_RATE_LIMIT_* envs can be
    tuned without a restart. In-memory only — the documented deployment
    is exactly one uvicorn worker (audit lock + SQLite correctness).
    """

    def __init__(self, app: ASGIApp, limiter: RateLimiter) -> None:
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> JSONResponse:
        path = request.url.path
        if path == _HEALTH_EXEMPT_PATH or request.method.upper() not in (
            _STATE_CHANGING_METHODS
        ):
            return await call_next(request)
        bucket = _rate_limit_bucket(path)
        if bucket is None:
            return await call_next(request)
        client = request.scope.get("client")
        ip = client[0] if client and client[0] else "unknown"
        allowed, retry_after = self._limiter.check(
            f"{bucket}:{ip}", _RATE_LIMIT_ACCESSORS[bucket](), 60.0
        )
        if not allowed:
            return self._too_many_requests(retry_after)
        allowed, retry_after = self._limiter.check(
            f"global:{ip}", config.rate_limit_global_per_min(), 60.0
        )
        if not allowed:
            return self._too_many_requests(retry_after)
        return await call_next(request)

    @staticmethod
    def _too_many_requests(retry_after: int) -> JSONResponse:
        response = JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
        _apply_security_headers(response)
        return response


# ---------------------------------------------------------------------------
# Health checks (design §3)
# ---------------------------------------------------------------------------


def _check_db(db_path: str) -> bool:
    """True iff the database can be opened AND answers SELECT 1.

    NEVER creates the file or its directory: a not-yet-provisioned
    database is precisely the degradation /health must report. The sqlite
    URI uses ``mode=rw`` (fails when the file is missing) and the parent
    directory must exist with write permission (os.access W_OK).
    """
    try:
        parent = os.path.dirname(os.path.abspath(db_path))
        if not os.path.isdir(parent) or not os.access(parent, os.W_OK):
            return False
        # as_uri() keeps Windows drive letters URI-safe; mode=rw never
        # creates the file (plain connect() would — that is why it exists).
        uri = Path(db_path).resolve().as_uri() + "?mode=rw"
        con = sqlite3.connect(uri, uri=True, timeout=2)
        try:
            con.execute("SELECT 1")
        finally:
            con.close()
        return True
    except (OSError, ValueError, sqlite3.Error):
        return False


def _check_audit_dir(audit_dir: str) -> bool:
    """True iff the append-only audit stream's directory exists+writable."""
    return os.path.isdir(audit_dir) and os.access(audit_dir, os.W_OK)


def _build_health_payload(app_env_value: str, verbose: bool) -> Dict[str, Any]:
    db_ok = _check_db(config.tax_db_path())
    audit_ok = _check_audit_dir(audit.audit_dir)
    checks = {
        "db": "ok" if db_ok else "degraded",
        "audit": "ok" if audit_ok else "degraded",
    }
    payload: Dict[str, Any] = {
        "status": "ok" if db_ok and audit_ok else "degraded",
        "checks": checks,
        "app_env": app_env_value,
        "version": APP_VERSION,
    }
    if verbose and app_env_value == "dev":
        # Dev-only diagnostics: process uptime + the registered tax-year
        # rule-set keys (never exposed in prod responses).
        payload["uptime_seconds"] = round(time.monotonic() - _STARTED_AT, 3)
        payload["registry"] = sorted(REGISTRY)
    return payload


# ---------------------------------------------------------------------------
# Session payload validation (Sprint 1+2 controls — unchanged)
# ---------------------------------------------------------------------------

# Income/deduction keys the engine reads numerically (N1): a client-supplied
# non-numeric value here used to 500 inside float() before the try block.
# Sprint 2 Step D: "80eea" was REMOVED (the section is discontinued — the
# key is rejected outright below, never silently ignored).
_SESSION_NUMERIC_KEYS = (
    "salary", "business", "rental", "other_income", "agriculture",
    "80c", "80d", "80d_parents", "80e", "80g", "nps",
    "80tta", "80ttb", "80gg", "80u_80dd", "80ddb", "24b", "hra",
    "professional_tax",
)

_MAX_SESSION_BYTES = 100_000  # serialized session payload cap

# Sprint 2 Step D: enum-strict session keys (security table). The 80U/80DD
# disability category and the 80G donation category are string enums — any
# other value (including numerics) is a 422, never a guess.
_80U_80DD_CATEGORIES = ("none", "40_79", "80_plus")
_80G_CATEGORIES = (
    "cat_100_no_limit",
    "cat_50_no_limit",
    "cat_100_qualifying_limit",
    "cat_50_qualifying_limit",
)

# Sprint 2 Step D2/G (V-2 closure): capital-gains entries are taxed BY TYPE
# at the engine — an unknown (or missing) type books income the engine never
# taxes (the untaxed-income hole). The enum is enforced at both boundaries:
# the /calculate model (Literal below) and the session validator here.
_CG_TYPES = ("equity_ltcg", "equity_stcg", "property_cg")


def _validate_session_payload(session: Dict[str, Any]) -> None:
    """Hardening for client-supplied session state (H5/N1); raises ValueError."""
    try:
        payload_size = len(json.dumps(session, default=str))
    except (TypeError, ValueError) as ser_err:
        raise ValueError("session payload is not serializable") from ser_err
    if payload_size > _MAX_SESSION_BYTES:
        raise ValueError("session payload too large")

    sid = session.get("id")
    if sid is not None and not is_valid_session_id(sid):
        raise ValueError("session.id must match [A-Za-z0-9_-]{4,64}")

    for key in _SESSION_NUMERIC_KEYS:
        if key in session:
            value = session[key]
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"session.{key} must be numeric")
            # Non-finite floats (inf/nan) would poison engine results and
            # get persisted to the blackbox while the background audit write
            # is skipped — reject them here so the state stays auditable.
            # ints are always finite (math.isfinite would overflow on huge
            # ints, so only floats are checked).
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"session.{key} must be a finite number")

    if "80eea" in session:
        # Sprint 2 Step D: the section is DISCONTINUED (only loans
        # sanctioned before 1 April 2022 qualified) — the key is rejected
        # outright on any presence (even null), never silently ignored.
        raise ValueError(
            "session.80eea is no longer accepted: Section 80EEA was "
            "discontinued — only loans sanctioned before 1 April 2022 "
            "qualified."
        )

    for key, allowed in (
        ("80u_80dd_category", _80U_80DD_CATEGORIES),
        ("80g_category", _80G_CATEGORIES),
    ):
        if key in session:
            value = session[key]
            if value is None:
                continue  # explicit null = not yet collected (engine default)
            if not isinstance(value, str) or value not in allowed:
                raise ValueError(
                    f"session.{key} must be one of: {', '.join(allowed)}"
                )

    # Sprint 2 Step B (security table): the split HRA legs are numeric
    # 0..1e11 non-finite-reject rows; the legacy "hra" key keeps its
    # unbounded numeric row above. Sprint 2 Step D adds the 80DDB
    # expenditure input to the same bounded row (it feeds a capped
    # deduction, so it needs the same 0..1e11 + finite guarantees).
    for key in ("hra_received", "rent_paid", "80ddb_expenditure"):
        if key in session:
            value = session[key]
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"session.{key} must be numeric")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"session.{key} must be a finite number")
            if not 0 <= value <= 1e11:
                raise ValueError(f"session.{key} must be between 0 and 1e11")

    if "is_metro" in session:
        # Sprint 2 Step B (security table): bool strictly — "yes" and 1 are
        # NOT bools (1 is isinstance-True of int, so the bool check must
        # come first, as everywhere else in this validator).
        metro = session["is_metro"]
        if metro is not None and not isinstance(metro, bool):
            raise ValueError("session.is_metro must be a boolean or null")

    if "capital_gains" in session:
        cg = session["capital_gains"]
        if not isinstance(cg, list):
            raise ValueError("session.capital_gains must be a list")
        for entry in cg:
            if not isinstance(entry, dict):
                raise ValueError("session.capital_gains entries must be objects")
            # Sprint 2 Step D2/G (V-2 closure): enum-strict type — an
            # unknown/missing type would book income the engine never
            # taxes. The NLP engine only ever writes the three enum
            # values, so legitimate sessions are unaffected.
            cg_type = entry.get("type")
            if not isinstance(cg_type, str) or cg_type not in _CG_TYPES:
                raise ValueError(
                    "session.capital_gains entries must have a type: "
                    + ", ".join(_CG_TYPES)
                )
            amount = entry.get("amount", 0)
            if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                raise ValueError("session.capital_gains amounts must be numeric")
            if isinstance(amount, float) and not math.isfinite(amount):
                raise ValueError("session.capital_gains amounts must be finite")

    if "age" in session:
        age = session["age"]
        if isinstance(age, bool) or not isinstance(age, int) or not (0 <= age <= 120):
            raise ValueError("session.age must be an integer between 0 and 120")

    if "cg_transfer_before_2024_07_23" in session:
        # Sprint 2 Step C (ruling R-e): tri-state property transfer-date
        # flag — True = transferred before 23-Jul-2024, False = on/after,
        # null/absent = unknown (the engine then books the default
        # post-cutoff route and emits the election advisory). Bool strictly
        # per the security table: 1 and "yes" are NOT bools (isinstance
        # True of int, so the bool check must come first — as everywhere
        # else in this validator).
        flag = session["cg_transfer_before_2024_07_23"]
        if flag is not None and not isinstance(flag, bool):
            raise ValueError(
                "session.cg_transfer_before_2024_07_23 must be a boolean or null"
            )

    if "tax_year" in session:
        # ADR-008: the session may pin the tax year for the real-time
        # computation; it must be None or a registered registry key.
        tax_year = session["tax_year"]
        if tax_year is not None and (not isinstance(tax_year, str) or tax_year not in REGISTRY):
            raise ValueError(
                f"session.tax_year must be one of: {', '.join(REGISTRY)}"
            )


def _validate_loaded_state(state: Dict[str, Any]) -> None:
    """422-map the Sprint-1+2 validator onto SERVER-side state (Wave D).

    The client can no longer supply state (ADR-013), so the H5/N1 rows
    now defend the server-side write path: a stored state that fails
    validation is refused at the load boundary — before NLP/engine see
    it — and the post-NLP state is re-checked before persisting. In
    production only validated states are ever written; a failure means a
    store/validator regression and must fail closed, never compute.
    """
    try:
        _validate_session_payload(state)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Session state rejected: {exc}"
        ) from exc


def session_projection(state: Dict[str, Any]) -> Dict[str, Any]:
    """Read-only response projection of the server-side state (ADR-013).

    Reuses the audit logger's scrub semantics (audit_logger.scrub_state):
    the internal keys — ``history``, ``_last_question``, ``_last_val``,
    ``_prev_salary``, ``memory`` — are dropped recursively, while every
    key the frontend reads survives: id, phase, profile, the income and
    deduction numbers, and the collected flags/categories.
    """
    scrubbed = scrub_state(state)
    return scrubbed if isinstance(scrubbed, dict) else {}


class ChatRequest(BaseModel):
    """Sprint 3 Wave D contract (ADR-013): ``{message, session_id}``.

    The client-authored ``session`` dict is GONE from the wire — state
    lives in app_sessions rows and only the server-issued id travels.
    An old-style body is rejected with an explicit migration message
    (no dual contract: one frontend, one deploy unit). The Sprint-1+2
    payload validator (``_validate_session_payload``) still runs — on the
    SERVER-side state, at both boundaries (load + post-NLP persist).
    """

    model_config = ConfigDict(extra="forbid")

    message: str = Field(max_length=4000)
    session_id: str = Field(min_length=1, max_length=64)

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy_session_dict(cls, data: Any) -> Any:
        # Breaking-contract guard (ADR-013): an old client sending the
        # pre-Wave-D session dict gets a 422 that says WHY, instead of a
        # generic unknown-field/missing-field error.
        if isinstance(data, dict) and "session" in data:
            raise ValueError(
                "Session state is now server-side; send session_id"
            )
        return data


def clean_json(obj):
    if hasattr(obj, "__dict__"): return clean_json(obj.__dict__)
    if isinstance(obj, dict): return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean_json(i) for i in obj]
    if hasattr(obj, "item"): return obj.item() # numpy handle
    return obj


class CalculateRequest(BaseModel):
    """Sprint 3 Wave D contract (ADR-013): ``{session_id, tax_year?}``.

    The full engine payload the client used to send is GONE — the numbers
    now come from the owned app_sessions state (validated by
    ``_validate_session_payload`` at the load boundary, which carries the
    same rows the old model enforced: numeric/finite/bounded incomes,
    enum-strict CG types + categories, bool-strict flags, registered
    tax_year). An old-style full-dict body -> 422 (session_id required).
    """

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(min_length=1, max_length=64)

    # ADR-008: optional tax-year OVERRIDE; None falls back to the state's
    # own pin (if any), then the registry default (fy_2025_26 since Step
    # A3). Registered keys validate via REGISTRY, which is also the 422
    # message's single source for the supported list.
    tax_year: Optional[str] = Field(None, max_length=32)

    @model_validator(mode="before")
    @classmethod
    def _reject_removed_80eea(cls, data: Any) -> Any:
        # Sprint 2 Step D control kept on the shrunk model: the section is
        # DISCONTINUED — extra="ignore" must not silently swallow the key
        # (any value, even null, is rejected with the discontinuation
        # message, mirroring the session validator).
        if isinstance(data, dict) and "80eea" in data:
            raise ValueError(
                "80eea is no longer accepted: Section 80EEA was discontinued "
                "— only loans sanctioned before 1 April 2022 qualified."
            )
        return data

    @field_validator("tax_year")
    @classmethod
    def _validate_tax_year(cls, value: Optional[str]) -> Optional[str]:
        # None or a registered registry key, else ValueError -> 422 listing
        # the supported keys (single source of truth: tax_rules.REGISTRY).
        if value is not None and value not in REGISTRY:
            raise ValueError(
                f"tax_year must be one of: {', '.join(REGISTRY)}"
            )
        return value


# ---------------------------------------------------------------------------
# Auth request models (Sprint 3 Wave C — ADR-012)
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str = Field(max_length=320)  # RFC 5321 practical limit; auth.py
    password: str = Field(max_length=1024)  # enforces the 254-char cap too.


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


# ---------------------------------------------------------------------------
# Application factory (Sprint 3 Step A)
# ---------------------------------------------------------------------------


def create_app(app_env: str = "dev") -> FastAPI:
    """Build the FastAPI application for *app_env* ("dev" | "prod").

    - prod: /docs, /redoc and /openapi.json are disabled (attack-surface
      reduction); dev keeps them enabled (current behavior).
    - Middleware order (request path, outermost first): body-cap ->
      security-headers -> origin-check -> rate-limit -> CORS. add_middleware
      registers innermost-first, so the CORS block comes FIRST here.
    - The rate limiter is per-app in-memory state, exposed at
      ``app.state.rate_limiter`` (single-worker deployment is documented).
    """
    # Fail-safe normalization: only the explicit "prod" selects prod posture
    # (same rule as config._normalize_app_env for the APP_ENV env var).
    env = "prod" if (app_env or "").strip().lower() == "prod" else "dev"
    docs_enabled = env != "prod"

    app = FastAPI(
        title="Tax Assist AI - Deep Consultant",
        version=APP_VERSION,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    limiter = RateLimiter()

    # Wave C: the session cookie exists now — the Sprint-1 wildcard is
    # retired permanently (design §4). Explicit allowlist from
    # config.cors_origins() + allow_credentials=True; a wildcard with
    # credentials would be unrepresentable anyway. Production with
    # unset/empty/wildcard CORS_ORIGINS fails closed at the config layer;
    # the RuntimeError is consumed here as an EMPTY allowlist (no origin
    # is trusted — same posture the origin-check middleware applies).
    # DELETE is allowed because Wave C adds DELETE /auth/sessions/{id}
    # (the design §4 method list predates that endpoint).
    try:
        allowed_origins = config.cors_origins()
    except RuntimeError:
        allowed_origins = []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    app.add_middleware(OriginCheckMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BodySizeCapMiddleware)

    app.state.rate_limiter = limiter
    app.state.app_env = env

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # N1: never leak stack traces / exception details in the response body.
        # The full traceback still goes to the server log (auditability).
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Reflection-amplification fix: the default handler echoes each error's
        # 'input' field verbatim (a 100KB padded session came back as a ~100KB
        # body), and it 500s outright when 'input' is inf/nan because
        # JSONResponse refuses non-finite floats. Respond with loc/msg/type
        # only, loc flattened to strings, capped at 20 entries.
        errors = [
            {
                "loc": [str(part) for part in err.get("loc", ())],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()[:20]
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": "Validation error", "errors": errors},
        )

    # ------------------------------------------------------------------
    # /auth/* (Sprint 3 Wave C — ADR-012)
    # ------------------------------------------------------------------

    def _current_user(request: Request) -> auth.CurrentUser:
        # Dependency wrapper: passes the module-level audit logger so auth
        # events (e.g. UA-mismatch revocations) land in the SAME stream the
        # endpoints use. The global is resolved at call time, so tests can
        # swap the stream per fixture.
        return auth.require_user(request, audit=audit)

    def _resolve_actor(request: Request) -> Optional[auth.CurrentUser]:
        """Auth dependency for the Wave D protected surface.

        Cookie present -> the FULL ADR-012 chain (401 on ANY failure —
        never bypassed, a stale cookie never silently downgrades to the
        demo posture). No cookie -> anonymous ONLY when the deny-by-default
        demo opt-in (TAX_ENABLE_ANON_DEMO=1) is set: the endpoint then
        operates on user_id NULL app sessions. Returns None for the demo
        branch, a CurrentUser otherwise. /history never takes this
        dependency (the demo flag never unlocks history).
        """
        if request.cookies.get(auth.session_cookie_name()) is None:
            if config.tax_enable_anon_demo():
                return None
            raise HTTPException(status_code=401, detail="Authentication required")
        return auth.require_user(request, audit=audit)

    def _owned_session_or_404(
        session_id: str, actor: Optional[auth.CurrentUser]
    ) -> sqlite3.Row:
        """Ownership resolution for {session_id} endpoints (ADR-013).

        get_owned returns None for a foreign AND an unknown id — both map
        to the same 404 (the IDOR posture: no existence oracle). Demo
        (actor None) matches only user_id NULL rows.
        """
        row = db.get_owned(
            session_id, actor.user_id if actor is not None else None
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return row

    def _load_owned_state(session_id: str, actor: Optional[auth.CurrentUser]):
        """Owned app_sessions row + its parsed, validated state."""
        row = _owned_session_or_404(session_id, actor)
        state = json.loads(row["state"])
        _validate_loaded_state(state)  # defense-in-depth: refuse forged rows
        return row, state

    def _client_ip(request: Request) -> str:
        client = request.scope.get("client")
        return client[0] if client and client[0] else "unknown"

    def _set_session_cookie(response: Response, token: str) -> None:
        # Design §1: __Host-ta_session when Secure else ta_session;
        # HttpOnly always; SameSite=Lax; Path=/; Max-Age mirrors the
        # sliding TTL. The token itself lives ONLY in this cookie —
        # never in a response body or a log line.
        response.set_cookie(
            auth.session_cookie_name(),
            token,
            max_age=config.session_ttl_minutes() * 60,
            httponly=True,
            secure=config.tax_cookie_secure(),
            samesite="lax",
            path="/",
        )

    def _clear_session_cookie(response: Response) -> None:
        # Mirror the issue-time attributes so the browser drops the cookie.
        response.delete_cookie(
            auth.session_cookie_name(),
            path="/",
            httponly=True,
            secure=config.tax_cookie_secure(),
            samesite="lax",
        )

    @app.post("/auth/register", status_code=201)
    async def auth_register(req: RegisterRequest, request: Request) -> Dict[str, str]:
        """Create a password account. 201 {user_id, email}.

        409 on a duplicate (case-insensitive); 422 on a malformed email or
        an out-of-policy password (12-1024 chars). Only sanitized values
        (email correlation hash) reach the audit stream.
        """
        email = auth.normalize_email(req.email)
        if email is None:
            raise HTTPException(status_code=422, detail="Invalid email address")
        if not auth.validate_password(req.password):
            raise HTTPException(
                status_code=422,
                detail="Password must be between 12 and 1024 characters",
            )
        if auth.find_user_by_email(email) is not None:
            raise HTTPException(status_code=409, detail="Email already registered")
        # scrypt runs only after the cheap checks (a duplicate registration
        # must not cost the server a full KDF).
        password_hash = auth.hash_password(req.password)
        try:
            user = auth.create_user(email, password_hash)
        except sqlite3.IntegrityError:
            # Race with a concurrent registration of the same email.
            raise HTTPException(status_code=409, detail="Email already registered")
        auth.log_auth_event(
            audit,
            "auth_register",
            user_id=user["id"],
            email_sha256_16=auth.email_hash(email),
            ip_sha256_16=auth.ip_hash(_client_ip(request)),
        )
        return {"user_id": user["id"], "email": user["email"]}

    @app.post("/auth/login")
    async def auth_login(req: LoginRequest, request: Request) -> JSONResponse:
        """Password login -> 200 {user_id, email} + hardened session cookie.

        Uniform 401 "Invalid email or password" for unknown emails AND
        wrong passwords (dummy-scrypt timing equalization); generic 423
        lockout response once the account is locked — shown only to a
        CORRECT password, so it is not an enumeration oracle.
        """
        email = auth.normalize_email(req.email)
        ip_sha256_16 = auth.ip_hash(_client_ip(request))
        ua_sha256_16 = auth.ua_hash(request.headers.get("user-agent", ""))
        result = auth.authenticate(
            email,
            req.password,
            request.headers.get("user-agent", ""),
            _client_ip(request),
        )
        if result["status"] == auth.AUTH_OK:
            user = result["user"]
            auth.log_auth_event(
                audit,
                "auth_login_success",
                user_id=user["id"],
                email_sha256_16=auth.email_hash(user["email"]),
                ip_sha256_16=ip_sha256_16,
                ua_sha256_16=ua_sha256_16,
            )
            response = JSONResponse(
                {"user_id": user["id"], "email": user["email"]}
            )
            _set_session_cookie(response, result["token"])
            return response

        if result["status"] == auth.AUTH_LOCKED:
            user = result["user"]
            auth.log_auth_event(
                audit,
                "auth_login_failure",
                user_id=user["id"],
                email_sha256_16=auth.email_hash(user["email"]),
                ip_sha256_16=ip_sha256_16,
                while_locked=True,
            )
            return JSONResponse(
                status_code=423,
                content={"detail": "Account temporarily locked"},
            )

        # Uniform failure path (unknown email or wrong password).
        user = result.get("user")
        failure_fields: Dict[str, Any] = {"ip_sha256_16": ip_sha256_16}
        if user is not None:
            failure_fields["user_id"] = user["id"]
            failure_fields["email_sha256_16"] = auth.email_hash(user["email"])
        elif email is not None:
            failure_fields["email_sha256_16"] = auth.email_hash(email)
        if result.get("while_locked"):
            failure_fields["while_locked"] = True
        auth.log_auth_event(audit, "auth_login_failure", **failure_fields)
        if result.get("locked_now") and user is not None:
            # The 5th failure just locked the account: record it once.
            auth.log_auth_event(
                audit,
                "auth_lockout",
                user_id=user["id"],
                email_sha256_16=auth.email_hash(user["email"]),
                ip_sha256_16=ip_sha256_16,
            )
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid email or password"},
        )

    @app.post("/auth/logout", status_code=204)
    async def auth_logout(request: Request) -> Response:
        """Revoke the presented session (idempotent) and clear the cookie.

        Deliberately NOT behind get_current_user: a stale/expired/garbage
        cookie still gets the clean 204 + cookie clear, so logout never
        becomes a session-validity oracle.
        """
        token = request.cookies.get(auth.session_cookie_name())
        if token:
            token_hash = auth.hash_token(token)
            row = auth.fetch_session_row(token_hash)
            if row is not None and row["revoked_at"] is None:
                auth.revoke_session(token_hash)
                auth.log_auth_event(
                    audit,
                    "auth_logout",
                    user_id=row["user_id"],
                    session_row_id=token_hash[: auth.SESSION_ROW_ID_LENGTH],
                    ip_sha256_16=auth.ip_hash(_client_ip(request)),
                )
        response = Response(status_code=204)
        _clear_session_cookie(response)
        return response

    @app.get("/auth/me")
    async def auth_me(
        user: auth.CurrentUser = Depends(_current_user),
    ) -> Dict[str, str]:
        """200 {user_id, email, expires_at} for a live session, else 401."""
        return {
            "user_id": user.user_id,
            "email": user.email,
            "expires_at": user.expires_at,
        }

    @app.get("/auth/sessions")
    async def auth_sessions_list(
        user: auth.CurrentUser = Depends(_current_user),
    ) -> List[Dict[str, Any]]:
        """The calling user's active sessions.

        Each row is identified by a 12-hex prefix of its (hashed) token —
        the token hash itself never leaves the store. ``current`` marks
        the session the request was authenticated with.
        """
        rows = auth.list_active_sessions(user.user_id)
        return [
            {
                "id": row["token_hash"][: auth.SESSION_ROW_ID_LENGTH],
                "created_at": row["created_at"],
                "last_used_at": row["last_used_at"],
                "expires_at": row["expires_at"],
                "current": row["token_hash"] == user.token_hash,
            }
            for row in rows
        ]

    @app.delete("/auth/sessions/{row_id}", status_code=204)
    async def auth_session_revoke(
        row_id: str,
        request: Request,
        user: auth.CurrentUser = Depends(_current_user),
    ) -> Response:
        """Revoke one of the caller's sessions (owner-checked; else 404)."""
        if not auth.revoke_session_by_public_id(user.user_id, row_id):
            raise HTTPException(status_code=404, detail="Session not found")
        auth.log_auth_event(
            audit,
            "auth_session_revoke",
            user_id=user.user_id,
            session_row_id=row_id,
            ip_sha256_16=auth.ip_hash(_client_ip(request)),
        )
        return Response(status_code=204)

    # ------------------------------------------------------------------
    # /sessions (Sprint 3 Wave D — ADR-013 app-session bootstrap + CRUD)
    # ------------------------------------------------------------------

    @app.post("/sessions")
    async def create_app_session_endpoint(
        actor: Optional[auth.CurrentUser] = Depends(_resolve_actor),
    ) -> Dict[str, Any]:
        """Bootstrap one server-side session. 200 {session_id, session}.

        Authenticated by default; under the deny-by-default anonymous demo
        opt-in (TAX_ENABLE_ANON_DEMO=1) a cookie-less request creates a
        user_id NULL row. The state starts as the fixed bootstrap {id,
        phase: PROFILING, history: []}; the response `session` is its
        read-only projection (the empty history is internal).
        """
        user_id = actor.user_id if actor is not None else None
        row = db.create_session(user_id)
        state = json.loads(row["state"])
        return {
            "session_id": row["id"],
            "session": session_projection(state),
        }

    @app.get("/sessions")
    async def list_app_sessions_endpoint(
        user: auth.CurrentUser = Depends(_current_user),
    ) -> List[Dict[str, Any]]:
        """The calling user's app sessions (id + timestamps, newest use
        first). Anonymous demo callers have no listable identity — auth
        only, even with the demo flag on."""
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in db.list_sessions(user.user_id)
        ]

    @app.get("/sessions/{session_id}")
    async def get_app_session_endpoint(
        session_id: str,
        user: auth.CurrentUser = Depends(_current_user),
    ) -> Dict[str, Any]:
        """The owned session's read-only projection (404 foreign/unknown)."""
        _row, state = _load_owned_state(session_id, user)
        return session_projection(state)

    @app.delete("/sessions/{session_id}", status_code=204)
    async def delete_app_session_endpoint(
        session_id: str,
        user: auth.CurrentUser = Depends(_current_user),
    ) -> Response:
        """Delete one of the caller's app sessions (owner-checked; 404
        foreign/unknown). Cascading FKs also remove the row when the
        owning user is deleted."""
        if not db.delete_owned_session(session_id, user.user_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return Response(status_code=204)

    @app.get("/health")
    async def health_endpoint(
        request: Request,
    ) -> JSONResponse:
        """Public, rate-limit-exempt liveness/readiness probe (design §3).

        db check: SELECT 1 against TAX_DB_PATH (never creates the file) +
        data-dir write permission. audit check: logs/audit dir writable.
        Any failing check -> 503 with the failing check named. ?verbose=1
        adds uptime + registry keys in dev only.
        """
        verbose = request.query_params.get("verbose") in {"1", "true", "True"}
        payload = _build_health_payload(env, verbose)
        status_code = 200 if payload["status"] == "ok" else 503
        return JSONResponse(status_code=status_code, content=payload)

    @app.post("/chat")
    async def chat_endpoint(
        request: ChatRequest,
        background_tasks: BackgroundTasks,
        actor: Optional[auth.CurrentUser] = Depends(_resolve_actor),
    ):
        # Wave D handler flow (ADR-013): resolve actor -> load OWNED state
        # -> NLP (unchanged signature) -> income gate -> engine -> re-valid-
        # ate -> persist -> audit/blackbox -> respond with the projection.
        # 0. Ownership: a foreign/unknown session id is a 404 (no oracle).
        row, state = _load_owned_state(request.session_id, actor)
        session_id = row["id"]
        user_id = actor.user_id if actor is not None else None

        # 1. Process Message (server-side state; NLP unchanged)
        result = nlp.process_message(request.message, state)

        # 2. Real-time Calculation (Insights)
        tax_result = None
        has_income = any(
            float(result["session"].get(k, 0) or 0) > 0
            for k in ["salary", "business", "rental", "other_income", "agriculture"]
        )
        if has_income:
            try:
                # ADR-008: the state may pin the tax year (validator-checked
                # at load); None falls back to the registry default.
                tax_result = engine.calculate_tax_advanced(
                    result["session"], result["session"].get("tax_year")
                )
            except Exception as e:
                # Graceful degradation: the chat continues with a null tax
                # report; the failure goes to the server log (never the
                # client response).
                logger.warning("chat calculation error: %s", e)

        # 3. Validate the mutated state before persisting (defense-in-depth:
        # the ONLY writer is NLP, and its output must keep satisfying the
        # Sprint-1+2 rows; a failure fails closed — nothing is persisted).
        _validate_loaded_state(result["session"])
        if not db.save_state(session_id, result["session"]):
            # The row vanished between the ownership check and the write
            # (deleted concurrently): nothing was persisted.
            raise HTTPException(status_code=404, detail="Session not found")

        # 4. Schedule Background Audit Log (user_id is the Wave D additive
        # field — the app_sessions owner; None for anonymous demo turns).
        background_tasks.add_task(
            audit.log_interaction,
            session_id=session_id,
            input_text=request.message,
            response=result["response"],
            session_state=result["session"],
            tax_results=tax_result,
            extracted=result.get("extracted"),
            plan=result.get("plan"),
            user_id=user_id,
        )

        # 5. Record to Industrial Black Box for Regression Auditing (keyed
        # by the server-issued session id).
        lab.record_turn(session_id, {
            "input": request.message,
            "response": result["response"],
            "extracted": result.get("extracted"),
            "plan": result.get("plan"),
            "state": result["session"],
            "audit": tax_result,
            "user_id": user_id,
        })

        # Return everything for the frontend to render real-time. `session`
        # is the READ-ONLY projection (internal keys dropped); the full
        # state stays server-side.
        return clean_json({
            "response": result["response"],
            "session_id": session_id,
            "session": session_projection(result["session"]),
            "extracted": result.get("extracted"),
            "plan": result.get("plan"),
            "tax_report": tax_result,
        })

    @app.get("/history/{sid}")
    async def get_history(
        sid: str,
        limit: int = Query(50, ge=1, le=200, description="Entries per page (hard max 200)"),
        offset: int = Query(0, ge=0, description="Entries to skip before the page"),
        user: auth.CurrentUser = Depends(_current_user),
    ):
        """Own-session history browsing (auth + ownership; Wave D).

        Sprint-1 interim C5 measure SUPERSEDED (design §2): the endpoint
        used to be disabled by default because it served audit entries by a
        client-chosen id to anyone. It now requires an authenticated user
        AND an app session they own (foreign/unknown -> 404, anonymous ->
        401), so TAX_ENABLE_HISTORY defaults to ON — the variable survives
        as an explicit kill-switch (0/false/False), read at request time.

        Serves the append-only JSONL global stream
        (logs/audit/session_audit.jsonl) line-by-line, filtered by the
        owned session id and paginated (limit default 50, hard max 200,
        offset). Response envelope: {entries, corrupt_lines_skipped,
        has_more}; the entry schema fields are unchanged (timestamp,
        session_id, user_input/ai_response — correlation/structured records
        per the write-time PII minimization, internal_state,
        tax_calculation — plus the Wave D additive user_id owner field).

        Read-only compat fallback: if the JSONL stream does not exist but
        the legacy logs/session_audit.json does, serve from it as before.
        The per-session blackbox streams are NEVER served here.
        """
        row = _owned_session_or_404(sid, user)
        if not config.tax_enable_history():
            # Kill-switch: same 404 shape as the pre-Wave-D disabled gate
            # (never reveals whether the id exists).
            raise HTTPException(status_code=404, detail="Not found")
        safe = safe_session_id(row["id"])  # server-issued id — passes through
        empty: Dict[str, Any] = {"entries": [], "corrupt_lines_skipped": 0, "has_more": False}
        if not os.path.exists(audit.log_file):
            legacy = getattr(audit, "legacy_file", None)
            if legacy and os.path.exists(legacy):
                try:
                    with open(legacy, "r", encoding="utf-8") as fh:
                        logs = json.load(fh)
                except (OSError, ValueError) as exc:
                    logger.warning("legacy audit log %s unreadable (%s)", legacy, exc)
                    return empty
                if not isinstance(logs, list):
                    return empty
                matches = [
                    entry
                    for entry in logs
                    if isinstance(entry, dict) and entry.get("session_id") == safe
                ]
                return {
                    "entries": matches[offset:offset + limit],
                    "corrupt_lines_skipped": 0,
                    "has_more": len(matches) > offset + limit,
                }
            return empty
        entries, corrupt_lines, has_more = audit.read_session_entries(
            safe, limit=limit, offset=offset
        )
        return {
            "entries": entries,
            "corrupt_lines_skipped": corrupt_lines,
            "has_more": has_more,
        }

    @app.post("/calculate")
    async def calculate_endpoint(
        req: CalculateRequest,
        actor: Optional[auth.CurrentUser] = Depends(_resolve_actor),
    ):
        # Wave D: the calculator computes from the OWNED server-side state
        # (the full engine payload the client used to send is gone — the
        # state was validated at the load boundary by _load_owned_state).
        _row, state = _load_owned_state(req.session_id, actor)
        # ADR-008: an explicit tax_year override wins over the state's own
        # pin; both are registry-validated (request model + state validator).
        tax_year = req.tax_year if req.tax_year is not None else state.get("tax_year")
        results = engine.calculate_tax_advanced(state, tax_year=tax_year)
        return clean_json(results)

    return app


app = create_app(os.environ.get("APP_ENV", "dev"))


if __name__ == "__main__":
    # Dev bind safety: TAX_HOST/TAX_PORT (defaults 127.0.0.1:8000) — the
    # server never defaults to a routable interface. TAX_LOG_LEVEL sets
    # the root logging level for the entry point.
    logging.basicConfig(level=config.tax_log_level())
    uvicorn.run(app, host=config.tax_host(), port=config.tax_port())

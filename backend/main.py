# Summer internship project
from datetime import date
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Dict, Any, List, Literal, Optional
from tax_engine import TaxEngine
from tax_rules import REGISTRY
from nlp_engine import NLPEngine
from audit_logger import AuditLogger
from session_lab import SessionLab
from validation import is_valid_session_id
import logging
import math
import uvicorn
import os
import json

logger = logging.getLogger(__name__)

app = FastAPI(title="Tax Assist AI - Deep Consultant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

nlp = NLPEngine()
engine = TaxEngine()
audit = AuditLogger()
lab = SessionLab()


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


class ChatRequest(BaseModel):
    message: str = Field(max_length=4000)
    session: Dict[str, Any]

    @field_validator("session", mode="after")
    @classmethod
    def _validate_session(cls, session: Dict[str, Any]) -> Dict[str, Any]:
        # C6: reject traversal/absolute/non-ASCII ids at the API boundary
        # (→ 422). session_lab still sanitizes as defense-in-depth, and the
        # audit logger records the (sanitized) id either way.
        _validate_session_payload(session)
        return session

def clean_json(obj):
    if hasattr(obj, "__dict__"): return clean_json(obj.__dict__)
    if isinstance(obj, dict): return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean_json(i) for i in obj]
    if hasattr(obj, "item"): return obj.item() # numpy handle
    return obj

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    # 1. Process Message
    result = nlp.process_message(request.message, request.session)
    
    # 2. Real-time Calculation (Insights)
    tax_result = None
    has_income = any(
        float(result["session"].get(k, 0) or 0) > 0
        for k in ["salary", "business", "rental", "other_income", "agriculture"]
    )
    if has_income:
        try:
            # ADR-008: the session may pin the tax year (validated above);
            # None falls back to the registry default.
            tax_result = engine.calculate_tax_advanced(
                result["session"], result["session"].get("tax_year")
            )
        except Exception as e:
            print(f"Calculation Error: {e}")

    # 3. Schedule Background Audit Log
    sid = request.session.get("id", "default")
    background_tasks.add_task(
        audit.log_interaction,
        session_id=sid,
        input_text=request.message,
        response=result["response"],
        session_state=result["session"],
        tax_results=tax_result
    )
    
    # 4. Record to Industrial Black Box for Regression Auditing
    lab.record_turn(sid, {
        "input": request.message,
        "response": result["response"],
        "extracted": result.get("extracted"),
        "plan": result.get("plan"),
        "state": result["session"],
        "audit": tax_result
    })
    
    # Return everything for the frontend to render real-time
    return clean_json({**result, "tax_report": tax_result})

@app.get("/history/{sid}")
async def get_history(sid: str):
    # C5 interim: history browsing is disabled by default (the audit log
    # itself keeps being written regardless). Opt in explicitly by setting
    # TAX_ENABLE_HISTORY to 1 / true / True. Read at request time so the
    # flag can be flipped without a restart.
    if os.environ.get("TAX_ENABLE_HISTORY") not in {"1", "true", "True"}:
        raise HTTPException(status_code=404, detail="Not found")
    log_file = "logs/session_audit.json"
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r") as f:
            logs = json.load(f)
        session_logs = [l for l in logs if l.get("session_id") == sid]
        return session_logs
    except:
        return []

class CapitalGainItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Sprint 2 Step D2/G (V-2 closure): enum-strict via Literal — any other
    # value (e.g. "crypto", which the engine would book as untaxed income)
    # is a 422. Required: an entry with no type is the same hole (the
    # engine taxes by type and would let it through untaxed).
    type: Literal["equity_ltcg", "equity_stcg", "property_cg"]
    amount: float = Field(0.0, ge=0, le=1e11)
    holding: str = Field("unknown", max_length=32)
    # Sprint 2 Step C (ruling R-e): ISO date (yyyy-mm-dd) of the transfer.
    # A plain pydantic date — parse failures 422 at the boundary; no further
    # bounds are needed (any valid date is accepted; the transfer-date
    # ROUTING/advisory is keyed on the tri-state
    # cg_transfer_before_2024_07_23 flag, and the 20%-with-indexation
    # election itself is out of scope — never fabricated).
    transfer_date: Optional[date] = None

    @field_validator("amount")
    @classmethod
    def _validate_amount_finite(cls, value: float) -> float:
        # The ge/le constraints already reject inf/nan; this keeps the
        # guarantee if the bounds are ever relaxed (non-finite engine input
        # must never pass validation).
        if not math.isfinite(value):
            raise ValueError("amount must be a finite number")
        return value


class CalculateRequest(BaseModel):
    """Validated /calculate payload (H5).

    Aliases mirror the engine's raw dict keys ("80c", "24b", ...) so
    model_dump(by_alias=True) hands TaxEngine exactly the key names it reads.
    All fields are optional with neutral defaults so partial payloads keep
    working as they did before validation existed.
    """
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    salary: float = Field(0.0, ge=0, le=1e11)
    business: float = Field(0.0, ge=0, le=1e11)
    rental: float = Field(0.0, ge=0, le=1e11)
    other_income: float = Field(0.0, ge=0, le=1e11)
    agriculture: float = Field(0.0, ge=0, le=1e11)
    age: Optional[int] = Field(None, ge=0, le=120)
    capital_gains: List[CapitalGainItem] = Field(default_factory=list)

    # Deduction fields — dumped back under the engine's original key names.
    # Sprint 2 Step D: the "80eea" alias is REMOVED (the section is
    # discontinued); a client-supplied 80eea key is rejected outright by
    # the mode="before" model validator below instead of being ignored.
    c80: float = Field(0.0, ge=0, le=1e11, alias="80c")
    d80: float = Field(0.0, ge=0, le=1e11, alias="80d")
    d80_parents: float = Field(0.0, ge=0, le=1e11, alias="80d_parents")
    e80: float = Field(0.0, ge=0, le=1e11, alias="80e")
    g80: float = Field(0.0, ge=0, le=1e11, alias="80g")
    nps: float = Field(0.0, ge=0, le=1e11)
    tta80: float = Field(0.0, ge=0, le=1e11, alias="80tta")
    ttb80: float = Field(0.0, ge=0, le=1e11, alias="80ttb")
    gg80: float = Field(0.0, ge=0, le=1e11, alias="80gg")
    u80_dd80: float = Field(0.0, ge=0, le=1e11, alias="80u_80dd")
    ddb80: float = Field(0.0, ge=0, le=1e11, alias="80ddb")
    b24: float = Field(0.0, ge=0, le=1e11, alias="24b")
    hra: float = Field(0.0, ge=0, le=1e11)
    # Sprint 2 Step B: the three Rule 2A inputs with identical bounds; the
    # legacy "hra" key above keeps its numeric row. is_metro is bool
    # strictly (the mode="before" validator below rejects the values
    # pydantic lax mode would coerce, e.g. "yes" / 1 — mirroring the
    # session validator).
    hra_received: float = Field(0.0, ge=0, le=1e11)
    rent_paid: float = Field(0.0, ge=0, le=1e11)
    is_metro: Optional[bool] = None
    professional_tax: float = Field(0.0, ge=0, le=1e11)
    # Sprint 2 Step D mirrors: the 80DDB expenditure input (bounded like
    # the other numerics) and the two enum-strict category keys (None =
    # not yet collected; the engine applies its disclosed defaults).
    ddb_expenditure: float = Field(0.0, ge=0, le=1e11, alias="80ddb_expenditure")
    u80_dd_category: Optional[str] = Field(None, alias="80u_80dd_category")
    g80_category: Optional[str] = Field(None, alias="80g_category")

    profile: Optional[str] = Field(None, max_length=64)
    has_parents: Optional[bool] = None
    has_home_loan: Optional[bool] = None
    pays_rent: Optional[bool] = None
    # Sprint 2 Step C (ruling R-e): tri-state property transfer-date flag —
    # True = transferred before 23-Jul-2024, False = on/after, None/absent =
    # unknown. Bool strictly per the security table (the validator below
    # rejects the values pydantic lax mode would coerce, e.g. "yes" / 1).
    cg_transfer_before_2024_07_23: Optional[bool] = None
    id: Optional[str] = None

    # ADR-008: optional tax-year pin; None keeps the registry default
    # (fy_2025_26 since Step A3). Both registered keys — fy_2024_25 and
    # fy_2025_26 — validate via REGISTRY, which is also the 422 message's
    # single source for the supported list.
    tax_year: Optional[str] = Field(None, max_length=32)

    @model_validator(mode="before")
    @classmethod
    def _reject_removed_80eea(cls, data: Any) -> Any:
        # Sprint 2 Step D: the 80eea field was REMOVED from this model —
        # but extra="ignore" would silently swallow the key, so its
        # presence is rejected outright (any value, even null) with the
        # discontinuation message, mirroring the session validator.
        if isinstance(data, dict) and "80eea" in data:
            raise ValueError(
                "80eea is no longer accepted: Section 80EEA was discontinued "
                "— only loans sanctioned before 1 April 2022 qualified."
            )
        return data

    @field_validator("u80_dd_category")
    @classmethod
    def _validate_u80_dd_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value not in _80U_80DD_CATEGORIES:
            raise ValueError(
                "80u_80dd_category must be one of: "
                f"{', '.join(_80U_80DD_CATEGORIES)}"
            )
        return value

    @field_validator("g80_category")
    @classmethod
    def _validate_g80_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value not in _80G_CATEGORIES:
            raise ValueError(
                "80g_category must be one of: " + ", ".join(_80G_CATEGORIES)
            )
        return value

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not is_valid_session_id(value):
            raise ValueError("id must match [A-Za-z0-9_-]{4,64}")
        return value

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

    @field_validator("cg_transfer_before_2024_07_23", mode="before")
    @classmethod
    def _validate_transfer_flag_strict_bool(cls, value: Any) -> Any:
        # Tri-state bool strictly (security table): pydantic lax mode would
        # coerce "yes"/"1"/1 to a bool — reject anything that is not a real
        # bool or null so the API boundary matches the session validator.
        # mode="before" sees the RAW wire value, before coercion.
        if value is not None and not isinstance(value, bool):
            raise ValueError(
                "cg_transfer_before_2024_07_23 must be a boolean or null"
            )
        return value

    @field_validator("is_metro", mode="before")
    @classmethod
    def _validate_is_metro_strict_bool(cls, value: Any) -> Any:
        # Sprint 2 Step B (security table): bool strictly, same pattern as
        # the transfer flag above and the session validator.
        if value is not None and not isinstance(value, bool):
            raise ValueError("is_metro must be a boolean or null")
        return value


@app.post("/calculate")
async def calculate_endpoint(req: CalculateRequest):
    # Maintain existing calculator endpoint for the UI.
    # by_alias → the engine sees its original keys ("80c", "24b", ...).
    # exclude_unset → keys the client never sent stay absent, so the engine's
    # own defaults keep applying exactly as before validation existed (e.g.
    # the engine's internal professional_tax default of 2500 for salaries);
    # injecting model defaults instead would silently change results.
    results = engine.calculate_tax_advanced(
        req.model_dump(by_alias=True, exclude_unset=True),
        # ADR-008: honor the client's tax-year pin (None -> registry default).
        tax_year=req.tax_year,
    )
    return clean_json(results)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

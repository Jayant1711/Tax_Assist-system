# API Reference

> Verified against the code 2026-10-31. Backend entry point: `backend/main.py` (Uvicorn on `0.0.0.0:8000`, `main.py:100-101`). Interactive docs: `http://localhost:8000/docs` (FastAPI auto).
>
> **There is no authentication on any endpoint.** CORS is `allow_origins=["*"]` with all methods/headers (`main.py:16-22`). See [security.md](security.md) before exposing this API anywhere but localhost.

## Endpoints at a glance

| Method | Path | Auth | Purpose | Defined |
|---|---|---|---|---|
| `POST` | `/chat` | none | Conversational extraction; mutates and returns the full session; attaches `tax_report` when any income is set | `main.py:40-79` |
| `GET` | `/history/{sid}` | none | Returns this session's entries from the audit log | `main.py:81-92` |
| `POST` | `/calculate` | none | Pure tax computation for an arbitrary session dict (used by the report UI) | `main.py:94-98` |

There is no `/health` endpoint yet (roadmap Week 3). `GET /docs` and `/redoc` are served by FastAPI defaults.

---

## `POST /chat`

### Request

```json
{
  "message": "I am a software engineer earning 18 LPA",
  "session": { "id": "sid_1730000000000", "phase": "PROFILING" }
}
```

Body is validated by the only Pydantic model in the codebase (`main.py:29-31`):

| Field | Type | Notes |
|---|---|---|
| `message` | `str` | No length limit; `/end`, `end`, `/done`, `done`, `finish`, `complete` force the FINAL phase (`nlp_engine.py:67`) |
| `session` | `Dict[str, Any]` | **The entire conversation state, client-owned.** First call may be almost empty; every later call must return the `session` object the server last sent. The `id` key is client-chosen (`sid_${Date.now()}` in `ChatInterface.tsx:105`) |

Session keys read or written by the backend (client may add more; unknown keys are preserved):

| Group | Keys |
|---|---|
| Income | `salary`, `business`, `rental`, `other_income`, `agriculture`, `capital_gains[]` (entries `{type, amount, holding}`) |
| Deductions | `80c`, `80d`, `80d_parents`, `80e`, `80g`, `80eea`, `nps`, `80tta`, `80ttb`, `80gg`, `80u_80dd`, `80ddb`, `24b`, `hra`, `professional_tax` |
| Profile / flow | `id`, `profile`, `phase`, `age`, `has_parents`, `has_home_loan`, `pays_rent`, `_last_question`, `_last_val`, `_prev_salary`, `history[]` (`{user, ai}`) |

### Processing

`nlp.process_message()` mutates the session in place (full pipeline: [nlp-pipeline.md](nlp-pipeline.md)). Then, **only if** any of `salary`, `business`, `rental`, `other_income`, `agriculture` is `> 0`, the engine runs and the result becomes `tax_report` (`main.py:47-55`); a calculation exception is caught, printed to the server console, and returned as `tax_report: null` (`main.py:52-55`).

After the response body is prepared, audit logging is deferred via `BackgroundTasks`, but the black-box write runs synchronously inside the handler (`main.py:57-76`) — both write PII to disk (see [security.md](security.md)).

### Response — 200

```json
{
  "response": "✅ Mapped — SALARY: ₹1,800,000. 💰 **Section 80C** — Have you made any tax-saving investments this year? …",
  "session": { "…": "full mutated session — replace your local copy with this" },
  "extracted": ["SALARY: ₹1,800,000"],
  "plan": "Ask about Section 80C investments (PPF, ELSS, PF, Life Insurance up to 1.5L).",
  "tax_report": null
}
```

| Field | Type | Source |
|---|---|---|
| `response` | `str` | Consultant reply (light markdown: `**bold**`, `_italics_`, bullets) — `nlp_engine.py:242` |
| `session` | `object` | Mutated state; the client must wholesale-replace its copy (frontend does this at `ChatInterface.tsx:157-158`) |
| `extracted` | `str[]` | Human-readable badges, e.g. `"SALARY: ₹1,800,000"`, `"80E: ₹500,000"`, `"SALARY (ANNUALIZED): ₹11,520,000"`, `"80C: ₹200,000 (CORRECTED)"`, `"80C: Noted (None)"` — `nlp_engine.py:135,154,185,217` |
| `plan` | `str` | The discovery agent's next step, without the `plan: ` prefix — `nlp_engine.py:220-221`. Quirk: on bare-"no" turns the plan can be one step **behind** the response text, because the zero-fill advance happens inside reply generation (`nlp_engine.py:276-287`) |
| `tax_report` | `object \| null` | Present (not `null`) only when at least one income key is positive; same shape as the `/calculate` response below |

### Errors

| Condition | Result |
|---|---|
| Body not matching `ChatRequest` (missing `message`/`session`, wrong types) | `422` with FastAPI's standard `{"detail": [...]}` |
| Engine exception during calculation | `200` with `tax_report: null`; the traceback text goes to the server console only (`main.py:52-55`) |
| Exception inside NLP itself | Unhandled → `500` (no global exception handler exists) |

---

## `POST /calculate`

Stateless recomputation used by the report dashboard (`TaxReport.tsx:24-28` sends the **whole session object** on every session change — duplicating work `/chat` already did).

### Request

```json
{
  "id": "sid_1730000000000",
  "salary": 1800000,
  "80c": 150000,
  "80d": 25000,
  "nps": 50000,
  "age": 30,
  "capital_gains": [{ "type": "equity_ltcg", "amount": 200000, "holding": "unknown" }]
}
```

**No schema validation** — the handler takes raw `Dict[str, Any]` (`main.py:94-98`). The engine coerces with `float(x or 0)` for amounts (`tax_engine.py:53-64`), so `null`/missing keys are tolerated, but malformed shapes crash: a `capital_gains` entry that is not an object raises `AttributeError` → `500` (`tax_engine.py:296-299`); a non-numeric string in any amount raises `ValueError` → `500`. Honored keys and caps are documented in [tax-rules.md](tax-rules.md) §2.

### Response — 200

The engine returns `{old_regime, new_regime, recommendation, savings, efficiency_score}` (`tax_engine.py:136-142`); each regime is a serialized `TaxResult` dataclass (`tax_engine.py:31-45`):

```json
{
  "old_regime": {
    "income_details":   [{ "source": "Income from Salary", "amount": 1800000.0, "section": "17(1)", "status": "Reported" }],
    "deduction_details": [],
    "gross_total_income": 1800000.0,
    "total_deductions": 277500.0,
    "taxable_income": 1722500.0,
    "total_tax": 289770.0,
    "recommendation": "New Regime",
    "savings": 64220.0,
    "explanations": [
      { "particular": "Standard Deduction", "reason": "Flat deduction for salaried employees.",
        "section": "16(ia)", "amount": 50000, "status": "Valid", "eli5": "" },
      { "particular": "Professional Tax", "reason": "State statutory tax on employment.",
        "section": "16(iii)", "amount": 2500.0, "status": "Valid", "eli5": "" },
      { "particular": "Section 80C", "reason": "PF, PPF, ELSS, Life Insurance, School Fees.",
        "section": "80C", "amount": 150000.0, "status": "Valid", "eli5": "" },
      { "particular": "Section 80D (Self & Family)", "reason": "Health insurance premium and preventive checkup.",
        "section": "80D", "amount": 25000.0, "status": "Valid", "eli5": "" },
      { "particular": "NPS Section 80CCD(1B)", "reason": "Additional voluntary contribution to National Pension System.",
        "section": "80CCD(1B)", "amount": 50000.0, "status": "Valid", "eli5": "" }
    ],
    "slabs_breakdown": [
      { "range": "Above 10L", "rate": "30%", "income": 522500.0, "tax": 156750.0 },
      { "range": "5L - 10L",  "rate": "20%", "income": 500000,   "tax": 100000.0 },
      { "range": "2.5L - 5L", "rate": "5%",  "income": 250000,   "tax": 12500.0 },
      { "range": "0 - 2.5L",  "rate": "0%",  "income": 250000,   "tax": 0.0 }
    ],
    "efficiency_score": 54.7,
    "savings_tips": [],
    "audit_observations": [],
    "risk_level": "Low"
  },
  "new_regime": { "…same TaxResult shape (std ded 75000, 115BAC slabs, total_tax 225550.0)…" },
  "recommendation": "New Regime",
  "savings": 64220.0,
  "efficiency_score": 54.7
}
```

(Values above are the engine's actual output for the example input, captured 2026-10-31. Note the professional-tax default ₹2,500 was assumed because `salary > 0` — see [tax-rules.md](tax-rules.md) §2 — and the ₹1.25L LTCG exemption was applied to the single `equity_ltcg` entry.)

| Field | Notes |
|---|---|
| `recommendation` | `"New Regime"` when `new.total_tax <= old.total_tax`, else `"Old Regime"` (`tax_engine.py:93`) |
| `savings` | `abs(old − new)`, rounded to 2 dp (`tax_engine.py:94,140`) |
| `efficiency_score` | ANFIS output 0-100 rounded to 1 dp — heuristic fallback (30-98.5) if numpy is missing (`ai_models.py:506-559`) |
| `income_details[]` | `{source, amount, section, status}` per populated income head (`tax_engine.py:193-203, 266-274`) |
| `explanations[]` | `{particular, reason, section, amount, status, eli5}` (`Explanation` dataclass, `tax_engine.py:21-28`) |
| `slabs_breakdown[]` | `{range, rate, income, tax}` top-down (`tax_engine.py:323-368`) |
| `savings_tips[]` / `audit_observations[]` / `risk_level` | From `ReasoningAgent.get_savings_tips` and the HRA/80G/CG risk heuristics (`tax_engine.py:107-134`, `ai_models.py:418-454`) |

Values are made JSON-safe by `clean_json` (dataclasses → `__dict__`, numpy scalars → `.item()`), `main.py:33-38`.

### Errors

Any engine exception is unhandled → `500` Internal Server Error (there is no global exception handler; `main.py:94-98`).

---

## `GET /history/{sid}`

Returns every audit-log entry recorded for `sid`. The **entire** `logs/session_audit.json` is read synchronously inside the async handler and filtered by `session_id` (`main.py:81-92`).

### Response — 200

Array of entries as written by `AuditLogger` (`audit_logger.py:14-34`):

```json
[
  {
    "timestamp": "2026-04-23T22:59:12.806796",
    "session_id": "sid_1776965272179",
    "user_input": "childs tution of 2 Lakhs",
    "ai_response": "Successfully mapped SALARY: ₹200,000. …",
    "internal_state": { "profile": "Salaried", "salary": 200000.0, "80c": 114000.0, "…": "…" },
    "tax_calculation": {
      "old_regime": { "total_tax": 0.0, "taxable_income": 0.0, "efficiency": 30.0 },
      "new_regime": { "total_tax": 0.0, "taxable_income": 0.0, "efficiency": 30.0 },
      "recommendation": "New Regime",
      "savings": 0.0,
      "efficiency_score": 30.0
    }
  }
]
```

| Field | Notes |
|---|---|
| `internal_state` | Full session minus `history`-style `"memory"` key (`audit_logger.py:38-45`) — contains all financial figures in plaintext |
| `tax_calculation` | `"Pending"` when no calculation ran; otherwise only `{total_tax, taxable_income, efficiency}` per regime plus the top-level scalars (`audit_logger.py:47-60`) |

### Errors / edge behavior

| Condition | Result |
|---|---|
| Log file missing | `200` with `[]` (`main.py:83-85`) |
| Log file corrupt (JSON parse error) | `200` with `[]` — broad `except` (`main.py:86-92`) |
| Unknown `sid` | `200` with `[]` (filter simply matches nothing) |

There is **no 404 and no 401/403** — any caller can read any session's financial data, and `sid` values are timestamp-guessable (`sid_${Date.now()}`). See [security.md](security.md).

---

## Worked curl examples

Backend running via `cd backend && python main.py`. (Quoting style matches Windows `cmd` / the existing [deployment.md](deployment.md) examples.)

```bash
:: 1. Open a consultation — profession + income in one message
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" ^
  -d "{\"message\":\"I am a software engineer earning 18 LPA\",\"session\":{\"id\":\"sid_demo1\",\"phase\":\"PROFILING\"}}"
```

Response `extracted` is `["SALARY: ₹1,800,000"]`, `plan` asks about 80C, and `tax_report` is already populated (income > 0). Copy the returned `session` object into the next call.

```bash
:: 2. Declare a deduction (session = the object returned above)
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" ^
  -d "{\"message\":\"1.5 lakhs in PPF\",\"session\":{ ...session from step 1... }}"

:: 3. Skip a slot, then force the final report
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" ^
  -d "{\"message\":\"no\",\"session\":{ ...session... }}"
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" ^
  -d "{\"message\":\"/end\",\"session\":{ ...session... }}"

:: 4. Recompute standalone (what the report dashboard does on every session change)
curl -X POST http://localhost:8000/calculate -H "Content-Type: application/json" ^
  -d "{\"id\":\"sid_demo1\",\"salary\":1800000,\"80c\":150000,\"80d\":25000,\"nps\":50000,\"age\":30}"

:: 5. Read the audit trail for a session
curl http://localhost:8000/history/sid_demo1

:: 6. Read a session you never created (no auth — this also succeeds)
curl http://localhost:8000/history/sid_1730000000000
```

Note on step 3: because bare `"no"` fills the currently-asked slot with `0` and advances the waterfall (`nlp_engine.py:276-287`), the `/end` call after it produces a `session` with `80c/80d/…: 0` for every skipped slot and `phase: "FINAL"`, with `tax_report` containing the complete dual-regime statement.

---

## Frontend consumption (reference)

| Call site | Behavior |
|---|---|
| `ChatInterface.tsx:148-157` | `POST /chat` with `{message, session}`; replaces its session with `data.session`; shows `data.extracted` as badges after an artificial 400 ms delay (`ChatInterface.tsx:160-174`) |
| `ChatInterface.tsx:171-173` | Opens the report pane when `session.phase === "FINAL"` or a non-empty `tax_report` arrives |
| `TaxReport.tsx:18-52` | `POST /calculate` with the **whole session** on every `session` object change (`useEffect` dep `[session]`), so every turn computes the tax twice |
| Error surfaces | Chat failure message hardcodes `http://localhost:8000` (`ChatInterface.tsx:183`); report failure likewise (`TaxReport.tsx:74-84`) |

Both data paths hardcode `localhost:8000` — the app cannot reach a hosted backend until ADR-010 ([decisions.md](decisions.md)) lands.

## Known limitations

- **No auth, no rate limiting, no request-size cap** — see [security.md](security.md).
- **CORS `*`** (`main.py:18`) means any origin can call and read these endpoints from a browser.
- **Session state is client-owned and tamperable** (ADR-002): a caller may send a forged `salary`, `age`, or `phase` directly to `/calculate`.
- **`/history` reads the whole audit file synchronously** per request; latency grows with total log size, and concurrent requests race with `AuditLogger`'s read-modify-write (`audit_logger.py:24-35`).
- **Double annualization trap for API consumers**: a message containing both a parser-level unit (`"80,000 per month"`) and the engine-level monthly keywords is multiplied by 12 twice — `"my salary is 80,000 per month"` yields `salary = 11,520,000` (verified; documented in [nlp-pipeline.md](nlp-pipeline.md) and [tax-rules.md](tax-rules.md) C3).

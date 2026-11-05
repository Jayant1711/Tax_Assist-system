# TAX_REPORT_TRANSPARENCY_AUDIT — Phase 4A.4

Scope: full read of every frontend source file (`frontend/src/**`), the API layer, and the
backend response contracts they consume (`backend/main.py`, `backend/tax_engine.py`,
`backend/audit_logger.py`). All `file:line` references are to this repo root.

---

## 1. Payload mapping: backend → api lib → TaxReport

### 1.1 Backend response shapes (ground truth)

**`POST /chat`** (`backend/main.py:1238-1245`) returns:

```
{
  "response":   str            # conversational text (NLP composer)
  "session_id": str
  "session":    {...}          # read-only projection (main.py:575-585, scrub via audit_logger.py:154-172);
                               # carries income + deduction keys: salary, 80c, 80d, 80d_parents,
                               # 80e, 80g, nps, 24b, hra_received/rent_paid, ... (main.py:402-407)
  "extracted":  [str] | null
  "plan":       {...} | null   # NEVER read by the frontend
  "tax_report": {...} | null   # FULL dual-regime engine payload — discarded by the frontend (see §3)
}
```

**`POST /calculate`** (`backend/main.py:1314-1327`) returns the engine dict directly
(`clean_json`'d `TaxResult` dataclasses, `main.py:617-622`):

```
{
  "fy_label": str,
  "old_regime": TaxResult,     # tax_engine.py:200-215
  "new_regime": TaxResult,
  "recommendation": "New Regime" | "Old Regime",   # tax_engine.py:361
  "savings": float,                                # tax_engine.py:362, 502
  "efficiency_score": float                        # tax_engine.py:503
}
```

Each `TaxResult` (`backend/tax_engine.py:200-215`) carries:
`income_details`, `deduction_details` (**declared at tax_engine.py:203, never populated anywhere —
grep confirms the only occurrence is the field declaration**), `gross_total_income`,
`total_deductions`, `taxable_income`, `total_tax`, `recommendation`, `savings`,
`explanations` (`Explanation` dataclass, tax_engine.py:191-198: `particular, reason, section,
amount, status, eli5`), `slabs_breakdown`, `efficiency_score`, `savings_tips`,
`audit_observations`, `risk_level`.

Regime internals:
- **OLD** (`_calc_old`, tax_engine.py:517-658): applies capped deductions (ded dict built at
  tax_engine.py:327-353 — caps applied via `min()` at 328-342, so the *booked* pre-cap amount is
  discarded at source) and emits one `Explanation` per applied section (tax_engine.py:600-656).
- **NEW** (`_calc_new`, tax_engine.py:660-732): applies only std deduction (tax_engine.py:663, 671);
  `explanations` = std deduction + one zero-amount `Section 115BAC` entry whose `eli5` says
  "itemized 80C/80D/HRA foregone" (tax_engine.py:727-730). **No ignored-deduction enumeration
  exists anywhere in the payload.**

### 1.2 Frontend API layer

`frontend/src/lib/api.ts:37-46` — `apiFetch` is a thin `fetch` wrapper (BASE + forced
`credentials: "include"` + 401 hook). It adds no typing and no shaping: the raw backend JSON
flows straight into components as `any`.

### 1.3 TaxReport consumption (`frontend/src/components/TaxReport.tsx`)

Fetches `POST /calculate {session_id}` (TaxReport.tsx:31-35; contract regression-tested in
`__tests__/TaxReport.test.tsx:63-77`) and reads, from the response:

| Field | Line(s) |
|---|---|
| `data.recommendation` | 96 |
| `data.new_regime` / `data.old_regime` → `best` | 97 |
| `data.efficiency_score ?? best.efficiency_score` | 99 |
| `data.savings` | 157 |
| `data.fy_label` | 117, 131 |
| `best.total_tax` | 164, 314, 322, 330 |
| `best.gross_total_income` | 167, 174, 250 |
| `best.total_deductions` | 177 |
| `best.income_details` (source/section/amount) | 239-245 |
| `best.explanations` (particular/reason/section/amount — **not** `status`, **not** `eli5`) | 254-260 |
| `best.taxable_income` | 272 |
| `best.slabs_breakdown` (range/rate/income/tax) | 301-307 |
| `best.audit_observations`, `best.risk_level` | 341-352 |
| `best.savings_tips` | 210, 367-383 |

`SavingsGraph.tsx` additionally reads `old_regime/new_regime` `.total_tax/.gross_total_income/
.taxable_income` (12-15, 74, 109), `data.recommendation` (18), `data.savings` (19).

**Fields never consumed by any frontend code:** `deduction_details` (empty backend-side anyway),
`Explanation.status`, `Explanation.eli5`, per-regime `savings`/`recommendation` duplicates,
and — critically — every `explanations`/`slabs_breakdown`/`audit_observations` field of the
**non-recommended** regime (see 2b).

---

## 2. Question-by-question transparency verdicts

**(a) Entered deductions — PARTIAL.**
The booked deduction values travel in the `/chat` `session` projection (keys per
`main.py:402-407`), but the only render surface is the **debug panel** — a raw
`<pre>{JSON.stringify(projection, null, 2)}</pre>` dump behind the "🔍 Debug" toggle
(`ChatInterface.tsx:287-297`, toggle at 244-251). There is no user-facing "here is what you
told us" list. The sidebar shows only `profile` + `phase` (`page.tsx:221-233`).

**(b) Applied deductions per regime — PARTIAL.**
Applied deductions render as the "Less:" rows of the computational statement from
`best.explanations` (`TaxReport.tsx:254-260`) — but `best` is hard-wired to the recommended
regime only (`TaxReport.tsx:97`: `const best = rec === 'New Regime' ? data.new_regime :
data.old_regime`). There is no regime toggle anywhere in the component. In the verified ₹46L
scenario (new recommended), the user sees only the ₹75k std row and **never** the old regime's
₹3,20,000 itemization (std 50k + 80C 150k + 80D 25k + NPS 50k + HRA 20k + 80G 25k) even though
the backend sends it (`tax_engine.py:499-500`).

**(c) Ignored deductions (booked but not applied) — VERIFIED-NO.**
No frontend surface and no backend field. `TaxResult.deduction_details`
(`tax_engine.py:203`) — the natural carrier — is declared and never populated. Pre-cap booked
amounts are destroyed at `tax_engine.py:328-342` (`min(booked, cap)` with the booked value not
retained), so the engine could not even report "80C booked ₹2,00,000 → allowed ₹1,50,000"
without a change.

**(d) WHY deductions were ignored (115BAC) — PARTIAL.**
The only data-driven hint is the zero-amount `Section 115BAC` Explanation
(`tax_engine.py:730`), which renders — when new regime is recommended — as a statement row
"Less: Section 115BAC (Default New Tax Regime with concessional slab rates.) (−) ₹0"
(`TaxReport.tsx:254-260`). Its `eli5` ("itemized 80C/80D/HRA foregone") is never rendered
(the mapper at TaxReport.tsx:256-258 reads only particular/reason/section/amount). The
SavingsGraph banner adds a **hard-coded, data-blind** sentence
(`SavingsGraph.tsx:147-151`). No enumeration of which sections were dropped, or for how much.

**(e) Deduction impact on tax (aggregate) — VERIFIED-NO.**
The frontend shows the aggregate `total_deductions` (`TaxReport.tsx:177`) and the aggregate
regime `savings` (`TaxReport.tsx:157`, `SavingsGraph.tsx:145`), but there is no
deduction→tax bridge anywhere.

**(f) Old vs new regime comparison — VERIFIED-YES.**
`SavingsGraph.tsx:42-112` renders both regimes' total tax, effective rate, taxable income,
winner badge; savings banner at 114-153. This is the one fully-verified transparency item.

**(g) Why a regime was selected — PARTIAL.**
Backend `recommendation` is a bare string from `new <= old` (`tax_engine.py:361`) with **no
rationale field**. The only "why" text is client-side static copy
(`SavingsGraph.tsx:147-151`) that does not reference the user's actual numbers. The KPI tile
(`TaxReport.tsx:151-159`) answers *what* (strategy + ₹savings), not *why*.

**(h) Per-deduction tax reduction (rupee saving per section) — VERIFIED-NO.**
Not sent (`TaxResult` has no per-deduction impact field; marginal slab rate × deduction is
never exposed) and not rendered. The advice tab's `savings_tips` are unquantified strings
(`tax_engine.py:489-491`).

**(i) Engine `explanations` / `audit_observations` — VERIFIED-YES (recommended regime only).**
- `explanations` → statement rows (`TaxReport.tsx:254-260`).
- `audit_observations` → "Compliance Observations" risk banner (`TaxReport.tsx:341-355`).
- `savings_tips` → advice tab cards (`TaxReport.tsx:366-388`).
Caveats: only for `best` (see 2b); `Explanation.status` ("Valid") and `Explanation.eli5`
(`tax_engine.py:197-198`) are dropped on the floor.

**Found bug (transparency defect):** when the New Regime is recommended, the statement shows the
std deduction **twice** — once from `best.explanations` (`tax_engine.py:728-729` emits it) and
again from the hard-coded block `TaxReport.tsx:262-268` ("Standard Deduction for Salaried
Employees … (−) ₹75,000"). The printed statement does not reconcile to `taxable_income`
(₹46,00,000 − 75,000 − 75,000 ≠ ₹45,25,000).

**Related hard-coded-copy defects:** `SavingsGraph.tsx:32` pins "FY 2024-25" while the report
header uses `data.fy_label`; `SavingsGraph.tsx:108` claims "Nil tax up to ₹7L (87A)" while the
sidebar (`page.tsx:212`) claims "zero tax up to ₹12L" — contradictory static strings on one
screen.

---

## 3. ChatInterface: intelligence vs chat text

`ChatInterface.tsx:164-181`: the handler reads `data.response` (chat text, rendered at 174 via
`formatMarkdown`), `data.extracted` (green "✓" badges, 311-330), `data.session` → projection
(165-167), and `data.session_id` (167).

**The full `tax_report` payload — including `explanations`, `audit_observations`,
`savings_tips`, `slabs_breakdown` for BOTH regimes — arrives on every income-bearing turn
(`main.py:1244`) and is used only as a boolean trigger**:
`if (nextProjection?.phase === 'FINAL' || (data.tax_report && Object.keys(data.tax_report).length > 0)) onShowReport(true)`
(`ChatInterface.tsx:180`). Nothing from it is rendered in the chat.
`data.plan` (`main.py:1243`) is never read at all.

Verdict: **VERIFIED-NO** — the chat reply surfaces only the conversational text + extracted
badges; all engine intelligence is silently dropped (the report panel is a separate pane the
user must open).

---

## 4. The visibility gap

### 4.1 Backend already sends; frontend fails to render

1. `tax_report` in every `/chat` response (`main.py:1244`) — the entire dual-regime payload;
   discarded except as a truthiness flag (`ChatInterface.tsx:180`).
2. `plan` in every `/chat` response (`main.py:1243`) — never read.
3. The **non-recommended regime's** full detail set — `explanations`, `income_details`,
   `slabs_breakdown`, `audit_observations`, `risk_level`, `total_deductions` — sent for both
   regimes (`tax_engine.py:499-500`) but only `best` is ever rendered (`TaxReport.tsx:97`).
   This is the single largest recoverable gap: in the ₹46L scenario the user cannot see the
   old regime's ₹3,20,000 itemization that justifies the ₹1,65,360 difference.
4. `Explanation.eli5` and `Explanation.status` (`tax_engine.py:197-198`) — never rendered
   (`TaxReport.tsx:256-258`).
5. Session projection deduction keys (`main.py:402-407`) — visible only as debug JSON
   (`ChatInterface.tsx:294`).

### 4.2 Missing backend-side (cannot be rendered even if the frontend tried)

1. **`deduction_details`** — declared (`tax_engine.py:203`), never populated. Needs one record
   per section per regime: `{section, booked, applied, ignored_amount, reason, tax_impact}`.
   Prerequisite: retain pre-cap booked amounts at `tax_engine.py:328-342`.
2. **Ignored-deduction list for the new regime** — which of the user's booked 80C/80D/NPS/HRA/
   24(b) amounts were foregone under 115BAC, with amounts and the statutory reason
   (data exists in session state + `tax_engine.py:660-672`; only the generic zero-amount
   115BAC Explanation at :730 exists today).
3. **Per-deduction rupee tax impact** — `applied × marginal slab rate` per section (all inputs
   available inside `_calc_old`); nothing similar exists in `TaxResult`.
4. **Regime-selection rationale** — a one-paragraph engine-generated comparison citing the
   user's actual numbers (₹3,20,000 itemized vs ₹75,000 std vs slab-rate delta); today
   `recommendation` is a bare string (`tax_engine.py:361`) and the "why" is client-side
   hard-coded copy (`SavingsGraph.tsx:147-151`).
5. Old-regime mirror of the 115BAC note (the zero-amount context entry exists only in
   `new_res.explanations`, `tax_engine.py:730`).

---

## 5. Concrete fix plan

| # | Fix | Files | Scope |
|---|---|---|---|
| F1 | **Delete the hard-coded std-deduction row** (`TaxReport.tsx:262-268`) — the payload's `explanations` already carries it; removes the double-count in the printed statement. | `TaxReport.tsx` | S |
| F2 | **Regime toggle** — turn `best` (TaxReport.tsx:97) into state initialized from `recommendation`; add Old/New tabs so all per-regime fields already in the payload become visible. Update `TaxReport.test.tsx` fixtures. | `TaxReport.tsx` | M |
| F3 | **Render `eli5` + `status`** — subtext under each statement row / tooltip; plus a 115BAC foregone-deductions callout when the new regime is recommended. | `TaxReport.tsx` | S |
| F4 | **"Deductions Booked vs Applied vs Ignored" card** — new component; Booked from session projection, Applied from `best.explanations`, Ignored from the new backend `deduction_details` (B1). Per-regime aware (needs F2). | new `DeductionsAuditCard.tsx`, `TaxReport.tsx` | L (frontend half M) |
| F5 | **Surface intelligence in chat** — when `data.tax_report` is present, append a compact strip to the AI message (recommendation, ₹savings, top audit observation, link/scroll to report) instead of discarding it at `ChatInterface.tsx:180`. | `ChatInterface.tsx` | S-M |
| F6 | **Per-deduction rupee impact column** — backend: compute `tax_impact` per Explanation in `_calc_old` (and `0`/n-a for new regime) or populate `deduction_details`; frontend: add "Tax Saved" column to the statement + total. | `tax_engine.py`, `TaxReport.tsx` | L |
| F7 | **Engine rationale for regime choice** — backend: add `rationale` string to the `/calculate` result citing actual figures; frontend: render it in the SavingsGraph banner replacing hard-coded copy (`SavingsGraph.tsx:147-151`). | `tax_engine.py`, `SavingsGraph.tsx` | M |
| F8 | **Populate `deduction_details`** with booked/applied/ignored/reason per section (retain pre-cap bookings at `tax_engine.py:328-342`); feeds F4 and makes (c)+(d) answerable. | `tax_engine.py` | M |
| F9 | **"What you told us" card** — friendly renderer of the projection's income/deduction keys (replaces debug-only JSON as the primary surface; keep the debug panel). | `page.tsx` sidebar or new component | S-M |
| F10 | **De-hard-code static copy** — `SavingsGraph.tsx:32` (use `data.fy_label`), `:108` (rebate text from payload/rules), reconcile with `page.tsx:212`. | `SavingsGraph.tsx`, `page.tsx` | S |

Sequencing note: B-items (F6 backend, F8, F7 backend) are prerequisites for full (c)/(d)/(e)/(h)
transparency; F1-F3, F5, F9, F10 are frontend-only and ship independently.

---

## 6. Ten-line summary

1. (a) Entered deductions: **PARTIAL** — projection keys exist (`main.py:402-407`) but render only as debug JSON (`ChatInterface.tsx:294`).
2. (b) Applied deductions per regime: **PARTIAL** — `best.explanations` rendered (`TaxReport.tsx:254-260`) for the recommended regime only (`TaxReport.tsx:97`); no toggle.
3. (c) Ignored deductions: **VERIFIED-NO** — no field (`tax_engine.py:203` never populated) and no UI.
4. (d) Why ignored (115BAC): **PARTIAL** — only a zero-amount 115BAC row (`tax_engine.py:730` → `TaxReport.tsx:254-260`); `eli5` never rendered; rest is hard-coded copy (`SavingsGraph.tsx:147-151`).
5. (e) Deduction impact on tax: **VERIFIED-NO** — aggregates only (`TaxReport.tsx:157,177`); no per-deduction bridge, backend or frontend.
6. (f) Old vs new comparison: **VERIFIED-YES** — `SavingsGraph.tsx:42-112` (tax, eff. rate, taxable income, winner, savings).
7. (g) Why the regime was selected: **PARTIAL** — bare `recommendation` string (`tax_engine.py:361`); the "why" is static, data-blind client text (`SavingsGraph.tsx:147-151`).
8. (h) Per-deduction tax reduction: **VERIFIED-NO** — no rupee-impact field anywhere in `TaxResult` (`tax_engine.py:200-215`).
9. (i) `explanations`/`audit_observations`: **VERIFIED-YES** — rendered for the recommended regime (statement rows `TaxReport.tsx:254-260`; risk banner `341-355`; tips `366-388`).
10. Chat: **VERIFIED-NO** — reply shows only `response`+`extracted` (`ChatInterface.tsx:174,311-330`); the full `tax_report` (`main.py:1244`) is a truthiness trigger (`:180`) and `plan` is never read. Plus: double-counted ₹75k std-deduction row in the New-Regime statement (`TaxReport.tsx:262-268`).

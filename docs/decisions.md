# Architecture Decision Records

Format: lightweight ADRs. **Status:** Accepted / Superseded / Proposed.
ADRs 001-007 document decisions already embodied in the code; ADRs 008-011 are proposed by the 2026-10-31 audit and tracked in [roadmap.md](roadmap.md).

---

## ADR-001 — Deterministic rule-based tax engine (no ML in the calculation path)

**Status:** Accepted
**Date:** project origin (pre-2026-04)

**Context:** Tax output feeds real filing decisions. A wrong slab or an ineligible deduction produces incorrect filings; probabilistic output is unacceptable for the core computation.

**Decision:** Tax liability is computed exclusively by deterministic rules (`backend/tax_engine.py`). Machine learning (ANFIS) is confined to a subjective "efficiency score" that never alters tax amounts.

**Consequences:** ✅ Reproducible, testable, explainable output. ❌ Every FY change is manual code work (see ADR-008); the ML layer's value is cosmetic until its ground truth matches the engine (W4 in [architecture.md](architecture.md#5-known-architectural-weaknesses-audit-2026-10-31)).

---

## ADR-002 — Client-owned session state

**Status:** Accepted — **flagged for reversal (see ADR-007)**
**Date:** project origin

**Context:** The chat frontend needs conversation continuity without a backend session store.

**Decision:** The entire session dict (income, deductions, internal keys like `_last_val`, `phase`, full `history[]`) is stored in React state and round-tripped on every request; the server keeps nothing (`backend/main.py:29-32`, `frontend/src/components/ChatInterface.tsx:148-152`).

**Consequences:** ✅ Zero server-side session infrastructure; trivial horizontal scale of compute. ❌ State is tamperable (client can forge `salary`, `phase`, `_last_val`); payloads grow unbounded; no multi-device; server logic depends on untrusted input. Security implications: [security implications in roadmap C5/H5].

---

## ADR-003 — Regex NLP + keyword-proximity semantic attention (no LLM)

**Status:** Accepted
**Date:** project origin

**Context:** The product must extract financial entities from free text (English + Hinglish) without external API cost or latency.

**Decision:** Hand-built `UniversalParser` (Indian money formats, word numbers) + `SemanticAttention` (keyword presence × Gaussian proximity decay × content score, profile-locked penalties) + a scripted discovery waterfall (`backend/ai_models.py`, `backend/nlp_engine.py`).

**Consequences:** ✅ Free, fast, deterministic, runs offline. ❌ Precision ceiling reached in practice — the repo's own logs show systematic misclassifications (education-loan interest → income; tuition → salary; property sale → other income) recorded in `backend/logs/session_audit.json` and tracked as finding C4. Improve within this paradigm (more tests, better keyword tables) before considering an LLM extractor.

---

## ADR-004 — ANFIS neuro-fuzzy efficiency scoring

**Status:** Accepted — quality concerns logged
**Date:** 2026-04 (ANFIS v3/v4 iterations)

**Context:** The product wants a single 0-100 "how optimized is this taxpayer" metric to visualize.

**Decision:** A 20-input × 64-rule TSK ANFIS (`backend/ai_models.py:459-545`) trained offline by `anfis_trainer.py` (EE-Bat search over synthetic scenarios) and shipped as `anfis_weights.json`.

**Consequences:** ✅ Works offline at inference (tiny numpy forward pass); deterministic fallback heuristic exists when numpy is absent. ❌ Training ground truth diverges from the live engine's math (HRA, surcharge bands differ — `anfis_trainer.py` vs `tax_engine.py:316-321,283-292`), so the advertised R²=0.88 is measured against the wrong target; the refiner `anfis_refine.py` is dimensionally incompatible (10×50 vs 20×64) and broken; weights are reshaped without validation at import (`ai_models.py:482-485`). Re-train against live-engine outputs or park the score behind a "beta" label (roadmap Week 4).

---

## ADR-005 — File-based JSON persistence for audit trails

**Status:** Accepted — **flagged for replacement (see ADR-009)**
**Date:** project origin

**Context:** Compliance instinct: record every user-AI turn for auditability, with zero infra.

**Decision:** `AuditLogger` rewrites the whole `logs/session_audit.json` on each turn (`backend/audit_logger.py:24-35`); `SessionLab` rewrites per-session JSON (`backend/session_lab.py:22-46`).

**Consequences:** ✅ Human-readable, zero-dependency. ❌ O(n²) I/O growth; no file locking → concurrent requests lose entries; a read error silently resets history to `[]` and the rewrite **destroys the audit trail** — a direct violation of the repo's own "preserve audit logging" rule (`AGENTS.md`). Client-controlled `session.id` is joined into a filesystem path (`session_lab.py:22`) — arbitrary file write (Critical, roadmap C6).

---

## ADR-006 — FastAPI + Next.js App Router split

**Status:** Accepted
**Date:** project origin

**Context:** Python for the rules/AI layer; modern React for the consultant-style dashboard UX.

**Decision:** FastAPI monolith backend (port 8000), Next.js 16 App Router frontend (port 3000), JSON over HTTP, CORS `allow_origins=["*"]` (`main.py:18`).

**Consequences:** ✅ Clean separation matching `AGENTS.md`; independent deploys possible. ❌ Frontend hardcodes `http://localhost:8000` (`ChatInterface.tsx:148`, `TaxReport.tsx:24`) — not deployable as-is; the dashboard duplicates `/chat`'s calculation via `/calculate` (2× work per turn). Fix via ADR-010/ADR-011.

---

## ADR-007 (Proposed) — Move session state server-side

**Status:** Proposed (roadmap Week 3)

**Context:** ADR-002's client-owned state is the root of the forged-session and data-exposure findings (C5, H5).

**Decision (proposed):** Backend issues an opaque session ID (UUID) and stores state server-side (SQLite to start, Redis later); the client sends only `{session_id, message}`. `/history` becomes server-authenticated.

**Consequences:** ✅ Tamper-proof state, auth becomes possible, small payloads. ❌ Migration touches every component; adds storage ops. Client-session signing is the fallback if server-side state is rejected.

---

## ADR-008 (Proposed) — Versioned tax-rules registry

**Status:** Proposed (roadmap Week 2)

**Context:** FY constants are scattered across `tax_engine.py`, `anfis_trainer.py`, `test_suite.py`, and four frontend files (checklist in [tax-rules.md §6](tax-rules.md#6-rule-change-checklist-where-fy-constants-live)); the engine is currently one FY stale (Critical C1).

**Decision (proposed):** `backend/tax_rules/fy_2024_25.py`, `fy_2025_26.py`, … each exporting slabs, caps, rebate, surcharge, CG rates as data; `TaxEngine` selects by a `tax_year` parameter and reports which FY it used in every response.

**Consequences:** ✅ FY updates become data diffs; the UI can warn when computing on a stale year. ❌ One-time refactor of engine + trainer + tests.

---

## ADR-009 (Proposed) — Append-only audit persistence

**Status:** Proposed (roadmap Week 2)

**Decision (proposed):** Replace read-modify-write with append-only JSONL (one line per turn) or SQLite in WAL mode; never truncate on read error; add rotation and a retention policy; sanitize `session_id` to `^[w-]{8,64}$`.

**Consequences:** ✅ O(1) writes, no lost entries, audit trail survives corruption, closes the path-traversal hole.

---

## ADR-010 (Proposed) — Configurable API base URL

**Status:** Proposed (roadmap Week 3)

**Decision (proposed):** `NEXT_PUBLIC_API_URL` env var (default `http://localhost:8000` for dev) consumed via a small `lib/api.ts`; remove both hardcoded fetch sites.

---

## ADR-011 (Proposed) — pytest + CI as the test harness

**Status:** Proposed (roadmap Week 1)

**Context:** The custom 97-check harness (`backend/test_suite.py`) has loose tolerances, cannot-fail smoke scripts (`backend/smoke_test.py:30,36,43` print `[PASS]` unconditionally), no API tests, and no CI.

**Decision (proposed):** Migrate to pytest; add FastAPI `TestClient` endpoint tests incl. malformed input and forged sessions; golden-file regression tests replaying the misclassified sentences from `backend/logs/session_audit.json`; GitHub Actions running pytest + `pip-audit` + `npm audit` + `next build`.

**Consequences:** ✅ CI-enforceable quality bar; IDE integration. ❌ One-time migration effort (~1 day).

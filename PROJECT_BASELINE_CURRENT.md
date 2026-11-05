# PROJECT_BASELINE_CURRENT.md — Sprint 7 Starting Baseline
**Frozen:** 2026-11-05 at the v0.6-sprint6 release (PR #5 merged, main `46051d8` + changelog `d3e7a0b`) · **Purpose:** the authoritative starting state for future planning — supersedes `PROJECT_BASELINE_V0_5.md` · every number measured, not transcribed

---

## 1. Architecture

```
Frontend  Next.js 16.4.3 / React 19.2.4 / TypeScript — 3-pane responsive shell
   │      chat UI · Applied-vs-Ignored panel · INTELLIGENCE CARDS (ranked,
   │      evidence, acceptance actions) · Per-Deduction Impact table ·
   │      regime comparison · ITR statement
   ▼      REST + HttpOnly cookie sessions (apiFetch, 401 → /login)
Backend   FastAPI 0.162.0 / Pydantic 2.14.2 / uvicorn 0.54 — 17 REST endpoints
   │      auth (scrypt + HttpOnly) · server-side sessions (ADR-013)
   │      rate limits · fail-closed CORS (ADR-014) · append-only audit (ADR-009)
   ├──    NLP Engine: prepass guards → UniversalParser → SemanticAttention →
   │      waterfall → Response Composer → Tax Intelligence →
   │      shared _closing_intelligence (natural + /end close identically)
   ├──    TaxEngine (tax_engine.py) + tax_rules/{fy_2024_25,fy_2025_26}
   │      — the ONLY tax calculator  [ADR-001] · now with deduction_impact()
   │      (exact leave-one-out per-deduction impact)
   ├──    calibration.py — ECE instrument + canary  [G7 gate]
   └──    SQLite (WAL) · recommendation_events (ADR-017) · tax_rules registry
Data      SQLite (users, app_sessions, recommendation_events) · JSONL audit
          · data/anfis_v3 (regenerable, 270MB local-only) · corpus-v1 (pinned)
CI        GitHub Actions, 3 jobs (green on every push + both release PRs)
```

**ADRs:** 001 (TaxEngine sole calculator) · 003 (offline/deterministic) · 008 (tax-rules registry) · 009 (append-only audit) · 012/013/014 (auth/sessions/edge) · 015 (deterministic extraction, macro F1 1.000) · 016 (exact rule heads deployed; TSK off-deployment — **promotion permanently denied**) · 017 (recommendation acceptance events — **loop closed end-to-end**)

## 2. Datasets

| Dataset | Shape | Source of truth |
|---|---|---|
| corpus-v1 | 2,226 records / 197 families · splits 1,537/434/255 | `data/manifest.json` (sha256, EOL-deterministic) |
| anfis-v3 | 21,964 scenarios · **377,753 opportunity rows · 51,873 positives (13.73%)** · schema `anfis-feature-schema/3` (f9/f11/f21/f22) | `data/anfis_v3/` (local-only, >100MB; regenerable via sampler v3, seed 472) — **BENCHMARK/EVAL asset; row-scaling STOPPED** (sampler worked; its TSK consumer is cancelled) |
| acceptance events | live ADR-017 store (young: single digits) | `recommendation_events` table |
| organic capture | opt-in `TAX_CORPUS_CAPTURE` | `data/corpus/` |

## 3. Models & intelligence surfaces

| Surface | Status | Anchor |
|---|---|---|
| composite efficiency | served, exact (MAE 0.136) | `tax_intelligence.py::composite_efficiency` |
| rule-heads-v5 | **production path** (opportunity/savings/confidence; P/R 1.0, savings MAE 0.00) | `rule_*` + `recommend()` |
| TSK learned heads | **experiments only — promotion denied at 3 scales** | `tools/train_anfis_v5.py` |
| confidence | constant 0.85/0.30 anchor; **G7: no learned confidence until ECE ≤ 0.05 on ≥ 30 resolved events** | `calibration.py` |
| research models | TF-IDF intent (96.41%) · BiLSTM NER (0.143) · BERT/GPT-2/T5 studies | `nlp_research/` |

## 4. Feedback loop (new in v0.6)

shown → accepted/rejected/ignored/viewed/dismissed → per-session funnel
(`GET /sessions/{sid}/recommendations/analytics`). Live-verified: 3 shown /
1 accepted / rate 0.333 in the release E2E. Sparse by design — the
instruments are the deliverable, volume accumulates from real usage.

## 5. Metrics baseline (Sprint 7 must not regress)

| Metric | v0.6 value |
|---|---|
| pytest | **1,166** passed / 0 failed / 1 deselected (re-certified on merged main) |
| Vitest | **31**/31 · tsc clean |
| Extraction | macro F1 1.000 · gate PASS · abstention 17/17 |
| Intelligence | composite MAE 0.136 · rule heads exact · ranking 95.72% |
| Calibration | canary ECE 0.0 (framework proven); live N below measurement threshold |
| Security | APPROVE posture maintained; ownership double-checks on all new endpoints |

## 6. Carried items (Sprint 7 candidates — see SPRINT7_PRIORITY_MATRIX.md)

1. Effectiveness Dashboard (cross-session/per-user funnel view).
2. Auto-fire `viewed` events from the card renderer.
3. NER expansion (P4, research track, unchanged since Sprint 5).
4. Personalization — **gated** on ~50 resolved acceptance events.
5. 24(b) impact-table reason string distinguishing self-occupied vs let-out (cosmetic).

## 7. Environment

- Docker Compose: backend :8000 (healthy) · frontend :3000 · loopback-only
- **App URL: `http://127.0.0.1:3000`** (NOT `localhost` — `.env` pins `CORS_ORIGINS`/`NEXT_PUBLIC_API_URL` to 127.0.0.1)
- Demo login: `demo@student.local` / `DemoPass@123`
- Releases: `v0.5-sprint4` (PR #4) → `v0.6-sprint6` (PR #5); CHANGELOG promoted both times
- Tools: `tools/run_eval.py` · `tools/generate_anfis_dataset.py` (continuous sampler v3) · `tools/train_anfis_v5.py` · `tools/forensics/`

# PROJECT_BASELINE_V0_5.md — Sprint 5 Starting Baseline
**Frozen:** 2026-11-04 at the v0.5-sprint4 release · **Purpose:** the authoritative starting state for Sprint 5 — every number here was measured, not transcribed

---

## 1. Architecture

```
Frontend  Next.js 16.4.3 / React 19.2.4 / TypeScript — 3-pane responsive shell
   │      chat UI · Applied-vs-Ignored transparency panel · regime comparison
   ▼      REST + HttpOnly cookie sessions (apiFetch, 401 → /login)
Backend   FastAPI 0.162.0 / Pydantic 2.14.2 / uvicorn 0.54 — 14 REST endpoints
   │      auth (scrypt + HttpOnly) · server-side sessions (ADR-013)
   │      rate limits · fail-closed CORS (ADR-014) · append-only audit (ADR-009)
   ├──    NLP Engine (nlp_engine.py): prepass guards → UniversalParser →
   │      SemanticAttention → waterfall → Response Composer (P2) →
   │      Tax Intelligence (tax_intelligence.py: composite efficiency,
   │      exact rule heads, CA advisor, explainability)  [ADR-016]
   ├──    TaxEngine (tax_engine.py:217) + tax_rules/{fy_2024_25,fy_2025_26}
   │      — the ONLY tax calculator  [ADR-001]
   └──    SQLite (WAL) · tax_rules registry  [ADR-008]
Data      SQLite (users, app_sessions) · JSONL audit · data/anfis_v1 (regenerable)
          · data/{training,validation,test} corpus (2,226 records, manifest-pinned)
CI        GitHub Actions, 3 jobs (green on every sprint-4 push)
```

**Invariants:** ADR-001 (TaxEngine sole calculator) · ADR-003 (offline/deterministic) · ADR-012/013/014 (auth/sessions/edge) · ADR-015 (deterministic extraction) · ADR-016 (exact rule heads deployed; TSK off-deployment) · one-way dependency (backend never imports nlp_research).

## 2. Datasets (Sprint 5 starting point)

| Dataset | Shape | Source of truth |
|---|---|---|
| corpus-v1 | 2,226 records / 2,255 spans / 197 families · splits 1,537/434/255 | `data/manifest.json` (sha256-pinned) + `data/{training,validation,test}/` |
| anfis-v1 (v2.1+f21) | 5,964 scenarios · 76,960 opportunity rows · **1,623 positives (2.11%)** · features 20-dim · savings 23-dim | `data/anfis_v1/*.npz|jsonl` + `tools/generate_anfis_dataset.py` (grid SATURATED — Sprint 5 P0 sampler required for growth) |
| ner-templates-v1 | 51 samples | `nlp_research/phase_d_ner.py` |
| organic capture | empty (opt-in `TAX_CORPUS_CAPTURE`) | `data/corpus/` |

## 3. Models

| Model | Status | Location |
|---|---|---|
| anfis-v4 (TSK 20×64) | production efficiency scorer (pre-v5 ground truth) | `ai_models.py::ANFIS` + `anfis_weights.json` (byte-unchanged) |
| composite efficiency | **served** (exact, MAE 0.136) | `tax_intelligence.py::composite_efficiency` |
| rule-heads-v5 | **deployed** intelligence (opportunity/savings/confidence — engine-priced) | `tax_intelligence.py::rule_*` + `recommend()` |
| TSK savings/opp heads | experiments, off-deployment (G4 795% · G5 P0/R0) | `tax_intelligence.py` + `tools/train_anfis_v5.py` |
| research models | TF-IDF intent (96.41%) · BiLSTM NER (0.143) · seq2seq · BERT/GPT-2/T5 studies | `nlp_research/phase_*` |

## 4. Registries (living, current)

`DATASET_REGISTRY.md` · `MODEL_REGISTRY.md` · `TRAINING_REGISTRY.md` · `EXPERIMENT_REGISTRY.md` — Sprint 5 must append (never rewrite history): every new run gets a RUN-*, every dataset a row, every experiment an EXP-*.

## 5. Metrics baseline (Sprint 5 must not regress)

| Metric | v0.5 value |
|---|---|
| pytest | 1,146 passed / 0 failed / 1 deselected |
| Vitest | 25/25 |
| Playwright | 7 specs green |
| Legacy | 97 green |
| Extraction | macro F1 1.000 · gate PASS · abstention 17/17 |
| Intelligence | composite MAE 0.136 · rule heads exact · ranking 95.72% (engine-ordered) |
| Security | APPROVE (all findings closed; amplification probes ≤587B) |
| Scorecard | 89/100 (Arch 88 · Sec 90 · Test 92 · Compl 88 · Prod 89 · NLP 91 · Intel 87) |

## 6. Known carried items (Sprint 5 backlog)

1. Continuous-value sampler (P0) — the only path to TSK promotion.
2. Regime-gate the legacy NPS tip (P3).
3. NER expansion (P4).
4. Recommendation acceptance tracking (P2) + frontend intelligence cards (P6).
5. Feature-normalization micro-fixes (P0.1).
6. Composite-score wiring to the results tile (v4 tile still displayed).

## 7. Environment

- Docker Compose: backend :8000 (healthy) · frontend :3000 · loopback-only
- Demo login: `demo@student.local` / `DemoPass@123` (12-char min rule)
- `.env`: APP_ENV=prod · CORS_ORIGINS=http://127.0.0.1:3000 · NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 (frontend rebuild required on change)
- Tools: `tools/run_eval.py` · `tools/generate_anfis_dataset.py` · `tools/train_anfis_v5.py` · `tools/retrain_anfis.py` · `tools/forensics/`

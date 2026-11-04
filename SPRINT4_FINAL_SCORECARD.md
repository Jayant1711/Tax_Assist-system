# SPRINT4_FINAL_SCORECARD.md
**Generated:** 2026-11-04 · **Scope:** Sprint 4 end-to-end (P0 → v0.5-sprint4 RC) · **Basis:** independent re-verification (`FINAL_TECHNICAL_AUDIT.md`, `FINAL_VALIDATION_REPORT.md`) — not report citations

---

## Dimension scores (0-100)

| Dimension | Score | Basis |
|---|---|---|
| **Architecture** | **88** | v5 intelligence layer cleanly separated (two-pass ADR-001 boundary verified by audit + 15/15 recomputation test); registries complete; deviation documentation honest (additive/48/v2.1). Deduction: legacy v4 scorer still served on the results tile pending v5 wiring (disclosed); ADR-016 recorded late |
| **Security** | **90** | Two APPROVE-WITH-NITS reviews; all 10 findings closed with re-run probes (5 amplification vectors bounded ≤587B); no XSS/ReDoS/injection/PII paths in the new surface; gitignore hardening. Deduction: the 3 sibling amplification vectors were pre-existing and caught only in the second pass |
| **Testing** | **92** | 1,146 pytest / 0 failed (independently re-run twice on two commits) · 22 Vitest · 7 Playwright · 97 legacy · ADR-001 recomputation 15/15 · determinism sha256-identical across dev and prod containers. Deduction: eval-gate CLI display bug found late (fixed); deselected advisory test run explicitly and passed |
| **Compliance (CSE472 + statutory)** | **88** | Extraction gate PASS (macro F1 1.000); FY 2025-26 constants verified (docs/tax-verification.md); honest-findings culture (NER 0.143, TSK failures) documented; ADR-015/016 recorded. Deduction: 80CCD(1B) new-regime treatment surfaced a legacy tip inaccuracy (filed, unfixed) |
| **Production readiness** | **89** | Docker build + live E2E both branches (block present/absent correctly); health/checks green; amplification probes bounded; rollback ladder intact (v4 untouched, no candidate weights). Deduction: rate-limiter pacing note for E2E; continuous-value sampler still pending |
| **NLP** | **91** | Extraction macro F1 1.000 (gate PASS); abstention 17/17; composer contract 23 tests + determinism; forensics-corrected label provenance. Deduction: NER 0.143 (accepted debt, roadmap P4); grid saturation limits scale |
| **Tax Intelligence** | **87** | Exact rule heads P/R 1.0/1.0, MAE 0.00 (engine-priced by construction); ranking 95.72% (engine-ordered protocol); CA-advisor honesty (zero-benefit → ₹0, NO BENEFIT) verified both directions. Deduction: TSK learned heads below deployment bar (data-limited, off-deployment); intelligence block rare for new-regime users (by design) |

**Overall Sprint 4: 89 / 100** (weighted mean; floor of no dimension < 87)

## Score movement across Sprint 4

| Dimension | Sprint-3 baseline | Post-P0/P1 | **Final (v0.5-rc)** |
|---|---|---|---|
| Architecture | 86 | 86 | **88** |
| Security | 88 | 88 | **90** |
| Testing | 91 | 91 | **92** |
| Compliance | 85 | 85 | **88** |
| Production | 90 | 90 | **89*** |
| NLP | — | ~80 (unmeasured) | **91** |
| Tax Intelligence | — | ~55 (ADR-004 open) | **87** |

*Production -1: the intelligence surface adds one more moving part (advisor block) whose live behavior, while correct, narrows the reply-shape guarantees; offset by the validation depth.

## What would raise each dimension next sprint

Architecture 88→92: wire the composite score to the results tile (replacing the v4 tile), record remaining ADRs. Security 90→94: proactive per-message caps on ALL note classes (the 3 siblings were found late). Testing 92→95: Playwright in CI on the live stack. Compliance 88→92: regime-gate the legacy NPS tip. Production 89→93: continuous-value sampler + deployed TSK heads on gates. NLP 91→94: NER corpus expansion. Intelligence 87→92: acceptance feedback loop + positive-rich strata at plan scale.

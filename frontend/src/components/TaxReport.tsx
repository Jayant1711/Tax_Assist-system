'use client';

import React, { useState, useEffect, useRef } from 'react';
import SavingsGraph from './SavingsGraph';
import { apiFetch } from '../lib/api';

/**
 * Wave D contract (ADR-013): the report computes from the owned
 * server-side state — the wire carries {session_id} only. The projection
 * prop rides along for identity fallbacks; the numbers never come from
 * the client anymore.
 */
interface Props {
  sessionId: string | null;
  projection?: Record<string, any> | null;
  activeView?: string;
}

export default function TaxReport({ sessionId, projection }: Props) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'computation' | 'slabs' | 'advice'>('computation');
  // Sprint 7 S7.2: the user's recorded decision per card (rec_id), and
  // S7.3: a reload tick so one-click Apply re-runs the whole report.
  const [acted, setActed] = useState<Record<string, string>>({});
  const [reloadTick, setReloadTick] = useState(0);
  const viewedFired = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!sessionId) return;

    let isMounted = true;
    setLoading(true);

    apiFetch('/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Backend calculation error: ${res.status}`);
        return res.json();
      })
      .then((resData) => {
        if (isMounted) {
          setData(resData);
          setError(null);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error('Calculation fetch error:', err);
          setError(err.message);
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [sessionId, projection, reloadTick]);

  // Sprint 7 S7.2: auto-fire the `viewed` action once per card when the
  // FINAL report renders (ADR-017). The backend treats viewed as a
  // passive action that never overwrites accepted/rejected, so re-fires
  // are harmless no-ops on the store.
  const recIds: string[] = (data?.recommendations ?? [])
    .map((r: any) => r.rec_id)
    .filter(Boolean);
  useEffect(() => {
    if (!sessionId || recIds.length === 0) return;
    const fresh = recIds.filter((id) => !viewedFired.current.has(id));
    if (fresh.length === 0) return;
    fresh.forEach((id) => viewedFired.current.add(id));
    fresh.forEach((id) => {
      apiFetch(
        `/sessions/${sessionId}/recommendations/${id}/action`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'viewed' }) },
      ).catch(() => {/* best-effort capture */});
    });
  }, [sessionId, recIds.join('|')]);

  const applyRecommendation = async (recId: string) => {
    setActed((prev) => ({ ...prev, [recId]: 'applied' }));
    try {
      const res = await apiFetch(
        `/sessions/${sessionId}/recommendations/${recId}/apply`,
        { method: 'POST' },
      );
      if (res.ok) {
        setReloadTick((t) => t + 1); // re-runs the whole priced report
      }
    } catch {
      // surfaced on the next manual recalculation; never fatal
    }
  };

  const decideRecommendation = (recId: string, action: string) => {
    setActed((prev) => ({ ...prev, [recId]: action }));
    apiFetch(
      `/sessions/${sessionId}/recommendations/${recId}/action`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }) },
    ).catch(() => {/* best-effort capture */});
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '350px', gap: '1.25rem' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="typing-dot"
              style={{ width: '12px', height: '12px', background: 'var(--primary)', animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.95rem' }}>Computing Dual-Regime Audit</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Evaluating Sec 80C/80D caps & ANFIS efficiency scoring...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" style={{ padding: '1.5rem', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-red)', fontWeight: 700, marginBottom: '0.5rem' }}>
          <span>⚠️</span> Calculation Service Offline
        </div>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-sub)' }}>
          Unable to reach the calculation service — please try again in a moment.
        </p>
      </div>
    );
  }

  if (!data) return null;

  const rec = data.recommendation || 'New Regime';
  const best = rec === 'New Regime' ? data.new_regime : data.old_regime;
  const other = rec === 'New Regime' ? data.old_regime : data.new_regime;

  const effScore = data.efficiency_score ?? best?.efficiency_score ?? 85.0;
  const effColor = effScore >= 75 ? 'var(--accent-green)' : effScore >= 50 ? 'var(--accent-amber)' : 'var(--accent-red)';
  const fmt = (n: number) => '₹' + Math.round(n || 0).toLocaleString('en-IN');

  // ── Sprint 4 Phase 4A: deductions — applied vs ignored transparency ──
  // The New Regime (Sec 115BAC) allows only the standard deduction: every
  // booked Chapter VI-A head is ignored there. The engine prices each
  // booked head in the Old Regime (with statutory caps applied upstream).
  const BOOKED_LABELS: Record<string, string> = {
    '80c': 'Section 80C investments', '80d': 'Section 80D health premium',
    '80d_parents': 'Section 80D (parents)', nps: 'NPS 80CCD(1B)',
    hra_received: 'HRA', '24b': 'Home-loan interest 24(b)',
    '80g': 'Section 80G donations', '80e': 'Section 80E interest',
    '80tta': 'Section 80TTA', '80ttb': 'Section 80TTB',
    '80u_80dd': 'Section 80U/80DD', '80ddb': 'Section 80DDB',
    '80eea': 'Section 80EEA',
  };
  const bookedDeductions = Object.entries(BOOKED_LABELS)
    .map(([key, label]) => ({ key, label, amount: Number((projection || {})?.[key] || 0) }))
    .filter((d) => d.amount > 0);
  const newAppliedRows = (data?.new_regime?.explanations || []).filter(
    (e: any) => Number(e.amount) > 0);
  const oldAppliedRows = (data?.old_regime?.explanations || []).filter(
    (e: any) => Number(e.amount) > 0);
  // top old-regime slab rate (for the per-deduction saving estimate)
  const marginalRate = (() => {
    let rate = 0;
    for (const s of data?.old_regime?.slabs_breakdown || []) {
      if (Number(s.tax) > 0) {
        const r = parseInt(String(s.rate).replace('%', ''), 10);
        if (!isNaN(r)) rate = Math.max(rate, r);
      }
    }
    return rate;
  })();


  const handlePrint = () => {
    window.print();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', animation: 'fadeSlideUp 0.4s ease-out' }}>
      {/* ── Print-Only Header (Form ITR Computational Statement) ── */}
      <div className="print-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              TaxAssist AI · Computational Statement of Income
            </h1>
            <div style={{ fontSize: '0.82rem', color: '#475569', marginTop: '2px' }}>
              {data?.fy_label ?? 'FY 2025-26 (AY 2026-27)'} | Direct Tax Advisory
            </div>
          </div>
          <div style={{ textAlign: 'right', fontSize: '0.75rem', color: '#64748b' }}>
            <div>Session ID: {sessionId ?? projection?.id ?? 'DEMO-AUDIT'}</div>
            <div>Generated: {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</div>
          </div>
        </div>
      </div>

      {/* ── Top Bar with Actions ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', fontWeight: 700 }}>
            Audit Output · {data?.fy_label ?? 'FY 2025-26 (AY 2026-27)'}
          </span>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '2px' }}>
            Tax Assessment & Optimization Report
          </h2>
        </div>
        <button
          onClick={handlePrint}
          className="btn btn-ghost btn-sm"
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <span>🖨️</span> Print / Save PDF
        </button>
      </div>

      {/* ── Interactive Regime Graph ── */}
      <SavingsGraph data={data} />

      {/* ── Core Executive KPIs ── */}
      <div className="metric-grid">
        <div className="metric-tile green">
          <div className="metric-label">Recommended Strategy</div>
          <div className="metric-value" style={{ color: 'var(--accent-green)', fontSize: '1.25rem' }}>
            {rec}
          </div>
          <div className="metric-sub">
            Saves you <strong style={{ color: 'var(--accent-green)' }}>{fmt(data.savings)}</strong> annually
          </div>
        </div>

        <div className="metric-tile amber">
          <div className="metric-label">Net Tax Payable ({rec})</div>
          <div className="metric-value" style={{ color: 'var(--accent-amber)' }}>
            {fmt(best?.total_tax)}
          </div>
          <div className="metric-sub">
            Effective Tax Rate: {((best?.total_tax / (best?.gross_total_income || 1)) * 100).toFixed(1)}%
          </div>
        </div>

        <div className="metric-tile blue">
          <div className="metric-label">Gross Total Income</div>
          <div className="metric-value">
            {fmt(best?.gross_total_income)}
          </div>
          <div className="metric-sub">
            Total deductions: {fmt(best?.total_deductions)}
          </div>
        </div>

        <div className="metric-tile" style={{ borderLeft: `3px solid ${effColor}` }}>
          <div className="metric-label">ANFIS Efficiency Score</div>
          <div className="metric-value" style={{ color: effColor }}>
            {effScore.toFixed(1)}<span style={{ fontSize: '0.8rem', fontWeight: 500 }}>/100</span>
          </div>
          <div className="metric-sub">
            {effScore >= 80 ? 'Highly optimized profile' : 'Unclaimed deduction potential detected'}
          </div>
        </div>
      </div>

      {/* ── Sprint 4 Phase 4A: Deductions — Applied vs Ignored ── */}
      {bookedDeductions.length > 0 && (
        <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
          <div className="card-header" style={{ padding: 0, borderBottom: '1px solid var(--border)', marginBottom: '1rem' }}>
            <div>
              <div className="card-title">Your Deductions — Applied vs Ignored</div>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Why your tax moved the way it did: the <strong>{rec}</strong> is cheaper by{' '}
                <strong style={{ color: 'var(--accent-green)' }}>{fmt(data.savings)}</strong> — your booked
                deductions apply in the <strong>{rec === 'New Regime' ? 'Old' : 'New'}</strong> regime.
              </p>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {/* Old Regime column */}
            <div>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--primary-light)', marginBottom: '0.5rem' }}>
                Old Regime — deductions apply
              </div>
              {oldAppliedRows.map((ex: any, i: number) => (
                <div key={`oa_${i}`} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', padding: '0.3rem 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ color: 'var(--text-sub)' }}>
                    ✓ {ex.particular} <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>Sec {ex.section}</span>
                    {marginalRate > 0 && (
                      <span style={{ color: 'var(--accent-green)', fontSize: '0.68rem' }}>
                        {' '}· est. saves {fmt((Number(ex.amount) * marginalRate) / 100)}
                      </span>
                    )}
                  </span>
                  <span style={{ color: 'var(--text-main)' }}>{fmt(ex.amount)}</span>
                </div>
              ))}
              {oldAppliedRows.length === 0 && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No deductions applied.</div>
              )}
            </div>
            {/* New Regime column */}
            <div>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--primary-light)', marginBottom: '0.5rem' }}>
                New Regime — Sec 115BAC applies
              </div>
              {newAppliedRows.map((ex: any, i: number) => (
                <div key={`na_${i}`} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', padding: '0.3rem 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ color: 'var(--text-sub)' }}>✓ {ex.particular} <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>Sec {ex.section}</span></span>
                  <span style={{ color: 'var(--text-main)' }}>{fmt(ex.amount)}</span>
                </div>
              ))}
              {bookedDeductions.map((d) => (
                <div key={`ni_${d.key}`} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', padding: '0.3rem 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ color: 'var(--accent-red)' }}>
                    ✗ {d.label}
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}> — not allowed under Sec 115BAC</span>
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>{fmt(d.amount)}</span>
                </div>
              ))}
            </div>
          </div>
          {marginalRate > 0 && (
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.6rem' }}>
              Savings estimates use your top Old-Regime slab rate ({marginalRate}%); the report prices every figure exactly.
            </div>
          )}
        </div>
      )}

      {/* ── Sprint 6 Phase 3: Intelligence Cards (ranked CA recommendations) ── */}
      {(() => {
        const review = (data as any)?.recommendations as
          | Array<{ rec_id: string; head: string; delta: number;
                    estimated_savings: number; confidence: number;
                    reason: string; verdict: string;
                    evidence?: string[] }> | undefined;
        if (!review?.length) return null;
        // ADR-017: acceptance actions resolve persisted shown events —
        // they exist only once the closing turn ran, i.e. the FINAL phase.
        const finalPhase = (projection?.phase || '') === 'FINAL';
        return (
          <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
            <div className="card-header" style={{ padding: 0, borderBottom: '1px solid var(--border)', marginBottom: '1rem' }}>
              <div className="card-title">CA Recommendations — Ranked Opportunities</div>
            </div>
            {review.map((card: any, i: number) => {
              const recommend = card.verdict === 'RECOMMEND';
              return (
                <div key={card.rec_id} style={{ padding: '0.75rem 0', borderBottom: i < review.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.85rem', color: recommend ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                      {i + 1}. Section {card.head.replace(/_/g, ' ').toUpperCase()}
                      {recommend ? '' : ' — no benefit'}
                    </span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      confidence {Math.round(card.confidence * 100)}%
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.3rem' }}>
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-sub)' }}>{card.reason}</span>
                    <span style={{ fontSize: '0.76rem', fontWeight: 600, color: recommend ? 'var(--accent-green)' : 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {recommend ? `est. saves ${fmt(card.estimated_savings)}` : '₹0'}
                    </span>
                  </div>
                  {card.evidence && card.evidence.length > 0 && (
                    <ul style={{ margin: '0.35rem 0 0 1rem', padding: 0, fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                      {card.evidence.map((e: string, j: number) => (
                        <li key={j}>{e}</li>
                      ))}
                    </ul>
                  )}
                  {recommend && finalPhase && acted[card.rec_id] === 'applied' && (
                    <div style={{ marginTop: '0.45rem', fontSize: '0.72rem', color: 'var(--accent-green)', fontWeight: 600 }}>
                      ✓ Applied — headroom booked, report re-priced below.
                    </div>
                  )}
                  {recommend && finalPhase && acted[card.rec_id] === 'accepted' && (
                    <div style={{ marginTop: '0.45rem', fontSize: '0.72rem', color: 'var(--accent-green)', fontWeight: 600 }}>
                      ✓ Accepted — recorded in your adoption history.
                    </div>
                  )}
                  {recommend && finalPhase && acted[card.rec_id] === 'rejected' && (
                    <div style={{ marginTop: '0.45rem', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      ✕ Rejected — recorded in your adoption history.
                    </div>
                  )}
                  {recommend && finalPhase && !acted[card.rec_id] && (
                    <div style={{ marginTop: '0.45rem', display: 'flex', gap: '0.5rem' }}>
                      <button className="btn btn-primary btn-sm" onClick={() => applyRecommendation(card.rec_id)}>
                        ✓ Apply this
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => decideRecommendation(card.rec_id, 'accepted')}>
                        👍 Keep as accepted
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => decideRecommendation(card.rec_id, 'rejected')}>
                        ✕ Not for me
                      </button>
                    </div>
                  )}
                  {recommend && !finalPhase && (
                    <div style={{ marginTop: '0.45rem', fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                      Acceptance unlocks in the final report.
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })()}

      {/* ── Sprint 6 Phase 5: exact per-deduction impact (leave-one-out) ── */}
      {(() => {
        const impacts = (data as any)?.deduction_impact as
          | Array<{ head: string; entered: number; applied_in_regime: boolean;
                    tax_reduction: number; tax_reduction_other_regime: number;
                    reason: string }> | undefined;
        if (!impacts?.length) return null;
        return (
          <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
            <div className="card-header" style={{ padding: 0, borderBottom: '1px solid var(--border)', marginBottom: '1rem' }}>
              <div>
                <div className="card-title">Per-Deduction Impact — Exact (Engine-Priced)</div>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Leave-one-out recomputation by the TaxEngine (ADR-001): the tax each booked
                  item actually removed in the recommended regime. Exact arithmetic — no estimates.
                </p>
              </div>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Deduction</th>
                  <th style={{ textAlign: 'right' }}>Entered (₹)</th>
                  <th style={{ textAlign: 'right' }}>Applied</th>
                  <th style={{ textAlign: 'right' }}>Tax Reduced (₹)</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {impacts.map((imp) => (
                  <tr key={imp.head}>
                    <td style={{ fontWeight: 600 }}>{imp.head.replace(/_/g, ' ').toUpperCase()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(imp.entered)}</td>
                    <td style={{ textAlign: 'right', color: imp.applied_in_regime ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                      {imp.applied_in_regime ? '✓' : '✗ 115BAC'}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: imp.tax_reduction > 0 ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                      {fmt(imp.tax_reduction)}
                    </td>
                    <td style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{imp.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}

      {/* ── Sprint 7 X3: CA-style savings plans (explainable layer +
          engine-priced) ── */}
      {(() => {
        const plans = (data as any)?.ca_plans as
          | Array<{ name: string; levers: string[]; savings_engine: number;
                    steps: Array<{ head: string; delta: number;
                                  sentence: string }> }> | undefined;
        if (!plans?.length) return null;
        return (
          <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
            <div className="card-header" style={{ padding: 0, borderBottom: '1px solid var(--border)', marginBottom: '1rem' }}>
              <div>
                <div className="card-title">CA-Style Savings Plans</div>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Readable rule-based suggestions, priced line by line by the tax engine. Every rupee is a recomputation.
                </p>
              </div>
            </div>
            {plans.map((plan, i) => (
              <div key={plan.name} style={{ padding: '0.85rem 0', borderBottom: i < plans.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--primary-light)' }}>
                    {plan.name}
                  </span>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-green)' }}>
                    est. saves {fmt(plan.savings_engine)}
                  </span>
                </div>
                <ul style={{ margin: '0.4rem 0 0 1.1rem', padding: 0 }}>
                  {plan.steps.map((st, j) => (
                    <li key={j} style={{ fontSize: '0.74rem', color: 'var(--text-sub)', marginBottom: '0.25rem' }}>
                      {st.sentence}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        );
      })()}

      {/* ── Tabs for Deeper Analysis ── */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
        <button
          onClick={() => setActiveTab('computation')}
          className={`btn btn-sm ${activeTab === 'computation' ? 'btn-primary' : 'btn-ghost'}`}
        >
          📄 Computational Statement
        </button>
        <button
          onClick={() => setActiveTab('slabs')}
          className={`btn btn-sm ${activeTab === 'slabs' ? 'btn-primary' : 'btn-ghost'}`}
        >
          📊 Slab Breakdown
        </button>
        <button
          onClick={() => setActiveTab('advice')}
          className={`btn btn-sm ${activeTab === 'advice' ? 'btn-primary' : 'btn-ghost'}`}
        >
          💡 CA Advice & Risks ({best?.savings_tips?.length || 0})
        </button>
      </div>

      {/* ── TAB 1: Computational Statement (CA Format) ── */}
      {activeTab === 'computation' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="card-header" style={{ padding: '1rem 1.5rem', marginBottom: 0 }}>
            <div>
              <div className="card-title">Statement of Total Income (Form ITR Format)</div>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Legal itemization compliant with Indian Income Tax Act 1961
              </p>
            </div>
            <span className="badge-luxe" style={{ fontSize: '0.7rem' }}>
              {rec} Basis
            </span>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Particulars</th>
                <th>Section</th>
                <th style={{ textAlign: 'right' }}>Amount (₹)</th>
              </tr>
            </thead>
            <tbody>
              {/* Income Sources */}
              {best?.income_details?.map((inc: any, i: number) => (
                <tr key={`inc_${i}`}>
                  <td>{inc.source}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>Sec {inc.section}</td>
                  <td>{fmt(inc.amount)}</td>
                </tr>
              ))}

              <tr className="total-row">
                <td>Gross Total Income (Head A to E)</td>
                <td style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>Sec 14</td>
                <td>{fmt(best?.gross_total_income)}</td>
              </tr>

              {/* Deductions (from the engine's per-regime Explanation list —
                  includes the standard deduction; no client-side rows) */}
              {best?.explanations?.map((ex: any, i: number) => (
                <tr key={`ded_${i}`} className="deduction-row">
                  <td>Less: {ex.particular} ({ex.reason})</td>
                  <td style={{ fontSize: '0.72rem' }}>Sec {ex.section}</td>
                  <td>(−) {fmt(ex.amount)}</td>
                </tr>
              ))}

              <tr className="final-row">
                <td colSpan={2}>Net Taxable Income</td>
                <td>{fmt(best?.taxable_income)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* ── TAB 2: Slab Breakdown & Cess ── */}
      {activeTab === 'slabs' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="card-header" style={{ padding: '1rem 1.5rem', marginBottom: 0 }}>
            <div>
              <div className="card-title">Tax Slab Step-by-Step Calculation</div>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Progression across brackets + 4% Health & Education Cess
              </p>
            </div>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Tax Bracket</th>
                <th>Rate</th>
                <th>Taxable in Slab</th>
                <th style={{ textAlign: 'right' }}>Tax Computed</th>
              </tr>
            </thead>
            <tbody>
              {best?.slabs_breakdown?.map((slab: any, idx: number) => (
                <tr key={idx}>
                  <td>{slab.range}</td>
                  <td><span className="slab-badge">{slab.rate}</span></td>
                  <td>{fmt(slab.income)}</td>
                  <td>{fmt(slab.tax)}</td>
                </tr>
              ))}

              <tr className="total-row">
                <td colSpan={3} style={{ textAlign: 'right', paddingRight: '1rem' }}>
                  Base Tax (Before Surcharge & Cess)
                </td>
                <td>{fmt(best?.total_tax / 1.04)}</td>
              </tr>

              <tr>
                <td colSpan={3} style={{ textAlign: 'right', paddingRight: '1rem', color: 'var(--text-muted)' }}>
                  Health & Education Cess (4%)
                </td>
                <td style={{ color: 'var(--text-muted)' }}>
                  {fmt(best?.total_tax - (best?.total_tax / 1.04))}
                </td>
              </tr>

              <tr className="final-row">
                <td colSpan={3} style={{ textAlign: 'right', paddingRight: '1rem' }}>
                  Total Tax Liability
                </td>
                <td style={{ color: 'var(--accent-amber)' }}>{fmt(best?.total_tax)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* ── TAB 3: CA Advice, Risk Alerts, and Optimization ── */}
      {activeTab === 'advice' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Risk Alerts */}
          {best?.audit_observations && best.audit_observations.length > 0 && (
            <div className={`risk-banner ${best.risk_level?.toLowerCase() || 'medium'}`}>
              <div style={{ fontSize: '1.4rem' }}>⚠️</div>
              <div>
                <div style={{ fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.25rem' }}>
                  Compliance Observations ({best.risk_level || 'Notice'} Risk)
                </div>
                <ul>
                  {best.audit_observations.map((obs: string, i: number) => (
                    <li key={i}>{obs}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Savings Tips */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">💡 CA Strategic Optimization Tips</div>
              <span className="badge-luxe" style={{ fontSize: '0.7rem' }}>
                AI Recommendations
              </span>
            </div>

            <div className="tips-grid">
              {best?.savings_tips?.length ? (
                best.savings_tips.map((tip: string, idx: number) => {
                  const parts = tip.split(':');
                  const title = parts[0];
                  const body = parts.slice(1).join(':').trim();
                  return (
                    <div key={idx} className="tip-card">
                      <span className="tip-icon">
                        {idx === 0 ? '🎯' : idx === 1 ? '🏥' : idx === 2 ? '🛡️' : '📈'}
                      </span>
                      <div className="tip-text">
                        <strong>{title}</strong>
                        {body || title}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '1rem' }}>
                  No extra deductions needed — your current profile is already utilizing optimal deductions.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

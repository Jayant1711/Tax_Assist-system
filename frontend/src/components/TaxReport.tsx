'use client';

import React, { useState, useEffect } from 'react';
import SavingsGraph from './SavingsGraph';

interface Props {
  session: any;
  activeView?: string;
  onUpdateSession?: (session: any) => void;
}

export default function TaxReport({ session, activeView }: Props) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'computation' | 'slabs' | 'advice'>('computation');

  useEffect(() => {
    if (!session || Object.keys(session).length === 0) return;

    let isMounted = true;
    setLoading(true);

    fetch('http://localhost:8000/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(session),
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
  }, [session]);

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
      <div style={{ padding: '1.5rem', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-red)', fontWeight: 700, marginBottom: '0.5rem' }}>
          <span>⚠️</span> Calculation Service Offline
        </div>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-sub)' }}>
          Could not communicate with the Python backend (`http://localhost:8000/calculate`). Ensure `main.py` is running.
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
              Assessment Year: <strong>2025-26</strong> | Financial Year: <strong>2024-25</strong> | Direct Tax Advisory
            </div>
          </div>
          <div style={{ textAlign: 'right', fontSize: '0.75rem', color: '#64748b' }}>
            <div>Session ID: {session?.id || 'DEMO-AUDIT'}</div>
            <div>Generated: {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</div>
          </div>
        </div>
      </div>

      {/* ── Top Bar with Actions ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', fontWeight: 700 }}>
            Audit Output · AY 2025-26
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

              {/* Deductions */}
              {best?.explanations?.map((ex: any, i: number) => (
                <tr key={`ded_${i}`} className="deduction-row">
                  <td>Less: {ex.particular} ({ex.reason})</td>
                  <td style={{ fontSize: '0.72rem' }}>Sec {ex.section}</td>
                  <td>(−) {fmt(ex.amount)}</td>
                </tr>
              ))}

              {rec === 'New Regime' && (
                <tr className="deduction-row">
                  <td>Less: Standard Deduction for Salaried Employees</td>
                  <td style={{ fontSize: '0.72rem' }}>Sec 16(ia)</td>
                  <td>(−) {fmt(75000)}</td>
                </tr>
              )}

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

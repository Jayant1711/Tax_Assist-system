'use client';

import React, { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';

/**
 * Sprint 7 S7.1 — the Recommendation Effectiveness Dashboard: the
 * cross-session adoption funnel over the user's own events, the
 * Accepted-Rupee metric, and the calibration gate's progress toward
 * its 30-resolved-event threshold. Read-only over the ADR-017 store.
 */
interface Overview {
  total_shown: number;
  total_accepted: number;
  acceptance_rate: number;
  accepted_rupees: number;
  resolved_events: number;
  calibration_gate: { target: number; met: boolean };
  per_head: Array<{ head: string; shown: number; accepted: number;
                    rejected: number; ignored: number; viewed: number;
                    dismissed: number; savings_engine: number;
                    accepted_savings: number }>;
}

export default function AdoptionDashboard() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    apiFetch('/analytics/overview')
      .then((res) => {
        if (!res.ok) throw new Error(`Overview error: ${res.status}`);
        return res.json();
      })
      .then((d) => {
        if (isMounted) {
          setData(d);
          setError(null);
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  if (error) {
    return (
      <div className="card" style={{ padding: '1.25rem 1.5rem' }} role="alert">
        Adoption service error: {error}
      </div>
    );
  }
  if (!data) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
        <div className="typing-dot" style={{ width: '12px', height: '12px', background: 'var(--primary)' }} />
      </div>
    );
  }

  const fmt = (n: number) =>
    new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0,
                                     style: 'currency', currency: 'INR' })
      .format(n);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
        <div className="card-header" style={{ padding: 0, borderBottom: '1px solid var(--border)', marginBottom: '1rem' }}>
          <div>
            <div className="card-title">Adoption Dashboard</div>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              What the system recommended, and what you actually did about it — across every session.
            </p>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
          <div className="metric-tile">
            <div className="metric-label">Recommendations shown</div>
            <div className="metric-value">{data.total_shown}</div>
          </div>
          <div className="metric-tile">
            <div className="metric-label">Accepted</div>
            <div className="metric-value">{data.total_accepted}</div>
            <div className="metric-sub">
              Acceptance rate: {(data.acceptance_rate * 100).toFixed(1)}%
            </div>
          </div>
          <div className="metric-tile" style={{ borderLeft: '3px solid var(--accent-green)' }}>
            <div className="metric-label">Accepted-Rupee</div>
            <div className="metric-value" style={{ color: 'var(--accent-green)' }}>
              {fmt(data.accepted_rupees)}
            </div>
            <div className="metric-sub">engine-priced savings you accepted</div>
          </div>
          <div className="metric-tile">
            <div className="metric-label">Calibration gate</div>
            <div className="metric-value">
              {data.resolved_events}<span style={{ fontSize: '0.8rem', fontWeight: 500 }}>/{data.calibration_gate.target}</span>
            </div>
            <div className="metric-sub">
              {data.calibration_gate.met
                ? 'threshold met — ECE can be measured'
                : 'resolved events needed before confidence is measured'}
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
        <div className="card-header" style={{ padding: 0, borderBottom: '1px solid var(--border)', marginBottom: '1rem' }}>
          <div className="card-title">Per-Head Adoption</div>
        </div>
        {data.per_head.length === 0 ? (
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            No recommendations shown yet — complete a consultation to start the loop.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Deduction head</th>
                <th style={{ textAlign: 'right' }}>Shown</th>
                <th style={{ textAlign: 'right' }}>Accepted</th>
                <th style={{ textAlign: 'right' }}>Rejected</th>
                <th style={{ textAlign: 'right' }}>Savings (max)</th>
                <th style={{ textAlign: 'right' }}>Accepted-Rupee</th>
              </tr>
            </thead>
            <tbody>
              {data.per_head.map((h) => (
                <tr key={h.head}>
                  <td style={{ fontWeight: 600 }}>
                    {h.head.replace(/_/g, ' ').toUpperCase()}
                  </td>
                  <td style={{ textAlign: 'right' }}>{h.shown}</td>
                  <td style={{ textAlign: 'right', color: 'var(--accent-green)' }}>{h.accepted}</td>
                  <td style={{ textAlign: 'right', color: 'var(--text-muted)' }}>{h.rejected}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(h.savings_engine)}</td>
                  <td style={{ textAlign: 'right', color: 'var(--accent-green)' }}>
                    {fmt(h.accepted_savings)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

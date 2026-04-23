'use client';

import React, { useState, useEffect } from 'react';
import SavingsGraph from './SavingsGraph';

interface TaxReportProps {
  session: any;
  onUpdateSession?: (session: any) => void;
}

const TaxReport: React.FC<TaxReportProps> = ({ session, onUpdateSession }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showJsonEdit, setShowJsonEdit] = useState(false);
  const [jsonContent, setJsonContent] = useState('');

  useEffect(() => {
    fetchCalculation();
  }, [session]);

  const fetchCalculation = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(session)
      });
      if (!res.ok) throw new Error("Backend calculation failed");
      const result = await res.json();
      setData(result);
      setJsonContent(JSON.stringify(session, null, 2));
    } catch (error) {
      console.error("Failed to fetch calculation", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !data) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <div className="glow-dot blue" style={{ margin: '0 auto 1rem' }} />
        <p style={{ color: 'var(--text-dim)' }}>Generating Industrial Audit Report...</p>
      </div>
    );
  }

  const best = data.recommendation === 'New Regime' ? data.new_regime : data.old_regime;
  const other = data.recommendation === 'New Regime' ? data.old_regime : data.new_regime;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2.5rem', animation: 'slideUp 0.5s ease-out', paddingBottom: '6rem' }}>
      
      {/* 1. TOP ANALYTICS & GRAPH */}
      <SavingsGraph data={data} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
        <div className="premium-card" style={{ borderLeft: '4px solid var(--accent-green)' }}>
          <p className="label-tiny">Tax Strategy</p>
          <h3 style={{ fontSize: '1.5rem', margin: '0.5rem 0' }}>{data.recommendation}</h3>
          <p style={{ color: 'var(--accent-green)', fontWeight: 700 }}>₹{data.savings?.toLocaleString('en-IN')} Annual Savings</p>
        </div>
        <div className="premium-card" style={{ borderLeft: '4px solid var(--accent-saffron)' }}>
          <p className="label-tiny">Net Tax Payable</p>
          <h3 style={{ fontSize: '1.5rem', margin: '0.5rem 0', color: 'var(--accent-saffron)' }}>₹{best.total_tax?.toLocaleString('en-IN')}</h3>
          <p style={{ color: 'var(--text-dim)' }}>Effective Tax Rate: {((best.total_tax / (best.gross_total_income || 1)) * 100).toFixed(1)}%</p>
        </div>
      </div>

      {/* 2. COMPUTATIONAL STATEMENT (CA STYLE) */}
      <div className="premium-card" style={{ padding: 0 }}>
        <div style={{ padding: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.02)' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>Computational Statement of Income</h3>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Particulars</th>
              <th>Reference</th>
              <th style={{ textAlign: 'right' }}>Amount (₹)</th>
            </tr>
          </thead>
          <tbody>
            {best.income_details.map((item: any, i: number) => (
              <tr key={i}>
                <td>{item.source}</td>
                <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Section {item.section}</td>
                <td style={{ textAlign: 'right' }}>{item.amount?.toLocaleString('en-IN')}</td>
              </tr>
            ))}
            <tr style={{ background: 'rgba(255,255,255,0.05)', fontWeight: 700 }}>
              <td>Gross Total Income (A)</td>
              <td>Sec 14</td>
              <td style={{ textAlign: 'right' }}>₹{best.gross_total_income?.toLocaleString('en-IN')}</td>
            </tr>
            {best.explanations.map((ex: any, i: number) => (
              <tr key={i} style={{ color: 'var(--accent-green)' }}>
                <td>Less: {ex.particular}</td>
                <td style={{ fontSize: '0.8rem' }}>Section {ex.section}</td>
                <td style={{ textAlign: 'right' }}>(-) {ex.amount?.toLocaleString('en-IN')}</td>
              </tr>
            ))}
            <tr style={{ background: 'rgba(16, 185, 129, 0.1)', fontWeight: 800 }}>
              <td>Total Taxable Income (A - B)</td>
              <td>Net Income</td>
              <td style={{ textAlign: 'right' }}>₹{best.taxable_income?.toLocaleString('en-IN')}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* 3. TAX SLAB ANALYSIS */}
      <div className="premium-card" style={{ padding: 0 }}>
        <div style={{ padding: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.02)' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>Tax Liability Breakdown (Slabs)</h3>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Tax Slab</th>
              <th>Rate</th>
              <th>Taxable Amount</th>
              <th style={{ textAlign: 'right' }}>Tax Computed</th>
            </tr>
          </thead>
          <tbody>
            {best.slabs_breakdown.map((slab: any, i: number) => (
              <tr key={i}>
                <td>{slab.range}</td>
                <td><span className="badge-luxe">{slab.rate}</span></td>
                <td>₹{slab.income?.toLocaleString('en-IN')}</td>
                <td style={{ textAlign: 'right', fontWeight: 600 }}>₹{slab.tax?.toLocaleString('en-IN')}</td>
              </tr>
            ))}
            <tr style={{ background: 'rgba(255,255,255,0.05)', fontWeight: 700 }}>
              <td colSpan={3} style={{ textAlign: 'right' }}>Total Tax (Before Cess)</td>
              <td style={{ textAlign: 'right' }}>₹{(best.total_tax / 1.04).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
            </tr>
            <tr>
              <td colSpan={3} style={{ textAlign: 'right' }}>Health & Education Cess (4%)</td>
              <td style={{ textAlign: 'right' }}>₹{(best.total_tax - (best.total_tax / 1.04)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
            </tr>
            <tr style={{ background: 'var(--bg-accent)', borderTop: '2px solid var(--primary)' }}>
              <td colSpan={3} style={{ textAlign: 'right', fontSize: '1.1rem', fontWeight: 800 }}>Final Tax Liability</td>
              <td style={{ textAlign: 'right', fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent-saffron)' }}>₹{best.total_tax?.toLocaleString('en-IN')}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* 4. AUDIT OBSERVATIONS */}
      {best.audit_observations.length > 0 && (
        <div className="premium-card" style={{ borderLeft: '4px solid var(--accent-saffron)', background: 'rgba(245, 158, 11, 0.05)' }}>
          <h4 style={{ fontSize: '0.9rem', marginBottom: '1rem', color: 'var(--accent-saffron)' }}>⚠️ Auditor Observations</h4>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', paddingLeft: '1.25rem' }}>
            {best.audit_observations.map((obs: string, i: number) => (
              <li key={i} style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>{obs}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 5. STRATEGIC TIPS */}
      <div className="premium-card" style={{ background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1), transparent)' }}>
        <h4 style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>💡 Optimization Strategies</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem' }}>
          {best.savings_tips.map((tip: string, i: number) => (
            <div key={i} className="premium-card" style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', fontSize: '0.85rem' }}>
              {tip}
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};

export default TaxReport;

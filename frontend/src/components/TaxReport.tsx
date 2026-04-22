'use client';

import React, { useState, useEffect } from 'react';

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
      const result = await res.json();
      setData(result);
      setJsonContent(JSON.stringify(session, null, 2));
      setLoading(false);
    } catch (error) {
      console.error("Failed to fetch calculation", error);
    }
  };

  const handleJsonUpdate = () => {
    try {
      const parsed = JSON.parse(jsonContent);
      if (onUpdateSession) onUpdateSession(parsed);
      setShowJsonEdit(false);
    } catch (e) {
      alert("Invalid JSON format");
    }
  };

  if (loading || !data) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', animation: 'fadeIn 1s' }}>
        <div className="premium-card" style={{ height: '120px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glow-dot blue" style={{ animation: 'pulse-slow 1.5s infinite' }} />
          <span style={{ fontSize: '0.9rem', color: 'var(--text-dim)' }}>Optimizing tax vectors...</span>
        </div>
        <div className="premium-card" style={{ height: '300px', opacity: 0.5 }}></div>
      </div>
    );
  }

  const best = data.recommendation === 'New Regime' ? data.new_regime : data.old_regime;
  const other = data.recommendation === 'New Regime' ? data.old_regime : data.new_regime;
  const score = data.efficiency_score || 0;
  const strokeDash = (score / 100) * 440; // 440 is approx circumference for r=70 (2*PI*70 = 439.8)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', animation: 'slideUp 0.5s ease-out' }}>
      
      {/* Top Stats Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div className="premium-card" style={{ borderLeft: '4px solid var(--accent-green)' }}>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Recommended Strategy</p>
          <h3 style={{ fontSize: '1.25rem', marginTop: '0.25rem' }}>{data.recommendation}</h3>
          <p style={{ fontSize: '0.75rem', color: 'var(--accent-green)', marginTop: '0.5rem' }}>
            Savings: ₹{data.savings.toLocaleString('en-IN')} vs Alternative
          </p>
        </div>
        <div className="premium-card" style={{ borderLeft: '4px solid var(--primary)' }}>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Final Tax Liability</p>
          <h3 style={{ fontSize: '1.5rem', marginTop: '0.25rem', color: 'var(--accent-saffron)' }}>₹{best.total_tax.toLocaleString('en-IN')}</h3>
        </div>
      </div>

      {/* Efficiency Gauge */}
      <div className="premium-card" style={{ textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: '1rem', right: '1rem' }}>
          <button className="btn-icon" onClick={() => setShowJsonEdit(!showJsonEdit)} title="Edit Source Data">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
          </button>
        </div>

        <div className="efficiency-ring-container">
          <svg className="ring-svg" viewBox="0 0 160 160">
            <circle className="ring-bg" cx="80" cy="80" r="70" />
            <circle 
              className="ring-fill" 
              cx="80" cy="80" r="70" 
              style={{ 
                strokeDasharray: `${strokeDash} 440`,
                stroke: score > 80 ? 'var(--accent-green)' : score > 50 ? 'var(--accent-saffron)' : '#ef4444'
              }} 
            />
          </svg>
          <div className="efficiency-value">
            <span className="efficiency-number">{score}%</span>
            <span className="efficiency-label">Efficiency</span>
          </div>
        </div>
        
        <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginTop: '1.5rem', maxWidth: '300px', margin: '1.5rem auto 0' }}>
          {score > 85 ? "Maximum legal tax optimization achieved for your profile." : "We've identified potential gaps in your deduction strategy."}
        </p>
      </div>

      {/* JSON Editor (Conditional) */}
      {showJsonEdit && (
        <div className="premium-card" style={{ background: '#0a0a0f', borderColor: 'var(--primary)' }}>
          <h4 style={{ fontSize: '0.8rem', marginBottom: '1rem', color: 'var(--primary)' }}>Advanced Profile Editor (JSON)</h4>
          <textarea 
            style={{ 
              width: '100%', height: '200px', background: 'transparent', 
              border: 'none', color: '#4ade80', fontFamily: 'monospace', 
              fontSize: '0.8rem', outline: 'none', resize: 'none' 
            }}
            value={jsonContent}
            onChange={(e) => setJsonContent(e.target.value)}
          />
          <button className="btn-primary" onClick={handleJsonUpdate} style={{ width: '100%', marginTop: '1rem', justifyContent: 'center' }}>
            Update Model Parameters
          </button>
        </div>
      )}

      {/* Main Data Breakdown */}
      <div className="premium-card">
        <h3 style={{ fontSize: '0.9rem', marginBottom: '1.5rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Audit Breakdown</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Particulars</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Amount (₹)</th>
            </tr>
          </thead>
          <tbody>
            {best.income_details.map((item: any, i: number) => (
              <tr key={`inc-${i}`}>
                <td>
                  <span className="glow-dot blue"></span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{item.source}</span>
                  <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: '16px' }}>{item.category}</p>
                </td>
                <td><span className="badge-luxe" style={{ fontSize: '0.6rem' }}>{item.status}</span></td>
                <td style={{ textAlign: 'right', fontWeight: 600 }}>{item.amount.toLocaleString('en-IN')}</td>
              </tr>
            ))}
            {best.deduction_details.map((item: any, i: number) => (
              <tr key={`ded-${i}`}>
                <td>
                  <span className="glow-dot green"></span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{item.section}</span>
                  <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: '16px' }}>Tax Saving Claim</p>
                </td>
                <td><span className="badge-luxe" style={{ fontSize: '0.6rem', borderColor: 'rgba(16, 185, 129, 0.3)', color: 'var(--accent-green)' }}>{item.status}</span></td>
                <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--accent-green)' }}>-{item.amount.toLocaleString('en-IN')}</td>
              </tr>
            ))}
          </tbody>
        </table>
        
        <div style={{ marginTop: '2rem', padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>Taxable Income</span>
          <span style={{ fontWeight: 700 }}>₹{best.taxable_income.toLocaleString('en-IN')}</span>
        </div>
      </div>

      {/* Legal Explainability Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <h3 style={{ fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Legal Reasoning</h3>
        {best.explanations.slice(0, 3).map((exp: any, i: number) => (
          <div key={i} className="premium-card" style={{ background: 'rgba(99, 102, 241, 0.03)', borderLeft: '3px solid var(--primary)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700 }}>{exp.section}</span>
              <span className="badge-luxe" style={{ fontSize: '0.6rem' }}>Verified</span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', lineHeight: '1.5' }}>{exp.reason}</p>
            <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
              <p style={{ fontSize: '0.75rem', color: 'var(--accent-green)', fontStyle: 'italic' }}>
                “{exp.eli5}”
              </p>
            </div>
          </div>
        ))}
      </div>

      <footer style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--text-muted)', fontSize: '0.65rem', lineHeight: '1.6' }}>
        AI AUDIT REPORT FY 2024-25 • GENERATED FOR {session.id?.split('_')[0] || 'SESSION'} • COMPLIANT WITH CBDT CIRCULAR 2024
      </footer>
    </div>
  );
};

export default TaxReport;

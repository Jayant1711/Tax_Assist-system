'use client';

import React, { useState, useEffect } from 'react';

interface TaxReportProps {
  session: any;
}

const TaxReport: React.FC<TaxReportProps> = ({ session }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('http://localhost:8000/calculate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(session)
        });
        const result = await res.json();
        setData(result);
        setLoading(false);
      } catch (error) {
        console.error("Failed to fetch calculation", error);
      }
    };
    fetchData();
  }, [session]);

  if (loading || !data) return <div className="glass-card">Deep analysis in progress...</div>;

  const best = data.recommendation === 'New Regime' ? data.new_regime : data.old_regime;

  return (
    <div className="glass-card" style={{ maxWidth: '1000px', overflowX: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.8rem' }}>AI Tax Audit Report</h2>
        <span className={`badge ${data.recommendation === 'New Regime' ? 'badge-green' : 'badge-saffron'}`} style={{ fontSize: '1rem', padding: '0.5rem 1rem' }}>
          Recommended: {data.recommendation}
        </span>
      </div>

      {/* Mandatory Table Format */}
      <div className="tax-table-container">
        <table className="tax-table">
          <thead>
            <tr>
              <th>Income Gain</th>
              <th>Income Deduct</th>
              <th>Source of Gain</th>
              <th>Tax Applicable</th>
              <th>Tax %</th>
              <th>Tax Claimable</th>
              <th>Category</th>
            </tr>
          </thead>
          <tbody>
            {best.income_details.map((item: any, i: number) => (
              <tr key={i}>
                <td>₹{item.amount.toLocaleString('en-IN')}</td>
                <td>-</td>
                <td>{item.source}</td>
                <td>₹{item.amount.toLocaleString('en-IN')}</td>
                <td>{item.tax_pct}</td>
                <td>No</td>
                <td>Income</td>
              </tr>
            ))}
            {best.deduction_details.map((item: any, i: number) => (
              <tr key={`ded-${i}`}>
                <td>-</td>
                <td>₹{item.amount.toLocaleString('en-IN')}</td>
                <td>Deduction</td>
                <td>-</td>
                <td>-</td>
                <td>Yes</td>
                <td>{item.section}</td>
              </tr>
            ))}
            {/* Summary Row */}
            <tr style={{ fontWeight: 700, background: 'rgba(255,255,255,0.05)', borderTop: '2px solid white' }}>
              <td>Total Income</td>
              <td>Total Deduction</td>
              <td>-</td>
              <td>Taxable Income</td>
              <td>-</td>
              <td>Total Tax</td>
              <td>Savings</td>
            </tr>
            <tr style={{ fontWeight: 700, background: 'rgba(255,255,255,0.05)' }}>
              <td className="highlight-saffron">₹{(best.income_details.reduce((a:any, b:any) => a + b.amount, 0)).toLocaleString('en-IN')}</td>
              <td className="highlight-green">₹{(best.deduction_details.reduce((a:any, b:any) => a + b.amount, 0)).toLocaleString('en-IN')}</td>
              <td>-</td>
              <td>₹{best.taxable_income.toLocaleString('en-IN')}</td>
              <td>-</td>
              <td className="highlight-saffron">₹{best.total_tax.toLocaleString('en-IN')}</td>
              <td className="highlight-green">₹{data.savings.toLocaleString('en-IN')}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Explainability Layer */}
      <div style={{ marginTop: '3rem' }}>
        <h3 style={{ marginBottom: '1rem', color: 'var(--text-secondary)' }}>Compliance & Logic (Explainable AI)</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {best.explanations.map((exp: any, i: number) => (
            <div key={i} style={{ padding: '1rem', borderLeft: '4px solid var(--accent-saffron)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ fontWeight: 600, fontSize: '0.9rem' }}>{exp.particular} - {exp.section}</p>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{exp.reason}</p>
              {exp.amount > 0 && <p style={{ fontSize: '0.8rem', marginTop: '0.5rem', color: 'var(--accent-green)' }}>Verified Deduction: ₹{exp.amount.toLocaleString('en-IN')}</p>}
            </div>
          ))}
          {best.explanations.length === 0 && <p style={{ fontSize: '0.85rem', fontStyle: 'italic' }}>All income is fully taxable under basic slab rates.</p>}
        </div>
      </div>
    </div>
  );
};

export default TaxReport;

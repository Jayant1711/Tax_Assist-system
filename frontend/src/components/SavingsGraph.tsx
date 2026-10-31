'use client';

import React from 'react';

interface Props {
  data: any;
}

export default function SavingsGraph({ data }: Props) {
  if (!data) return null;

  const oldTax = data.old_regime?.total_tax || 0;
  const newTax = data.new_regime?.total_tax || 0;
  const oldGross = data.old_regime?.gross_total_income || 1;
  const newGross = data.new_regime?.gross_total_income || 1;

  const maxTax = Math.max(oldTax, newTax, 1);
  const rec = data.recommendation || (newTax <= oldTax ? 'New Regime' : 'Old Regime');
  const savings = data.savings ?? Math.abs(oldTax - newTax);

  const oldRate = ((oldTax / oldGross) * 100).toFixed(1);
  const newRate = ((newTax / newGross) * 100).toFixed(1);

  const fmt = (n: number) => '₹' + Math.round(n).toLocaleString('en-IN');

  return (
    <div className="card" style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: 0, right: 0, width: '150px', height: '150px', background: 'radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)', pointerEvents: 'none' }} />

      <div className="card-header">
        <div>
          <div className="card-title">Regime Tax Comparison (FY 2024-25)</div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Direct side-by-side computation based on declared deductions & income
          </p>
        </div>
        <span className="regime-badge recommended">
          ✓ {rec} is Optimal
        </span>
      </div>

      <div className="regime-bar-wrap">
        {/* Old Regime */}
        <div className="regime-bar-item">
          <div className="regime-bar-header">
            <span className="regime-bar-name" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>Old Tax Regime</span>
              {rec === 'Old Regime' && (
                <span className="regime-badge recommended" style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}>
                  ★ Winner
                </span>
              )}
            </span>
            <div style={{ textAlign: 'right' }}>
              <span className="regime-bar-amount" style={{ fontSize: '1rem', fontWeight: 700, color: rec === 'Old Regime' ? 'var(--accent-green)' : 'var(--text-main)' }}>
                {fmt(oldTax)}
              </span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                ({oldRate}% eff.)
              </span>
            </div>
          </div>
          <div className="regime-bar-track">
            <div
              className="regime-bar-fill old"
              style={{
                width: `${Math.max(4, (oldTax / maxTax) * 100)}%`,
                opacity: rec === 'Old Regime' ? 1 : 0.65,
              }}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.3rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            <span>Eligible for 80C, 80D, HRA & 24(b)</span>
            <span>Taxable: {fmt(data.old_regime?.taxable_income || 0)}</span>
          </div>
        </div>

        {/* New Regime */}
        <div className="regime-bar-item">
          <div className="regime-bar-header">
            <span className="regime-bar-name" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>New Tax Regime (Sec 115BAC)</span>
              {rec === 'New Regime' && (
                <span className="regime-badge recommended" style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}>
                  ★ Winner
                </span>
              )}
            </span>
            <div style={{ textAlign: 'right' }}>
              <span className="regime-bar-amount" style={{ fontSize: '1rem', fontWeight: 700, color: rec === 'New Regime' ? 'var(--accent-green)' : 'var(--text-main)' }}>
                {fmt(newTax)}
              </span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                ({newRate}% eff.)
              </span>
            </div>
          </div>
          <div className="regime-bar-track">
            <div
              className="regime-bar-fill new"
              style={{
                width: `${Math.max(4, (newTax / maxTax) * 100)}%`,
                opacity: rec === 'New Regime' ? 1 : 0.65,
              }}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.3rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            <span>₹75k Standard Ded. + Nil tax up to ₹7L (87A)</span>
            <span>Taxable: {fmt(data.new_regime?.taxable_income || 0)}</span>
          </div>
        </div>
      </div>

      {/* Savings Summary Banner */}
      <div
        style={{
          marginTop: '1.5rem',
          padding: '1rem 1.25rem',
          background: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          borderRadius: 'var(--radius-md)',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
        }}
      >
        <div
          style={{
            width: '38px',
            height: '38px',
            borderRadius: '50%',
            background: 'rgba(16, 185, 129, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.1rem',
            color: 'var(--accent-green)',
            flexShrink: 0,
          }}
        >
          💰
        </div>
        <div>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)' }}>
            Choosing <span style={{ color: 'var(--accent-green)' }}>{rec}</span> will save you {fmt(savings)} in taxes!
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-sub)', marginTop: '2px' }}>
            {rec === 'New Regime'
              ? 'Lower slab rates and higher standard deduction outweigh your eligible itemized deductions.'
              : 'Your combined deductions under Section 80 and house property exceed the threshold where New Regime would be beneficial.'}
          </div>
        </div>
      </div>
    </div>
  );
}

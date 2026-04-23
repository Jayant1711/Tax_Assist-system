'use client';

import React from 'react';

interface SavingsGraphProps {
  data: any;
}

const SavingsGraph: React.FC<SavingsGraphProps> = ({ data }) => {
  if (!data) return null;

  const oldTax = data.old_regime?.total_tax || 0;
  const newTax = data.new_regime?.total_tax || 0;
  const maxTax = Math.max(oldTax, newTax, 1);
  
  const oldWidth = (oldTax / maxTax) * 100;
  const newWidth = (newTax / maxTax) * 100;

  return (
    <div className="premium-card graph-entrance" style={{ padding: '2rem' }}>
      <h4 style={{ fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '1.5rem', color: 'var(--text-muted)' }}>
        Regime Comparison Graph
      </h4>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        {/* Old Regime Bar */}
        <div style={{ position: 'relative' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.85rem' }}>
            <span style={{ fontWeight: 600 }}>Old Regime</span>
            <span style={{ color: 'var(--text-dim)' }}>₹{oldTax.toLocaleString('en-IN')}</span>
          </div>
          <div style={{ height: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', overflow: 'hidden' }}>
            <div style={{ 
              height: '100%', 
              width: `${oldWidth}%`, 
              background: 'linear-gradient(90deg, #6366f1, #a855f7)', 
              borderRadius: '6px',
              transition: 'width 1s ease-out'
            }} />
          </div>
        </div>

        {/* New Regime Bar */}
        <div style={{ position: 'relative' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.85rem' }}>
            <span style={{ fontWeight: 600 }}>New Regime (U/S 115BAC)</span>
            <span style={{ color: 'var(--text-dim)' }}>₹{newTax.toLocaleString('en-IN')}</span>
          </div>
          <div style={{ height: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', overflow: 'hidden' }}>
            <div style={{ 
              height: '100%', 
              width: `${newWidth}%`, 
              background: 'linear-gradient(90deg, #10b981, #34d399)', 
              borderRadius: '6px',
              transition: 'width 1s ease-out'
            }} />
          </div>
        </div>
      </div>

      <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div style={{ 
          width: '40px', 
          height: '40px', 
          borderRadius: '50%', 
          background: 'rgba(16, 185, 129, 0.1)', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          color: 'var(--accent-green)',
          fontSize: '1.2rem'
        }}>✨</div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
          The <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>{data.recommendation}</span> saves you 
          <span style={{ color: 'var(--accent-green)', fontWeight: 700 }}> ₹{data.savings?.toLocaleString('en-IN')}</span> annually.
        </p>
      </div>
    </div>
  );
};

export default SavingsGraph;

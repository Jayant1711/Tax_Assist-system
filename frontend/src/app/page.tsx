'use client';

import React, { useState } from 'react';
import ChatInterface from '@/components/ChatInterface';
import TaxReport from '@/components/TaxReport';

export default function Home() {
  const [session, setSession] = useState<any>({});
  const [showReport, setShowReport] = useState(false);

  return (
    <main>
      <div className="container">
        <header style={{ textAlign: 'center', marginBottom: '1rem' }}>
          <h1 style={{ fontSize: '2.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Tax Assist <span className="highlight-saffron">AI</span>
          </h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Your intelligent companion for Indian Income Tax filing
          </p>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: showReport ? '1fr 1fr' : '1fr', gap: '2rem', transition: 'all 0.5s ease' }}>
          <ChatInterface 
            onUpdateSession={setSession} 
            onShowReport={setShowReport} 
          />
          
          {showReport && (
            <div style={{ animation: 'fadeIn 0.5s ease-out' }}>
              <TaxReport session={session} />
            </div>
          )}
        </div>

        <footer style={{ marginTop: 'auto', padding: '2rem 0', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
          Based on Income Tax Rules for FY 2024-25 (AY 2025-26). This is a tool for assistance and not a substitute for professional tax advice.
        </footer>
      </div>
    </main>
  );
}

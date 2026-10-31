'use client';

import React, { useState } from 'react';
import ChatInterface from '@/components/ChatInterface';
import TaxReport from '@/components/TaxReport';
import SavingsGraph from '@/components/SavingsGraph';

export default function Home() {
  const [session, setSession] = useState<any>({ phase: 'PROFILING' });
  const [showReport, setShowReport] = useState(false);
  const [activeView, setActiveView] = useState<'chat' | 'summary' | 'graph'>('chat');

  const hasData = session && (session.salary > 0 || session.business > 0 || session.rental > 0);

  return (
    <main className="app-shell">
      {/* ── Left Sidebar (Navigation & Controls) ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">T</div>
          <div>
            <div className="logo-text">
              TaxAssist <span>AI</span>
            </div>
            <div className="logo-sub">Deep Consultant · FY 24-25</div>
          </div>
        </div>

        <div className="nav-section-label">Consultation Views</div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          <div
            className={`nav-item ${activeView === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveView('chat')}
          >
            <span className="icon">💬</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>Active Dialogue</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                Guided discovery flow
              </div>
            </div>
            <span style={{ fontSize: '0.65rem', background: 'rgba(99,102,241,0.2)', color: 'var(--primary-light)', padding: '0.1rem 0.4rem', borderRadius: '10px' }}>
              Live
            </span>
          </div>

          <div
            className={`nav-item ${activeView === 'summary' ? 'active' : ''}`}
            onClick={() => {
              setActiveView('summary');
              setShowReport(true);
            }}
          >
            <span className="icon">📋</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>Tax Summary & Statement</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                ITR computation breakdown
              </div>
            </div>
          </div>

          <div
            className={`nav-item ${activeView === 'graph' ? 'active' : ''}`}
            onClick={() => {
              setActiveView('graph');
              setShowReport(true);
            }}
          >
            <span className="icon">📈</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>Regime Comparison</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                Old vs New tax visualizer
              </div>
            </div>
          </div>
        </nav>

        <div className="nav-section-label">Quick Rules (FY 2024-25)</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '0.25rem 0.5rem' }}>
          <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.6rem 0.75rem', fontSize: '0.73rem', lineHeight: 1.5 }}>
            <span style={{ color: 'var(--accent-green)', fontWeight: 600 }}>New Regime:</span>
            <div style={{ color: 'var(--text-sub)' }}>Standard ded. ₹75k, rebate up to ₹7L (Sec 87A).</div>
          </div>
          <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.6rem 0.75rem', fontSize: '0.73rem', lineHeight: 1.5 }}>
            <span style={{ color: 'var(--primary-light)', fontWeight: 600 }}>Old Regime:</span>
            <div style={{ color: 'var(--text-sub)' }}>80C (₹1.5L), 80D (₹25k-₹50k), HRA & Sec 24(b) home loan.</div>
          </div>
        </div>

        {/* Profile Status Badge */}
        {session?.profile && (
          <div style={{ margin: '1rem 0 0.5rem', padding: '0.75rem', background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--primary-light)', fontWeight: 700 }}>
              Profile Detected
            </div>
            <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-main)', marginTop: '2px' }}>
              {session.profile}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Phase: {session.phase || 'PROFILING'}
            </div>
          </div>
        )}

        <div className="sidebar-footer">
          <strong>⚡ Powered by ANFIS v3.5</strong>
          Dual-engine neuro-fuzzy inference & compliance checks for Indian tax filing.
        </div>
      </aside>

      {/* ── Main Content Area (Chat + Live Dashboard) ── */}
      <div className="main-content">
        {/* Left: Chat Conversation Pane */}
        <div className="chat-panel">
          <ChatInterface
            onUpdateSession={setSession}
            onShowReport={setShowReport}
          />
        </div>

        {/* Right: Live Tax Intelligence Dashboard */}
        <div className="report-panel">
          <div className="report-header">
            <div>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-main)' }}>
                Real-Time Tax Audit
              </h2>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Instant parity calculation & deduction optimization
              </p>
            </div>
            {hasData && (
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <button
                  className={`btn btn-sm ${activeView === 'chat' || activeView === 'summary' ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => {
                    setActiveView('summary');
                    setShowReport(true);
                  }}
                >
                  Statement
                </button>
                <button
                  className={`btn btn-sm ${activeView === 'graph' ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => {
                    setActiveView('graph');
                    setShowReport(true);
                  }}
                >
                  Regime Graph
                </button>
              </div>
            )}
          </div>

          <div className="report-body">
            {showReport || hasData ? (
              <TaxReport
                session={session}
                activeView={activeView}
                onUpdateSession={setSession}
              />
            ) : (
              <div className="empty-state">
                <div className="empty-icon">📊</div>
                <div className="empty-title">Awaiting Financial Discovery</div>
                <div className="empty-desc">
                  Provide your profession and income details in the chat to generate real-time tax simulations.
                </div>

                <div className="empty-steps">
                  <div className="empty-step">
                    <div className="empty-step-num">1</div>
                    <span>Declare salary or business revenue</span>
                  </div>
                  <div className="empty-step">
                    <div className="empty-step-num">2</div>
                    <span>Specify 80C, 80D, rent or home loan</span>
                  </div>
                  <div className="empty-step">
                    <div className="empty-step-num">3</div>
                    <span>Review instant side-by-side tax comparison</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

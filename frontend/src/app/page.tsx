'use client';

import React, { useState } from 'react';
import ChatInterface from '@/components/ChatInterface';
import TaxReport from '@/components/TaxReport';

export default function Home() {
  const [session, setSession] = useState<any>({});
  const [showReport, setShowReport] = useState(false);
  const [activeView, setActiveView] = useState<'chat' | 'summary' | 'graph'>('chat');

  return (
    <main className="app-shell">
      {/* Sidebar - Premium Navigation */}
      <aside className="sidebar">
        <div style={{ marginBottom: '3rem' }}>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ 
              width: '40px', 
              height: '40px', 
              background: 'linear-gradient(135deg, var(--primary), #4f46e5)', 
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.25rem',
              color: 'white',
              boxShadow: '0 8px 16px var(--primary-glow)'
            }}>T</span>
            TaxAssist <span style={{ color: 'var(--accent-saffron)' }}>AI</span>
          </h1>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div className="badge-luxe" style={{ marginBottom: '1rem', textAlign: 'center' }}>FY 2024-25</div>
          
          <button 
            className={`premium-card ${activeView === 'chat' ? 'active' : ''}`} 
            style={{ padding: '1rem', textAlign: 'left', cursor: 'pointer', background: activeView === 'chat' ? 'rgba(99, 102, 241, 0.1)' : 'rgba(255,255,255,0.05)', border: activeView === 'chat' ? '1px solid var(--primary)' : '1px solid transparent' }}
            onClick={() => setActiveView('chat')}
          >
            <span style={{ display: 'block', fontSize: '0.9rem', fontWeight: 600 }}>Active Session</span>
            <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-dim)' }}>Consulting now...</span>
          </button>
          
          <div style={{ marginTop: '2rem' }}>
            <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '1rem' }}>Tools</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div 
                style={{ fontSize: '0.85rem', color: activeView === 'summary' ? 'var(--primary)' : 'var(--text-dim)', padding: '0.5rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.75rem' }}
                onClick={() => { setActiveView('summary'); setShowReport(true); }}
              >
                <span style={{ fontSize: '1.1rem' }}>📋</span> Tax Summary
              </div>
              <div 
                style={{ fontSize: '0.85rem', color: activeView === 'graph' ? 'var(--primary)' : 'var(--text-dim)', padding: '0.5rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.75rem' }}
                onClick={() => { setActiveView('graph'); setShowReport(true); }}
              >
                <span style={{ fontSize: '1.1rem' }}>📈</span> Savings Graph
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', padding: '0.5rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '1.1rem' }}>⚙️</span> Preferences
              </div>
            </div>
          </div>
        </nav>

        <div style={{ marginTop: 'auto', padding: '1rem', background: 'var(--bg-accent)', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
            Expert AI analysis powered by ANFIS v3 + EE-BAT Intelligence.
          </p>
        </div>
      </aside>

      {/* Main Content Area */}
      <section className="main-content">
        <div className="dashboard-grid">
          {/* Chat Pane */}
          <div className="chat-section">
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>AI Consultant</h2>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Multi-source income reasoning active</p>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <div className="badge-luxe" style={{ color: 'var(--accent-green)', borderColor: 'rgba(16, 185, 129, 0.2)' }}>● Live</div>
              </div>
            </header>
            
            <ChatInterface 
              onUpdateSession={setSession} 
              onShowReport={setShowReport} 
            />
          </div>

          {/* Report Pane - Real-time Dashboard */}
          <div className="report-section">
            <header style={{ marginBottom: '2rem' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Real-time Insights</h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Instant tax simulation and optimization</p>
            </header>

            {showReport ? (
              <TaxReport session={session} onUpdateSession={setSession} />
            ) : (
              <div style={{ 
                height: '80%', 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'center', 
                justifyContent: 'center',
                textAlign: 'center',
                color: 'var(--text-muted)',
                gap: '1.5rem'
              }}>
                <div style={{ 
                  fontSize: '4rem', 
                  opacity: 0.2, 
                  animation: 'pulse-slow 3s infinite ease-in-out' 
                }}>📊</div>
                <div>
                  <h3 style={{ color: 'var(--text-dim)', marginBottom: '0.5rem' }}>Waiting for Data</h3>
                  <p style={{ maxWidth: '250px', margin: '0 auto', fontSize: '0.85rem' }}>
                    Speak with our AI consultant to build your real-time tax profile.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

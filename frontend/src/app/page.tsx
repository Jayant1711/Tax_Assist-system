'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import ChatInterface from '@/components/ChatInterface';
import TaxReport from '@/components/TaxReport';
import { apiFetch, onUnauthorized } from '@/lib/api';

/**
 * The client holds ONLY the server-issued session id plus the read-only
 * state projection (ADR-013 Wave D contract). Full state never leaves the
 * backend; /chat and /calculate address it with {session_id}.
 */
type Projection = Record<string, any>;
type AuthPhase = 'checking' | 'ready' | 'error';

export default function Home() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [projection, setProjection] = useState<Projection | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [authPhase, setAuthPhase] = useState<AuthPhase>('checking');
  const [bootstrapAttempt, setBootstrapAttempt] = useState(0);
  const [showReport, setShowReport] = useState(false);
  const [activeView, setActiveView] = useState<'chat' | 'summary' | 'graph'>('chat');

  // Central 401 hook → client-side redirect to /login (App Router,
  // no middleware). Any apiFetch 401 (expired/revoked cookie) lands here.
  useEffect(() => {
    onUnauthorized(() => router.push('/login'));
  }, [router]);

  const bootstrap = useCallback(async (): Promise<AuthPhase> => {
    try {
      // 1. Server-side session check. On 401 the hook above also redirects;
      // the explicit push keeps this page's contract self-evident.
      const meRes = await apiFetch('/auth/me');
      if (meRes.status === 401) {
        router.push('/login');
        return 'checking';
      }
      if (!meRes.ok) return 'error';
      const me = await meRes.json();
      // 2. Bootstrap the server-side consultation session.
      const bootRes = await apiFetch('/sessions', { method: 'POST' });
      if (bootRes.status === 401) {
        router.push('/login');
        return 'checking';
      }
      if (!bootRes.ok) return 'error';
      const boot = await bootRes.json();
      setUserEmail(me.email ?? null);
      setSessionId(boot.session_id);
      setProjection(boot.session ?? { phase: 'PROFILING' });
      return 'ready';
    } catch {
      return 'error';
    }
  }, [router]);

  useEffect(() => {
    let cancelled = false;
    bootstrap().then((phase) => {
      if (!cancelled) setAuthPhase(phase);
    });
    return () => {
      cancelled = true;
    };
  }, [bootstrap, bootstrapAttempt]);

  const handleUpdateSession = useCallback((proj: Projection, sid?: string) => {
    setProjection(proj);
    if (sid) setSessionId(sid);
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      // 204: revokes the server session row and clears the cookie.
      await apiFetch('/auth/logout', { method: 'POST' });
    } catch {
      // Logout is idempotent server-side; always end at /login.
    }
    router.push('/login');
  }, [router]);

  const hasData =
    !!projection &&
    (Number(projection.salary) > 0 ||
      Number(projection.business) > 0 ||
      Number(projection.rental) > 0);

  if (authPhase !== 'ready') {
    return (
      <main
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1.25rem',
        }}
      >
        {authPhase === 'checking' ? (
          <div role="status" style={{ textAlign: 'center' }}>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginBottom: '1rem' }}>
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="typing-dot"
                  style={{ width: '12px', height: '12px', background: 'var(--primary)', animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
            <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>Verifying your session…</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Securing the consultation workspace
            </div>
          </div>
        ) : (
          <div role="alert" style={{ textAlign: 'center' }}>
            <div style={{ fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.35rem' }}>
              Unable to reach the service
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              The session could not be established. Please try again.
            </div>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => {
                setAuthPhase('checking');
                setBootstrapAttempt((n) => n + 1);
              }}
            >
              Retry
            </button>
          </div>
        )}
      </main>
    );
  }

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
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }} aria-label="Consultation views">
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

        <div className="nav-section-label">Quick Rules (FY 2025-26)</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '0.25rem 0.5rem' }}>
          <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.6rem 0.75rem', fontSize: '0.73rem', lineHeight: 1.5 }}>
            <span style={{ color: 'var(--accent-green)', fontWeight: 600 }}>New Regime:</span>
            <div style={{ color: 'var(--text-sub)' }}>Standard ded. ₹75k, zero tax up to ₹12L (Sec 87A).</div>
          </div>
          <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.6rem 0.75rem', fontSize: '0.73rem', lineHeight: 1.5 }}>
            <span style={{ color: 'var(--primary-light)', fontWeight: 600 }}>Old Regime:</span>
            <div style={{ color: 'var(--text-sub)' }}>80C (₹1.5L), 80D (₹25k-₹50k), HRA & Sec 24(b) home loan.</div>
          </div>
        </div>

        {/* Profile Status Badge */}
        {projection?.profile && (
          <div style={{ margin: '1rem 0 0.5rem', padding: '0.75rem', background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--primary-light)', fontWeight: 700 }}>
              Profile Detected
            </div>
            <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-main)', marginTop: '2px' }}>
              {projection.profile}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Phase: {projection.phase || 'PROFILING'}
            </div>
          </div>
        )}

        <div className="sidebar-footer">
          <strong>⚡ Powered by ANFIS v3.5</strong>
          Dual-engine neuro-fuzzy inference & compliance checks for Indian tax filing.
          {userEmail && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.72rem', color: 'var(--text-muted)', wordBreak: 'break-all' }}>
              Signed in as <span style={{ color: 'var(--text-sub)', fontWeight: 600 }}>{userEmail}</span>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="btn btn-ghost btn-sm"
            style={{ marginTop: '0.6rem', width: '100%', justifyContent: 'center' }}
            title="End this session and return to sign-in"
          >
            ⎋ Sign out
          </button>
        </div>
      </aside>

      {/* ── Main Content Area (Chat + Live Dashboard) ── */}
      <div className="main-content">
        {/* Left: Chat Conversation Pane */}
        <div className="chat-panel">
          <ChatInterface
            sessionId={sessionId as string}
            onUpdateSession={handleUpdateSession}
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
                sessionId={sessionId}
                projection={projection}
                activeView={activeView}
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

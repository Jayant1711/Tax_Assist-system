'use client';

import React, { useState, useEffect, useRef } from 'react';

interface Message {
  id: string;
  role: 'ai' | 'user';
  text: string;
  timestamp: string;
  extracted?: string[];
}

interface Props {
  onUpdateSession: (session: any) => void;
  onShowReport: (show: boolean) => void;
}

const PHASES = ['PROFILING', 'INCOME', 'EXPENDITURE', 'RECALL', 'FINAL'];

const QUICK_SUGGESTIONS: Record<string, string[]> = {
  PROFILING: [
    "I'm a Software Engineer",
    "I run a Retail Shop",
    "Freelance Designer",
    "Doctor / Clinic Owner",
  ],
  INCOME: [
    "15 Lakhs per year",
    "24 LPA salaried",
    "8.5 Lakhs business profit",
    "50,000 per month",
  ],
  EXPENDITURE: [
    "1.5 Lakhs in PF & ELSS (80C)",
    "25,000 Health Insurance (80D)",
    "50,000 in NPS",
    "No investments to declare",
  ],
  RECALL: [
    "No other deductions",
    "Yes, 1.2L home loan interest",
    "Proceed to final report",
  ],
  FINAL: [
    "Recalculate with New Regime",
    "Start fresh session",
  ],
};

function formatMarkdown(text: string): React.ReactNode {
  // Simple markdown renderer for bold, italic, inline code, bullets
  const lines = text.split('\n');
  return lines.map((line, lineIdx) => {
    // Check if bullet point
    const isBullet = line.trim().startsWith('- ') || line.trim().startsWith('* ');
    const cleanLine = isBullet ? line.trim().substring(2) : line;

    const parts = cleanLine.split(/(\*\*[^*]+\*\*|_[^_]+_|`[^`]+`)/g);
    const renderedParts = parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-amber-300">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('_') && part.endsWith('_')) {
        return <em key={i} className="text-slate-400 not-italic">{part.slice(1, -1)}</em>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={i} className="px-1.5 py-0.5 rounded bg-white/10 text-emerald-300 text-xs font-mono">
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });

    if (isBullet) {
      return (
        <div key={lineIdx} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', margin: '0.2rem 0' }}>
          <span style={{ color: 'var(--primary-light)', fontSize: '0.8rem', marginTop: '2px' }}>•</span>
          <div>{renderedParts}</div>
        </div>
      );
    }

    return (
      <p key={lineIdx} style={{ margin: lineIdx > 0 ? '0.35rem 0 0 0' : 0 }}>
        {renderedParts}
      </p>
    );
  });
}

export default function ChatInterface({ onUpdateSession, onShowReport }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'ai',
      text: "Namaste! 🙏 I am your **AI Tax Consultant** for Indian Tax Laws (FY 2025-26 / AY 2026-27).\n\nLet's calculate your exact tax, optimize deductions, and choose between the **Old and New Regimes**.\n\nTo begin, what is your **profession or source of livelihood**?",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [session, setSession] = useState<any>({
    id: `sid_${Date.now()}`,
    phase: 'PROFILING',
  });
  const [showDebug, setShowDebug] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const chatRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    if (chatRef.current) {
      chatRef.current.scrollTo({
        top: chatRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  };

  useEffect(() => {
    scrollToBottom();
    if (!isTyping) {
      inputRef.current?.focus();
    }
  }, [messages, isTyping]);

  const currentPhase = session?.phase || 'PROFILING';
  const currentPhaseIdx = Math.max(0, PHASES.indexOf(currentPhase));

  const sendMessage = async (messageText?: string) => {
    const textToSend = (messageText ?? input).trim();
    if (!textToSend || isTyping) return;

    const userMsg: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: textToSend, session }),
      });

      if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);

      const data = await res.json();
      setSession(data.session);
      onUpdateSession(data.session);

      setTimeout(() => {
        setIsTyping(false);
        const aiMsg: Message = {
          id: `ai_${Date.now()}`,
          role: 'ai',
          text: data.response,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          extracted: data.extracted && data.extracted.length > 0 ? data.extracted : undefined,
        };
        setMessages((prev) => [...prev, aiMsg]);

        if (data.session?.phase === 'FINAL' || (data.tax_report && Object.keys(data.tax_report).length > 0)) {
          onShowReport(true);
        }
      }, 400);
    } catch (err) {
      console.error('Chat error:', err);
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          role: 'ai',
          text: '⚠️ **Backend Unavailable** — Ensure the FastAPI server is running on `http://localhost:8000`. You can start it via `cd backend && python main.py`.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
  };

  const handleResetSession = () => {
    const newSession = { id: `sid_${Date.now()}`, phase: 'PROFILING' };
    setSession(newSession);
    onUpdateSession(newSession);
    setMessages([
      {
        id: 'welcome_reset',
        role: 'ai',
        text: "New consultation started! What is your **profession and annual income**? (e.g. 'Software Engineer earning 15 LPA')",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  const currentSuggestions = QUICK_SUGGESTIONS[currentPhase] || [];

  return (
    <>
      {/* ── Chat Header ── */}
      <div className="chat-header">
        <div>
          <div className="chat-title">AI Tax Consultant</div>
          <div className="chat-subtitle">Dual-Regime Discovery · ANFIS v3.5 Optimization</div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <div className="live-badge">
            <span className="live-dot" /> Live
          </div>
          <button
            className="debug-toggle"
            onClick={() => setShowDebug(!showDebug)}
            title="Toggle session telemetry"
          >
            {showDebug ? '✕ Hide State' : '🔍 Debug'}
          </button>
          <button
            onClick={handleResetSession}
            className="btn btn-ghost btn-sm"
            style={{ padding: '0.25rem 0.5rem', fontSize: '0.7rem' }}
            title="Reset consultation"
          >
            ↺ Reset
          </button>
        </div>
      </div>

      {/* ── Progress Stepper ── */}
      <div className="stepper">
        {PHASES.map((p, i) => {
          const isDone = i < currentPhaseIdx;
          const isActive = i === currentPhaseIdx;
          return (
            <div key={p} className="step">
              <div
                className={`step-bar ${isActive ? 'active' : isDone ? 'done' : ''}`}
              />
              <div
                className={`step-label ${isActive ? 'active' : isDone ? 'done' : ''}`}
              >
                {p === 'PROFILING' ? '1. PROFILE' :
                 p === 'INCOME' ? '2. INCOME' :
                 p === 'EXPENDITURE' ? '3. DEDUCTIONS' :
                 p === 'RECALL' ? '4. AUDIT' : '5. REPORT'}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Debug Panel ── */}
      {showDebug && (
        <div style={{ padding: '0.75rem 1.5rem', background: 'rgba(0,0,0,0.4)', borderBottom: '1px solid var(--border)' }}>
          <div className="debug-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <span style={{ color: 'var(--accent-blue)', fontWeight: 600 }}>Active Session ID: {session?.id}</span>
              <span style={{ color: 'var(--accent-green)' }}>Phase: {session?.phase}</span>
            </div>
            <pre>{JSON.stringify(session, null, 2)}</pre>
          </div>
        </div>
      )}

      {/* ── Chat Messages ── */}
      <div className="chat-history" ref={chatRef}>
        {messages.map((msg) => (
          <div key={msg.id} className={`msg-row ${msg.role}`}>
            <div className={`avatar ${msg.role}`}>
              {msg.role === 'ai' ? 'AI' : 'YOU'}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', maxWidth: '82%' }}>
              <div className={`bubble ${msg.role}`}>
                {formatMarkdown(msg.text)}

                {/* Extracted badges inside AI reply */}
                {msg.extracted && msg.extracted.length > 0 && (
                  <div style={{ marginTop: '0.6rem', paddingTop: '0.5rem', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                    {msg.extracted.map((item, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: '0.68rem',
                          padding: '0.15rem 0.5rem',
                          borderRadius: '6px',
                          background: 'rgba(16,185,129,0.15)',
                          color: 'var(--accent-green)',
                          border: '1px solid rgba(16,185,129,0.25)',
                          fontWeight: 600,
                        }}
                      >
                        ✓ {item}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div
                className="msg-time"
                style={{ textAlign: msg.role === 'user' ? 'right' : 'left' }}
              >
                {msg.timestamp}
              </div>
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="msg-row ai">
            <div className="avatar ai">AI</div>
            <div className="typing-bubble">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          </div>
        )}
      </div>

      {/* ── Quick Suggestion Chips & Demo Profiles ── */}
      {!isTyping && (
        <div style={{ padding: '0.4rem 1.5rem', display: 'flex', gap: '0.4rem', overflowX: 'auto', background: 'rgba(8,12,26,0.6)' }}>
          {currentPhase === 'PROFILING' && (
            <>
              <button
                onClick={() => sendMessage("I am a software engineer earning 24 LPA. I invest 1.5L in 80C, 25k in 80D health insurance, and 50k in NPS.")}
                style={{
                  fontSize: '0.72rem',
                  padding: '0.25rem 0.65rem',
                  borderRadius: '16px',
                  background: 'rgba(99,102,241,0.18)',
                  border: '1px solid rgba(99,102,241,0.4)',
                  color: 'var(--primary-light)',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  fontWeight: 600,
                  transition: 'all 0.2s',
                }}
                title="1-Click Auto Demo: SDE Profile"
              >
                ⚡ 1-Click: SDE ₹24L (80C+80D+NPS)
              </button>
              <button
                onClick={() => sendMessage("I run a retail business with 18 lakhs net profit. I have 1.5 lakhs in PPF and senior citizen parents.")}
                style={{
                  fontSize: '0.72rem',
                  padding: '0.25rem 0.65rem',
                  borderRadius: '16px',
                  background: 'rgba(16,185,129,0.15)',
                  border: '1px solid rgba(16,185,129,0.35)',
                  color: 'var(--accent-green)',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  fontWeight: 600,
                  transition: 'all 0.2s',
                }}
                title="1-Click Auto Demo: Business Profile"
              >
                ⚡ 1-Click: Trader ₹18L (Business+Parents)
              </button>
            </>
          )}

          {currentSuggestions.map((sug, i) => (
            <button
              key={i}
              onClick={() => sendMessage(sug)}
              style={{
                fontSize: '0.72rem',
                padding: '0.25rem 0.65rem',
                borderRadius: '16px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid var(--border)',
                color: 'var(--text-sub)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--primary)';
                e.currentTarget.style.color = 'var(--text-main)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.color = 'var(--text-sub)';
              }}
            >
              + {sug}
            </button>
          ))}
        </div>
      )}

      {/* ── Input Box ── */}
      <div className="chat-input-area">
        <div className="input-wrapper">
          <input
            ref={inputRef}
            className="chat-input"
            type="text"
            placeholder={isTyping ? 'Consultant is analyzing your inputs...' : 'Type details e.g. "I earn 12L and invest 1.5L in PPF"...'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            disabled={isTyping}
          />
          <button
            className="send-btn"
            onClick={() => sendMessage()}
            disabled={isTyping || !input.trim()}
            title="Send message"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
        <div className="input-hint">
          Pro-tip: Type <code style={{ color: 'var(--accent-amber)' }}>/end</code> anytime to force-generate the final calculation report.
        </div>
      </div>
    </>
  );
}

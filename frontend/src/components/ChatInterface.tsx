'use client';

import React, { useState, useEffect, useRef } from 'react';

interface Message {
  role: 'ai' | 'user';
  text: string;
}

interface ChatInterfaceProps {
  onUpdateSession: (session: any) => void;
  onShowReport: (show: boolean) => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ onUpdateSession, onShowReport }) => {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', text: "Namaste! I am your personal AI tax companion. To help you save the most on your taxes, could you tell me a bit about what you do? For instance, are you in a job, running a business, or perhaps a professional?" }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [session, setSession] = useState<any>({ 
    id: `sid_${Date.now()}`, 
    phase: "PROFILING" 
  });
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const chatRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    if (chatRef.current) {
      chatRef.current.scrollTo({
        top: chatRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  };

  useEffect(() => {
    scrollToBottom();
    // Focus input when messages update or isTyping finishes
    if (!isTyping) {
      inputRef.current?.focus();
    }
  }, [messages, isTyping]);

  const handleScroll = () => {
    if (chatRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = chatRef.current;
      // Show button if we are more than 100px away from bottom
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
      setShowScrollButton(!isAtBottom);
    }
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMsg = { role: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, session })
      });
      
      if (!res.ok) throw new Error(`Server responded with ${res.status}`);
      
      const data = await res.json();
      
      setSession(data.session);
      onUpdateSession(data.session);
      
      // Artificial delay for premium feel
      setTimeout(() => {
        setIsTyping(false);
        setMessages(prev => [...prev, { role: 'ai', text: data.response }]);
      }, 600);

      if (data.session.phase === "FINAL") {
        onShowReport(true);
      }
    } catch (error) {
      console.error("Chat Error:", error);
      setIsTyping(false);
      setMessages(prev => [...prev, { role: 'ai', text: "Service temporarily unavailable. Please ensure the AI backend is running on port 8000." }]);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch(`http://localhost:8000/history/${session.id}`);
      const data = await res.json();
      setHistory(data);
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    if (showDebug) fetchHistory();
  }, [showDebug, messages]);

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100%', 
      gap: '1.5rem', 
      position: 'relative',
      padding: '2rem'
    }}>
      {/* Header with Debug Toggle */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>AI Consultant</h3>
        <button 
          onClick={() => setShowDebug(!showDebug)}
          className="btn-icon" 
          style={{ width: 'auto', height: 'auto', padding: '0.4rem 0.8rem', fontSize: '0.7rem', gap: '0.4rem' }}
        >
          <span style={{ fontSize: '0.9rem' }}>🔍</span> {showDebug ? "Hide State" : "Debug State"}
        </button>
      </div>

      {/* Debug Panel (Conditional) */}
      {showDebug && (
        <div className="premium-card" style={{ 
          background: 'rgba(5, 5, 8, 0.95)', 
          borderColor: 'var(--accent-blue)', 
          maxHeight: '300px', 
          overflowY: 'auto',
          fontSize: '0.75rem',
          zIndex: 50
        }}>
          <h4 style={{ color: 'var(--accent-blue)', marginBottom: '0.75rem' }}>Current Session Parameters</h4>
          <pre style={{ color: '#4ade80', marginBottom: '1.5rem' }}>{JSON.stringify(session, null, 2)}</pre>
          
          <h4 style={{ color: 'var(--accent-blue)', marginBottom: '0.75rem' }}>Audit Trail (Internal Reasoning)</h4>
          {history.length === 0 ? <p style={{ color: 'var(--text-muted)' }}>No audit logs yet.</p> : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {history.map((h, i) => (
                <div key={i} style={{ padding: '0.5rem', borderLeft: '2px solid var(--border)', background: 'var(--bg-accent)' }}>
                  <p style={{ color: 'var(--text-main)', marginBottom: '0.2rem' }}>U: {h.user_input}</p>
                  <p style={{ color: 'var(--text-dim)' }}>AI: {h.ai_response}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Progress Stepper */}
      <div style={{ display: 'flex', gap: '0.75rem' }}>
        {["PROFILING", "INCOME", "EXPENDITURE", "RECALL", "FINAL"].map((p, i) => (
          <div key={p} style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ 
              height: '3px', 
              background: session.phase === p ? 'var(--primary)' : 'var(--bg-accent)',
              borderRadius: '2px',
              boxShadow: session.phase === p ? '0 0 10px var(--primary-glow)' : 'none',
              transition: 'all 0.5s'
            }} />
            <span style={{ 
              fontSize: '0.6rem', 
              fontWeight: 700, 
              color: session.phase === p ? 'var(--text-main)' : 'var(--text-muted)',
              textAlign: 'center',
              letterSpacing: '0.05em'
            }}>{p}</span>
          </div>
        ))}
      </div>
      
      {/* Messages Area */}
      <div 
        className="chat-history" 
        ref={chatRef}
        onScroll={handleScroll}
      >
        {messages.map((msg, i) => (
          <div key={i} className={`message-bubble ${msg.role}`}>
            {msg.text}
          </div>
        ))}
        {isTyping && (
          <div className="message-bubble ai" style={{ display: 'flex', gap: '4px', padding: '0.75rem 1rem' }}>
            <div className="glow-dot blue" style={{ width: '4px', height: '4px', margin: 0, animation: 'pulse-slow 1s infinite' }} />
            <div className="glow-dot blue" style={{ width: '4px', height: '4px', margin: 0, animation: 'pulse-slow 1s infinite 0.2s' }} />
            <div className="glow-dot blue" style={{ width: '4px', height: '4px', margin: 0, animation: 'pulse-slow 1s infinite 0.4s' }} />
          </div>
        )}
      </div>

      {/* Floating Scroll Button */}
      {showScrollButton && (
        <button 
          onClick={scrollToBottom}
          className="scroll-bottom-btn"
          aria-label="Scroll to bottom"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7 13l5 5 5-5M7 6l5 5 5-5" />
          </svg>
        </button>
      )}

      {/* Modern Input */}
      <div className="chat-input-wrapper">
        <input 
          ref={inputRef}
          className="chat-input"
          type="text" 
          placeholder={isTyping ? "AI is thinking..." : "Type your response..."} 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          disabled={isTyping}
        />
        <button 
          className="btn-primary" 
          onClick={sendMessage}
          disabled={isTyping || !input.trim()}
          style={{ 
            padding: '0.5rem 1.25rem', 
            borderRadius: '14px',
            opacity: (isTyping || !input.trim()) ? 0.6 : 1,
            cursor: (isTyping || !input.trim()) ? 'not-allowed' : 'pointer'
          }}
        >
          {isTyping ? 'Thinking...' : 'Send'}
          {!isTyping && (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          )}
        </button>
      </div>
    </div>
  );
};

export default ChatInterface;

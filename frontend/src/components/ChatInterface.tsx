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
    { role: 'ai', text: "Namaste! I am your Deep AI Tax Consultant. I don't just calculate - I analyze and discover. To begin, what was your total income last year, and what do you do for a living?" }
  ]);
  const [input, setInput] = useState('');
  const [session, setSession] = useState<any>({ phase: "PROFILING" });
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMsg = { role: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');

    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, session })
      });
      const data = await res.json();
      
      setSession(data.session);
      onUpdateSession(data.session);
      
      setMessages(prev => [...prev, { role: 'ai', text: data.response }]);

      if (data.session.phase === "FINAL") {
        onShowReport(true);
      }
    } catch (error) {
      setMessages(prev => [...prev, { role: 'ai', text: "Error connecting to AI backend." }]);
    }
  };

  return (
    <div className="glass-card">
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        {["PROFILING", "INCOME", "EXPENDITURE", "RECALL", "FINAL"].map((p, i) => (
          <div key={p} style={{ 
            height: '4px', 
            flex: 1, 
            background: session.phase === p ? 'var(--accent-saffron)' : 'rgba(255,255,255,0.1)',
            borderRadius: '2px',
            transition: 'background 0.3s'
          }} />
        ))}
      </div>
      
      <div className="chat-container" ref={chatRef}>
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.text}
          </div>
        ))}
      </div>
      <div className="input-area">
        <input 
          type="text" 
          placeholder="Answer or ask a question..." 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
        />
        <button onClick={sendMessage}>Consult AI</button>
      </div>
    </div>
  );
};

export default ChatInterface;

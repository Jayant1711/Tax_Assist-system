'use client';

import React, { useEffect, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch, onUnauthorized } from '@/lib/api';

/**
 * Sign-in / registration (Sprint 3 Objective E, design §6).
 *
 * Unauthenticated users land here via the client-side redirect wired in
 * page.tsx (apiFetch 401 hook). On success the flow verifies the session
 * cookie (GET /auth/me), bootstraps the server-side consultation session
 * (POST /sessions) and hands over to the app. Server messages (uniform
 * 401 copy, lockout, password policy) are surfaced verbatim.
 */
type Mode = 'login' | 'register';

async function extractServerMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (data && typeof data.detail === 'string') return data.detail;
  } catch {
    // Non-JSON error body — fall through to the generic copy.
  }
  return `Request failed (HTTP ${res.status})`;
}

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A 401 while already on /login (e.g. a rejected login) must not loop.
  useEffect(() => {
    onUnauthorized(() => router.push('/login'));
  }, [router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      if (mode === 'register') {
        const registerRes = await apiFetch('/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        if (!registerRes.ok) throw new Error(await extractServerMessage(registerRes));
        // Registration does not issue a session cookie — fall through to
        // login with the credentials just created.
      }
      const loginRes = await apiFetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!loginRes.ok) throw new Error(await extractServerMessage(loginRes));

      // Cookie is in the jar: verify it, then bootstrap the consultation
      // session so the app shell opens ready to chat.
      const meRes = await apiFetch('/auth/me');
      if (!meRes.ok) {
        throw new Error('Signed in, but the session could not be verified. Please try again.');
      }
      const sessionRes = await apiFetch('/sessions', { method: 'POST' });
      if (!sessionRes.ok) {
        throw new Error('Signed in, but the consultation session could not be started. Please try again.');
      }
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.25rem',
      }}
    >
      <div className="card" style={{ width: 'min(100%, 420px)', padding: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <div className="logo-icon">T</div>
          <div>
            <div className="logo-text">
              TaxAssist <span>AI</span>
            </div>
            <div className="logo-sub">Deep Consultant · FY 24-25</div>
          </div>
        </div>

        <h1 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)', marginBottom: '0.35rem' }}>
          {mode === 'login' ? 'Welcome back' : 'Create your account'}
        </h1>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
          {mode === 'login'
            ? 'Sign in to continue your tax consultation.'
            : 'Register to start your guided, server-side tax session.'}
        </p>

        {/* Mode toggle */}
        <div
          role="tablist"
          aria-label="Authentication mode"
          style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem' }}
        >
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            className={`btn btn-sm ${mode === 'login' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ flex: 1, justifyContent: 'center' }}
            onClick={() => {
              setMode('login');
              setError(null);
            }}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'register'}
            className={`btn btn-sm ${mode === 'register' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ flex: 1, justifyContent: 'center' }}
            onClick={() => {
              setMode('register');
              setError(null);
            }}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div style={{ marginBottom: '0.9rem' }}>
            <label
              htmlFor="login-email"
              style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.3rem' }}
            >
              Email
            </label>
            <input
              id="login-email"
              className="chat-input"
              style={{
                width: '100%',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.55rem 0.75rem',
              }}
              type="email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={busy}
              aria-invalid={!!error}
            />
          </div>

          <div style={{ marginBottom: '1.1rem' }}>
            <label
              htmlFor="login-password"
              style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.3rem' }}
            >
              Password
            </label>
            <input
              id="login-password"
              className="chat-input"
              style={{
                width: '100%',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.55rem 0.75rem',
              }}
              type="password"
              name="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
              minLength={mode === 'register' ? 12 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
              aria-invalid={!!error}
              aria-describedby={mode === 'register' ? 'password-policy' : undefined}
            />
            {mode === 'register' && (
              <div id="password-policy" style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                12–1024 characters (NIST 800-63B length policy).
              </div>
            )}
          </div>

          {error && (
            <div
              role="alert"
              style={{
                background: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--accent-red)',
                fontSize: '0.8rem',
                fontWeight: 600,
                padding: '0.6rem 0.75rem',
                marginBottom: '1rem',
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center', padding: '0.6rem' }}
            disabled={busy}
          >
            {busy
              ? mode === 'register'
                ? 'Creating account…'
                : 'Signing in…'
              : mode === 'register'
                ? 'Create account & continue'
                : 'Sign in & continue'}
          </button>
        </form>
      </div>
    </main>
  );
}

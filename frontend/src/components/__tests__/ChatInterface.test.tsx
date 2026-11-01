/**
 * ChatInterface unit tests (Sprint 3 Objective E, design §6).
 * Contract regression: /chat is called with {message, session_id} (never a
 * session dict), the server projection is applied, errors degrade to an
 * in-chat bubble, and Reset re-bootstraps via POST /sessions.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ChatInterface from '../ChatInterface';

const apiFetchMock = vi.fn();

// Path is relative to THIS file (__tests__/): ../../lib/api -> src/lib/api.
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}));

const CHAT_RESPONSE = {
  response: 'Got it — income recorded.',
  session_id: 'sess_1',
  session: { id: 'sess_1', phase: 'INCOME', salary: 2400000 },
  extracted: ['salary: 2400000'],
  plan: null,
  tax_report: null,
};

const BOOTSTRAP_RESPONSE = {
  session_id: 'sess_9',
  session: { id: 'sess_9', phase: 'PROFILING' },
};

function jsonResponse(data: unknown): Response {
  return { ok: true, status: 200, json: async () => data } as unknown as Response;
}

function renderChat(
  onUpdateSession = vi.fn(),
  onShowReport = vi.fn(),
  sessionId = 'sess_1'
) {
  render(
    <ChatInterface
      sessionId={sessionId}
      onUpdateSession={onUpdateSession}
      onShowReport={onShowReport}
    />
  );
  return { onUpdateSession, onShowReport };
}

function typeAndSend(text: string) {
  const input = screen.getByRole('textbox');
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: /send/i }));
}

describe('ChatInterface', () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue(jsonResponse(CHAT_RESPONSE));
  });

  it('sends {message, session_id} to /chat — never a session dict', async () => {
    renderChat();

    typeAndSend('I earn 24 LPA');

    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1));
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/chat',
      expect.objectContaining({ method: 'POST' })
    );
    const init = apiFetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(init.body));
    expect(body).toEqual({ message: 'I earn 24 LPA', session_id: 'sess_1' });
    expect(body).not.toHaveProperty('session');
  });

  it('applies the server projection and notifies the parent with the session id', async () => {
    const { onUpdateSession } = renderChat();

    typeAndSend('I earn 24 LPA');

    await waitFor(() =>
      expect(onUpdateSession).toHaveBeenCalledWith(CHAT_RESPONSE.session, 'sess_1')
    );
    // The AI reply eventually lands in the transcript (typing delay elapses).
    expect(await screen.findByText(/income recorded/i)).toBeInTheDocument();
  });

  it('degrades to an in-chat error bubble when /chat fails', async () => {
    apiFetchMock.mockRejectedValue(new Error('network down'));
    const { onUpdateSession } = renderChat();

    typeAndSend('hello');

    expect(
      await screen.findByText(/Unable to reach the calculation service/i)
    ).toBeInTheDocument();
    expect(onUpdateSession).not.toHaveBeenCalled();
  });

  it('re-bootstraps a fresh server session on Reset', async () => {
    apiFetchMock.mockResolvedValue(jsonResponse(BOOTSTRAP_RESPONSE));
    const { onUpdateSession } = renderChat();

    fireEvent.click(screen.getByRole('button', { name: /reset/i }));

    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1));
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/sessions',
      expect.objectContaining({ method: 'POST' })
    );
    expect(onUpdateSession).toHaveBeenCalledWith(BOOTSTRAP_RESPONSE.session, 'sess_9');
    expect(await screen.findByText(/New consultation started/i)).toBeInTheDocument();
  });

  it('renders the phase stepper and quick suggestions', () => {
    renderChat();

    expect(screen.getByText('1. PROFILE')).toBeInTheDocument();
    // The header title (distinct from the welcome bubble's <strong>).
    expect(document.querySelector('.chat-title')).toHaveTextContent('AI Tax Consultant');
    expect(screen.getByRole('button', { name: /1-Click: SDE/i })).toBeInTheDocument();
  });
});

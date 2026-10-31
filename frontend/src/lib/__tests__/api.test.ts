/**
 * api.ts contract tests (Sprint 3 Objective E, design §6):
 * BASE resolution from NEXT_PUBLIC_API_URL, forced credentials:"include",
 * and the central 401 → onUnauthorized hook.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const fetchMock = vi.fn();

// api.ts reads NEXT_PUBLIC_API_URL at module load, so every scenario
// re-imports it with vi.resetModules() under the desired env.
async function loadApi(envUrl?: string) {
  vi.resetModules();
  if (envUrl === undefined) {
    delete process.env.NEXT_PUBLIC_API_URL;
  } else {
    process.env.NEXT_PUBLIC_API_URL = envUrl;
  }
  return import('../api');
}

describe('api.ts', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  it('resolves BASE from NEXT_PUBLIC_API_URL when set', async () => {
    const { apiFetch } = await loadApi('http://api.test:8000');
    fetchMock.mockResolvedValue({ ok: true, status: 200 } as Response);

    await apiFetch('/chat');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe('http://api.test:8000/chat');
  });

  it('defaults BASE to "" (same-origin) when the env var is unset', async () => {
    const { apiFetch } = await loadApi(undefined);
    fetchMock.mockResolvedValue({ ok: true, status: 200 } as Response);

    await apiFetch('/health');

    expect(fetchMock.mock.calls[0][0]).toBe('/health');
  });

  it('always injects credentials:"include" (HttpOnly session cookie rides along)', async () => {
    const { apiFetch } = await loadApi(undefined);
    fetchMock.mockResolvedValue({ ok: true, status: 200 } as Response);

    await apiFetch('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe('include');
    expect(init.method).toBe('POST');
    // The caller's init is preserved, not replaced.
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' });
  });

  it('fires the onUnauthorized handler exactly once on a 401 and still returns the response', async () => {
    const { apiFetch, onUnauthorized } = await loadApi(undefined);
    const handler = vi.fn();
    onUnauthorized(handler);
    fetchMock.mockResolvedValue({ ok: false, status: 401 } as Response);

    const res = await apiFetch('/chat');

    expect((res as unknown as { status: number }).status).toBe(401);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('leaves the handler untouched on non-401 responses', async () => {
    const { apiFetch, onUnauthorized } = await loadApi(undefined);
    const handler = vi.fn();
    onUnauthorized(handler);
    fetchMock.mockResolvedValue({ ok: true, status: 200 } as Response);

    await apiFetch('/health');

    expect(handler).not.toHaveBeenCalled();
  });
});

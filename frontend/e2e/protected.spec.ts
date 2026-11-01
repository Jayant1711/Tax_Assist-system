/**
 * Protected-endpoint E2E — Sprint 3 Wave G (design §6 "protected.spec").
 *
 * Fresh Playwright contexts carry no session cookie, so page.request is an
 * unauthenticated client: /chat and /history must answer 401 while /health
 * stays public.
 */
import { randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';
import { API_URL } from './helpers';

test.describe('protected endpoints (unauthenticated)', () => {
  test('POST /chat -> 401', async ({ page }) => {
    const res = await page.request.post(`${API_URL}/chat`, {
      data: { message: 'e2e protection probe', session_id: randomUUID() },
    });
    expect(res.status()).toBe(401);
  });

  test('GET /history/<uuid> -> 401', async ({ page }) => {
    const res = await page.request.get(`${API_URL}/history/${randomUUID()}`);
    expect(res.status()).toBe(401);
  });

  test('GET /health -> 200 ok', async ({ page }) => {
    const res = await page.request.get(`${API_URL}/health`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe('ok');
  });
});

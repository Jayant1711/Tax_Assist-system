/**
 * Server-side session contract E2E — Sprint 3 Wave G (design §6
 * "session.spec": Sprint-2 journey via {session_id}).
 *
 * The wire-contract assertion is the Sprint 3 acceptance requirement: the
 * /chat request payload must contain the server-issued session_id and must
 * NEVER contain a `session` key (the full state lives server-side,
 * ADR-013) — asserted on the actual browser request via page.on('request').
 */
import { expect, test } from '@playwright/test';
import { API_URL, E2E_PASSWORD, SESSION_ID_RE, uniqueEmail } from './helpers';

test('1-click SDE demo: /chat payload carries session_id and no session key; statement/report and regime comparison render', async ({
  page,
}) => {
  const email = uniqueEmail();
  const registerRes = await page.request.post(`${API_URL}/auth/register`, {
    data: { email, password: E2E_PASSWORD },
  });
  expect(registerRes.status()).toBe(201);

  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Sign in & continue' }).click();
  await page.waitForURL(/^http:\/\/localhost:3000\/$/);

  const input = page.getByRole('textbox', { name: 'Message the tax consultant' });
  await expect(input).toBeVisible();

  // Wire-contract capture (registered BEFORE the click, races nothing).
  const chatRequestPromise = page.waitForRequest(
    (r) => r.url().endsWith('/chat') && r.method() === 'POST',
  );
  const chatResponsePromise = page.waitForResponse(
    (r) => r.url().endsWith('/chat') && r.request().method() === 'POST' && r.status() === 200,
  );

  // -- 1-click SDE demo chip ---------------------------------------------
  await page.getByRole('button', { name: /1-Click: SDE/ }).click();

  const chatRequest = await chatRequestPromise;
  const payload = chatRequest.postDataJSON();
  expect(payload.message).toContain('software engineer');
  expect(payload.session_id).toMatch(SESSION_ID_RE); // server-issued id addresses the state
  expect(payload).not.toHaveProperty('session'); // full state never travels

  const chatResponse = await chatResponsePromise;
  expect(chatResponse.status()).toBe(200);
  const chatBody = await chatResponse.json();
  expect(chatBody.session_id).toMatch(SESSION_ID_RE);
  expect(chatBody.session).toBeDefined(); // read-only projection rides along
  expect(Number(chatBody.session?.salary)).toBeGreaterThan(0);

  // -- Statement / report renders ------------------------------------------
  await expect(page.getByText('Tax Assessment & Optimization Report')).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText('Statement of Total Income (Form ITR Format)')).toBeVisible();

  // -- Regime comparison visible -------------------------------------------
  await expect(page.getByText('Regime Tax Comparison')).toBeVisible();
});

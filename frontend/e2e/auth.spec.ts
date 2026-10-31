/**
 * Auth journey E2E — Sprint 3 Wave G (design §6 "auth.spec" +
 * Playwright-MCP acceptance protocol: register -> app -> chat -> report ->
 * sign out -> /login redirect; uniform 401 copy).
 *
 * Every test self-creates its user (unique Date.now()/uuid email) so the
 * file is retry- and parallel-safe on a throwaway backend DB.
 */
import { expect, test } from '@playwright/test';
import { API_URL, E2E_PASSWORD, uniqueEmail } from './helpers';

test.describe('auth journey', () => {
  test('register lands on the app (not /login), first chat turn books income, report renders, sign out redirects root to /login', async ({
    page,
  }) => {
    const email = uniqueEmail();

    // -- Register (login page ships in Register mode after the toggle) ----
    await page.goto('/login');
    await page.getByRole('tab', { name: 'Register' }).click();
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill(E2E_PASSWORD);
    await page.getByRole('button', { name: 'Create account & continue' }).click();

    // Registration auto-signs-in and hands over to the app shell — never /login.
    await page.waitForURL(/^http:\/\/localhost:3000\/$/);
    await expect(page).toHaveURL(/^http:\/\/localhost:3000\/$/);
    await expect(page.getByRole('button', { name: /Sign out/ })).toBeVisible();

    // -- First chat turn books income -------------------------------------
    const input = page.getByRole('textbox', { name: 'Message the tax consultant' });
    await expect(input).toBeVisible();

    const chatResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith('/chat') && r.request().method() === 'POST',
    );
    await input.fill('I earn 12 lakhs');
    await input.press('Enter');

    const chatResponse = await chatResponsePromise;
    expect(chatResponse.status()).toBe(200);
    const chatBody = await chatResponse.json();
    expect(chatBody.session_id).toBeTruthy();
    expect(Number(chatBody.session?.salary)).toBeGreaterThan(0); // income booked

    // -- Report panel renders ----------------------------------------------
    await expect(page.getByText('Real-Time Tax Audit')).toBeVisible();
    await expect(page.getByText('Awaiting Financial Discovery')).toBeHidden();
    await expect(page.getByText('Tax Assessment & Optimization Report')).toBeVisible({
      timeout: 20_000,
    });

    // -- Sign out -> /login; root now redirects there ----------------------
    await page.getByRole('button', { name: /Sign out/ }).click();
    await page.waitForURL(/\/login$/);
    await expect(page).toHaveURL(/\/login$/);

    await page.goto('/');
    await page.waitForURL(/\/login$/);
    await expect(page).toHaveURL(/\/login$/);
  });

  test('wrong password shows the uniform error (identical copy for an unknown email)', async ({
    page,
  }) => {
    const email = uniqueEmail();
    const registerRes = await page.request.post(`${API_URL}/auth/register`, {
      data: { email, password: E2E_PASSWORD },
    });
    expect(registerRes.status()).toBe(201);

    await page.goto('/login');
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill('definitely-not-the-password');
    await page.getByRole('button', { name: 'Sign in & continue' }).click();
    // Scoped to <main>: Next injects a document-level role="alert" announcer.
    await expect(page.locator('main').getByRole('alert')).toHaveText('Invalid email or password');

    // Uniformity (anti-enumeration): an unknown email yields the SAME copy.
    await page.getByLabel('Email').fill(uniqueEmail());
    await page.getByLabel('Password').fill('definitely-not-the-password');
    await page.getByRole('button', { name: 'Sign in & continue' }).click();
    await expect(page.locator('main').getByRole('alert')).toHaveText('Invalid email or password');
  });

  test('login with the created credentials reaches the app', async ({ page }) => {
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
    await expect(page).toHaveURL(/^http:\/\/localhost:3000\/$/);
    await expect(page.getByRole('button', { name: /Sign out/ })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Message the tax consultant' })).toBeVisible();
  });
});

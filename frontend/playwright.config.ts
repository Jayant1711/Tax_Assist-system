/**
 * Playwright E2E config — Sprint 3 Wave G (design §6, Objective E).
 *
 * - chromium-only project, 1 retry, trace retained on failure;
 * - baseURL http://localhost:3000 (the frontend `next start` server);
 * - webServer entries (a) `next start` on :3000 reusing the existing build
 *   and (b) uvicorn on :8000 with a TEMP TAX_DB_PATH + APP_ENV=dev +
 *   CORS_ORIGINS=http://localhost:3000, waited on via GET /health 200.
 *
 * Both entries carry `reuseExistingServer: true` because
 * e2e/global-setup.ts (Playwright globalSetup) starts and health-waits the
 * SAME two processes first — whichever mechanism comes up first wins and
 * the other becomes a no-op. That keeps the config self-sufficient while
 * the global-setup file owns the /health wait and deterministic cleanup.
 *
 * The frontend must be BUILT with NEXT_PUBLIC_API_URL=http://localhost:8000
 * so the browser reaches the backend cross-origin (the backend allowlists
 * http://localhost:3000 with credentials — see design §4).
 */
import { defineConfig, devices } from '@playwright/test';
import {
  BACKEND_DIR,
  BACKEND_HEALTH_URL,
  FRONTEND_DIR,
  FRONTEND_PROBE_URL,
  backendEnv,
} from './e2e/global-setup';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: [
    {
      // (a) Frontend: serve the existing production build on :3000.
      command: 'npm run start',
      cwd: FRONTEND_DIR,
      url: FRONTEND_PROBE_URL,
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      // (b) Backend: uvicorn on :8000 with a TEMP TAX_DB_PATH (see
      // e2e/global-setup.ts for the full env contract).
      command: 'python -m uvicorn main:app --port 8000',
      cwd: BACKEND_DIR,
      env: backendEnv(),
      url: BACKEND_HEALTH_URL,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});

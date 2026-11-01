/**
 * Playwright global setup — Sprint 3 Wave G (design §6, Objective E).
 *
 * Starts and owns BOTH processes the E2E suite needs, waits until each is
 * healthy, and (via global-teardown) stops them and cleans up:
 *
 *   (a) frontend — `npm run start` (next start) on http://localhost:3000,
 *       reusing the existing production build (`next build` must have run);
 *   (b) backend  — `python -m uvicorn main:app --port 8000` from the
 *       backend directory with a TEMP `TAX_DB_PATH` (a throwaway SQLite
 *       store wiped at the start of every run and deleted on teardown),
 *       `APP_ENV=dev` and `CORS_ORIGINS=http://localhost:3000`.
 *
 * Readiness: the backend is polled via GET /health until 200, the frontend
 * via GET / until 200. Node-side probes target 127.0.0.1 explicitly so a
 * `localhost` -> ::1 resolution fork cannot stall the wait.
 *
 * playwright.config.ts also declares `webServer` entries with the same
 * commands, env and readiness URLs plus `reuseExistingServer: true`, so
 * whichever mechanism comes up first wins and the other is a no-op. The
 * config's entries keep the config self-sufficient; this file guarantees
 * the health wait and deterministic cleanup even on Windows.
 *
 * Shared constants (ports, URLs, TEMP DB path, backend env) are exported
 * so the config's fallback webServer entries address the SAME temp DB and
 * the SAME CORS posture as this file.
 */
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';

// --- Shared topology (imported by playwright.config.ts) ---------------------

export const FRONTEND_PORT = 3000;
export const BACKEND_PORT = 8000;

/** The URL the browser talks to (matches NEXT_PUBLIC_API_URL and CORS). */
export const FRONTEND_URL = `http://localhost:${FRONTEND_PORT}`;
export const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

/** Node-side probe URLs: 127.0.0.1 avoids a localhost/::1 resolution fork. */
export const FRONTEND_PROBE_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
export const BACKEND_HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/health`;

export const REPO_ROOT = path.resolve(__dirname, '..', '..');
export const BACKEND_DIR = path.join(REPO_ROOT, 'backend');
export const FRONTEND_DIR = path.join(REPO_ROOT, 'frontend');

/**
 * Throwaway SQLite store for the E2E backend. Deterministic (no state must
 * travel between processes) and wiped at the start of every run we own.
 */
export const E2E_DB_DIR = path.join(os.tmpdir(), 'taxassist-e2e');
export const E2E_DB_PATH = path.join(E2E_DB_DIR, 'e2e.db');

/**
 * Environment for the E2E backend (shared by this file and the config's
 * fallback webServer entry). `db.py` runs idempotent migrations at import,
 * so an empty temp file/path is sufficient — the store bootstraps itself.
 *
 * TAX_RATE_LIMIT_AUTH_PER_MIN is raised because the functional journey
 * makes >10 /auth/* calls per minute across tests; rate-limit behavior is
 * covered by the backend unit suite, not by E2E (avoiding artificial 429s).
 */
export function backendEnv(): Record<string, string> {
  const env: Record<string, string> = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (value !== undefined) env[key] = value;
  }
  env.TAX_DB_PATH = E2E_DB_PATH;
  env.APP_ENV = 'dev';
  env.CORS_ORIGINS = 'http://localhost:3000';
  env.TAX_RATE_LIMIT_AUTH_PER_MIN = '100';
  return env;
}

// --- Process registry and lifecycle -----------------------------------------

const children: ChildProcess[] = [];
const outputTails = new Map<string, string[]>();
let stopping = false;

const LOG_TAIL_LINES = 60;

function track(name: string, child: ChildProcess): void {
  children.push(child);
  const tail: string[] = [];
  outputTails.set(name, tail);
  const collect = (chunk: Buffer): void => {
    tail.push(chunk.toString('utf8'));
    if (tail.length > LOG_TAIL_LINES) tail.shift();
  };
  child.stdout?.on('data', collect);
  child.stderr?.on('data', collect);
  child.once('close', (code, signal) => {
    if (!stopping && code !== 0) {
      console.error(
        `[e2e-global-setup] ${name} exited early (code=${code} signal=${signal}):\n` +
          (tail.join('') || '<no output>'),
      );
    }
  });
}

function killAllSync(): void {
  for (const child of children) {
    if (child.pid == null || child.exitCode != null || child.signalCode != null) continue;
    if (process.platform === 'win32') {
      // /T takes the whole tree (npm/cmd wrappers), /F is immediate.
      spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    } else {
      try {
        process.kill(-child.pid, 'SIGTERM'); // detached group
      } catch {
        child.kill('SIGTERM');
      }
    }
  }
}

/** Stop every server this file started; resolves when they are gone. */
export async function stopE2EServers(): Promise<void> {
  stopping = true;
  const list = children.splice(0, children.length);
  killAllSync();
  const deadline = Date.now() + 10_000;
  for (const child of list) {
    const remaining = Math.max(0, deadline - Date.now());
    await Promise.race([
      new Promise<void>((resolve) => {
        if (child.exitCode != null || child.signalCode != null) return resolve();
        child.once('close', () => resolve());
      }),
      new Promise<void>((resolve) => {
        const t = setTimeout(resolve, remaining);
        if (typeof t.unref === 'function') t.unref();
      }),
    ]);
    if (child.exitCode == null && child.signalCode == null && process.platform !== 'win32' && child.pid != null) {
      try {
        process.kill(-child.pid, 'SIGKILL');
      } catch {
        // already gone
      }
    }
  }
}

/** Delete the throwaway SQLite store (best-effort; the next run re-wipes). */
export function cleanupTempDb(): void {
  try {
    fs.rmSync(E2E_DB_DIR, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 });
  } catch (err) {
    console.warn(`[e2e-global-setup] could not remove temp DB dir ${E2E_DB_DIR}: ${err}`);
  }
}

// --- Probes and spawning -----------------------------------------------------

function probe(url: string, timeoutMs = 2000): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      res.resume(); // drain so the socket is released
      const status = res.statusCode ?? 500;
      resolve(status >= 200 && status < 300);
    });
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
    req.on('error', () => resolve(false));
  });
}

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForHealthy(url: string, label: string, timeoutMs = 120_000): Promise<void> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await probe(url)) {
      console.log(
        `[e2e-global-setup] ${label} ready at ${url} (${Math.round((Date.now() - startedAt) / 1000)}s)`,
      );
      return;
    }
    await sleep(500);
  }
  throw new Error(
    `[e2e-global-setup] ${label} at ${url} not healthy within ${timeoutMs}ms\n` +
      [...outputTails.entries()].map(([name, tail]) => `--- ${name} ---\n${tail.join('')}`).join('\n'),
  );
}

function startBackend(): void {
  console.log(
    `[e2e-global-setup] starting backend: python -m uvicorn main:app --port ${BACKEND_PORT} ` +
      `(cwd=${BACKEND_DIR}, TAX_DB_PATH=${E2E_DB_PATH})`,
  );
  const child = spawn(
    'python',
    ['-m', 'uvicorn', 'main:app', '--port', String(BACKEND_PORT)],
    {
      cwd: BACKEND_DIR,
      // Object.assign keeps the spawn env typed as ProcessEnv while layering
      // the E2E overrides from backendEnv() (shared with playwright.config).
      env: Object.assign({}, process.env, backendEnv()),
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: process.platform !== 'win32',
    },
  );
  track('backend', child);
}

function startFrontend(): void {
  console.log(`[e2e-global-setup] starting frontend: npm run start (cwd=${FRONTEND_DIR})`);
  const child = spawn(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'start'], {
    cwd: FRONTEND_DIR,
    env: process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: process.platform === 'win32',
    detached: process.platform !== 'win32',
  });
  track('frontend', child);
}

function registerExitHooks(): void {
  const bail = (): void => {
    killAllSync();
    cleanupTempDb();
  };
  process.once('exit', bail);
  process.once('SIGINT', () => {
    bail();
    process.exit(130);
  });
  process.once('SIGTERM', () => {
    bail();
    process.exit(143);
  });
}

// --- Playwright globalSetup entry --------------------------------------------

/**
 * Prepare the throwaway DB, start whichever servers are not already up
 * (idempotent: externally started servers — e.g. by the config's webServer
 * entries — are detected and reused), and wait for /health 200 + / 200.
 */
export default async function globalSetup(): Promise<void> {
  try {
    const backendUp = await probe(BACKEND_HEALTH_URL);
    if (!backendUp) {
      // We own the backend lifecycle: give it a fresh throwaway store.
      fs.rmSync(E2E_DB_DIR, { recursive: true, force: true });
      fs.mkdirSync(E2E_DB_DIR, { recursive: true });
      startBackend();
      await waitForHealthy(BACKEND_HEALTH_URL, 'backend /health');
    } else {
      console.log('[e2e-global-setup] backend already serving on :8000 — reusing');
    }

    if (!(await probe(FRONTEND_PROBE_URL))) {
      startFrontend();
    } else {
      console.log('[e2e-global-setup] frontend already serving on :3000 — reusing');
    }
    await waitForHealthy(FRONTEND_PROBE_URL, 'frontend /');

    registerExitHooks();
    console.log('[e2e-global-setup] both servers ready — starting test suite');
  } catch (err) {
    console.error(
      [...outputTails.entries()].map(([name, tail]) => `--- ${name} tail ---\n${tail.join('')}`).join('\n'),
    );
    await stopE2EServers();
    cleanupTempDb();
    throw err;
  }
}

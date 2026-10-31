/**
 * Playwright global teardown — Sprint 3 Wave G (design §6).
 *
 * Stops the servers started by e2e/global-setup.ts and deletes the
 * throwaway SQLite store. Both steps are best-effort and idempotent: the
 * exit hooks registered in global-setup cover abnormal termination, and
 * servers started by the config's fallback webServer entries are killed by
 * Playwright itself after teardown.
 */
import { cleanupTempDb, stopE2EServers } from './global-setup';

export default async function globalTeardown(): Promise<void> {
  await stopE2EServers();
  cleanupTempDb();
  console.log('[e2e-global-setup] teardown complete (servers stopped, temp DB removed)');
}

/**
 * Shared E2E helpers — Sprint 3 Wave G.
 *
 * API_URL MUST match NEXT_PUBLIC_API_URL baked into the production build
 * (see playwright.config.ts header): the browser reaches the backend on
 * http://localhost:8000 cross-origin, which the backend allowlists via
 * CORS_ORIGINS=http://localhost:3000 with credentials.
 */
import { randomUUID } from 'node:crypto';

export const API_URL = 'http://localhost:8000';

/** Backend password policy is 12-1024 chars (design §1, NIST 800-63B). */
export const E2E_PASSWORD = 'e2e-Playwright-Suite-2026!';

/** Unique per-test email — registration tests must be retry/parallel safe. */
export function uniqueEmail(): string {
  return `e2e-${Date.now()}-${randomUUID().slice(0, 8)}@taxassist.test`;
}

/**
 * Server-issued app session ids: `uuid.uuid4().hex` — 32 hex chars, no
 * dashes (backend/db.py create_session).
 */
export const SESSION_ID_RE = /^[0-9a-f]{32}$/;

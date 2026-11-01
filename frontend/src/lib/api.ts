/**
 * Central API access layer (Sprint 3 Step A, ADR-010).
 *
 * All backend calls go through {@link apiFetch}:
 * - BASE resolution: `NEXT_PUBLIC_API_URL` when set, else "" (same-origin —
 *   the single-origin production posture behind a reverse proxy; dev sets
 *   e.g. http://localhost:8000). No hardcoded localhost anywhere else.
 * - `credentials: "include"` is always injected so the HttpOnly session
 *   cookie (arriving in the auth wave) rides on every request, same- or
 *   cross-origin.
 * - A single 401 hook: the exported {@link onUnauthorized} setter registers
 *   the redirect-to-login handler (wired up in the auth wave; the default
 *   is a no-op so behavior is unchanged this wave).
 */

const BASE: string = process.env.NEXT_PUBLIC_API_URL ?? "";

export type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler = () => {};

/**
 * Register the handler invoked on any 401 response (auth wave wires the
 * client redirect to /login). Passing a new handler replaces the previous
 * one; passing nothing is not allowed — use a no-op to clear.
 */
export function onUnauthorized(handler: UnauthorizedHandler): void {
  unauthorizedHandler = handler;
}

/**
 * Fetch the backend API with session credentials and central 401 handling.
 *
 * `path` is backend-root-relative (e.g. "/chat"). `init` mirrors the
 * standard RequestInit; `credentials` is forced to "include".
 */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
  });
  if (response.status === 401) {
    unauthorizedHandler();
  }
  return response;
}

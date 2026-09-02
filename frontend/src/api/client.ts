/**
 * Base API client for the Forecast Viewer frontend.
 *
 * Uses relative URLs so the Vite dev proxy forwards /api requests
 * to the backend at http://localhost:8000.
 */

import { buildUrl, STATIC_MODE } from "./staticMode";

/**
 * Structured error for non-2xx API responses.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly body: unknown;

  constructor(status: number, statusText: string, body: unknown) {
    super(`API error ${status}: ${statusText}`);
    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.body = body;
  }
}

/**
 * Perform a GET request against the backend API.
 *
 * @param path - API path (e.g. "/api/health"). Must start with "/".
 * @param params - Optional query parameters appended to the URL.
 * @param signal - Optional AbortSignal for request cancellation.
 * @returns Parsed JSON response body typed as T.
 * @throws {ApiError} on non-2xx responses.
 */
export async function apiGet<T>(
  path: string,
  params?: Record<string, string>,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(path, window.location.origin);

  if (params) {
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, value);
    }
  }

  const response = await fetch(url.toString(), { signal });

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = await response.text().catch(() => null);
    }
    throw new ApiError(response.status, response.statusText, body);
  }

  return (await response.json()) as T;
}

/**
 * Options for apiGetStatic.
 */
export interface StaticOpts {
  /** Override the module-level STATIC_MODE flag (tests). */
  static?: boolean;
  /** Resolve null instead of throwing when static mode hits a 404. */
  allowMissing?: boolean;
}

/**
 * Fetch endpoint data in either dynamic (/api/...) or static (./data/...) mode.
 *
 * Delegates URL construction to buildUrl so hooks stay agnostic of mode.
 */
export async function apiGetStatic<T>(
  endpoint: string,
  params?: Record<string, string>,
  signal?: AbortSignal,
  opts: StaticOpts = {},
): Promise<T | null> {
  const isStatic = opts.static ?? STATIC_MODE;
  const url = buildUrl(endpoint, params ?? {}, isStatic);
  const response = await fetch(url, { signal });

  if (!response.ok) {
    if (response.status === 404 && opts.allowMissing) return null;
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = await response.text().catch(() => null);
    }
    throw new ApiError(response.status, response.statusText, body);
  }

  return (await response.json()) as T;
}

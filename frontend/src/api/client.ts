/**
 * Base API client for the Forecast Viewer frontend.
 *
 * Uses relative URLs so the Vite dev proxy forwards /api requests
 * to the backend at http://localhost:8000.
 */

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

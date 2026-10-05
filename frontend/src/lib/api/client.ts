import { getApiBaseUrl } from "@/lib/config";

/** Error raised for any failed API call, carrying the backend's stable error code. */
export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly requestId?: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ErrorEnvelope {
  error?: { code?: unknown; message?: unknown; request_id?: unknown; details?: unknown };
}

export async function parseApiError(response: Response): Promise<ApiError> {
  let body: ErrorEnvelope | null = null;
  try {
    body = (await response.json()) as ErrorEnvelope;
  } catch {
    // Non-JSON error (proxy page, HTML 502, ...): fall through to generic error.
  }
  const err = body?.error;
  const code = typeof err?.code === "string" ? err.code : `HTTP_${response.status}`;
  const message = typeof err?.message === "string" ? err.message : response.statusText;
  const requestId =
    typeof err?.request_id === "string"
      ? err.request_id
      : (response.headers.get("x-request-id") ?? undefined);
  return new ApiError(code, message, response.status, requestId, err?.details);
}

export const CSRF_COOKIE = "csrf_token";
export const CSRF_HEADER = "X-CSRF-Token";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);
/** Codes after which a browser session may be renewed with the refresh cookie. */
const RENEWABLE = new Set(["TOKEN_EXPIRED", "NOT_AUTHENTICATED"]);

/** Read a non-httpOnly cookie in the browser (null on the server). */
export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  for (const part of document.cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

export interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  locale?: string;
  /** Internal: prevents infinite refresh loops. */
  _retried?: boolean;
}

/** Low-level request: resolves with the Response for any HTTP status. */
export async function apiRequest(path: string, options: ApiFetchOptions = {}): Promise<Response> {
  const base = getApiBaseUrl();
  if (base === null) throw new ApiError("API_NOT_CONFIGURED", "API URL is not configured", 0);

  const { body, locale, headers, _retried, ...init } = options;
  void _retried;
  const method = (init.method ?? "GET").toUpperCase();
  const finalHeaders = new Headers(headers);
  finalHeaders.set("Accept", "application/json");
  if (locale) finalHeaders.set("Accept-Language", locale);
  const isBlob = typeof Blob !== "undefined" && body instanceof Blob;
  if (isBlob) {
    // Raw uploads (e.g. a rendered video) keep their own media type.
    if (!finalHeaders.has("Content-Type")) {
      finalHeaders.set("Content-Type", (body as Blob).type || "application/octet-stream");
    }
  } else if (body !== undefined && !(body instanceof FormData)) {
    finalHeaders.set("Content-Type", "application/json");
  }
  if (UNSAFE.has(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf && !finalHeaders.has(CSRF_HEADER)) finalHeaders.set(CSRF_HEADER, csrf);
  }

  let payload: BodyInit | undefined;
  if (body instanceof FormData || isBlob) payload = body as BodyInit;
  else if (body !== undefined) payload = JSON.stringify(body);

  try {
    return await fetch(`${base}${path}`, {
      credentials: "same-origin",
      ...init,
      method,
      headers: finalHeaders,
      body: payload,
    });
  } catch (cause) {
    throw new ApiError("NETWORK_ERROR", String(cause), 0);
  }
}

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Renew the browser session using the httpOnly refresh cookie. Concurrent
 * callers share one request so the single-use refresh token is not replayed.
 */
export function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = apiRequest("/api/v1/auth/refresh", { method: "POST" })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

/** JSON request that throws ApiError on any non-2xx response. */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const response = await apiRequest(path, options);
  if (!response.ok) {
    const error = await parseApiError(response);
    const canRenew =
      response.status === 401 &&
      RENEWABLE.has(error.code) &&
      !options._retried &&
      readCookie(CSRF_COOKIE) !== null && // a browser session exists
      !path.startsWith("/api/v1/auth/");
    if (canRenew && (await refreshSession())) {
      return apiFetch<T>(path, { ...options, _retried: true });
    }
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

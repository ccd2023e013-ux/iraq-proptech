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

export interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  locale?: string;
}

/** Low-level request: resolves with the Response for any HTTP status. */
export async function apiRequest(path: string, options: ApiFetchOptions = {}): Promise<Response> {
  const base = getApiBaseUrl();
  if (base === null) throw new ApiError("API_NOT_CONFIGURED", "API URL is not configured", 0);

  const { body, locale, headers, ...init } = options;
  const finalHeaders = new Headers(headers);
  finalHeaders.set("Accept", "application/json");
  if (locale) finalHeaders.set("Accept-Language", locale);
  if (body !== undefined) finalHeaders.set("Content-Type", "application/json");

  try {
    return await fetch(`${base}${path}`, {
      ...init,
      headers: finalHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (cause) {
    throw new ApiError("NETWORK_ERROR", String(cause), 0);
  }
}

/** JSON request that throws ApiError on any non-2xx response. */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const response = await apiRequest(path, options);
  if (!response.ok) throw await parseApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

import "server-only";

import { cookies, headers } from "next/headers";

import { ApiError, parseApiError } from "@/lib/api/client";
import { getInternalApiUrl } from "@/lib/config";

/**
 * Server-side API call on behalf of the current browser request.
 *
 * Forwards the visitor's cookies (session) and language so server components
 * see exactly what the user is allowed to see. Only safe (GET) requests are
 * made from the server; mutations happen in the browser with CSRF protection.
 */
export async function serverApiRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const base = getInternalApiUrl();
  if (!base) throw new ApiError("API_NOT_CONFIGURED", "API_INTERNAL_URL is not set", 0);
  const jar = await cookies();
  const incoming = await headers();
  const outgoing = new Headers(init.headers);
  outgoing.set("Accept", "application/json");
  const cookieHeader = jar
    .getAll()
    .map((c) => `${c.name}=${encodeURIComponent(c.value)}`)
    .join("; ");
  if (cookieHeader) outgoing.set("Cookie", cookieHeader);
  const lang = incoming.get("accept-language");
  if (lang) outgoing.set("Accept-Language", lang);
  const forwarded = incoming.get("x-forwarded-for");
  if (forwarded) outgoing.set("X-Forwarded-For", forwarded);
  try {
    return await fetch(`${base}${path}`, { cache: "no-store", ...init, headers: outgoing });
  } catch (cause) {
    throw new ApiError("NETWORK_ERROR", String(cause), 0);
  }
}

export async function serverApiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await serverApiRequest(path, init);
  if (!response.ok) throw await parseApiError(response);
  return (await response.json()) as T;
}

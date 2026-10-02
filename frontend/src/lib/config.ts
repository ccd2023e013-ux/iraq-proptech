/**
 * Runtime configuration. The API URL always comes from the environment —
 * never hard-coded — so the same build talks to Codespaces, a temporary cloud
 * API, or the production PC.
 *
 * Browser: calls NEXT_PUBLIC_API_URL when set; otherwise calls the frontend's
 *   own origin, where `app/api/[...path]/route.ts` proxies to the backend.
 *   Same-origin is the default because it works behind any port-forwarding
 *   proxy (Codespaces, tunnels) and needs no CORS.
 * Server: API_INTERNAL_URL (e.g. http://backend:8000 in Docker), falling back
 *   to NEXT_PUBLIC_API_URL. Returns null when neither is set.
 */
export function getApiBaseUrl(): string | null {
  if (typeof window !== "undefined") {
    return (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");
  }
  return getInternalApiUrl();
}

export function getInternalApiUrl(): string | null {
  const raw = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL;
  return raw ? raw.replace(/\/+$/, "") : null;
}

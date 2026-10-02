/**
 * Helpers for the same-origin API proxy (app/api/[...path]/route.ts).
 * Kept framework-free so they are unit-testable.
 */

// Hop-by-hop headers (RFC 9110 §7.6.1) plus ones fetch recomputes itself.
const STRIP_REQUEST = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

// Node's fetch transparently decompresses, so length/encoding no longer match.
const STRIP_RESPONSE = new Set([...STRIP_REQUEST, "content-encoding", "content-length"]);

/**
 * Headers forwarded to the API. `X-Forwarded-For` is passed through unchanged:
 * this proxy cannot know the browser's address itself, and the API trusts
 * exactly `TRUSTED_PROXY_HOPS` entries appended by the edge proxies in front
 * of the frontend (see backend/app/core/client_ip.py).
 */
export function filterRequestHeaders(source: Headers): Headers {
  const out = new Headers();
  source.forEach((value, key) => {
    if (!STRIP_REQUEST.has(key.toLowerCase())) out.append(key, value);
  });
  return out;
}

export function filterResponseHeaders(source: Headers): Headers {
  const out = new Headers();
  source.forEach((value, key) => {
    if (key.toLowerCase() === "set-cookie") return; // handled below, one per cookie
    if (!STRIP_RESPONSE.has(key.toLowerCase())) out.append(key, value);
  });
  // Each cookie must stay a separate Set-Cookie header (they cannot be comma-joined).
  for (const cookie of source.getSetCookie()) out.append("set-cookie", cookie);
  return out;
}

/** Only the versioned API is proxied; anything else is rejected. */
export function buildUpstreamUrl(base: string, pathname: string, search: string): string | null {
  if (!pathname.startsWith("/api/v1/") && pathname !== "/api/v1") return null;
  return `${base}${pathname}${search}`;
}

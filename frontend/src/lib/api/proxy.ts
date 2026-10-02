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

export function filterRequestHeaders(source: Headers, clientIp?: string | null): Headers {
  const out = new Headers();
  source.forEach((value, key) => {
    if (!STRIP_REQUEST.has(key.toLowerCase())) out.set(key, value);
  });
  if (clientIp) {
    const prior = source.get("x-forwarded-for");
    out.set("x-forwarded-for", prior ? `${prior}, ${clientIp}` : clientIp);
  }
  return out;
}

export function filterResponseHeaders(source: Headers): Headers {
  const out = new Headers();
  source.forEach((value, key) => {
    if (!STRIP_RESPONSE.has(key.toLowerCase())) out.set(key, value);
  });
  return out;
}

/** Only the versioned API is proxied; anything else is rejected. */
export function buildUpstreamUrl(base: string, pathname: string, search: string): string | null {
  if (!pathname.startsWith("/api/v1/") && pathname !== "/api/v1") return null;
  return `${base}${pathname}${search}`;
}

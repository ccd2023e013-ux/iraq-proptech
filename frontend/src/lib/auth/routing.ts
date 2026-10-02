/**
 * Pure helpers for authentication routing (shared by middleware, route
 * handlers and pages; unit-tested).
 */

export const ACCESS_COOKIE = "access_token";
export const REFRESH_COOKIE = "refresh_token";

/** Paths that require a signed-in user. */
export const PROTECTED_PREFIXES = [
  "/dashboard",
  "/account",
  "/admin",
  "/favorites",
  "/saved-searches",
  "/messages",
  "/notifications",
];

export const DEFAULT_AFTER_LOGIN = "/dashboard";

export function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/**
 * Only allow same-site relative paths after login (prevents open redirects
 * such as `//evil.com`, `/\\evil.com` or `https://evil.com`).
 */
export function safeNextPath(
  next: string | null | undefined,
  fallback = DEFAULT_AFTER_LOGIN,
): string {
  if (!next || typeof next !== "string") return fallback;
  if (!next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  for (let i = 0; i < next.length; i++) {
    const code = next.charCodeAt(i);
    if (code < 0x20 || code === 0x7f) return fallback; // control characters
  }
  try {
    const parsed = new URL(next, "http://placeholder.local");
    if (parsed.origin !== "http://placeholder.local") return fallback;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}

export type GuardDecision =
  | { action: "allow" }
  | { action: "login"; next: string }
  | { action: "refresh"; next: string };

/** Decide what middleware does for a request, from cookie presence only. */
export function guardDecision(
  pathname: string,
  search: string,
  hasAccess: boolean,
  hasRefresh: boolean,
): GuardDecision {
  if (!isProtectedPath(pathname)) return { action: "allow" };
  const next = `${pathname}${search}`;
  if (hasAccess) return { action: "allow" };
  if (hasRefresh) return { action: "refresh", next };
  return { action: "login", next };
}

export function hasPermission(permissions: readonly string[] | undefined, perm: string): boolean {
  return !!permissions && permissions.includes(perm);
}

import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, REFRESH_COOKIE, guardDecision } from "@/lib/auth/routing";

/**
 * Route guard based on cookie *presence* only (cheap, no network). The real
 * authorization decision is always made by the API; pages that need the user
 * fetch /auth/me on the server and handle 401/403 themselves.
 *
 * Next.js 16 "proxy" (formerly middleware); it runs on the Node.js runtime.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const decision = guardDecision(
    pathname,
    search,
    request.cookies.has(ACCESS_COOKIE),
    request.cookies.has(REFRESH_COOKIE),
  );

  if (decision.action === "login") {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", decision.next);
    return NextResponse.redirect(url);
  }
  if (decision.action === "refresh") {
    const url = new URL("/auth/refresh", request.url);
    url.searchParams.set("next", decision.next);
    return NextResponse.redirect(url);
  }

  // Let server components know the current path (for post-refresh redirects).
  const forwarded = new Headers(request.headers);
  forwarded.set("x-pathname", `${pathname}${search}`);
  return NextResponse.next({ request: { headers: forwarded } });
}

export const config = {
  // Skip static assets and the API proxy.
  matcher: ["/((?!api/|_next/static|_next/image|favicon.ico|.*\\.[a-z0-9]+$).*)"],
};

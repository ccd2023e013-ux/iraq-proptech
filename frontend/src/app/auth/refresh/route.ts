import { type NextRequest, NextResponse } from "next/server";

import { filterResponseHeaders } from "@/lib/api/proxy";
import { safeNextPath } from "@/lib/auth/routing";
import { getInternalApiUrl } from "@/lib/config";

export const dynamic = "force-dynamic";

/**
 * Renews an expired browser session during navigation, then returns the user
 * to where they were going. Called by middleware when only the refresh cookie
 * is left. On failure the user is sent to /login with the same destination.
 */
export async function GET(request: NextRequest) {
  const next = safeNextPath(request.nextUrl.searchParams.get("next"));
  const base = getInternalApiUrl();
  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", next);

  const csrf = request.cookies.get("csrf_token")?.value;
  if (!base || !csrf) return NextResponse.redirect(loginUrl);

  let upstream: Response;
  try {
    upstream = await fetch(`${base}/api/v1/auth/refresh`, {
      method: "POST",
      headers: {
        Cookie: request.headers.get("cookie") ?? "",
        "X-CSRF-Token": csrf,
        "X-Forwarded-For": request.headers.get("x-forwarded-for") ?? "",
        "User-Agent": request.headers.get("user-agent") ?? "",
      },
      cache: "no-store",
    });
  } catch {
    return NextResponse.redirect(loginUrl);
  }

  const target = upstream.ok ? new URL(next, request.url) : loginUrl;
  const response = NextResponse.redirect(target);
  // Forward rotated (or cleared) cookies from the API to the browser.
  for (const cookie of filterResponseHeaders(upstream.headers).getSetCookie()) {
    response.headers.append("set-cookie", cookie);
  }
  return response;
}

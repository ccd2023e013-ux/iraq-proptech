import type { NextRequest } from "next/server";

import { getInternalApiUrl } from "@/lib/config";
import { buildUpstreamUrl, filterRequestHeaders, filterResponseHeaders } from "@/lib/api/proxy";

/**
 * Same-origin proxy: /api/v1/* on the frontend → API_INTERNAL_URL/api/v1/*.
 * The upstream is read at *runtime*, so one built image works against any
 * backend (Docker network, Codespaces, temporary cloud API, production PC).
 */
export const dynamic = "force-dynamic";

function errorResponse(status: number, code: string, message: string): Response {
  return Response.json({ error: { code, message } }, { status });
}

async function proxy(request: NextRequest): Promise<Response> {
  const base = getInternalApiUrl();
  if (!base) return errorResponse(503, "API_NOT_CONFIGURED", "API_INTERNAL_URL is not set");

  const url = buildUpstreamUrl(base, request.nextUrl.pathname, request.nextUrl.search);
  if (!url) return errorResponse(404, "NOT_FOUND", "Not found");

  const hasBody = !["GET", "HEAD"].includes(request.method);
  try {
    const upstream = await fetch(url, {
      method: request.method,
      headers: filterRequestHeaders(request.headers, request.headers.get("x-real-ip")),
      body: hasBody ? request.body : undefined,
      redirect: "manual",
      cache: "no-store",
      // Required by Node's fetch when streaming a request body.
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: filterResponseHeaders(upstream.headers),
    });
  } catch {
    return errorResponse(502, "NETWORK_ERROR", "Backend unreachable");
  }
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
  proxy as HEAD,
  proxy as OPTIONS,
};

import { describe, expect, it } from "vitest";

import { buildUpstreamUrl, filterRequestHeaders, filterResponseHeaders } from "./proxy";

describe("API proxy helpers", () => {
  it("drops hop-by-hop request headers and keeps auth", () => {
    const out = filterRequestHeaders(
      new Headers({
        host: "frontend.test",
        connection: "keep-alive",
        authorization: "Bearer abc",
        "accept-language": "ar",
      }),
    );
    expect(out.get("host")).toBeNull();
    expect(out.get("connection")).toBeNull();
    expect(out.get("authorization")).toBe("Bearer abc");
  });

  it("passes the edge proxy's forwarded-for chain through unchanged", () => {
    const out = filterRequestHeaders(new Headers({ "x-forwarded-for": "6.6.6.6, 203.0.113.7" }));
    expect(out.get("x-forwarded-for")).toBe("6.6.6.6, 203.0.113.7");
    expect(filterRequestHeaders(new Headers()).get("x-forwarded-for")).toBeNull();
  });

  it("drops encoding headers from upstream responses", () => {
    const out = filterResponseHeaders(
      new Headers({ "content-encoding": "gzip", "x-request-id": "r1" }),
    );
    expect(out.get("content-encoding")).toBeNull();
    expect(out.get("x-request-id")).toBe("r1");
  });

  it("keeps every Set-Cookie header separate", () => {
    const upstream = new Headers();
    upstream.append("set-cookie", "access_token=a; Path=/; HttpOnly; Max-Age=900");
    upstream.append("set-cookie", "refresh_token=r; Path=/; HttpOnly");
    upstream.append("set-cookie", "csrf_token=c; Path=/");
    const out = filterResponseHeaders(upstream);
    expect(out.getSetCookie()).toEqual([
      "access_token=a; Path=/; HttpOnly; Max-Age=900",
      "refresh_token=r; Path=/; HttpOnly",
      "csrf_token=c; Path=/",
    ]);
  });

  it("only proxies the versioned API", () => {
    expect(buildUpstreamUrl("http://backend:8000", "/api/v1/health", "?a=1")).toBe(
      "http://backend:8000/api/v1/health?a=1",
    );
    expect(buildUpstreamUrl("http://backend:8000", "/api/internal", "")).toBeNull();
    expect(buildUpstreamUrl("http://backend:8000", "/api/v10/x", "")).toBeNull();
  });
});

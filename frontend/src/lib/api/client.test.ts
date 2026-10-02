import { describe, expect, it, vi, afterEach } from "vitest";

import { ApiError, apiFetch } from "./client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Request-ID": "req-1" },
  });
}

describe("apiFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("uses the configured API URL and returns JSON", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test/");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/health")).resolves.toEqual({ status: "ok" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("https://api.example.test/api/v1/health");
  });

  it("maps the backend error envelope to ApiError", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(404, {
          error: { code: "PROPERTY_NOT_FOUND", message: "Property not found", request_id: "r9" },
        }),
      ),
    );

    const error = await apiFetch("/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "PROPERTY_NOT_FOUND", status: 404, requestId: "r9" });
  });

  it("reports network failures with a stable code", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    await expect(apiFetch("/x")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });

  it("calls the same-origin proxy when no public API URL is set", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/api/v1/health");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/health");
  });
});

describe("browser session handling", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    document.cookie = "csrf_token=; max-age=0; path=/";
  });

  it("sends the CSRF cookie value on unsafe requests only", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    document.cookie = "csrf_token=tok123; path=/";
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/x", { method: "POST", body: {} });
    await apiFetch("/api/v1/x");
    const postHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
    const getHeaders = fetchMock.mock.calls[1]?.[1]?.headers as Headers;
    expect(postHeaders.get("X-CSRF-Token")).toBe("tok123");
    expect(getHeaders.get("X-CSRF-Token")).toBeNull();
  });

  it("renews an expired session once and retries", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    document.cookie = "csrf_token=tok123; path=/";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: "TOKEN_EXPIRED", message: "x" } }))
      .mockResolvedValueOnce(jsonResponse(200, {})) // refresh
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/favorites")).resolves.toEqual({ ok: true });
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/auth/refresh");
  });

  it("does not try to renew without a browser session", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(401, { error: { code: "NOT_AUTHENTICATED", message: "x" } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiFetch("/api/v1/favorites")).rejects.toMatchObject({
      code: "NOT_AUTHENTICATED",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shares one refresh between concurrent requests", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    document.cookie = "csrf_token=tok123; path=/";
    let refreshCalls = 0;
    const attempts = new Map<string, number>();
    const fetchMock = vi.fn((url: string) => {
      if (url === "/api/v1/auth/refresh") {
        refreshCalls += 1;
        return Promise.resolve(jsonResponse(200, {}));
      }
      const n = (attempts.get(url) ?? 0) + 1;
      attempts.set(url, n);
      return Promise.resolve(
        n === 1
          ? jsonResponse(401, { error: { code: "TOKEN_EXPIRED", message: "x" } })
          : jsonResponse(200, { url }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    await Promise.all([apiFetch("/api/v1/a"), apiFetch("/api/v1/b")]);
    expect(refreshCalls).toBe(1);
  });
});

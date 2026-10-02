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

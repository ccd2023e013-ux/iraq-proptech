import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getDictionary } from "@/i18n";

import { LoginForm } from "./LoginForm";

const replace = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, refresh }) }));

const ar = getDictionary("ar");

function respond(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fill() {
  fireEvent.change(screen.getByLabelText(ar.auth.email), {
    target: { value: "sara@example.com" },
  });
  fireEvent.change(screen.getByLabelText(ar.auth.password), {
    target: { value: "Correct-Horse-9" },
  });
  fireEvent.click(screen.getByRole("button", { name: ar.auth.submitLogin }));
}

describe("LoginForm", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    replace.mockReset();
  });

  it("signs in and goes to the safe return path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(200, { user: {} }));
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginForm dict={ar} next="/account" />);
    fill();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/account"));
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/auth/login");
    expect(JSON.parse(init.body)).toEqual({
      email: "sara@example.com",
      password: "Correct-Horse-9",
    });
  });

  it("never redirects off-site", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(200, { user: {} })));
    render(<LoginForm dict={ar} next="https://evil.example" />);
    fill();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("shows the Arabic error for wrong credentials", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          respond(401, { error: { code: "INVALID_CREDENTIALS", message: "Invalid" } }),
        ),
    );
    render(<LoginForm dict={ar} />);
    fill();
    expect(await screen.findByRole("alert")).toHaveTextContent(ar.errors.INVALID_CREDENTIALS);
    expect(replace).not.toHaveBeenCalled();
  });
});

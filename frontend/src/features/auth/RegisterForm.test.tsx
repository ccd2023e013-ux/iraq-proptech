import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getDictionary } from "@/i18n";

import { ForgotPasswordForm } from "./RecoveryForms";
import { RegisterForm } from "./RegisterForm";

const en = getDictionary("en");

function respond(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fill(values: { name: string; email: string; password: string }) {
  fireEvent.change(screen.getByLabelText(en.auth.fullName), { target: { value: values.name } });
  fireEvent.change(screen.getByLabelText(en.auth.email), { target: { value: values.email } });
  fireEvent.change(screen.getByLabelText(en.auth.password), {
    target: { value: values.password },
  });
  fireEvent.click(screen.getByRole("button", { name: en.auth.submitRegister }));
}

describe("RegisterForm", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows field errors and does not call the API for invalid input", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<RegisterForm dict={en} locale="en" />);
    fill({ name: "S", email: "not-an-email", password: "short" });
    expect(await screen.findByText(en.auth.errNameShort)).toBeInTheDocument();
    expect(screen.getByText(en.auth.errEmail)).toBeInTheDocument();
    expect(screen.getByText(en.auth.errPasswordShort)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("is honest when the site cannot send the confirmation email", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(201, { id: "x" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<RegisterForm dict={en} locale="en" emailDelivery={false} />);
    fill({ name: " Sara Ali ", email: " sara@example.com ", password: "Correct-Horse-9" });
    expect(await screen.findByText(en.auth.registeredNoEmail)).toBeInTheDocument();
    expect(screen.getByText(en.auth.emailUnavailable)).toBeInTheDocument();
    expect(screen.queryByText(en.auth.registeredBody)).not.toBeInTheDocument();
    const body = JSON.parse(fetchMock.mock.calls[0]![1].body);
    expect(body).toMatchObject({ full_name: "Sara Ali", email: "sara@example.com", locale: "en" });
  });

  it("toggles password visibility", () => {
    render(<RegisterForm dict={en} locale="en" />);
    const input = screen.getByLabelText(en.auth.password);
    expect(input).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: en.auth.show }));
    expect(input).toHaveAttribute("type", "text");
  });
});

describe("ForgotPasswordForm", () => {
  it("does not promise a reset email when delivery is unavailable", () => {
    render(<ForgotPasswordForm dict={en} emailDelivery={false} />);
    expect(screen.getByText(en.auth.resetUnavailable)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: en.auth.forgotSubmit })).not.toBeInTheDocument();
  });

  it("validates the email before sending", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(202, {}));
    vi.stubGlobal("fetch", fetchMock);
    render(<ForgotPasswordForm dict={en} />);
    fireEvent.click(screen.getByRole("button", { name: en.auth.forgotSubmit }));
    expect(await screen.findByText(en.auth.errRequired)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(en.auth.email), {
      target: { value: "sara@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.auth.forgotSubmit }));
    await waitFor(() => expect(screen.getByText(en.auth.forgotSent)).toBeInTheDocument());
    vi.unstubAllGlobals();
  });
});

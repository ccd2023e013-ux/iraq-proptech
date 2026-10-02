import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getDictionary } from "@/i18n";

import { InquiryForm } from "./InquiryForm";

const ar = getDictionary("ar");

afterEach(() => vi.restoreAllMocks());

function renderForm(signedIn = true) {
  return render(
    <InquiryForm
      dict={ar}
      propertyId="p-1"
      signedIn={signedIn}
      defaultName="سارة"
      defaultPhone=""
      defaultEmail=""
    />,
  );
}

describe("InquiryForm", () => {
  it("asks visitors to sign in", () => {
    renderForm(false);
    expect(screen.getByRole("link", { name: ar.inquiry.loginToSend })).toHaveAttribute(
      "href",
      "/login?next=%2Fproperties%2Fp-1",
    );
  });

  it("requires a phone or email before sending", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    renderForm();
    fireEvent.click(screen.getByRole("button", { name: ar.inquiry.send }));
    expect(await screen.findByText(ar.inquiry.contactHint)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("posts the inquiry and confirms", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => new Response(JSON.stringify({ id: "i-1" }), { status: 201 }));
    renderForm();
    fireEvent.change(screen.getByLabelText(ar.inquiry.phone), { target: { value: "07701234567" } });
    fireEvent.click(screen.getByRole("button", { name: ar.inquiry.send }));
    await waitFor(() => expect(screen.getByText(ar.inquiry.sent)).toBeInTheDocument());
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/properties/p-1/inquiries");
    const body = JSON.parse(String(init.body));
    expect(body).toMatchObject({ name: "سارة", phone: "07701234567", email: null });
  });
});

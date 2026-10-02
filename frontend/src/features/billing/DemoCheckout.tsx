"use client";

import Link from "next/link";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

import type { Payment } from "./types";

export function DemoCheckout({ dict, payment }: { dict: Dictionary; payment: Payment }) {
  const b = dict.billing;
  const [current, setCurrent] = useState(payment);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function finish(outcome: "SUCCEEDED" | "FAILED") {
    setBusy(true);
    setError(null);
    try {
      setCurrent(
        await apiFetch<Payment>(`/api/v1/billing/payments/${payment.id}/demo-complete`, {
          method: "POST",
          body: { outcome },
        }),
      );
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  if (current.status !== "PENDING") {
    return (
      <div className="flex flex-col gap-3">
        <Alert tone={current.status === "SUCCEEDED" ? "success" : "error"}>
          {current.status === "SUCCEEDED" ? b.paymentSucceeded : b.paymentFailed}
        </Alert>
        <div className="flex gap-3 text-sm">
          {current.property_id && (
            <Link href={`/dashboard/properties/${current.property_id}`} className="text-brand-700">
              {dict.myListings.title}
            </Link>
          )}
          <Link href="/account/billing" className="text-brand-700">
            {b.myBilling}
          </Link>
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3">
        <Button onClick={() => finish("SUCCEEDED")} loading={busy}>
          {b.simulateSuccess}
        </Button>
        <Button variant="secondary" onClick={() => finish("FAILED")} disabled={busy}>
          {b.simulateFailure}
        </Button>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  );
}

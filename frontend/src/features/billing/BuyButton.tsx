"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { ApiError, apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";

import { safeRedirect } from "./types";

export function BuyButton({
  dict,
  planCode,
  propertyId,
  label,
  loginNext,
}: {
  dict: Dictionary;
  planCode: string;
  propertyId?: string;
  label: string;
  loginNext?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function buy() {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch<{ redirect_url: string }>("/api/v1/billing/checkout", {
        method: "POST",
        body: { plan_code: planCode, ...(propertyId ? { property_id: propertyId } : {}) },
      });
      const target = safeRedirect(res.redirect_url);
      if (target) router.push(target);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401 && loginNext) {
        router.push(`/login?next=${encodeURIComponent(loginNext)}`);
        return;
      }
      setError(describeError(dict, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Button onClick={buy} loading={busy} size="sm">
        {label}
      </Button>
      {error && (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

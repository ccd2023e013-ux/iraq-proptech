"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type { Property, PropertyStatus } from "@/types/property";

type Action = "submit" | "unpublish" | "archive" | "mark-sold" | "mark-rented";

const AVAILABLE: Record<Action, PropertyStatus[]> = {
  submit: ["DRAFT", "REJECTED", "EXPIRED"],
  unpublish: ["APPROVED", "PENDING_REVIEW"],
  archive: ["DRAFT", "APPROVED", "PENDING_REVIEW", "REJECTED", "SOLD", "RENTED", "EXPIRED"],
  "mark-sold": ["APPROVED"],
  "mark-rented": ["APPROVED"],
};

/** Which owner actions apply to a listing (mirrors the backend state machine). */
export function availableActions(property: Pick<Property, "status" | "purpose">): Action[] {
  const saleLike = property.purpose === "SALE" || property.purpose === "EXCHANGE";
  return (Object.keys(AVAILABLE) as Action[]).filter((action) => {
    if (!AVAILABLE[action].includes(property.status)) return false;
    if (action === "mark-sold") return saleLike;
    if (action === "mark-rented") return !saleLike;
    return true;
  });
}

export function ListingActions({ dict, property }: { dict: Dictionary; property: Property }) {
  const router = useRouter();
  const f = dict.listingForm;
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const labels: Record<Action, string> = {
    submit: f.submit,
    unpublish: f.unpublish,
    archive: f.archive,
    "mark-sold": f.markSold,
    "mark-rented": f.markRented,
  };

  async function run(action: Action) {
    setBusy(action);
    setError(null);
    try {
      await apiFetch(`/api/v1/properties/${property.id}/${action}`, { method: "POST" });
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!window.confirm(f.confirmDelete)) return;
    try {
      await apiFetch(`/api/v1/properties/${property.id}`, { method: "DELETE" });
      router.push("/dashboard/properties");
      router.refresh();
    } catch (err) {
      setError(describeError(dict, err));
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <Alert tone="error">{error}</Alert>}
      {property.status === "DRAFT" && <p className="text-sm text-sand-500">{f.reviewNote}</p>}
      <div className="flex flex-wrap gap-2">
        {availableActions(property).map((action) => (
          <Button
            key={action}
            variant={action === "submit" ? "primary" : "secondary"}
            loading={busy === action}
            onClick={() => run(action)}
          >
            {labels[action]}
          </Button>
        ))}
        <Button variant="ghost" className="text-danger" onClick={remove}>
          {f.deleteListing}
        </Button>
      </div>
    </div>
  );
}

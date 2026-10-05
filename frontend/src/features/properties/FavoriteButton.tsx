"use client";

import { useRouter } from "next/navigation";
import { type MouseEvent, useState } from "react";

import { apiFetch } from "@/lib/api/client";

export function FavoriteButton({
  propertyId,
  initial,
  signedIn,
  labels,
  variant = "icon",
}: {
  propertyId: string;
  initial: boolean;
  signedIn: boolean;
  labels: { save: string; saved: string; loginToSave: string };
  variant?: "icon" | "button";
}) {
  const router = useRouter();
  const [saved, setSaved] = useState(initial);
  const [busy, setBusy] = useState(false);

  async function toggle(event: MouseEvent) {
    event.preventDefault(); // the button sits inside a card link
    event.stopPropagation();
    if (!signedIn) {
      router.push(`/login?next=${encodeURIComponent(`/properties/${propertyId}`)}`);
      return;
    }
    setBusy(true);
    const next = !saved;
    setSaved(next); // optimistic
    try {
      await apiFetch(`/api/v1/properties/${propertyId}/favorite`, {
        method: next ? "PUT" : "DELETE",
      });
    } catch {
      setSaved(!next);
    } finally {
      setBusy(false);
    }
  }

  const label = signedIn ? (saved ? labels.saved : labels.save) : labels.loginToSave;
  if (variant === "button") {
    return (
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        aria-pressed={saved}
        className="inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm font-medium text-ink ring-1 ring-inset ring-hairline-strong transition hover:bg-fill"
      >
        <Heart filled={saved} />
        {saved ? labels.saved : labels.save}
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-pressed={saved}
      aria-label={label}
      title={label}
      className="grid size-9 place-items-center rounded-full bg-glass text-danger shadow-soft backdrop-blur-md transition hover:scale-105 active:scale-95"
    >
      <Heart filled={saved} />
    </button>
  );
}

function Heart({ filled }: { filled: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-5"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="M12 21s-7.5-4.6-9.5-9.2C1.2 8.5 3.4 5 7 5c2 0 3.4 1 5 3 1.6-2 3-3 5-3 3.6 0 5.8 3.5 4.5 6.8C19.5 16.4 12 21 12 21z" />
    </svg>
  );
}

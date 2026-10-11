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
  // Only a save made by the user pops the heart (not hearts that load already filled).
  const [pop, setPop] = useState(false);

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
    setPop(next);
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
        className="press surface-1 inline-flex h-10 items-center gap-2 rounded-[var(--radius-control)] px-4 text-sm font-medium text-ink"
      >
        <Heart filled={saved} pop={pop} onDone={() => setPop(false)} />
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
      className={`press surface-float grid size-9 place-items-center rounded-[var(--radius-control)] ${saved ? "text-danger" : "text-ink"}`}
    >
      <Heart filled={saved} pop={pop} onDone={() => setPop(false)} />
    </button>
  );
}

function Heart({ filled, pop, onDone }: { filled: boolean; pop: boolean; onDone: () => void }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className={`size-[18px] transition-[fill] duration-[var(--duration-quick)] ${pop ? "heart-pop" : ""} ${filled ? "text-danger" : ""}`}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinejoin="round"
      onAnimationEnd={onDone}
    >
      <path d="M12 21s-7.5-4.6-9.5-9.2C1.2 8.5 3.4 5 7 5c2 0 3.4 1 5 3 1.6-2 3-3 5-3 3.6 0 5.8 3.5 4.5 6.8C19.5 16.4 12 21 12 21z" />
    </svg>
  );
}

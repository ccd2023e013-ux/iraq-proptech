"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import type { Dictionary } from "@/i18n";
import { apiFetch } from "@/lib/api/client";

export function UserMenu({ dict, name }: { dict: Dictionary; name: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function logout() {
    try {
      await apiFetch("/api/v1/auth/logout", { method: "POST" });
    } finally {
      setOpen(false);
      router.replace("/");
      router.refresh();
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="press flex h-9 items-center gap-2 rounded-full ps-1 pe-3 text-sm font-medium text-ink hover:bg-fill aria-expanded:bg-fill"
      >
        <span
          aria-hidden
          className="grid size-7 place-items-center rounded-full bg-accent-tint text-xs font-semibold text-accent"
        >
          {name.trim().charAt(0)}
        </span>
        <span className="max-w-32 truncate">{name}</span>
      </button>
      {open && (
        <div
          role="menu"
          className="surface-focus pop-in absolute end-0 z-40 mt-2 w-56 origin-top overflow-hidden rounded-[var(--radius-card)] p-1.5"
        >
          <Link
            role="menuitem"
            href="/dashboard"
            onClick={() => setOpen(false)}
            className="block rounded-xl px-3 py-2.5 text-sm text-ink transition-colors hover:bg-fill"
          >
            {dict.nav.dashboard}
          </Link>
          <Link
            role="menuitem"
            href="/account"
            onClick={() => setOpen(false)}
            className="block rounded-xl px-3 py-2.5 text-sm text-ink transition-colors hover:bg-fill"
          >
            {dict.nav.account}
          </Link>
          <button
            role="menuitem"
            type="button"
            onClick={logout}
            className="mt-1 block w-full rounded-xl border-t border-hairline px-3 py-2.5 text-start text-sm text-danger transition-colors hover:bg-fill"
          >
            {dict.nav.logout}
          </button>
        </div>
      )}
    </div>
  );
}

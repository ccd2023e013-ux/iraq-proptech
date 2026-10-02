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
        className="flex items-center gap-2 rounded-lg border border-sand-200 px-3 py-1.5 text-sm font-medium text-sand-900 hover:border-brand-300"
      >
        <span
          aria-hidden
          className="grid size-6 place-items-center rounded-full bg-brand-100 text-xs text-brand-800"
        >
          {name.trim().charAt(0)}
        </span>
        <span className="max-w-32 truncate">{name}</span>
      </button>
      {open && (
        <div
          role="menu"
          className="absolute end-0 z-40 mt-2 w-48 overflow-hidden rounded-lg border border-sand-200 bg-white py-1 shadow-lg"
        >
          <Link
            role="menuitem"
            href="/dashboard"
            onClick={() => setOpen(false)}
            className="block px-4 py-2 text-sm hover:bg-sand-100"
          >
            {dict.nav.dashboard}
          </Link>
          <Link
            role="menuitem"
            href="/account"
            onClick={() => setOpen(false)}
            className="block px-4 py-2 text-sm hover:bg-sand-100"
          >
            {dict.nav.account}
          </Link>
          <button
            role="menuitem"
            type="button"
            onClick={logout}
            className="block w-full px-4 py-2 text-start text-sm text-danger hover:bg-sand-100"
          >
            {dict.nav.logout}
          </button>
        </div>
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

/** Phone navigation: a small sheet that closes itself after navigating. */
export function MobileMenu({
  label,
  links,
}: {
  label: string;
  links: { href: string; label: string }[];
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  const pathname = usePathname();
  useEffect(() => {
    if (ref.current) ref.current.open = false;
  }, [pathname]);
  return (
    <details ref={ref} className="relative md:hidden">
      <summary
        aria-label={label}
        className="icon-btn size-9 cursor-pointer list-none [&::-webkit-details-marker]:hidden"
      >
        <svg
          aria-hidden
          viewBox="0 0 24 24"
          className="size-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        >
          <path d="M4 8h16M4 16h16" />
        </svg>
      </summary>
      <nav
        aria-label={label}
        className="surface-focus pop-in absolute end-0 top-12 z-40 flex w-60 origin-top flex-col rounded-[var(--radius-card)] p-1.5 text-sm"
      >
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="rounded-xl px-3 py-2.5 text-ink transition-colors hover:bg-fill"
          >
            {l.label}
          </Link>
        ))}
      </nav>
    </details>
  );
}

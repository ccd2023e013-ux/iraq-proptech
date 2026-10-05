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
        className="grid size-9 cursor-pointer list-none place-items-center rounded-full text-ink-2 hover:bg-fill [&::-webkit-details-marker]:hidden"
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
        className="absolute end-0 top-11 z-40 flex w-56 animate-enter flex-col rounded-[var(--radius-card)] bg-surface p-2 text-sm shadow-float ring-1 ring-hairline"
      >
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="rounded-xl px-3 py-2.5 text-ink hover:bg-fill"
          >
            {l.label}
          </Link>
        ))}
      </nav>
    </details>
  );
}

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
      {/* A sheet under the header: large ruled links, thumb-sized. */}
      <nav
        aria-label={label}
        className="fade-in fixed inset-x-0 top-[var(--header-h)] z-40 flex flex-col border-b border-hairline bg-canvas px-4 pb-4 shadow-[var(--shadow-float)]"
      >
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            aria-current={pathname === l.href ? "page" : undefined}
            className="flex h-12 items-center border-b border-hairline font-display text-[17px] text-ink transition-colors last:border-b-0 hover:text-accent aria-[current=page]:text-accent"
          >
            {l.label}
          </Link>
        ))}
      </nav>
    </details>
  );
}

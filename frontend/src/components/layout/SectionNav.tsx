"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Secondary navigation for a section (e.g. admin). Wide screens: a vertical
 * list with the current page marked by an emerald edge. Phones: one row of
 * chips that scrolls sideways, so the content starts on the first screen.
 */
export function SectionNav({
  title,
  root,
  items,
}: {
  title: string;
  /** The section's own index route (matched exactly). */
  root: string;
  items: { href: string; label: string }[];
}) {
  const pathname = usePathname() ?? "";
  const current = (href: string) =>
    href === root ? pathname === root : pathname === href || pathname.startsWith(`${href}/`);
  return (
    <nav
      aria-label={title}
      className="flex min-w-0 flex-col gap-2 lg:sticky lg:top-24 lg:self-start"
    >
      <p className="meta font-medium max-lg:sr-only">{title}</p>
      <ul className="quiet-scroll -mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:px-0">
        {items.map(({ href, label }) => {
          const active = current(href);
          return (
            <li key={href} className="shrink-0">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`press relative flex h-9 items-center rounded-[var(--radius-control)] px-3.5 text-sm whitespace-nowrap transition-colors lg:h-10 lg:rounded-xl ${
                  active
                    ? "bg-fill font-medium text-ink lg:before:absolute lg:before:inset-y-2.5 lg:before:start-0 lg:before:w-0.5 lg:before:rounded-full lg:before:bg-accent-fill"
                    : "text-ink-2 ring-1 ring-inset ring-hairline hover:bg-fill hover:text-ink lg:ring-0"
                }`}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

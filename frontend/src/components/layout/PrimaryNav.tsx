"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface NavItem {
  href: string;
  label: string;
}

/** True when `pathname` is the link's page or one of its sub-pages. */
export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Desktop navigation: text links on the header's baseline. The current
 * section is set in ink with a 2px emerald rule on the header's bottom edge;
 * the others stay quiet until hover (the rule previews in hairline).
 */
export function PrimaryNav({ items, label }: { items: NavItem[]; label: string }) {
  const pathname = usePathname() ?? "/";
  return (
    <nav aria-label={label} className="hidden h-full items-stretch gap-0.5 text-[15px] lg:flex">
      {items.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`group relative flex items-center px-3.5 whitespace-nowrap transition-colors duration-[var(--duration-quick)] ${
              active ? "font-medium text-ink" : "text-ink-2 hover:text-ink"
            }`}
          >
            {item.label}
            <span
              aria-hidden
              className={`absolute inset-x-3.5 -bottom-px h-0.5 origin-center transition-[transform,background-color] duration-[var(--duration-base)] ease-[var(--ease-standard)] ${
                active
                  ? "scale-x-100 bg-accent-fill"
                  : "scale-x-0 bg-hairline-strong group-hover:scale-x-100"
              }`}
            />
          </Link>
        );
      })}
    </nav>
  );
}

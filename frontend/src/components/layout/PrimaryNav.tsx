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
 * Desktop navigation inside the floating bar. The current section is a soft
 * filled pill (no underline, no colour shout); others stay quiet until hover.
 */
export function PrimaryNav({ items, label }: { items: NavItem[]; label: string }) {
  const pathname = usePathname() ?? "/";
  return (
    <nav aria-label={label} className="hidden items-center gap-0.5 text-sm md:flex">
      {items.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`press relative rounded-full px-3.5 py-1.5 whitespace-nowrap ${
              active ? "bg-fill font-medium text-ink" : "text-ink-2 hover:text-ink"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Icon, type IconName } from "@/components/ui/Icon";

import { isActive } from "./PrimaryNav";

export interface TabItem {
  href: string;
  label: string;
  icon: IconName;
}

/**
 * Phone navigation: a flat bar on the bottom edge (thumb reach), separated by
 * a hairline. The current tab is set in ink with a 2px emerald rule on its
 * top edge; the rule slides in, nothing bounces. Hidden from md up.
 */
export function MobileTabBar({ items, label }: { items: TabItem[]; label: string }) {
  const pathname = usePathname() ?? "/";
  return (
    <nav
      aria-label={label}
      className="fixed inset-x-0 bottom-0 z-[var(--z-tabbar)] border-t border-hairline bg-canvas/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden"
    >
      <ul className="mx-auto flex h-14 max-w-lg items-stretch">
        {items.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`press relative flex h-full flex-col items-center justify-center gap-0.5 text-[10.5px] font-medium ${
                  active ? "text-ink" : "text-ink-3"
                }`}
              >
                <span
                  aria-hidden
                  className={`absolute inset-x-5 top-0 h-0.5 bg-accent-fill transition-transform duration-[var(--duration-base)] ease-[var(--ease-standard)] ${
                    active ? "scale-x-100" : "scale-x-0"
                  }`}
                />
                <Icon
                  name={item.icon}
                  className={`size-5 ${active ? "text-accent" : ""}`}
                  strokeWidth={active ? 1.9 : 1.6}
                />
                <span className="max-w-full truncate px-1">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

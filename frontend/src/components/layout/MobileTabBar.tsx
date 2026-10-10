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
 * Phone navigation: a floating tab bar at thumb height, like a native app.
 * The active tab's icon fills its pill and rises a little; labels stay small.
 * Hidden from md up (the floating top bar takes over).
 */
export function MobileTabBar({ items, label }: { items: TabItem[]; label: string }) {
  const pathname = usePathname() ?? "/";
  return (
    <nav
      aria-label={label}
      className="fixed inset-x-0 bottom-0 z-[var(--z-tabbar)] px-3 pb-[max(env(safe-area-inset-bottom),0.5rem)] md:hidden"
    >
      <ul className="surface-float mx-auto flex max-w-md items-stretch justify-between rounded-[1.375rem] px-1.5 py-1.5">
        {items.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`press flex flex-col items-center gap-0.5 rounded-2xl py-1.5 text-[10.5px] font-medium ${
                  active ? "text-accent" : "text-ink-3"
                }`}
              >
                <span
                  className={`grid h-7 w-11 place-items-center rounded-full transition-[background-color,translate] duration-[var(--duration-base)] ease-[var(--ease-spring)] ${
                    active ? "-translate-y-px bg-accent-tint" : ""
                  }`}
                >
                  <Icon name={item.icon} className="size-[19px]" strokeWidth={active ? 2 : 1.75} />
                </span>
                <span className="max-w-full truncate px-1">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

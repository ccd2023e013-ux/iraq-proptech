"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Renders its children except on full-bleed app routes (the map fills the whole
 * screen there, so page chrome such as the footer would only add a scroll).
 */
export function HideOnRoutes({ routes, children }: { routes: string[]; children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const hidden = routes.some((r) => pathname === r || pathname.startsWith(`${r}/`));
  return hidden ? null : <>{children}</>;
}

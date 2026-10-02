import "server-only";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";

import { REFRESH_COOKIE, hasPermission, safeNextPath } from "@/lib/auth/routing";
import { getCurrentUser } from "@/lib/auth/session";
import type { Me } from "@/types/auth";

/** For protected pages: the current user, or a redirect to refresh / sign in. */
export async function requireUser(): Promise<Me> {
  const me = await getCurrentUser();
  if (me) return me;
  const next = safeNextPath((await headers()).get("x-pathname"));
  const target = (await cookies()).has(REFRESH_COOKIE) ? "/auth/refresh" : "/login";
  redirect(`${target}?next=${encodeURIComponent(next)}`);
}

/** Like requireUser, but also requires a permission (otherwise 404 to avoid probing). */
export async function requirePermission(permission: string): Promise<Me> {
  const me = await requireUser();
  if (!hasPermission(me.permissions, permission)) redirect("/dashboard?denied=1");
  return me;
}

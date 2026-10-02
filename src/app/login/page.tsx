import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthShell } from "@/features/auth/AuthShell";
import { LoginForm } from "@/features/auth/LoginForm";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { safeNextPath } from "@/lib/auth/routing";
import { getCurrentUser } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  if (await getCurrentUser()) redirect(safeNextPath(next));
  const dict = getDictionary(await getRequestLocale());
  return (
    <AuthShell
      title={dict.auth.loginTitle}
      subtitle={dict.auth.loginSubtitle}
      footer={
        <div className="flex flex-col gap-2">
          <Link href="/forgot-password" className="text-brand-700 hover:underline">
            {dict.auth.forgotLink}
          </Link>
          <span>
            {dict.auth.noAccount}{" "}
            <Link href="/register" className="font-medium text-brand-700 hover:underline">
              {dict.nav.register}
            </Link>
          </span>
        </div>
      }
    >
      <LoginForm dict={dict} next={next} />
    </AuthShell>
  );
}

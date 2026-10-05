import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthLink, AuthShell } from "@/features/auth/AuthShell";
import { LoginForm } from "@/features/auth/LoginForm";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { safeNextPath } from "@/lib/auth/routing";
import { getCurrentUser } from "@/lib/auth/session";
import { first, type RawParams } from "@/lib/search";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.auth.loginTitle };
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<RawParams> }) {
  const next = first((await searchParams).next);
  if (await getCurrentUser()) redirect(safeNextPath(next));
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  return (
    <AuthShell
      dict={dict}
      locale={locale}
      title={dict.auth.loginTitle}
      subtitle={dict.auth.loginSubtitle}
      footer={
        <p>
          {dict.auth.noAccount} <AuthLink href="/register">{dict.auth.submitRegister}</AuthLink>
        </p>
      }
    >
      <LoginForm dict={dict} next={next} />
    </AuthShell>
  );
}

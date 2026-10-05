import type { Metadata } from "next";

import { AuthLink, AuthShell } from "@/features/auth/AuthShell";
import { ResetPasswordForm } from "@/features/auth/RecoveryForms";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { first, type RawParams } from "@/lib/search";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.auth.resetTitle, referrer: "no-referrer" };
}

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<RawParams>;
}) {
  const token = first((await searchParams).token) ?? null;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  return (
    <AuthShell
      dict={dict}
      locale={locale}
      title={dict.auth.resetTitle}
      footer={<AuthLink href="/forgot-password">{dict.auth.forgotLink}</AuthLink>}
    >
      <ResetPasswordForm dict={dict} token={token} />
    </AuthShell>
  );
}

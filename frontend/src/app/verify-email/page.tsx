import type { Metadata } from "next";

import { AuthShell } from "@/features/auth/AuthShell";
import { VerifyEmail } from "@/features/auth/RecoveryForms";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { first, type RawParams } from "@/lib/search";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.auth.verifyTitle, referrer: "no-referrer" };
}

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<RawParams>;
}) {
  const token = first((await searchParams).token) ?? null;
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  return (
    <AuthShell dict={dict} locale={locale} title={dict.auth.verifyTitle}>
      <VerifyEmail dict={dict} token={token} />
    </AuthShell>
  );
}

import type { Metadata } from "next";

import { AuthLink, AuthShell } from "@/features/auth/AuthShell";
import { ForgotPasswordForm } from "@/features/auth/RecoveryForms";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { emailDeliveryAvailable } from "@/lib/auth/capabilities";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.auth.forgotTitle };
}

export default async function ForgotPasswordPage() {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const emailDelivery = await emailDeliveryAvailable();
  return (
    <AuthShell
      dict={dict}
      locale={locale}
      title={dict.auth.forgotTitle}
      subtitle={emailDelivery ? dict.auth.forgotSubtitle : undefined}
      footer={<AuthLink href="/login">{dict.auth.submitLogin}</AuthLink>}
    >
      <ForgotPasswordForm dict={dict} emailDelivery={emailDelivery} />
    </AuthShell>
  );
}

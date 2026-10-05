import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthLink, AuthShell } from "@/features/auth/AuthShell";
import { RegisterForm } from "@/features/auth/RegisterForm";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { emailDeliveryAvailable } from "@/lib/auth/capabilities";
import { getCurrentUser } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const dict = getDictionary(await getRequestLocale());
  return { title: dict.auth.registerTitle };
}

export default async function RegisterPage() {
  if (await getCurrentUser()) redirect("/dashboard");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const emailDelivery = await emailDeliveryAvailable();
  return (
    <AuthShell
      dict={dict}
      locale={locale}
      title={dict.auth.registerTitle}
      subtitle={dict.auth.registerSubtitle}
      footer={
        <p>
          {dict.auth.haveAccount} <AuthLink href="/login">{dict.auth.submitLogin}</AuthLink>
        </p>
      }
    >
      <RegisterForm dict={dict} locale={locale} emailDelivery={emailDelivery} />
    </AuthShell>
  );
}

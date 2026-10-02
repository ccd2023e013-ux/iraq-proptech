import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthShell } from "@/features/auth/AuthShell";
import { RegisterForm } from "@/features/auth/RegisterForm";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { getCurrentUser } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

export default async function RegisterPage() {
  if (await getCurrentUser()) redirect("/dashboard");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  return (
    <AuthShell
      title={dict.auth.registerTitle}
      subtitle={dict.auth.registerSubtitle}
      footer={
        <span>
          {dict.auth.haveAccount}{" "}
          <Link href="/login" className="font-medium text-brand-700 hover:underline">
            {dict.nav.login}
          </Link>
        </span>
      }
    >
      <RegisterForm dict={dict} locale={locale} />
    </AuthShell>
  );
}

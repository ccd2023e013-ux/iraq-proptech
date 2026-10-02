import { AuthShell } from "@/features/auth/AuthShell";
import { ForgotPasswordForm } from "@/features/auth/RecoveryForms";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";

export default async function ForgotPasswordPage() {
  const dict = getDictionary(await getRequestLocale());
  return (
    <AuthShell title={dict.auth.forgotTitle} subtitle={dict.auth.forgotSubtitle}>
      <ForgotPasswordForm dict={dict} />
    </AuthShell>
  );
}

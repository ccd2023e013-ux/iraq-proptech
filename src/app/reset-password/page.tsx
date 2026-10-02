import { AuthShell } from "@/features/auth/AuthShell";
import { ResetPasswordForm } from "@/features/auth/RecoveryForms";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;
  const dict = getDictionary(await getRequestLocale());
  return (
    <AuthShell title={dict.auth.resetTitle}>
      <ResetPasswordForm dict={dict} token={token ?? null} />
    </AuthShell>
  );
}

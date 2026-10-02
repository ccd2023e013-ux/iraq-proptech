import { AuthShell } from "@/features/auth/AuthShell";
import { VerifyEmail } from "@/features/auth/RecoveryForms";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;
  const dict = getDictionary(await getRequestLocale());
  return (
    <AuthShell title={dict.auth.verifyTitle}>
      <VerifyEmail dict={dict} token={token ?? null} />
    </AuthShell>
  );
}

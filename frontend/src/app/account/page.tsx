import { Card } from "@/components/ui/Card";
import {
  ChangePasswordForm,
  ProfileForm,
  ResendVerification,
  SessionsList,
} from "@/features/account/AccountForms";
import { Alert } from "@/components/ui/Alert";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { requireUser } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

export default async function AccountPage() {
  const me = await requireUser();
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const { user } = me;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-8 sm:px-6">
      <h1 className="text-2xl font-bold text-brand-900">{dict.account.title}</h1>

      {!user.email_verified && (
        <Alert tone="warning" title={dict.auth.verifyPending}>
          <div className="mt-2">
            <ResendVerification dict={dict} />
          </div>
        </Alert>
      )}

      <Card title={dict.account.profile}>
        <ProfileForm dict={dict} user={user} />
      </Card>

      <Card title={dict.account.roles}>
        <ul className="flex flex-wrap gap-2">
          {user.roles.map((role) => (
            <li
              key={role}
              className="rounded-full bg-brand-50 px-3 py-1 text-sm font-medium text-brand-800"
            >
              {dict.roles[role]}
            </li>
          ))}
        </ul>
      </Card>

      <Card title={dict.account.security}>
        <h3 className="mb-3 text-sm font-semibold text-sand-700">{dict.account.changePassword}</h3>
        <ChangePasswordForm dict={dict} />
        <h3 className="mt-8 mb-3 text-sm font-semibold text-sand-700">{dict.account.sessions}</h3>
        <SessionsList dict={dict} locale={locale} />
      </Card>
    </div>
  );
}

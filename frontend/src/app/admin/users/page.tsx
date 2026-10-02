import { ActionButton } from "@/features/admin/ActionButton";
import { formatDateTime } from "@/features/crm/labels";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";
import { first, type RawParams } from "@/lib/search";

export const dynamic = "force-dynamic";

interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  status: string;
  roles: string[];
  created_at: string;
  last_login_at: string | null;
}

export default async function UsersPage({ searchParams }: { searchParams: Promise<RawParams> }) {
  const me = await requirePermission("users.read");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const a = dict.admin;
  const q = (first((await searchParams).q) ?? "").trim();
  const users = await serverApiFetch<{ items: AdminUser[]; total: number }>(
    `/api/v1/admin/users?page_size=50${q ? `&q=${encodeURIComponent(q)}` : ""}`,
  );
  const canSuspend = me.permissions.includes("users.suspend");

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-brand-900">
        {a.users}{" "}
        <span className="text-base font-normal text-sand-500 tabular">({users.total})</span>
      </h1>
      <form method="get" className="flex gap-2">
        <input
          name="q"
          defaultValue={q}
          placeholder={a.searchUsers}
          aria-label={a.searchUsers}
          className="h-10 min-w-0 flex-1 rounded-lg border border-sand-200 px-3 text-sm"
        />
      </form>
      <div className="overflow-x-auto rounded-[var(--radius-card)] border border-sand-200 bg-white">
        <table className="w-full min-w-[720px] text-sm">
          <tbody>
            {users.items.map((u) => (
              <tr key={u.id} className="border-b border-sand-100">
                <td className="p-3">
                  <p className="font-medium">{u.full_name}</p>
                  <p className="text-xs text-sand-500" dir="ltr">
                    {u.email}
                  </p>
                </td>
                <td className="p-3 text-xs">
                  {u.roles.map((r) => dict.roles[r as keyof typeof dict.roles] ?? r).join("، ")}
                </td>
                <td className="p-3 text-xs">{u.status}</td>
                <td className="p-3 text-xs text-sand-500">
                  {formatDateTime(u.created_at, locale)}
                </td>
                <td className="p-3">
                  {canSuspend && u.id !== me.user.id && u.status === "SUSPENDED" && (
                    <ActionButton
                      dict={dict}
                      label={a.reactivate}
                      path={`/api/v1/admin/users/${u.id}/reactivate`}
                      tone="good"
                    />
                  )}
                  {canSuspend && u.id !== me.user.id && u.status !== "SUSPENDED" && (
                    <ActionButton
                      dict={dict}
                      label={a.suspend}
                      path={`/api/v1/admin/users/${u.id}/suspend`}
                      body={{ reason: "{text}" }}
                      prompt={a.reasonPrompt}
                      tone="bad"
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

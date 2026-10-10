import { SettingEditor } from "@/features/admin/SettingEditor";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { requirePermission } from "@/lib/auth/guard";

export const dynamic = "force-dynamic";

interface Setting {
  key: string;
  value: unknown;
  default: unknown;
  description: string;
}

export default async function SettingsPage() {
  await requirePermission("settings.manage");
  const dict = getDictionary(await getRequestLocale());
  const a = dict.admin;
  const settings = await serverApiFetch<Setting[]>("/api/v1/admin/settings");
  return (
    <div className="flex flex-col gap-4">
      <h1 className="display-md text-ink">{a.settings}</h1>
      <ul className="flex flex-col gap-3">
        {settings.map((s) => (
          <li key={s.key} className="flex flex-col gap-2 surface-1 rounded-2xl p-4">
            <p className="font-mono text-sm" dir="ltr">
              {s.key}
            </p>
            <p className="text-xs text-sand-500" dir="ltr">
              {s.description} · {a.defaultValue}: {JSON.stringify(s.default)}
            </p>
            <SettingEditor dict={dict} settingKey={s.key} value={s.value} />
          </li>
        ))}
      </ul>
    </div>
  );
}

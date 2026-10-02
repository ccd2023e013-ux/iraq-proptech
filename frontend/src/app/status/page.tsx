import type { Metadata } from "next";

import { loadSystemStatus } from "@/features/system/loadSystemStatus";
import { SystemStatusPanel } from "@/features/system/SystemStatusPanel";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";

// Status must be live; never cached.
export const dynamic = "force-dynamic";

export const metadata: Metadata = { robots: { index: false } };

export default async function StatusPage() {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const status = await loadSystemStatus();
  return (
    <div className="mx-auto max-w-xl px-4 py-12 sm:px-6">
      <SystemStatusPanel result={status} dict={dict} />
    </div>
  );
}

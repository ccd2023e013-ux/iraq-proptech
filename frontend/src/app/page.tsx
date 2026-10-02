import { loadSystemStatus } from "@/features/system/loadSystemStatus";
import { SystemStatusPanel } from "@/features/system/SystemStatusPanel";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";

// Rendered per request: status must be live, and locale comes from cookies.
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const status = await loadSystemStatus();

  return (
    <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.4fr_1fr] lg:py-20">
      <section className="flex flex-col justify-center gap-6">
        <span className="w-fit rounded-full bg-gold-100 px-3 py-1 text-xs font-semibold text-gold-700">
          {dict.home.badge}
        </span>
        <h1 className="text-4xl leading-tight font-bold text-brand-900 sm:text-5xl">
          {dict.home.title}
        </h1>
        <p className="max-w-2xl text-lg text-sand-700">{dict.home.subtitle}</p>
        <p className="max-w-2xl border-s-4 border-gold-300 ps-4 text-sm text-sand-500">
          {dict.home.foundationNote}
        </p>
      </section>
      <aside className="self-center">
        <SystemStatusPanel result={status} dict={dict} />
      </aside>
    </div>
  );
}

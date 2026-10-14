import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { stagger } from "@/lib/motion";

export default async function NotFound() {
  const dict = getDictionary(await getRequestLocale());
  return (
    <div className="relative isolate mx-auto flex max-w-xl flex-col items-center px-4 py-24 text-center">
      <div aria-hidden className="stage-grid absolute inset-0 -z-10" />
      <div
        aria-hidden
        className="surface-1 reveal mb-6 grid size-14 place-items-center rounded-2xl"
      >
        <Icon name="pin" className="size-6 text-spatial" />
      </div>
      <p className="reveal kpi text-6xl text-ink-3" style={stagger(1)}>
        404
      </p>
      <h1 className="reveal display-md mt-3 text-ink" style={stagger(2)}>
        {dict.errors.NOT_FOUND}
      </h1>
      <div className="reveal mt-8 flex flex-wrap justify-center gap-2" style={stagger(3)}>
        <Link href="/" className="btn btn-primary">
          {dict.nav.home}
        </Link>
        <Link
          href="/map"
          className="press surface-1 inline-flex h-11 items-center gap-2 rounded-[var(--radius-control)] px-5 font-medium text-ink"
        >
          <Icon name="map" className="size-4 text-spatial" />
          {dict.nav.map}
        </Link>
      </div>
    </div>
  );
}

import Link from "next/link";

import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";

export default async function NotFound() {
  const dict = getDictionary(await getRequestLocale());
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <p className="mb-2 text-6xl font-bold text-brand-200 tabular">404</p>
      <h1 className="mb-6 text-xl font-semibold text-brand-900">{dict.errors.NOT_FOUND}</h1>
      <Link href="/" className="font-medium text-accent underline underline-offset-4">
        {dict.nav.home}
      </Link>
    </div>
  );
}

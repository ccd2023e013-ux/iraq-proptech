import { ListingForm } from "@/features/listings/ListingForm";
import { loadListingReference } from "@/features/listings/reference";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { requirePermission } from "@/lib/auth/guard";
import { resolveMapConfig } from "@/lib/map/provider";

export const dynamic = "force-dynamic";

export default async function NewListingPage() {
  await requirePermission("properties.create");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const reference = await loadListingReference();
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-8 sm:px-6">
      <h1 className="text-2xl font-bold text-brand-900">{dict.listingForm.newTitle}</h1>
      <ListingForm
        dict={dict}
        locale={locale}
        reference={reference}
        mapConfig={resolveMapConfig(process.env)}
        initial={null}
      />
    </div>
  );
}

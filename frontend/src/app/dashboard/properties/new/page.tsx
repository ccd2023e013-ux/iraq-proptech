import { PageHeader } from "@/components/ui/PageHeader";
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
    <div className="page flex flex-col gap-6 pb-8">
      <PageHeader title={dict.listingForm.newTitle} />
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

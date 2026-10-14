import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { redirect } from "next/navigation";

import { PropertyCard } from "@/features/properties/PropertyCard";
import { getDictionary } from "@/i18n";
import { getRequestLocale } from "@/i18n/server";
import { serverApiFetch } from "@/lib/api/server";
import { getCurrentUser } from "@/lib/auth/session";
import type { PropertyCard as Card, ReferenceItem } from "@/types/property";

export const dynamic = "force-dynamic";

interface Page {
  items: Card[];
  total: number;
}

export default async function FavoritesPage() {
  const me = await getCurrentUser();
  if (!me) redirect("/login?next=/favorites");
  const locale = await getRequestLocale();
  const dict = getDictionary(locale);
  const [page, types] = await Promise.all([
    serverApiFetch<Page>("/api/v1/me/favorites?page_size=100"),
    serverApiFetch<ReferenceItem[]>("/api/v1/reference/property-types"),
  ]);
  const typeNames = new Map(types.map((t) => [t.code, locale === "ar" ? t.name_ar : t.name_en]));

  return (
    <div className="page flex flex-col gap-6 pb-8">
      <PageHeader title={dict.favorites.title} />
      {page.items.length === 0 ? (
        <EmptyState
          title={dict.favorites.empty}
          glyph="heart"
          action={{ href: "/properties", label: dict.nav.properties }}
          secondary={{ href: "/map", label: dict.nav.map }}
        />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {page.items.map((card) => (
            <li key={card.id}>
              <PropertyCard
                card={card}
                dict={dict}
                locale={locale}
                typeName={typeNames.get(card.property_type_code)}
                favorite
                signedIn
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

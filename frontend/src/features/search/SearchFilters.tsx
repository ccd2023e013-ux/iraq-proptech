"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { type RawParams, all, first, toApiQuery, withParam } from "@/lib/search";
import type { Place, ReferenceItem } from "@/types/property";

const PURPOSES = ["SALE", "RENT", "LEASE", "RAHN", "MUSATAHA", "EXCHANGE"] as const;
const SORTS = ["newest", "price_asc", "price_desc", "area_desc", "area_asc", "relevance"] as const;

export function SearchFilters({
  dict,
  locale,
  params,
  types,
  governorates,
  basePath = "/properties",
}: {
  dict: Dictionary;
  locale: Locale;
  params: RawParams;
  types: ReferenceItem[];
  governorates: Place[];
  basePath?: string;
}) {
  const router = useRouter();
  const s = dict.search;
  const name = (p: { name_ar: string; name_en: string }) =>
    locale === "ar" ? p.name_ar : p.name_en;
  const [form, setForm] = useState(() => ({
    q: first(params.q) ?? "",
    governorate_id: first(params.governorate_id) ?? "",
    city_id: first(params.city_id) ?? "",
    purpose: first(params.purpose) ?? "",
    property_types: all(params.property_types),
    currency: first(params.currency) ?? "IQD",
    min_price: first(params.min_price) ?? "",
    max_price: first(params.max_price) ?? "",
    min_area: first(params.min_area) ?? "",
    max_area: first(params.max_area) ?? "",
    bedrooms_min: first(params.bedrooms_min) ?? "",
    verified_only: first(params.verified_only) === "true",
    exclude_demo: first(params.exclude_demo) === "true",
  }));
  const [cities, setCities] = useState<Place[]>([]);

  useEffect(() => {
    if (!form.governorate_id) {
      setCities([]);
      return;
    }
    let cancelled = false;
    apiFetch<Place[]>(`/api/v1/locations/cities?governorate_id=${form.governorate_id}`)
      .then((rows) => !cancelled && setCities(rows))
      .catch(() => !cancelled && setCities([]));
    return () => {
      cancelled = true;
    };
  }, [form.governorate_id]);

  function go(query: string) {
    router.push(query ? `${basePath}?${query}` : basePath);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const hasPrice = form.min_price !== "" || form.max_price !== "";
    go(
      toApiQuery({
        // keep non-form params (map viewport, sort) but reset the page
        bbox: first(params.bbox),
        sort: first(params.sort),
        q: form.q.trim(),
        governorate_id: form.governorate_id,
        city_id: form.city_id,
        purpose: form.purpose,
        property_types: form.property_types,
        currency: hasPrice ? form.currency : undefined,
        min_price: form.min_price,
        max_price: form.max_price,
        min_area: form.min_area,
        max_area: form.max_area,
        bedrooms_min: form.bedrooms_min,
        verified_only: form.verified_only ? "true" : undefined,
        exclude_demo: form.exclude_demo ? "true" : undefined,
      }),
    );
  }

  const input = "h-10 w-full rounded-lg border border-sand-200 bg-white px-3 text-sm";
  const label = "flex flex-col gap-1 text-xs font-medium text-sand-700";

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-label={s.filters}>
      <input
        type="search"
        value={form.q}
        onChange={(e) => setForm({ ...form, q: e.target.value })}
        placeholder={s.keyword}
        aria-label={s.keyword}
        className={input}
      />
      <div className="grid grid-cols-2 gap-3">
        <label className={label}>
          {dict.listingForm.governorate}
          <select
            className={input}
            value={form.governorate_id}
            onChange={(e) => setForm({ ...form, governorate_id: e.target.value, city_id: "" })}
          >
            <option value="">{s.allGovernorates}</option>
            {governorates.map((g) => (
              <option key={g.id} value={g.id}>
                {name(g)}
              </option>
            ))}
          </select>
        </label>
        <label className={label}>
          {dict.listingForm.city}
          <select
            className={input}
            value={form.city_id}
            disabled={!cities.length}
            onChange={(e) => setForm({ ...form, city_id: e.target.value })}
          >
            <option value="">{s.allCities}</option>
            {cities.map((c) => (
              <option key={c.id} value={c.id}>
                {name(c)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className={label}>
        {dict.property.purpose}
        <select
          className={input}
          value={form.purpose}
          onChange={(e) => setForm({ ...form, purpose: e.target.value })}
        >
          <option value="">{s.anyPurpose}</option>
          {PURPOSES.map((p) => (
            <option key={p} value={p}>
              {dict.listing.purposes[p]}
            </option>
          ))}
        </select>
      </label>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-xs font-medium text-sand-700">{s.types}</legend>
        <div className="flex flex-wrap gap-1.5">
          {types.map((t) => {
            const on = form.property_types.includes(t.code);
            return (
              <button
                key={t.code}
                type="button"
                aria-pressed={on}
                onClick={() =>
                  setForm({
                    ...form,
                    property_types: on
                      ? form.property_types.filter((c) => c !== t.code)
                      : [...form.property_types, t.code],
                  })
                }
                className={`rounded-full border px-3 py-1 text-xs transition ${on ? "border-brand-600 bg-brand-600 text-white" : "border-sand-200 bg-white text-sand-700 hover:border-brand-300"}`}
              >
                {name(t)}
              </button>
            );
          })}
        </div>
      </fieldset>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-xs font-medium text-sand-700">{s.priceRange}</legend>
        <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
          <input
            className={input}
            inputMode="numeric"
            dir="ltr"
            placeholder={s.minPrice}
            aria-label={`${s.priceRange} ${s.minPrice}`}
            value={form.min_price}
            onChange={(e) => setForm({ ...form, min_price: e.target.value.replace(/[^\d]/g, "") })}
          />
          <input
            className={input}
            inputMode="numeric"
            dir="ltr"
            placeholder={s.maxPrice}
            aria-label={`${s.priceRange} ${s.maxPrice}`}
            value={form.max_price}
            onChange={(e) => setForm({ ...form, max_price: e.target.value.replace(/[^\d]/g, "") })}
          />
          <select
            className={`${input} w-auto`}
            aria-label={dict.listingForm.currency}
            value={form.currency}
            onChange={(e) => setForm({ ...form, currency: e.target.value })}
          >
            <option value="IQD">IQD</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <p className="text-[11px] text-sand-500">{s.currencyNote}</p>
      </fieldset>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-xs font-medium text-sand-700">{s.areaRange}</legend>
        <div className="grid grid-cols-2 gap-2">
          <input
            className={input}
            inputMode="numeric"
            dir="ltr"
            placeholder={s.minPrice}
            aria-label={`${s.areaRange} ${s.minPrice}`}
            value={form.min_area}
            onChange={(e) => setForm({ ...form, min_area: e.target.value.replace(/[^\d]/g, "") })}
          />
          <input
            className={input}
            inputMode="numeric"
            dir="ltr"
            placeholder={s.maxPrice}
            aria-label={`${s.areaRange} ${s.maxPrice}`}
            value={form.max_area}
            onChange={(e) => setForm({ ...form, max_area: e.target.value.replace(/[^\d]/g, "") })}
          />
        </div>
      </fieldset>
      <label className={label}>
        {s.minBedrooms}
        <select
          className={input}
          value={form.bedrooms_min}
          onChange={(e) => setForm({ ...form, bedrooms_min: e.target.value })}
        >
          <option value="">{s.any}</option>
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <option key={n} value={n}>
              {n}+
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.verified_only}
          onChange={(e) => setForm({ ...form, verified_only: e.target.checked })}
        />
        {s.verifiedOnly}
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.exclude_demo}
          onChange={(e) => setForm({ ...form, exclude_demo: e.target.checked })}
        />
        {s.excludeDemo}
      </label>
      <div className="flex gap-2">
        <Button type="submit" block>
          {s.apply}
        </Button>
        <Button variant="ghost" onClick={() => go("")}>
          {s.reset}
        </Button>
      </div>
    </form>
  );
}

export function SortSelect({
  dict,
  params,
  basePath = "/properties",
}: {
  dict: Dictionary;
  params: RawParams;
  basePath?: string;
}) {
  const router = useRouter();
  const current = first(params.sort) ?? "newest";
  return (
    <label className="flex items-center gap-2 text-sm text-sand-700">
      {dict.search.sort}
      <select
        value={current}
        onChange={(e) => router.push(`${basePath}?${withParam(params, "sort", e.target.value)}`)}
        className="h-9 rounded-lg border border-sand-200 bg-white px-2 text-sm"
      >
        {SORTS.filter((sort) => sort !== "relevance" || first(params.q)).map((sort) => (
          <option key={sort} value={sort}>
            {dict.search.sorts[sort]}
          </option>
        ))}
      </select>
    </label>
  );
}

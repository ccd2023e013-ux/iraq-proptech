"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { AuthoringAssistant } from "@/features/ai/AuthoringAssistant";
import { LocationPicker, type Resolved } from "@/features/map/LocationPicker";
import type { Dictionary } from "@/i18n";
import type { Locale } from "@/i18n/config";
import { apiFetch } from "@/lib/api/client";
import { describeError } from "@/lib/errors";
import type { MapConfig } from "@/lib/map/provider";
import type {
  Condition,
  Currency,
  Furnishing,
  LocationPrivacy,
  OwnershipDocument,
  Place,
  Property,
  Purpose,
  ReferenceItem,
  RentPeriod,
} from "@/types/property";

const PURPOSES: Purpose[] = ["SALE", "RENT", "LEASE", "RAHN", "MUSATAHA", "EXCHANGE"];
const RENT_LIKE: Purpose[] = ["RENT", "LEASE"];
const PERIODS: RentPeriod[] = ["MONTHLY", "YEARLY", "DAILY"];
const CONDITIONS: Condition[] = [
  "NEW",
  "EXCELLENT",
  "GOOD",
  "NEEDS_RENOVATION",
  "UNDER_CONSTRUCTION",
];
const FURNISHING: Furnishing[] = ["UNFURNISHED", "SEMI_FURNISHED", "FURNISHED"];
const OWNERSHIP: OwnershipDocument[] = [
  "TAPU",
  "AGRICULTURAL",
  "HUJJA",
  "INVESTMENT",
  "MUSATAHA",
  "SHARED",
  "OTHER",
  "UNKNOWN",
];
const PRIVACY: LocationPrivacy[] = ["APPROXIMATE", "EXACT", "HIDDEN"];

export interface ListingReference {
  types: ReferenceItem[];
  amenities: ReferenceItem[];
  governorates: Place[];
}

interface FormState {
  title_ar: string;
  title_en: string;
  description_ar: string;
  description_en: string;
  property_type_code: string;
  purpose: Purpose;
  rent_period: RentPeriod | "";
  price_amount: string;
  currency: Currency;
  price_on_request: boolean;
  negotiable: boolean;
  area_m2: string;
  land_area_m2: string;
  bedrooms: string;
  bathrooms: string;
  floors: string;
  floor_number: string;
  year_built: string;
  condition: Condition | "";
  furnishing: Furnishing | "";
  ownership_document: OwnershipDocument;
  amenities: string[];
  governorate_id: string;
  city_id: string;
  district_id: string;
  neighborhood_id: string;
  street: string;
  address_text: string;
  lat: string;
  lon: string;
  location_privacy: LocationPrivacy;
  show_phone: boolean;
  allow_whatsapp: boolean;
}

function initialState(p: Property | null): FormState {
  const loc = p?.exact_location ?? null;
  return {
    title_ar: p?.title_ar ?? "",
    title_en: p?.title_en ?? "",
    description_ar: p?.description_ar ?? "",
    description_en: p?.description_en ?? "",
    property_type_code: p?.property_type_code ?? "",
    purpose: p?.purpose ?? "SALE",
    rent_period: p?.rent_period ?? "",
    price_amount: p?.price_amount ? String(Number(p.price_amount)) : "",
    currency: p?.currency ?? "IQD",
    price_on_request: p?.price_on_request ?? false,
    negotiable: p?.negotiable ?? false,
    area_m2: p?.area_m2 ? String(Number(p.area_m2)) : "",
    land_area_m2: p?.land_area_m2 ? String(Number(p.land_area_m2)) : "",
    bedrooms: p?.bedrooms?.toString() ?? "",
    bathrooms: p?.bathrooms?.toString() ?? "",
    floors: p?.floors?.toString() ?? "",
    floor_number: p?.floor_number?.toString() ?? "",
    year_built: p?.year_built?.toString() ?? "",
    condition: p?.condition ?? "",
    furnishing: p?.furnishing ?? "",
    ownership_document: p?.ownership_document ?? "UNKNOWN",
    amenities: p?.amenities ?? [],
    governorate_id: p?.governorate.id ?? "",
    city_id: p?.city.id ?? "",
    district_id: p?.district?.id ?? "",
    neighborhood_id: p?.neighborhood?.id ?? "",
    street: p?.street ?? "",
    address_text: p?.address_text ?? "",
    lat: loc ? String(loc.lat) : "",
    lon: loc ? String(loc.lon) : "",
    location_privacy: p?.location_privacy ?? "APPROXIMATE",
    show_phone: p?.show_phone ?? false,
    allow_whatsapp: p?.allow_whatsapp ?? false,
  };
}

const intOrNull = (v: string) => (v.trim() === "" ? null : Number.parseInt(v, 10));
const strOrNull = (v: string) => (v.trim() === "" ? null : v.trim());

/** Build the API payload; empty optional fields become null (never invented). */
export function toPayload(s: FormState) {
  const hasPoint = s.lat.trim() !== "" && s.lon.trim() !== "";
  return {
    title_ar: s.title_ar.trim(),
    title_en: strOrNull(s.title_en),
    description_ar: strOrNull(s.description_ar),
    description_en: strOrNull(s.description_en),
    property_type_code: s.property_type_code,
    purpose: s.purpose,
    rent_period: RENT_LIKE.includes(s.purpose) ? s.rent_period || null : null,
    price_amount: s.price_on_request ? null : strOrNull(s.price_amount),
    currency: s.currency,
    price_on_request: s.price_on_request,
    negotiable: s.negotiable,
    area_m2: strOrNull(s.area_m2),
    land_area_m2: strOrNull(s.land_area_m2),
    bedrooms: intOrNull(s.bedrooms),
    bathrooms: intOrNull(s.bathrooms),
    floors: intOrNull(s.floors),
    floor_number: intOrNull(s.floor_number),
    year_built: intOrNull(s.year_built),
    condition: s.condition || null,
    furnishing: s.furnishing || null,
    ownership_document: s.ownership_document,
    amenities: s.amenities,
    governorate_id: s.governorate_id,
    city_id: s.city_id,
    district_id: s.district_id || null,
    neighborhood_id: s.neighborhood_id || null,
    street: strOrNull(s.street),
    address_text: strOrNull(s.address_text),
    location: hasPoint ? { lat: Number(s.lat), lon: Number(s.lon) } : null,
    location_privacy: s.location_privacy,
    show_phone: s.show_phone,
    allow_whatsapp: s.allow_whatsapp,
  };
}

function Select({
  label,
  value,
  onChange,
  children,
  required,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: ReactNode;
  required?: boolean;
  disabled?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm font-medium text-sand-900">
      {label}
      <select
        value={value}
        required={required}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 rounded-lg border border-sand-200 bg-surface px-3 font-normal disabled:bg-sand-100"
      >
        {children}
      </select>
    </label>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="rounded-[var(--radius-card)] border border-sand-200 bg-surface p-5 sm:p-6">
      <legend className="px-2 text-base font-semibold text-brand-900">{title}</legend>
      <div className="grid gap-4 sm:grid-cols-2">{children}</div>
    </fieldset>
  );
}

function usePlaces(path: string | null): Place[] {
  const [places, setPlaces] = useState<Place[]>([]);
  useEffect(() => {
    if (!path) {
      setPlaces([]);
      return;
    }
    let cancelled = false;
    apiFetch<Place[]>(path)
      .then((rows) => !cancelled && setPlaces(rows))
      .catch(() => !cancelled && setPlaces([]));
    return () => {
      cancelled = true;
    };
  }, [path]);
  return places;
}

export function ListingForm({
  dict,
  locale,
  reference,
  initial,
  mapConfig = null,
}: {
  dict: Dictionary;
  locale: Locale;
  reference: ListingReference;
  initial: Property | null;
  mapConfig?: MapConfig | null;
}) {
  const router = useRouter();
  const f = dict.listingForm;
  const [s, setS] = useState<FormState>(() => initialState(initial));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setSaved(false);
    setS((prev) => ({ ...prev, [key]: value }));
  };
  const name = (p: { name_ar: string; name_en: string }) =>
    locale === "ar" ? p.name_ar : p.name_en;

  const cities = usePlaces(
    s.governorate_id ? `/api/v1/locations/cities?governorate_id=${s.governorate_id}` : null,
  );
  const districts = usePlaces(
    s.city_id ? `/api/v1/locations/districts?city_id=${s.city_id}` : null,
  );
  const neighborhoods = usePlaces(
    s.district_id ? `/api/v1/locations/neighborhoods?district_id=${s.district_id}` : null,
  );

  function applyArea(r: Resolved) {
    setSaved(false);
    setS((prev) => ({
      ...prev,
      governorate_id: r.governorate?.id ?? prev.governorate_id,
      city_id: r.city?.id ?? (r.governorate ? "" : prev.city_id),
      district_id: r.district?.id ?? "",
      neighborhood_id: r.neighborhood?.id ?? "",
    }));
  }

  function fillMyLocation() {
    navigator.geolocation?.getCurrentPosition((pos) => {
      set("lat", pos.coords.latitude.toFixed(6));
      set("lon", pos.coords.longitude.toFixed(6));
    });
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const payload = toPayload(s);
      if (initial) {
        await apiFetch<Property>(`/api/v1/properties/${initial.id}`, {
          method: "PATCH",
          body: payload,
        });
        setSaved(true);
        router.refresh();
      } else {
        const created = await apiFetch<Property>("/api/v1/properties", {
          method: "POST",
          body: payload,
        });
        router.push(`/dashboard/properties/${created.id}`);
      }
    } catch (err) {
      setError(describeError(dict, err));
    } finally {
      setPending(false);
    }
  }

  const rentLike = RENT_LIKE.includes(s.purpose);

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-6">
      {error && <Alert tone="error">{error}</Alert>}

      <Section title={f.basics}>
        <TextField
          className="sm:col-span-2"
          label={f.titleAr}
          required
          minLength={5}
          maxLength={200}
          value={s.title_ar}
          onChange={(e) => set("title_ar", e.target.value)}
        />
        <TextField
          className="sm:col-span-2"
          label={f.titleEn}
          dir="ltr"
          maxLength={200}
          value={s.title_en}
          onChange={(e) => set("title_en", e.target.value)}
        />
        <label className="flex flex-col gap-1.5 text-sm font-medium text-sand-900 sm:col-span-2">
          {f.descriptionAr}
          <textarea
            rows={5}
            maxLength={8000}
            value={s.description_ar}
            onChange={(e) => set("description_ar", e.target.value)}
            className="rounded-lg border border-sand-200 bg-surface p-3 font-normal"
          />
        </label>
        <div className="sm:col-span-2">
          <AuthoringAssistant
            dict={dict}
            propertyId={initial?.id ?? null}
            currentDescription={s.description_ar}
            onUseDescription={(text) => set("description_ar", text)}
            onUseTitle={(text) => set("title_ar", text)}
          />
        </div>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-sand-900 sm:col-span-2">
          {f.descriptionEn}
          <textarea
            rows={3}
            dir="ltr"
            maxLength={8000}
            value={s.description_en}
            onChange={(e) => set("description_en", e.target.value)}
            className="rounded-lg border border-sand-200 bg-surface p-3 font-normal"
          />
        </label>
        <Select
          label={f.type}
          required
          value={s.property_type_code}
          onChange={(v) => set("property_type_code", v)}
        >
          <option value="">{f.choose}</option>
          {reference.types.map((t) => (
            <option key={t.code} value={t.code}>
              {name(t)}
            </option>
          ))}
        </Select>
        <Select label={f.purpose} value={s.purpose} onChange={(v) => set("purpose", v as Purpose)}>
          {PURPOSES.map((p) => (
            <option key={p} value={p}>
              {dict.listing.purposes[p]}
            </option>
          ))}
        </Select>
      </Section>

      <Section title={f.price}>
        {rentLike && (
          <Select
            label={f.rentPeriod}
            required
            value={s.rent_period}
            onChange={(v) => set("rent_period", v as RentPeriod)}
          >
            <option value="">{f.choose}</option>
            {PERIODS.map((p) => (
              <option key={p} value={p}>
                {dict.listing.rentPeriods[p]}
              </option>
            ))}
          </Select>
        )}
        <TextField
          label={f.priceAmount}
          inputMode="decimal"
          dir="ltr"
          disabled={s.price_on_request}
          required={!s.price_on_request}
          value={s.price_amount}
          onChange={(e) => set("price_amount", e.target.value.replace(/[^\d.]/g, ""))}
        />
        <Select
          label={f.currency}
          value={s.currency}
          onChange={(v) => set("currency", v as Currency)}
        >
          <option value="IQD">{dict.listing.currencies.IQD}</option>
          <option value="USD">{dict.listing.currencies.USD}</option>
        </Select>
        <p className="text-xs text-sand-500 sm:col-span-2">{f.currencyNote}</p>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={s.price_on_request}
            onChange={(e) => set("price_on_request", e.target.checked)}
          />
          {dict.listing.priceOnRequest}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={s.negotiable}
            onChange={(e) => set("negotiable", e.target.checked)}
          />
          {dict.listing.negotiable}
        </label>
      </Section>

      <Section title={f.details}>
        {(
          [
            ["area_m2", dict.listing.area],
            ["land_area_m2", dict.listing.landArea],
            ["bedrooms", dict.listing.bedrooms],
            ["bathrooms", dict.listing.bathrooms],
            ["floors", f.floors],
            ["floor_number", f.floorNumber],
            ["year_built", f.yearBuilt],
          ] as const
        ).map(([key, label]) => (
          <TextField
            key={key}
            label={label}
            inputMode="numeric"
            dir="ltr"
            value={s[key]}
            onChange={(e) => set(key, e.target.value.replace(/[^\d.-]/g, ""))}
          />
        ))}
        <Select
          label={f.condition}
          value={s.condition}
          onChange={(v) => set("condition", v as Condition)}
        >
          <option value="">{f.choose}</option>
          {CONDITIONS.map((c) => (
            <option key={c} value={c}>
              {dict.listing.conditions[c]}
            </option>
          ))}
        </Select>
        <Select
          label={f.furnishing}
          value={s.furnishing}
          onChange={(v) => set("furnishing", v as Furnishing)}
        >
          <option value="">{f.choose}</option>
          {FURNISHING.map((c) => (
            <option key={c} value={c}>
              {dict.listing.furnishing[c]}
            </option>
          ))}
        </Select>
        <div className="sm:col-span-2">
          <Select
            label={f.ownership}
            value={s.ownership_document}
            onChange={(v) => set("ownership_document", v as OwnershipDocument)}
          >
            {OWNERSHIP.map((c) => (
              <option key={c} value={c}>
                {dict.listing.ownership[c]}
              </option>
            ))}
          </Select>
          <p className="mt-1 text-xs text-sand-500">{f.ownershipNote}</p>
        </div>
      </Section>

      <Section title={f.amenities}>
        <div className="grid gap-2 sm:col-span-2 sm:grid-cols-3">
          {reference.amenities.map((a) => (
            <label key={a.code} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={s.amenities.includes(a.code)}
                onChange={(e) =>
                  set(
                    "amenities",
                    e.target.checked
                      ? [...s.amenities, a.code]
                      : s.amenities.filter((c) => c !== a.code),
                  )
                }
              />
              {name(a)}
            </label>
          ))}
        </div>
      </Section>

      <Section title={f.location}>
        <Select
          label={f.governorate}
          required
          value={s.governorate_id}
          onChange={(v) => {
            set("governorate_id", v);
            set("city_id", "");
            set("district_id", "");
            set("neighborhood_id", "");
          }}
        >
          <option value="">{f.choose}</option>
          {reference.governorates.map((g) => (
            <option key={g.id} value={g.id}>
              {name(g)}
            </option>
          ))}
        </Select>
        <Select
          label={f.city}
          required
          disabled={!cities.length}
          value={s.city_id}
          onChange={(v) => {
            set("city_id", v);
            set("district_id", "");
            set("neighborhood_id", "");
          }}
        >
          <option value="">{f.choose}</option>
          {cities.map((c) => (
            <option key={c.id} value={c.id}>
              {name(c)}
            </option>
          ))}
        </Select>
        <Select
          label={f.district}
          disabled={!districts.length}
          value={s.district_id}
          onChange={(v) => {
            set("district_id", v);
            set("neighborhood_id", "");
          }}
        >
          <option value="">{f.choose}</option>
          {districts.map((d) => (
            <option key={d.id} value={d.id}>
              {name(d)}
            </option>
          ))}
        </Select>
        <Select
          label={f.neighborhood}
          disabled={!neighborhoods.length}
          value={s.neighborhood_id}
          onChange={(v) => set("neighborhood_id", v)}
        >
          <option value="">{f.choose}</option>
          {neighborhoods.map((n) => (
            <option key={n.id} value={n.id}>
              {name(n)}
            </option>
          ))}
        </Select>
        <TextField
          label={f.street}
          value={s.street}
          onChange={(e) => set("street", e.target.value)}
        />
        <TextField
          label={f.addressText}
          value={s.address_text}
          onChange={(e) => set("address_text", e.target.value)}
        />
        <TextField
          label={f.latitude}
          dir="ltr"
          inputMode="decimal"
          value={s.lat}
          onChange={(e) => set("lat", e.target.value)}
        />
        <TextField
          label={f.longitude}
          dir="ltr"
          inputMode="decimal"
          value={s.lon}
          onChange={(e) => set("lon", e.target.value)}
        />
        {mapConfig && (
          <div className="sm:col-span-2">
            <LocationPicker
              config={mapConfig}
              dict={dict}
              locale={locale}
              lat={s.lat.trim() === "" ? null : Number(s.lat)}
              lon={s.lon.trim() === "" ? null : Number(s.lon)}
              onPick={(lat, lon) => {
                set("lat", String(lat));
                set("lon", String(lon));
              }}
              onApply={applyArea}
            />
          </div>
        )}
        <div className="sm:col-span-2">
          <Button variant="secondary" size="sm" onClick={fillMyLocation}>
            {f.useMyLocation}
          </Button>
        </div>
        <div className="sm:col-span-2">
          <Select
            label={f.privacy}
            value={s.location_privacy}
            onChange={(v) => set("location_privacy", v as LocationPrivacy)}
          >
            {PRIVACY.map((p) => (
              <option key={p} value={p}>
                {dict.listing.privacy[p]}
              </option>
            ))}
          </Select>
        </div>
      </Section>

      <Section title={f.contact}>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={s.show_phone}
            onChange={(e) => set("show_phone", e.target.checked)}
          />
          {f.showPhone}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={s.allow_whatsapp}
            onChange={(e) => set("allow_whatsapp", e.target.checked)}
          />
          {f.allowWhatsapp}
        </label>
      </Section>

      <div className="flex items-center gap-3">
        <Button type="submit" size="lg" loading={pending}>
          {initial ? f.save : f.create}
        </Button>
        {saved && <span className="text-sm text-success">{f.saved}</span>}
      </div>
    </form>
  );
}

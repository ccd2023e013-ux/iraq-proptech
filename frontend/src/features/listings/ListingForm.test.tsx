import { describe, expect, it } from "vitest";

import { toPayload } from "./ListingForm";

const base = {
  title_ar: "  بيت للبيع  ",
  title_en: "",
  description_ar: "",
  description_en: "",
  property_type_code: "HOUSE",
  purpose: "SALE" as const,
  rent_period: "MONTHLY" as const,
  price_amount: "250000000",
  currency: "IQD" as const,
  price_on_request: false,
  negotiable: true,
  area_m2: "200",
  land_area_m2: "",
  bedrooms: "3",
  bathrooms: "",
  floors: "",
  floor_number: "",
  year_built: "",
  condition: "" as const,
  furnishing: "" as const,
  ownership_document: "UNKNOWN" as const,
  amenities: ["PARKING"],
  governorate_id: "g",
  city_id: "c",
  district_id: "",
  neighborhood_id: "",
  street: "",
  address_text: "",
  lat: "",
  lon: "",
  location_privacy: "APPROXIMATE" as const,
  show_phone: false,
  allow_whatsapp: false,
};

describe("toPayload", () => {
  it("sends null for every empty optional field (nothing is invented)", () => {
    const payload = toPayload(base);
    expect(payload.title_ar).toBe("بيت للبيع");
    expect(payload.title_en).toBeNull();
    expect(payload.bathrooms).toBeNull();
    expect(payload.location).toBeNull();
    expect(payload.condition).toBeNull();
    expect(payload.district_id).toBeNull();
    expect(payload.bedrooms).toBe(3);
  });

  it("drops the rent period for sales and the price when on request", () => {
    expect(toPayload(base).rent_period).toBeNull();
    const onRequest = toPayload({ ...base, price_on_request: true });
    expect(onRequest.price_amount).toBeNull();
    const rent = toPayload({ ...base, purpose: "RENT" });
    expect(rent.rent_period).toBe("MONTHLY");
  });

  it("keeps the chosen currency untouched", () => {
    expect(toPayload({ ...base, currency: "USD", price_amount: "185000" })).toMatchObject({
      currency: "USD",
      price_amount: "185000",
    });
  });

  it("includes coordinates only when both are given", () => {
    expect(toPayload({ ...base, lat: "30.5", lon: "" }).location).toBeNull();
    expect(toPayload({ ...base, lat: "30.5", lon: "47.8" }).location).toEqual({
      lat: 30.5,
      lon: 47.8,
    });
  });
});

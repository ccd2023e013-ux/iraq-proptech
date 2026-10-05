export interface MarketCity {
  city_id: string;
  slug: string;
  name_ar: string;
  name_en: string;
  governorate_code: string;
  listings: number;
  includes_demo: boolean;
}

export interface MarketSegment {
  property_type_code: string;
  purpose: "SALE" | "RENT";
  currency: "IQD" | "USD";
  listings: number;
  median_price: string | null;
  median_price_per_m2: string | null;
}

export interface MarketSummary {
  city_id: string | null;
  data_class: "platform";
  basis: string;
  includes_demo: boolean;
  listings: number;
  segments: MarketSegment[];
  generated_at: string;
}

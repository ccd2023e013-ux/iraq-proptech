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

export type MarketKind = "FACT" | "OBSERVED" | "ESTIMATE" | "AI_INTERPRETATION" | "SIMULATION";

export interface MarketStatement {
  kind: MarketKind;
  origin: "platform" | "observed" | "model" | "ai" | "scenario";
  section: "supply" | "prices" | "dynamics" | "demand" | "areas" | "quality" | "interpretation";
  key: string;
  params: Record<string, unknown>;
  text: string | null;
  sample: number | null;
  demo: boolean;
}

export interface MarketUnavailable {
  metric: string;
  reason: string;
  detail: Record<string, unknown>;
}

export interface MarketProvenance {
  source: string;
  coverage: string;
  observation_from: string | null;
  observation_to: string | null;
  sample_listings: number;
  includes_demo: boolean;
  demo_share: number;
  methodology: string[];
  confidence: "none" | "low" | "medium" | "high";
  last_update: string;
}

export interface MarketSegmentRow {
  property_type_code: string;
  type_ar: string;
  type_en: string;
  purpose: string;
  currency: "IQD" | "USD";
  listings: number;
  median_price: string | null;
  p25_price: string | null;
  p75_price: string | null;
  median_price_per_m2: string | null;
}

export interface MarketAreaRow {
  level: "city" | "district";
  id: string;
  name_ar: string;
  name_en: string | null;
  active_listings: number;
  median_price_per_m2: string | null;
  currency: "IQD" | "USD" | null;
  sample: number;
}

export interface MarketReport {
  scope: {
    level: "iraq" | "governorate" | "city" | "district";
    id: string | null;
    name_ar: string;
    name_en: string | null;
  };
  provenance: MarketProvenance;
  statements: MarketStatement[];
  segments: MarketSegmentRow[];
  areas: MarketAreaRow[];
  unavailable: MarketUnavailable[];
  supply_history: { day: string; active_listings: number }[];
  disclaimer: string;
  provider: string | null;
}

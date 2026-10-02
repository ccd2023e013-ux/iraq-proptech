export interface AIEnvelope<R = Record<string, unknown>> {
  feature: string;
  kind: "generated" | "estimate" | "analysis" | "extraction" | "ranking";
  provider: string;
  model: string;
  generation_id: string | null;
  confidence: number | null;
  methodology: string;
  data_sources: string[];
  limitations: string[];
  disclaimer: string | null;
  created_at: string;
  result: R;
}

export interface PriceResult {
  currency: "IQD" | "USD";
  comparable_count: number;
  comparable_scope: string;
  value: string | null;
  low: string | null;
  high: string | null;
  price_per_m2_median: string | null;
  asking_price_position: "below_range" | "within_range" | "above_range" | null;
  unavailable_reason?: string;
}

export interface InvestmentResult {
  currency: "IQD" | "USD";
  gross_yield_percent: string | null;
  estimated_monthly_rent: string | null;
  rent_comparable_count: number;
  unavailable_reason?: string;
}

export interface ParseResult {
  filters: Record<string, unknown>;
  understood: { field: string; value: string; phrase: string }[];
  ambiguities: string[];
  unparsed: string;
}

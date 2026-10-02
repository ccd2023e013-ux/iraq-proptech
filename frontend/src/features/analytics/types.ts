export interface DayPoint {
  day: string;
  views: number;
  inquiries: number;
  leads: number;
}

export interface AnalyticsOverview {
  scope: "me" | "agency" | "platform" | "property";
  date_from: string;
  date_to: string;
  include_demo: boolean;
  summary: {
    listings_active: number;
    listings_published: number;
    views: number;
    favorites: number;
    inquiries: number;
    leads: number;
    leads_won: number;
    inquiry_rate: number | null;
    win_rate: number | null;
  };
  listings_by_status: Record<string, number>;
  leads_by_status: Record<string, number>;
  series: DayPoint[];
  top_listings?: {
    property_id: string;
    title_ar: string;
    title_en: string | null;
    views: number;
    inquiries: number;
    favorites: number;
  }[];
  agents?: {
    user_id: string;
    name: string;
    leads_assigned: number;
    leads_won: number;
    activities: number;
  }[];
  platform?: {
    new_users: number;
    searches: number;
    zero_result_searches: number;
    zero_result_rate: number | null;
    searches_by_governorate: {
      governorate_id: string;
      name_ar: string;
      name_en: string;
      searches: number;
    }[];
    searches_by_purpose: Record<string, number>;
  };
}

export type RangeParams = { date_from?: string; date_to?: string; include_demo?: string };

/** Query string for the analytics API from page search params (only known keys). */
export function rangeQuery(params: RangeParams, extra: Record<string, string> = {}): string {
  const q = new URLSearchParams(extra);
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  if (params.date_from && iso.test(params.date_from)) q.set("date_from", params.date_from);
  if (params.date_to && iso.test(params.date_to)) q.set("date_to", params.date_to);
  if (params.include_demo === "1") q.set("include_demo", "true");
  return q.toString();
}

export function percent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}

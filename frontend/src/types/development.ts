export interface DevelopmentEvidence {
  url: string;
  title: string;
  published_on: string | null;
  retrieved_at: string;
  excerpt: string | null;
  supports: "EXISTENCE" | "STATUS" | "TIMELINE" | "LOCATION" | "FIGURES";
  source: { name: string; organization: string; kind: string; url: string };
}

export interface DevelopmentProject {
  id: string;
  slug: string;
  name_ar: string;
  name_en: string | null;
  category: string;
  status: string;
  summary_ar: string;
  summary_en: string | null;
  location_precision: "EXACT" | "APPROXIMATE" | "AREA";
  location_note: string | null;
  timeline_ar: string | null;
  timeline_en: string | null;
  target_year: number | null;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  is_demo: boolean;
  last_verified_at: string | null;
  latest_source_date: string | null;
  sources: string[];
  evidence?: DevelopmentEvidence[];
}

export interface DevelopmentCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    id: string;
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: DevelopmentProject;
  }[];
  meta: { count: number; basis: string };
}

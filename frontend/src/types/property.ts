/** Mirrors backend/app/properties/schemas.py and geo/router.py. */

export type Purpose = "SALE" | "RENT" | "LEASE" | "RAHN" | "MUSATAHA" | "EXCHANGE";
export type RentPeriod = "DAILY" | "MONTHLY" | "YEARLY";
export type Currency = "IQD" | "USD";
export type PropertyStatus =
  | "DRAFT"
  | "PENDING_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "SUSPENDED"
  | "ARCHIVED"
  | "SOLD"
  | "RENTED"
  | "EXPIRED";
export type LocationPrivacy = "EXACT" | "APPROXIMATE" | "HIDDEN";
export type Condition = "NEW" | "EXCELLENT" | "GOOD" | "NEEDS_RENOVATION" | "UNDER_CONSTRUCTION";
export type Furnishing = "UNFURNISHED" | "SEMI_FURNISHED" | "FURNISHED";
export type OwnershipDocument =
  | "TAPU"
  | "AGRICULTURAL"
  | "HUJJA"
  | "INVESTMENT"
  | "MUSATAHA"
  | "SHARED"
  | "OTHER"
  | "UNKNOWN";

export interface LatLon {
  lat: number;
  lon: number;
}

export interface PlaceRef {
  id: string;
  name_ar: string;
  name_en: string;
}

export interface Place extends PlaceRef {
  slug: string;
  code: string | null;
  parent_id: string | null;
  centroid: LatLon | null;
  has_boundary: boolean;
  geometry_source: string | null;
}

export interface ReferenceItem {
  code: string;
  category: string;
  name_ar: string;
  name_en: string;
}

export interface Media {
  id: string;
  kind: "IMAGE" | "FLOOR_PLAN" | "VIDEO";
  content_type: string;
  width: number | null;
  height: number | null;
  sort_order: number;
  caption: string | null;
  url: string;
  thumbnail_url: string | null;
}

export interface Lister {
  kind: "agency" | "agent" | "owner";
  name: string;
  agency_id: string | null;
  agent_id: string | null;
  phone: string | null;
  whatsapp: string | null;
  agency_verified: boolean;
}

export interface Property {
  id: string;
  reference_code: string;
  title_ar: string;
  title_en: string | null;
  description_ar: string | null;
  description_en: string | null;
  property_type_code: string;
  purpose: Purpose;
  rent_period: RentPeriod | null;
  price_amount: string | null;
  currency: Currency;
  price_on_request: boolean;
  negotiable: boolean;
  area_m2: string | null;
  land_area_m2: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  floors: number | null;
  floor_number: number | null;
  year_built: number | null;
  condition: Condition | null;
  furnishing: Furnishing | null;
  ownership_document: OwnershipDocument;
  amenities: string[];
  governorate: PlaceRef;
  city: PlaceRef;
  district: PlaceRef | null;
  neighborhood: PlaceRef | null;
  street: string | null;
  address_text: string | null;
  location_privacy: LocationPrivacy;
  display_location: LatLon | null;
  status: PropertyStatus;
  published_at: string | null;
  expires_at: string | null;
  verified: boolean;
  verified_at: string | null;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  virtual_tour_url: string | null;
  media: Media[];
  lister: Lister;
  exact_location: LatLon | null;
  status_reason: string | null;
  needs_review: boolean | null;
  show_phone: boolean | null;
  allow_whatsapp: boolean | null;
  agent_id: string | null;
  can_edit: boolean;
}

export interface PropertyCard {
  id: string;
  reference_code: string;
  title_ar: string;
  title_en: string | null;
  property_type_code: string;
  purpose: Purpose;
  rent_period: RentPeriod | null;
  price_amount: string | null;
  currency: Currency;
  price_on_request: boolean;
  area_m2: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  city: PlaceRef;
  district: PlaceRef | null;
  neighborhood: PlaceRef | null;
  display_location: LatLon | null;
  status: PropertyStatus;
  verified: boolean;
  is_demo: boolean;
  published_at: string | null;
  created_at: string;
  cover_url: string | null;
  agency_name: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface PropertyDocument {
  id: string;
  doc_type: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Agency {
  id: string;
  name_ar: string;
  name_en: string | null;
  slug: string;
  description: string | null;
  phone: string | null;
  whatsapp: string | null;
  email: string | null;
  website: string | null;
  license_number: string | null;
  address: string | null;
  city_id: string | null;
  status: "PENDING_VERIFICATION" | "VERIFIED" | "REJECTED" | "SUSPENDED";
  verified_at: string | null;
  is_demo: boolean;
  created_at: string;
}

export interface AgencyInvitation {
  id: string;
  agency_id: string;
  email: string;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  agency_name: string | null;
}

export interface AgencyMember {
  user_id: string;
  full_name: string;
  role: "OWNER" | "AGENT";
  title: string | null;
  joined_at: string;
}

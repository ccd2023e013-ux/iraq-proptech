import type { Currency } from "@/types/property";

export interface Plan {
  id: string;
  code: string;
  kind: "SUBSCRIPTION" | "PROMOTION";
  name_ar: string;
  name_en: string;
  description_ar: string | null;
  description_en: string | null;
  price_amount: string;
  currency: Currency;
  duration_days: number;
  featured_credits: number;
  is_active: boolean;
  is_demo: boolean;
  sort_order: number;
}

export type PaymentStatus = "PENDING" | "SUCCEEDED" | "FAILED" | "CANCELED" | "REFUNDED";

export interface Payment {
  id: string;
  plan_id: string;
  property_id: string | null;
  amount: string;
  currency: Currency;
  provider: string;
  status: PaymentStatus;
  is_demo: boolean;
  failure_reason: string | null;
  created_at: string;
  paid_at: string | null;
  refunded_at: string | null;
}

export interface Subscription {
  id: string;
  plan_id: string;
  status: string;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  credits_remaining: number;
  is_demo: boolean;
}

export interface Promotion {
  id: string;
  property_id: string;
  starts_at: string;
  ends_at: string;
  canceled_at: string | null;
  is_demo: boolean;
}

export interface BillingConfig {
  enabled: boolean;
  provider: string;
  demo: boolean;
}

export interface MyBilling {
  subscription: Subscription | null;
  subscription_plan: Plan | null;
  payments: Payment[];
  promotions: Promotion[];
}

/** Only same-site relative redirects are followed after checkout (no open redirect). */
export function safeRedirect(url: string): string | null {
  return url.startsWith("/") && !url.startsWith("//") && !url.includes("\\") ? url : null;
}

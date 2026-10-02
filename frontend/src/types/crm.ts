export type Priority = "LOW" | "NORMAL" | "HIGH";
export type LeadSource =
  | "INQUIRY"
  | "MANUAL"
  | "PHONE"
  | "WHATSAPP"
  | "WALK_IN"
  | "REFERRAL"
  | "SOCIAL"
  | "OTHER";
export type ActivityKind =
  | "NOTE"
  | "CALL"
  | "WHATSAPP"
  | "EMAIL"
  | "SMS"
  | "MEETING"
  | "INQUIRY"
  | "STATUS_CHANGE"
  | "ASSIGNMENT"
  | "TASK"
  | "APPOINTMENT"
  | "MESSAGE";
export const MANUAL_ACTIVITY_KINDS = [
  "NOTE",
  "CALL",
  "WHATSAPP",
  "EMAIL",
  "SMS",
  "MEETING",
] as const;

export interface PersonRef {
  id: string;
  full_name: string;
}

export interface PropertyRef {
  id: string;
  reference_code: string;
  title_ar: string;
  title_en: string | null;
  status: string;
}

export interface Customer {
  id: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  notes: string | null;
  source: LeadSource;
  is_platform_user: boolean;
  agency_id: string | null;
  created_at: string;
  lead_count: number;
}

export interface Lead {
  id: string;
  status_code: string;
  source: LeadSource;
  priority: Priority;
  customer: Customer;
  property: PropertyRef | null;
  agency_id: string | null;
  owner: PersonRef | null;
  assigned_to: PersonRef | null;
  budget_min: string | null;
  budget_max: string | null;
  budget_currency: "IQD" | "USD" | null;
  next_follow_up_at: string | null;
  last_activity_at: string | null;
  closed_at: string | null;
  lost_reason: string | null;
  created_at: string;
  updated_at: string;
  can_manage: boolean;
  can_assign: boolean;
}

export interface LeadStatus {
  code: string;
  name_ar: string;
  name_en: string;
  sort_order: number;
  is_terminal: boolean;
  is_won: boolean;
  is_active: boolean;
  is_system: boolean;
}

export interface Activity {
  id: string;
  kind: ActivityKind;
  body: string | null;
  data: Record<string, unknown> | null;
  actor: PersonRef | null;
  occurred_at: string;
}

export interface Task {
  id: string;
  title: string;
  description: string | null;
  lead_id: string | null;
  assigned_to: PersonRef | null;
  due_at: string | null;
  completed_at: string | null;
  priority: Priority;
  overdue: boolean;
  created_at: string;
}

export interface Appointment {
  id: string;
  lead_id: string;
  property_id: string | null;
  starts_at: string;
  ends_at: string | null;
  location_text: string | null;
  status: "SCHEDULED" | "COMPLETED" | "CANCELLED" | "NO_SHOW";
  notes: string | null;
}

export interface CrmDashboard {
  total_open: number;
  new_last_7_days: number;
  by_status: { code: string; count: number }[];
  overdue_follow_ups: number;
  tasks_due_today: number;
  tasks_overdue: number;
  upcoming_appointments: Appointment[];
  won: number;
  lost: number;
  conversion_rate: number | null;
}

export interface Conversation {
  id: string;
  property: PropertyRef | null;
  lead_id: string | null;
  customer: PersonRef | null;
  lister: PersonRef | null;
  last_message_at: string | null;
  last_message: string | null;
  unread: number;
  role: "customer" | "lister";
}

export interface ChatMessage {
  id: string;
  sender: PersonRef | null;
  body: string;
  created_at: string;
  read_at: string | null;
  mine: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

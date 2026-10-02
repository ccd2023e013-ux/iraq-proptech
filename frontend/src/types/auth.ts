/** Mirrors backend/app/auth/schemas.py. */
export type RoleCode =
  | "SUPER_ADMIN"
  | "ADMIN"
  | "MODERATOR"
  | "AGENCY_OWNER"
  | "AGENT"
  | "PROPERTY_OWNER"
  | "CUSTOMER";

export interface User {
  id: string;
  email: string;
  phone: string | null;
  full_name: string;
  preferred_locale: "ar" | "en";
  status: "ACTIVE" | "SUSPENDED" | "DEACTIVATED";
  email_verified: boolean;
  phone_verified_at: string | null;
  created_at: string;
  roles: RoleCode[];
}

export interface Me {
  user: User;
  permissions: string[];
}

export interface AuthSessionInfo {
  id: string;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  user_agent: string | null;
  current: boolean;
}

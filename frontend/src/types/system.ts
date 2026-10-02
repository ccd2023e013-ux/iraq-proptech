/** Mirrors backend/app/system/router.py response models. */
export type CheckStatus = "ok" | "error" | "unavailable";

export interface DependencyCheck {
  status: CheckStatus;
  detail?: string | null;
}

export interface Readiness {
  status: "ok" | "degraded" | "error";
  database: DependencyCheck;
  postgis: DependencyCheck;
  redis: DependencyCheck;
}

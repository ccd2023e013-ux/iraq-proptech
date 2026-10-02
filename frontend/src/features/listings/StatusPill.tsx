import { type BadgeTone, StatusBadge } from "@/components/ui/StatusBadge";
import type { Dictionary } from "@/i18n";
import type { PropertyStatus } from "@/types/property";

const TONES: Record<PropertyStatus, BadgeTone> = {
  DRAFT: "neutral",
  PENDING_REVIEW: "warning",
  APPROVED: "success",
  REJECTED: "danger",
  SUSPENDED: "danger",
  ARCHIVED: "neutral",
  SOLD: "neutral",
  RENTED: "neutral",
  EXPIRED: "warning",
};

export function StatusPill({ status, dict }: { status: PropertyStatus; dict: Dictionary }) {
  return <StatusBadge tone={TONES[status]}>{dict.listing.statuses[status]}</StatusBadge>;
}

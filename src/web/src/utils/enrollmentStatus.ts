import type { EnrollmentOut } from "@/types/api";

export type EnrollmentStatusLabel = "Ready" | "Add samples" | "Check quality" | "Off";

export interface EnrollmentStatus {
  label: EnrollmentStatusLabel;
  type: "success" | "warning" | "default";
}

export function enrollmentStatus(
  enrollment: Pick<EnrollmentOut, "enabled" | "sample_count" | "quality">,
): EnrollmentStatus {
  if (!enrollment.enabled) return { label: "Off", type: "default" };
  if (enrollment.sample_count <= 0) return { label: "Add samples", type: "warning" };
  if (!enrollment.quality?.usable) return { label: "Check quality", type: "warning" };
  return { label: "Ready", type: "success" };
}

export function needsAttention(
  enrollment: Pick<EnrollmentOut, "enabled" | "sample_count" | "quality">,
): boolean {
  if (!enrollment.enabled) return false;
  return enrollment.sample_count <= 0 || !enrollment.quality?.usable;
}

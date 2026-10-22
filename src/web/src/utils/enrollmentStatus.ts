import type { EnrollmentOut } from "@/types/api";

export type EnrollmentStatusLabel = "Ready" | "Needs samples" | "Needs a check" | "Off";

export interface EnrollmentStatus {
  label: EnrollmentStatusLabel;
  tone: "success" | "warning" | "default";
  /** @deprecated use tone */
  type: "success" | "warning" | "default";
}

export function enrollmentStatus(
  enrollment: Pick<EnrollmentOut, "enabled" | "sample_count" | "quality">,
): EnrollmentStatus {
  if (!enrollment.enabled) return { label: "Off", tone: "default", type: "default" };
  if (enrollment.sample_count <= 0) {
    return { label: "Needs samples", tone: "warning", type: "warning" };
  }
  if (!enrollment.quality?.usable) {
    return { label: "Needs a check", tone: "warning", type: "warning" };
  }
  return { label: "Ready", tone: "success", type: "success" };
}

export function needsAttention(
  enrollment: Pick<EnrollmentOut, "enabled" | "sample_count" | "quality">,
): boolean {
  if (!enrollment.enabled) return false;
  return enrollment.sample_count <= 0 || !enrollment.quality?.usable;
}

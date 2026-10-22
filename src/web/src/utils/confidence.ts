export type ConfidenceTone = "met" | "near" | "far" | "none";

/**
 * Classify a score against the threshold it needed.
 * - met: at or above the threshold
 * - near: within 10 points below the threshold
 * - far: everything else
 */
export function confidenceTone(value: number | null | undefined, threshold?: number | null): ConfidenceTone {
  if (value == null || Number.isNaN(value)) return "none";
  if (threshold == null) {
    if (value >= 0.75) return "met";
    if (value >= 0.5) return "near";
    return "far";
  }
  if (value >= threshold) return "met";
  if (value >= threshold - 0.1) return "near";
  return "far";
}

export function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

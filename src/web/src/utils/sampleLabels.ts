/** Human labels for enrollment sample metadata and flags. */

export const sampleSourceLabels: Record<string, string> = {
  upload: "Upload",
  voice_wizard: "Guided voice",
  face_wizard: "Guided face",
  photo_wizard: "Guided photo",
  enrollment_create: "Initial enrollment",
  match_learn: "Learned match",
  unknown: "Unknown",
};

export const sampleFlagLabels: Record<string, { label: string; type: "warning" | "error" | "default" }> = {
  outdated_model: {
    label: "Old embedding model",
    type: "warning",
  },
  low_fit: {
    label: "Low match to profile",
    type: "warning",
  },
  poor_fit: {
    label: "Poor match to profile",
    type: "error",
  },
  unknown_source: {
    label: "Source not recorded",
    type: "default",
  },
};

export function formatSampleDuration(ms: number | null | undefined): string {
  if (ms == null || ms <= 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function formatSampleSize(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatFitPct(sim: number | null | undefined): string {
  if (sim == null) return "—";
  return `${Math.round(sim * 100)}%`;
}

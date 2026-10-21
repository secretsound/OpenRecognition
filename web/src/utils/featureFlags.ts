export const FEATURE_FLAG_META: Record<
  string,
  { label: string; description: string }
> = {
  "biometrics.face_enabled": {
    label: "Face recognition",
    description: "Detect and match enrolled faces in images and video.",
  },
  "biometrics.speaker_enabled": {
    label: "Speaker recognition",
    description: "Identify enrolled speakers from audio.",
  },
  "biometrics.pet_enabled": {
    label: "Pet identity",
    description: "Match individual enrolled pets in images.",
  },
  "recognition.sound_events_enabled": {
    label: "Sound events (legacy flag)",
    description: "Reserved; use “Classify sound events by default” in Recognition defaults.",
  },
};

export function featureFlagEntries(flags: Record<string, boolean>) {
  const keys = new Set([...Object.keys(FEATURE_FLAG_META), ...Object.keys(flags)]);
  return [...keys].sort().map((key) => ({
    key,
    label: FEATURE_FLAG_META[key]?.label ?? key,
    description: FEATURE_FLAG_META[key]?.description ?? "",
    value: flags[key] ?? false,
  }));
}

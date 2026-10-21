const EVENT_LABELS: Record<string, string> = {
  "recognition.match": "Match",
  "recognition.unknown": "Unknown",
  "recognition.no_match": "No match",
  "recognition.gate": "Speech check",
  "recognition.gate_reject": "Speech check rejected",
  "wyoming.transcript": "Transcript",
  "wyoming.blocked": "Blocked",
  "wyoming.empty": "Nothing heard",
  "enrollment.created": "Created",
  "enrollment.samples_added": "Samples added",
};

export function formatLogEvent(event: string) {
  return (
    EVENT_LABELS[event] ??
    event.replace(/^(recognition|enrollment|wyoming)\./, "").replace(/_/g, " ")
  );
}

export function formatLogMedia(modality: string | null | undefined) {
  if (!modality) return "—";
  if (modality === "audio") return "Voice";
  if (modality === "image") return "Photo";
  if (modality === "video") return "Video";
  if (modality === "enrollment") return "Library";
  return modality;
}

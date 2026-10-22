export const WEBHOOK_DEFAULT_TITLE = "{{label}} was recognized";
export const WEBHOOK_DEFAULT_MESSAGE = "{{label}} matched at {{confidence}} on {{modality}}";

export const WEBHOOK_EVENTS = [
  {
    value: "recognition.match",
    label: "Someone matched",
    hint: "A known person, pet, or object was recognized.",
  },
  {
    value: "recognition.unknown",
    label: "Nobody matched",
    hint: "A face or voice was seen but it is not in the library.",
  },
  {
    value: "recognition.no_match",
    label: "Nothing found",
    hint: "The clip had no recognizable face, voice, or object.",
  },
  {
    value: "recognition.gate_reject",
    label: "Speech check failed",
    hint: "Audio was too short, quiet, or not speech.",
  },
] as const;

export const WEBHOOK_VARIABLES = [
  { key: "label", example: "Alex", hint: "Who or what was recognized" },
  { key: "event_label", example: "Someone matched", hint: "A short description of the event" },
  { key: "confidence", example: "92%", hint: "How sure the match was" },
  { key: "confidence_raw", example: "0.920", hint: "Confidence as a number from 0 to 1" },
  { key: "modality", example: "voice", hint: "voice, photo, or video" },
  { key: "mode", example: "identify", hint: "The recognition mode that ran" },
  { key: "type", example: "person", hint: "person, pet, object, or sound" },
  { key: "gate", example: "accept", hint: "Whether the speech check passed" },
  { key: "reason", example: "", hint: "Why a check failed, if it did" },
  { key: "camera", example: "front-door", hint: "Camera id from the request" },
  { key: "zone", example: "porch", hint: "Zone from the request" },
  { key: "transcript", example: "hey there", hint: "Spoken words, when available" },
  { key: "entity_id", example: "enr_123", hint: "Library id of the match" },
  { key: "event", example: "recognition.match", hint: "The raw event id" },
] as const;

export const WEBHOOK_PREVIEW_CONTEXT: Record<string, string> = Object.fromEntries(
  WEBHOOK_VARIABLES.map((item) => [item.key, item.example]),
);

export const WEBHOOK_PREVIEW_DETAILS = {
  mode: "identify",
  label: "Alex",
  entity_id: "enr_123",
  type: "person",
  modality: "audio",
  confidence: 0.92,
  gate: "accept",
  scores: { speech: 0.97, similarity: 0.92 },
  camera_id: "front-door",
  zone: "porch",
  pipelines: ["speaker"],
};

export function renderWebhookTemplate(
  template: string,
  context: Record<string, string> = WEBHOOK_PREVIEW_CONTEXT,
): string {
  return template.replace(
    /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}|\{([a-zA-Z0-9_]+)\}/g,
    (_match, doubleKey: string | undefined, singleKey: string | undefined) => {
      const key = doubleKey || singleKey || "";
      return context[key] ?? "";
    },
  );
}

export function webhookEventLabel(event: string): string {
  return WEBHOOK_EVENTS.find((item) => item.value === event)?.label
    ?? event.replace(/^recognition\./, "").replace(/_/g, " ");
}

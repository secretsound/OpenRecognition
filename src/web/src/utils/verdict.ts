import type { RecognizeResponse, RecognitionLogOut } from "@/types/api";
import { pct } from "@/utils/confidence";
import { formatLogEvent, formatLogMedia } from "@/utils/logEvent";

export type VerdictKind = "match" | "closest" | "unknown" | "rejected" | "empty" | "event";

export interface Verdict {
  kind: VerdictKind;
  sentence: string;
  label: string | null;
  type: string | null;
  entityId: string | null;
  confidence: number | null;
  threshold: number | null;
  modality: string | null;
}

function mediaWord(modality: string | null | undefined): string {
  const word = formatLogMedia(modality).toLowerCase();
  return word === "—" ? "media" : word;
}

export function verdictFromRecognize(
  result: RecognizeResponse,
  opts?: { minConfidence?: number },
): Verdict {
  if (result.gate === "reject") {
    const reason = result.reason || "not speech";
    let extra = "";
    if (result.scores) {
      const top = Object.entries(result.scores).sort((a, b) => b[1] - a[1])[0];
      if (top) extra = ` (${top[0]} ${pct(top[1])})`;
    }
    return {
      kind: "rejected",
      sentence: `Rejected: ${reason}${extra}`,
      label: null,
      type: null,
      entityId: null,
      confidence: null,
      threshold: null,
      modality: "audio",
    };
  }

  const known = result.entities.filter((e) => e.label !== "unknown");
  const best = [...known].sort((a, b) => b.confidence - a.confidence)[0];
  if (best) {
    const needed = best.threshold_used ?? opts?.minConfidence ?? null;
    const neededPart = needed != null ? ` (needed ${pct(needed)})` : "";
    return {
      kind: "match",
      sentence: `Matched ${best.label} by ${mediaWord(best.modality)} · ${pct(best.confidence)}${neededPart}`,
      label: best.label,
      type: best.type,
      entityId: best.entity_id,
      confidence: best.confidence,
      threshold: needed,
      modality: best.modality,
    };
  }

  const candidates = result.diagnostics?.candidates ?? [];
  const top = [...candidates].sort((a, b) => b.confidence - a.confidence)[0];
  if (top) {
    const needed = top.threshold_used ?? opts?.minConfidence ?? null;
    const neededPart = needed != null ? `, needed ${pct(needed)}` : "";
    return {
      kind: "closest",
      sentence: `Closest was ${top.label} at ${pct(top.confidence)}${neededPart}`,
      label: top.label,
      type: top.type,
      entityId: top.entity_id,
      confidence: top.confidence,
      threshold: needed,
      modality: top.modality,
    };
  }

  const unknown = result.entities.find((e) => e.label === "unknown");
  if (unknown) {
    return {
      kind: "unknown",
      sentence: `Below threshold — closest hit ${pct(unknown.confidence)}`,
      label: null,
      type: unknown.type,
      entityId: unknown.entity_id,
      confidence: unknown.confidence,
      threshold: unknown.threshold_used ?? opts?.minConfidence ?? null,
      modality: unknown.modality,
    };
  }

  return {
    kind: "empty",
    sentence: "Nothing in the library was close enough",
    label: null,
    type: null,
    entityId: null,
    confidence: null,
    threshold: opts?.minConfidence ?? null,
    modality: null,
  };
}

export function verdictFromLog(row: RecognitionLogOut): Verdict {
  const media = mediaWord(row.modality);
  if (row.event === "recognition.match") {
    return {
      kind: "match",
      sentence: `Matched ${row.label ?? "someone"} by ${media}${row.confidence != null ? ` · ${pct(row.confidence)}` : ""}`,
      label: row.label,
      type: null,
      entityId: row.entity_id,
      confidence: row.confidence,
      threshold: row.details?.min_confidence ?? null,
      modality: row.modality,
    };
  }
  if (row.event === "recognition.unknown") {
    return {
      kind: "unknown",
      sentence: row.label
        ? `Closest was ${row.label}${row.confidence != null ? ` at ${pct(row.confidence)}` : ""}, below threshold`
        : "Nobody matched",
      label: row.label,
      type: null,
      entityId: row.entity_id,
      confidence: row.confidence,
      threshold: row.details?.min_confidence ?? null,
      modality: row.modality,
    };
  }
  if (row.event === "recognition.no_match") {
    return {
      kind: "empty",
      sentence: row.summary || "No match",
      label: row.label,
      type: null,
      entityId: row.entity_id,
      confidence: row.confidence,
      threshold: row.details?.min_confidence ?? null,
      modality: row.modality,
    };
  }
  if (row.event === "recognition.gate_reject") {
    return {
      kind: "rejected",
      sentence: row.reason ? `Rejected: ${row.reason}` : "Rejected: not speech",
      label: null,
      type: null,
      entityId: null,
      confidence: null,
      threshold: null,
      modality: row.modality,
    };
  }
  return {
    kind: "event",
    sentence: row.summary || formatLogEvent(row.event),
    label: row.label,
    type: null,
    entityId: row.entity_id,
    confidence: row.confidence,
    threshold: null,
    modality: row.modality,
  };
}

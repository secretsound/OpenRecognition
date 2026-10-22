import type {
  RecognitionLogGateScores,
  RecognitionLogOut,
  RecognitionLogSpeakerCandidate,
} from "@/types/api";
import { formatLogEvent, formatLogMedia } from "@/utils/logEvent";
import { formatClock, formatPrecise } from "@/utils/time";

/** Nearby Wyoming voice commands are one conversation in the activity list. */
const BURST_MS = 60_000;

export interface ActivityGroup {
  id: string;
  /** Oldest first. */
  logs: RecognitionLogOut[];
}

export interface StoryPerson {
  label: string;
  score: string;
  bar: string | null;
  passed: boolean;
}

export interface StoryStep {
  key: string;
  type: "default" | "success" | "info" | "warning" | "error";
  title: string;
  lines: string[];
  people?: StoryPerson[];
  time?: string;
  quote?: boolean;
}

export interface TechRow {
  label: string;
  value: string;
}

export interface ProcessEvent {
  key: string;
  title: string;
  lines: string[];
}

export function spokenText(raw: string | null | undefined): string {
  if (!raw) return "";
  const text = raw.replace(/\r\n/g, "\n").trim();
  const mark = text.match(/\[transcript\]\s*/i);
  if (mark && mark.index != null) {
    return text.slice(mark.index + mark[0].length).trim();
  }
  const inline = text.match(/^\[speaker:\s*[^\]]+\]\s*/i);
  if (inline) return text.slice(inline[0].length).trim();
  if (/^\[(speaker|confidence|sounds)\b/i.test(text)) return "";
  return text;
}

export function percentLabel(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function collapseActivityRows(newestFirst: RecognitionLogOut[]): ActivityGroup[] {
  const groups: ActivityGroup[] = [];
  for (const row of newestFirst) {
    const open = groups[groups.length - 1];
    const oldest = open?.logs[0];
    if (open && oldest && sameBurst(oldest, row)) {
      open.logs.unshift(row);
      continue;
    }
    groups.push({ id: row.id, logs: [row] });
  }
  return groups;
}

export function newestLog(logs: RecognitionLogOut[]): RecognitionLogOut | null {
  return logs[logs.length - 1] ?? null;
}

export function groupLabel(logs: RecognitionLogOut[]): string {
  const names: string[] = [];
  for (const log of logs) {
    const label = log.label?.trim();
    if (!label || names.includes(label)) continue;
    names.push(label);
  }
  return names.length ? names.join(" · ") : "—";
}

export function groupBlurb(logs: RecognitionLogOut[]): string {
  const lines = logs.map(activityBlurb).filter((line) => line && line !== "—");
  const unique = [...new Set(lines)];
  return unique.length ? unique.join(" · ") : "—";
}

export function activityBlurb(log: RecognitionLogOut): string {
  const spoken = spokenText(log.details?.transcript);
  if (spoken) return spoken;
  const fromSummary = blurbFromSummary(log.summary);
  if (fromSummary) return fromSummary;
  return friendlyReason(log.reason) || "—";
}

export function storyTitle(logs: RecognitionLogOut[]): string {
  if (logs.length > 1) return `${logs.length} voice commands`;
  const log = logs[0];
  if (!log) return "Event details";
  if (log.event === "wyoming.empty") return "Nothing heard";
  if (log.event === "wyoming.blocked") return "Voice command blocked";
  if (log.event === "recognition.gate_reject") return "Didn't sound like speech";
  if (log.event === "recognition.no_match") return "Nothing found";
  if (log.event === "recognition.unknown") return "Nobody matched";
  if (isKnownLabel(log.label) && wasMatched(log)) return log.label!.trim();
  if (log.event.startsWith("wyoming.") && spokenText(log.details?.transcript)) return "Someone spoke";
  if (log.event.startsWith("enrollment.")) return formatLogEvent(log.event);
  return formatLogEvent(log.event);
}

export function storyMeta(logs: RecognitionLogOut[]): string {
  const oldest = logs[0];
  const newest = newestLog(logs);
  if (!oldest || !newest) return "";
  const parts: string[] = [];
  if (logs.length > 1) {
    parts.push(`${formatFull(oldest.created_at)} – ${formatClock(newest.created_at)}`);
  } else {
    parts.push(formatFull(newest.created_at));
  }
  const media = formatLogMedia(newest.modality);
  if (media !== "—") parts.push(media);
  const actor = actorLabel(newest);
  if (actor) parts.push(actor);
  return parts.join(" · ");
}

export function storySteps(logs: RecognitionLogOut[]): StoryStep[] {
  const showTime = logs.length > 1;
  return logs.flatMap((log) => stepsForLog(log, showTime ? formatClock(log.created_at) : undefined));
}

export function eventHeading(log: RecognitionLogOut): string {
  return `${formatLogEvent(log.event)} · ${formatClock(log.created_at)}`;
}

export function processEvents(log: RecognitionLogOut): ProcessEvent[] {
  const events: ProcessEvent[] = [];
  const scores = log.details?.gate_scores;
  if (scores || log.gate) {
    const lines: string[] = [];
    if (log.gate) lines.push(log.gate === "accept" ? "Passed" : "Rejected");
    if (scores?.speech != null) lines.push(`Speech ${percentLabel(scores.speech)}`);
    if (scores?.music != null) lines.push(`Music ${percentLabel(scores.music)}`);
    if (scores?.noise != null) lines.push(`Noise ${percentLabel(scores.noise)}`);
    events.push({ key: `${log.id}-speech`, title: "Speech check", lines });
  }
  const candidates = [...(log.details?.speaker_candidates ?? [])].sort((a, b) => b.confidence - a.confidence);
  const bar = defaultBar(log);
  if (candidates.length) {
    events.push({
      key: `${log.id}-speaker`,
      title: "Speaker match",
      lines: candidates.map((row) => personAmount(row, bar)),
    });
  } else if (log.details?.speaker_match_attempted || (log.confidence != null && !log.event.startsWith("enrollment."))) {
    events.push({
      key: `${log.id}-speaker`,
      title: "Speaker match",
      lines: [log.confidence != null ? percentLabel(log.confidence) : "No candidates"],
    });
  }
  const quote = spokenText(log.details?.transcript) || spokenText(quotedSummary(log.summary));
  if (quote) events.push({ key: `${log.id}-said`, title: "Transcript", lines: [quote] });
  const timing = log.details?.timing_ms;
  if (timing) {
    const lines: string[] = [];
    if (timing.identify != null) lines.push(`Matching ${timing.identify} ms`);
    if (log.details?.upstream_skipped) lines.push("Speech-to-text skipped");
    else if (timing.upstream != null && timing.upstream > 0) lines.push(`Speech-to-text ${timing.upstream} ms`);
    if (timing.total != null) lines.push(`${timing.total} ms in all`);
    if (lines.length) events.push({ key: `${log.id}-timing`, title: "Timing", lines });
  }
  return events;
}

export function technicalRows(log: RecognitionLogOut): TechRow[] {
  const rows: TechRow[] = [{ label: "Event", value: formatLogEvent(log.event) }];
  const why = friendlyReason(log.reason);
  if (why) rows.push({ label: "Reason", value: why });
  else if (log.reason) rows.push({ label: "Reason", value: log.reason });
  if (log.camera_id) rows.push({ label: "Camera", value: log.camera_id });
  if (log.zone) rows.push({ label: "Zone", value: log.zone });
  rows.push({ label: "Sandbox", value: log.dry_run ? "Yes — webhooks skipped" : "No" });
  if (log.entity_id) rows.push({ label: "Enrollment", value: log.entity_id });
  if (log.request_id) rows.push({ label: "Request", value: log.request_id });
  rows.push({ label: "Log", value: log.id });
  return rows;
}

export function enrollmentTarget(logs: RecognitionLogOut[]): string | null {
  for (let i = logs.length - 1; i >= 0; i -= 1) {
    const log = logs[i];
    if (!log.entity_id || !isKnownLabel(log.label)) continue;
    if (log.event.startsWith("enrollment.") || log.event === "recognition.match" || log.details?.accepted) {
      return log.entity_id;
    }
  }
  return null;
}

export function groupEvent(logs: RecognitionLogOut[]): { label: string; event: string } {
  const newest = newestLog(logs);
  if (!newest) return { label: "Event", event: "" };
  const same = logs.every((log) => log.event === newest.event);
  if (same) return { label: formatLogEvent(newest.event), event: newest.event };
  return { label: "Voice", event: newest.event };
}

function sameBurst(newer: RecognitionLogOut, older: RecognitionLogOut): boolean {
  if (!newer.event.startsWith("wyoming.") || !older.event.startsWith("wyoming.")) return false;
  const gap = new Date(newer.created_at).getTime() - new Date(older.created_at).getTime();
  return gap >= 0 && gap <= BURST_MS;
}

function stepsForLog(log: RecognitionLogOut, time?: string): StoryStep[] {
  const steps: StoryStep[] = [];
  const gate = gateStep(log);
  if (gate) steps.push(gate);
  const speaker = speakerStep(log);
  if (speaker) steps.push(speaker);
  const said = transcriptStep(log);
  if (said) steps.push(said);
  const stopped = stoppedStep(log);
  if (stopped) steps.push(stopped);
  const done = timingStep(log);
  if (done) steps.push(done);
  if (!steps.length) {
    const line = activityBlurb(log);
    steps.push({
      key: `${log.id}-event`,
      type: stepType(log.event),
      title: formatLogEvent(log.event),
      lines: line === "—" ? [] : [line],
    });
  }
  if (time && steps[0]) steps[0].title = `${time} · ${steps[0].title}`;
  steps.forEach((step, index) => {
    step.key = `${log.id}-${index}`;
  });
  return steps;
}

function gateStep(log: RecognitionLogOut): StoryStep | null {
  const scores = log.details?.gate_scores;
  const gate = log.gate;
  if (!scores && !gate) return null;
  if (log.event.startsWith("enrollment.")) return null;
  const rejected = gate === "reject" || log.event === "recognition.gate_reject";
  const lines: string[] = [];
  const mix = scoreMix(scores);
  if (mix) lines.push(mix);
  if (rejected) {
    const why = friendlyReason(log.reason);
    if (why && why !== mix) lines.push(why);
  }
  return {
    key: "gate",
    type: rejected ? "warning" : "success",
    title: rejected ? "Didn't sound like speech" : "Sounded like speech",
    lines,
  };
}

function speakerStep(log: RecognitionLogOut): StoryStep | null {
  const details = log.details;
  const candidates = details?.speaker_candidates ?? [];
  const attempted = details?.speaker_match_attempted === true || candidates.length > 0;
  const matched = wasMatched(log);
  if (!attempted && !matched && log.confidence == null) return null;
  if (log.event.startsWith("enrollment.")) return null;
  if (log.event === "wyoming.empty") return null;

  if (
    log.modality === "audio" &&
    log.gate === "reject" &&
    !attempted &&
    candidates.length === 0
  ) {
    return {
      key: "speaker",
      type: "default",
      title: "Nobody was matched",
      lines: ["Speaker matching was skipped."],
    };
  }

  const bar = defaultBar(log);
  if (candidates.length && (matched || attempted)) {
    const people = [...candidates]
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 4)
      .map((row) => storyPerson(row, bar));
    const anyone = people.some((person) => person.passed);
    return {
      key: "speaker",
      type: anyone ? "success" : "warning",
      title: anyone ? "Speakers" : "Nobody matched",
      lines: [],
      people,
    };
  }

  if (!attempted && log.confidence != null && !matched) {
    return {
      key: "speaker",
      type: "warning",
      title: "Closest score",
      lines: [percentLabel(log.confidence)],
    };
  }

  if (!attempted) return null;

  const ranked = [...candidates].sort((a, b) => b.confidence - a.confidence).slice(0, 4);
  const lines = ranked.map((row) => personAmount(row, bar));
  if (!lines.length && log.reason) {
    const why = emptyGalleryLine(log);
    if (why) lines.push(why);
  }
  return {
    key: "speaker",
    type: "warning",
    title: "Nobody matched",
    lines,
  };
}

function transcriptStep(log: RecognitionLogOut): StoryStep | null {
  const quote = spokenText(log.details?.transcript) || spokenText(quotedSummary(log.summary));
  if (!quote) return null;
  return {
    key: "said",
    type: "info",
    title: "They said",
    lines: [quote],
    quote: true,
  };
}

function stoppedStep(log: RecognitionLogOut): StoryStep | null {
  if (log.event !== "wyoming.blocked" && !log.details?.block_reason && !log.details?.upstream_skipped) {
    return null;
  }
  if (log.event === "wyoming.transcript" && !log.details?.upstream_skipped) return null;
  const reason = log.details?.block_reason;
  let line = "The voice command was held back.";
  if (reason && /speaker not matched/i.test(reason)) {
    line = "Speech-to-text was skipped because nobody matched.";
  } else if (reason && /audio gate/i.test(reason)) {
    line = "Speech-to-text was skipped because this did not sound like speech.";
  } else if (log.details?.upstream_skipped) {
    line = "Speech-to-text was skipped.";
  }
  return {
    key: "stopped",
    type: "warning",
    title: "Stopped",
    lines: [line],
  };
}

function timingStep(log: RecognitionLogOut): StoryStep | null {
  const timing = log.details?.timing_ms;
  if (!timing) return null;
  const parts: string[] = [];
  if (timing.identify != null) parts.push(`Matching ${timing.identify} ms`);
  if (log.details?.upstream_skipped) parts.push("Speech-to-text skipped");
  else if (timing.upstream != null && timing.upstream > 0) parts.push(`Speech-to-text ${timing.upstream} ms`);
  if (!parts.length && timing.total == null) return null;
  return {
    key: "timing",
    type: "default",
    title: timing.total != null ? `${timing.total} ms in all` : "Timing",
    lines: parts.length ? [parts.join(" · ")] : [],
  };
}

function scoreMix(scores: RecognitionLogGateScores | null | undefined): string {
  if (!scores) return "";
  const parts: string[] = [];
  if (scores.speech != null) parts.push(`Speech ${percentLabel(scores.speech)}`);
  if (scores.music != null) parts.push(`Music ${percentLabel(scores.music)}`);
  if (scores.noise != null) parts.push(`Noise ${percentLabel(scores.noise)}`);
  return parts.join(" · ");
}

function defaultBar(log: RecognitionLogOut): number | null {
  const details = log.details;
  if (!details) return null;
  if (details.default_min_confidence != null) return details.default_min_confidence;
  return details.min_confidence ?? null;
}

function personPassed(row: RecognitionLogSpeakerCandidate, fallback: number | null): boolean {
  if (row.accepted != null) return row.accepted;
  const needed = row.threshold_used ?? fallback;
  return needed != null && row.confidence >= needed - 0.0001;
}

function storyPerson(row: RecognitionLogSpeakerCandidate, fallback: number | null): StoryPerson {
  const needed = row.threshold_used ?? fallback;
  return {
    label: row.label,
    score: percentLabel(row.confidence),
    bar: needed != null ? percentLabel(needed) : null,
    passed: personPassed(row, fallback),
  };
}

function personAmount(row: RecognitionLogSpeakerCandidate, fallback: number | null): string {
  const person = storyPerson(row, fallback);
  const bar = person.bar ? `, bar ${person.bar}` : "";
  return `${person.label} — ${person.passed ? "Passed" : "Below"}, ${person.score}${bar}`;
}

function wasMatched(log: RecognitionLogOut): boolean {
  if (log.event === "recognition.match") return isKnownLabel(log.label);
  if (log.details?.accepted === true) return isKnownLabel(log.label);
  if (log.event === "wyoming.transcript" && isKnownLabel(log.label) && log.details?.accepted !== false) {
    return log.reason !== "unknown_or_low_confidence";
  }
  return false;
}

function isKnownLabel(label: string | null | undefined): boolean {
  const cleaned = label?.trim();
  return !!cleaned && cleaned.toLowerCase() !== "unknown";
}

function emptyGalleryLine(log: RecognitionLogOut): string {
  const reason = log.reason;
  if (reason === "empty_gallery" || log.details?.gallery_count === 0) {
    return "No enrollments have voice samples yet.";
  }
  if (log.details?.comparable_speaker_count === 0) {
    return "Enrollments exist, but none have a voice sample that can be compared.";
  }
  return "";
}

function friendlyReason(reason: string | null | undefined): string {
  if (!reason) return "";
  if (reason === "unknown_or_low_confidence") return "Below the match bar";
  if (reason === "background_noise") return "This sounded like background noise.";
  if (reason === "empty_gallery") return "No enrollments have voice samples yet.";
  if (reason.includes("_")) return "";
  return reason;
}

function blurbFromSummary(summary: string | null | undefined): string {
  const quote = quotedSummary(summary);
  if (quote) {
    const spoken = spokenText(quote);
    if (spoken) return spoken;
  }
  if (!summary) return "";
  if (/audio [\d.]+s/.test(summary) && /identify \d+ms/.test(summary)) return "";
  return summary;
}

function quotedSummary(summary: string | null | undefined): string {
  if (!summary) return "";
  const quoted = summary.match(/^"([\s\S]+)"(?: · |$)/);
  return quoted?.[1] ?? "";
}

function actorLabel(log: RecognitionLogOut): string {
  if (log.actor_type === "integration" && (log.actor_name ?? "").toLowerCase() === "wyoming") {
    return "Wyoming";
  }
  if (log.actor_name) return log.actor_name;
  if (log.actor_type === "api_key") return "API key";
  if (log.actor_type === "user") return "User";
  return "";
}

function stepType(event: string): StoryStep["type"] {
  if (event === "recognition.match" || event === "wyoming.transcript") return "success";
  if (event === "recognition.unknown" || event === "wyoming.blocked") return "warning";
  if (event === "recognition.gate_reject") return "error";
  if (event.startsWith("enrollment.")) return "info";
  return "default";
}

function formatFull(iso: string): string {
  return formatPrecise(iso);
}

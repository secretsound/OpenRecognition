import type { SamplePreviewOut } from "@/types/api";

export interface TakeQuality {
  score: number;
  verdict: "keep" | "retry";
  durationMs: number;
  speech: number | null;
  fit: number | null;
  issues: string[];
  advice: string;
}

export const TAKE_ISSUE_LABELS: Record<string, string> = {
  too_short: "Too short",
  a_bit_short: "A bit short",
  too_quiet: "Too quiet",
  clipped: "Peaking / clipped",
  mostly_silence: "Mostly silence",
  silence: "No voice heard",
  background_noise: "Background noise",
  music: "Sounds like music",
  not_speech: "Not speech",
  low_fit: "Doesn't match this voice well",
  poor_fit: "Doesn't match this voice",
};

const HARD_ISSUES = new Set(["too_short", "silence", "poor_fit", "music", "mostly_silence"]);

function durationScore(ms: number): number {
  if (ms < 1500) return 0.15;
  if (ms < 2500) return 0.35;
  if (ms < 4000) return 0.7;
  if (ms <= 8000) return 1;
  if (ms <= 12000) return 0.9;
  return 0.75;
}

function adviceFor(issues: string[], hasFit: boolean): string {
  if (issues.includes("silence") || issues.includes("mostly_silence")) {
    return "Almost no voice was heard. Move closer or speak louder.";
  }
  if (issues.includes("too_short")) {
    return "Finish the whole sentence — four to six seconds works best.";
  }
  if (issues.includes("clipped")) {
    return "The mic peaked. Back up a little or speak a bit softer.";
  }
  if (issues.includes("too_quiet")) {
    return "This take is quiet. Move closer to the mic and try again.";
  }
  if (issues.includes("music")) {
    return "This sounds like music, not speech. Try again in a quiet room.";
  }
  if (issues.includes("background_noise")) {
    return "Too much background noise. Try a quieter room and re-record.";
  }
  if (issues.includes("poor_fit")) {
    return "This take does not match your other voice samples. Make sure it is the same person.";
  }
  if (issues.includes("low_fit")) {
    return "This take is a bit different from your other samples. Re-record if someone else was talking.";
  }
  if (issues.includes("a_bit_short")) {
    return "A little short. Re-record if you cut off the last words.";
  }
  if (hasFit) return "This take looks good and matches the voice you already taught.";
  return "This take looks good.";
}

export function issueLabel(code: string): string {
  return TAKE_ISSUE_LABELS[code] ?? code.replaceAll("_", " ");
}

export async function analyzeTakeLocally(blob: Blob): Promise<TakeQuality> {
  const ctx = new AudioContext();
  try {
    const buf = await ctx.decodeAudioData(await blob.arrayBuffer());
    const samples = buf.getChannelData(0);
    const durationMs = buf.duration * 1000;
    const n = samples.length || 1;

    let sumSq = 0;
    let clipped = 0;
    let peak = 0;
    for (let i = 0; i < samples.length; i++) {
      const s = samples[i] ?? 0;
      const a = Math.abs(s);
      sumSq += s * s;
      if (a > peak) peak = a;
      if (a >= 0.99) clipped += 1;
    }
    const rms = Math.sqrt(sumSq / n);

    const frame = Math.max(1, Math.round(buf.sampleRate * 0.02));
    let voiced = 0;
    let frames = 0;
    for (let i = 0; i < samples.length; i += frame) {
      let fsq = 0;
      const end = Math.min(samples.length, i + frame);
      for (let j = i; j < end; j++) {
        const s = samples[j] ?? 0;
        fsq += s * s;
      }
      const frms = Math.sqrt(fsq / Math.max(1, end - i));
      frames += 1;
      if (frms >= 0.02) voiced += 1;
    }
    const activity = frames > 0 ? voiced / frames : 0;

    const issues: string[] = [];
    if (durationMs < 2500) issues.push("too_short");
    else if (durationMs < 4000) issues.push("a_bit_short");
    if (rms < 0.01) issues.push("too_quiet");
    if (clipped / n > 0.02) issues.push("clipped");
    if (activity < 0.25) issues.push("mostly_silence");

    const speech = Math.max(0, Math.min(1, activity));
    const score = Math.max(
      0,
      Math.min(1, 0.45 * durationScore(durationMs) + 0.55 * speech * (rms < 0.01 ? 0.4 : 1)),
    );
    const verdict = score < 0.55 || issues.some((i) => HARD_ISSUES.has(i)) ? "retry" : "keep";

    return {
      score,
      verdict,
      durationMs,
      speech,
      fit: null,
      issues,
      advice: adviceFor(issues, false),
    };
  } finally {
    await ctx.close();
  }
}

export function mergeTakeQuality(local: TakeQuality, remote: SamplePreviewOut): TakeQuality {
  const issues = [...new Set([...local.issues, ...remote.issues])];
  const score = remote.score;
  const verdict = remote.verdict === "keep" && !issues.some((i) => HARD_ISSUES.has(i))
    ? "keep"
    : remote.verdict === "keep"
      ? "keep"
      : "retry";
  return {
    score,
    verdict: verdict === "keep" ? "keep" : "retry",
    durationMs: remote.duration_ms ?? local.durationMs,
    speech: remote.speech ?? local.speech,
    fit: remote.centroid_similarity,
    issues,
    advice: remote.advice || adviceFor(issues, remote.centroid_similarity != null),
  };
}

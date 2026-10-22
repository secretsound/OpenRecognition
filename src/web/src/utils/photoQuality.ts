import type { SamplePreviewOut } from "@/types/api";
import type { TakeQuality } from "@/utils/takeQuality";
import { issueLabel as voiceIssueLabel, mergeTakeQuality } from "@/utils/takeQuality";

export const PHOTO_ISSUE_LABELS: Record<string, string> = {
  too_dark: "Too dark",
  too_bright: "Too bright",
  blurry: "Soft / blurry",
  no_face: "No face found",
  face_too_small: "Face is too small in the frame",
  multiple_faces: "More than one face",
  low_fit: "Doesn't match this face well",
  poor_fit: "Doesn't match this face",
};

const HARD_ISSUES = new Set(["too_dark", "blurry", "no_face", "poor_fit"]);

export function photoIssueLabel(code: string): string {
  return PHOTO_ISSUE_LABELS[code] ?? voiceIssueLabel(code);
}

function adviceFor(issues: string[], hasFit: boolean, kind: "face" | "photo"): string {
  if (issues.includes("no_face")) {
    return "No face was found. Look at the camera and fit your face in the oval.";
  }
  if (issues.includes("face_too_small")) {
    return "Move closer so your face fills more of the frame.";
  }
  if (issues.includes("too_dark")) {
    return "This is too dark. Face a window or lamp — don't stand with bright light behind you.";
  }
  if (issues.includes("too_bright")) {
    return "This is washed out. Turn a bit so the light is not shining straight into the lens.";
  }
  if (issues.includes("blurry")) {
    return "This is soft. Hold still, tap to focus, and try again.";
  }
  if (issues.includes("multiple_faces")) {
    return "More than one face is in the shot. Get the others out of frame.";
  }
  if (issues.includes("poor_fit") || issues.includes("low_fit")) {
    return kind === "face"
      ? "This photo does not match the face you already taught. Make sure it is the same person."
      : "This photo does not match the other shots. Check that it is the same subject.";
  }
  if (hasFit) return "This photo looks good and matches what you already taught.";
  return "This photo looks good.";
}

export async function analyzePhotoLocally(blob: Blob): Promise<TakeQuality> {
  const bitmap = await createImageBitmap(blob);
  const canvas = document.createElement("canvas");
  const maxSide = 320;
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) {
    bitmap.close();
    return {
      score: 0.5,
      verdict: "keep",
      durationMs: 0,
      speech: null,
      fit: null,
      issues: [],
      advice: "This photo looks good.",
    };
  }
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const { data, width, height } = ctx.getImageData(0, 0, canvas.width, canvas.height);

  let sum = 0;
  let grad = 0;
  const px = width * height;
  for (let i = 0; i < data.length; i += 4) {
    const y = (data[i]! * 0.299 + data[i + 1]! * 0.587 + data[i + 2]! * 0.114) / 255;
    sum += y;
  }
  const brightness = sum / px;
  for (let row = 0; row < height - 1; row += 2) {
    for (let col = 0; col < width - 1; col += 2) {
      const i = (row * width + col) * 4;
      const j = (row * width + col + 1) * 4;
      const k = ((row + 1) * width + col) * 4;
      const a = (data[i]! + data[i + 1]! + data[i + 2]!) / 3;
      const b = (data[j]! + data[j + 1]! + data[j + 2]!) / 3;
      const c = (data[k]! + data[k + 1]! + data[k + 2]!) / 3;
      grad += Math.abs(a - b) + Math.abs(a - c);
    }
  }
  const sharpness = grad / (px * 255);

  const issues: string[] = [];
  if (brightness < 0.18) issues.push("too_dark");
  else if (brightness > 0.9) issues.push("too_bright");
  if (sharpness < 0.012) issues.push("blurry");

  const lightScore = brightness < 0.18 || brightness > 0.9 ? 0.25 : 1;
  const sharpScore = Math.max(0, Math.min(1, sharpness / 0.03));
  const score = Math.max(0, Math.min(1, 0.45 * lightScore + 0.55 * sharpScore));
  const verdict = score < 0.55 || issues.some((i) => HARD_ISSUES.has(i)) ? "retry" : "keep";

  return {
    score,
    verdict,
    durationMs: 0,
    speech: null,
    fit: null,
    issues,
    advice: adviceFor(issues, false, "face"),
  };
}

export function mergePhotoQuality(
  local: TakeQuality,
  remote: SamplePreviewOut,
  kind: "face" | "photo" = "face",
): TakeQuality {
  const merged = mergeTakeQuality(local, remote);
  return {
    ...merged,
    advice: remote.advice || adviceFor(merged.issues, remote.centroid_similarity != null, kind),
  };
}

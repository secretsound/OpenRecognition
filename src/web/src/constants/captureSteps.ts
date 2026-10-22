export interface CaptureStepCopy {
  id: string;
  title: string;
  description?: string;
  instruction: string;
  hint?: string;
  facingMode?: "user" | "environment";
}

/** Real-world views a doorbell or room camera actually sees. */
export const FACE_CAPTURE_BANK: CaptureStepCopy[] = [
  {
    id: "front",
    title: "Straight on",
    instruction: "Look straight at the camera. Eyes at camera height, neutral face.",
    hint: "This is the everyday match — a video call or a camera in front of you.",
    facingMode: "user",
  },
  {
    id: "left",
    title: "Turn left",
    instruction: "Turn your head about 45° to the left. Keep both eyes in frame.",
    hint: "Like walking past a doorbell on your right.",
    facingMode: "user",
  },
  {
    id: "right",
    title: "Turn right",
    instruction: "Turn your head about 45° to the right. Keep both eyes in frame.",
    hint: "Same idea from the other side.",
    facingMode: "user",
  },
  {
    id: "up",
    title: "Chin up",
    instruction: "Tilt your chin up a little so the camera sees under the brow.",
    hint: "A camera on a desk or counter looking up at you.",
    facingMode: "user",
  },
  {
    id: "down",
    title: "Chin down",
    instruction: "Tilt your chin down a little — as if the camera is above you.",
    hint: "A doorbell or hallway cam mounted over a door.",
    facingMode: "user",
  },
  {
    id: "close",
    title: "Closer",
    instruction: "Move in so your face fills the oval. Shoulders can clip the edge.",
    hint: "How you look when you lean in to check a phone or tablet.",
    facingMode: "user",
  },
  {
    id: "far",
    title: "A few steps back",
    instruction: "Step back so your head and shoulders are clearly in frame.",
    hint: "How a room camera or a doorbell sees you from the walkway.",
    facingMode: "user",
  },
  {
    id: "smile",
    title: "Natural smile",
    instruction: "Look at the camera and smile the way you would at the door.",
    hint: "People rarely have a passport face on camera.",
    facingMode: "user",
  },
];

export const FACE_CORE_COUNT = 6;
export const FACE_IMPROVE_COUNT = 4;

/** @deprecated use FACE_CAPTURE_BANK / pickFaceSteps */
export const FACE_CAPTURE_STEPS = FACE_CAPTURE_BANK.slice(0, FACE_CORE_COUNT);

export const PHOTO_CAPTURE_BANK: CaptureStepCopy[] = [
  {
    id: "front",
    title: "Straight on",
    instruction: "Fill the frame with a clear front view in even light.",
    facingMode: "environment",
  },
  {
    id: "left",
    title: "Left side",
    instruction: "Move left and capture the same subject from that side.",
    facingMode: "environment",
  },
  {
    id: "right",
    title: "Right side",
    instruction: "Move right and capture the other side.",
    facingMode: "environment",
  },
  {
    id: "close",
    title: "Close-up",
    instruction: "Move in. Keep the subject sharp — this is the detail shot.",
    facingMode: "environment",
  },
  {
    id: "far",
    title: "Full view",
    instruction: "Step back so the whole subject is visible.",
    facingMode: "environment",
  },
  {
    id: "high",
    title: "From above",
    instruction: "Hold the camera a bit higher and look down at the subject.",
    facingMode: "environment",
  },
  {
    id: "low",
    title: "From below",
    instruction: "Hold the camera lower and look up — how a floor cam would see it.",
    facingMode: "environment",
  },
  {
    id: "context",
    title: "In the room",
    instruction: "Include some of the room. Different light is better than a studio match.",
    facingMode: "environment",
  },
];

export const PHOTO_CORE_COUNT = 6;
export const PHOTO_IMPROVE_COUNT = 4;

/** @deprecated use PHOTO_CAPTURE_BANK / pickPhotoSteps */
export const PHOTO_CAPTURE_STEPS = PHOTO_CAPTURE_BANK.slice(0, 5);

export const MIN_PET_OBJECT_PHOTOS = 10;

export type CaptureSessionMode = "core" | "improve" | "encore";

function pickFromBank(
  bank: CaptureStepCopy[],
  usedIds: string[],
  coreCount: number,
  improveCount: number,
): { steps: CaptureStepCopy[]; mode: CaptureSessionMode } {
  const used = new Set(usedIds.filter(Boolean));
  const unused = bank.filter((s) => !used.has(s.id));
  if (used.size < coreCount) {
    return { steps: unused.slice(0, coreCount), mode: "core" };
  }
  if (unused.length > 0) {
    return { steps: unused.slice(0, improveCount), mode: "improve" };
  }
  return { steps: bank.slice(0, improveCount), mode: "encore" };
}

export function pickFaceSteps(usedIds: string[]) {
  return pickFromBank(FACE_CAPTURE_BANK, usedIds, FACE_CORE_COUNT, FACE_IMPROVE_COUNT);
}

export function pickPhotoSteps(usedIds: string[]) {
  return pickFromBank(PHOTO_CAPTURE_BANK, usedIds, PHOTO_CORE_COUNT, PHOTO_IMPROVE_COUNT);
}

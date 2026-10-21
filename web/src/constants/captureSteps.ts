export interface CaptureStepCopy {
  id: string;
  title: string;
  description?: string;
  instruction: string;
  hint?: string;
  facingMode?: "user" | "environment";
}

export const FACE_CAPTURE_STEPS: CaptureStepCopy[] = [
  {
    id: "front",
    title: "Front",
    instruction: "Look straight at the camera with a neutral expression.",
    facingMode: "user",
  },
  {
    id: "left",
    title: "Left profile",
    instruction: "Turn your head about 45° to the left.",
    facingMode: "user",
  },
  {
    id: "right",
    title: "Right profile",
    instruction: "Turn your head about 45° to the right.",
    facingMode: "user",
  },
  {
    id: "up",
    title: "Slight up",
    instruction: "Tilt your chin up slightly — hairline visible.",
    facingMode: "user",
  },
  {
    id: "distance",
    title: "Step back",
    instruction: "Move back so your head and shoulders are in frame.",
    facingMode: "user",
  },
];

export const PHOTO_CAPTURE_STEPS: CaptureStepCopy[] = [
  {
    id: "close",
    title: "Close-up",
    instruction: "Fill the frame with your subject from one clear angle.",
    facingMode: "environment",
  },
  {
    id: "left",
    title: "Left angle",
    instruction: "Capture from the left side with different lighting if possible.",
    facingMode: "environment",
  },
  {
    id: "right",
    title: "Right angle",
    instruction: "Capture from the right side.",
    facingMode: "environment",
  },
  {
    id: "far",
    title: "Full view",
    instruction: "Step back so the whole subject is visible.",
    facingMode: "environment",
  },
  {
    id: "context",
    title: "Environment",
    instruction: "Include some background context — another room or lighting.",
    facingMode: "environment",
  },
];

export const MIN_PET_OBJECT_PHOTOS = 10;

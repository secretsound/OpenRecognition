/**
 * Enrollment phrases chosen for speaker-ID coverage:
 * varied vowels, consonant clusters, sibilants, numbers, and natural rhythm.
 * (Similar idea to phonetically rich read speech used in voice biometrics.)
 */
export const VOICE_ENROLLMENT_PHRASES = [
  "Please read each phrase clearly at a calm, natural speaking pace.",
  "The quick brown fox jumps over the lazy dog near the wide riverbank.",
  "She sells seashells where the soft waves wash against the shore.",
  "Three hundred forty-seven callers registered before noon on Tuesday.",
  "OpenRecognition will learn to recognize my voice from these samples.",
  "Those thick books thought through the path beneath the wooden booth.",
] as const;

export const SOUND_ENROLLMENT_PHRASES = [
  "Record this sound clearly, about five seconds.",
  "Capture the same sound again from a similar distance.",
  "One more sample with a little variation in timing.",
] as const;

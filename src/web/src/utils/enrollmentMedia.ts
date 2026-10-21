import type { EnrollmentType } from "@/types/api";

export interface EnrollmentMediaConfig {
  hint: string;
  detail: string;
  accept: string;
  formatTags: string[];
}

export interface SampleMethod {
  id: "voice" | "files";
  title: string;
  subtitle: string;
  formats: string[];
}

export const enrollmentMediaByType: Record<EnrollmentType, EnrollmentMediaConfig> = {
  person: {
    hint: "Build a voice profile and/or add face photos for recognition.",
    detail: "Use guided voice enrollment for speaker ID, or drop files below.",
    accept:
      "audio/*,image/*,video/*,.wav,.mp3,.flac,.ogg,.m4a,.aac,.jpg,.jpeg,.png,.webp,.mp4,.webm,.mov",
    formatTags: ["WAV", "MP3", "JPEG", "PNG", "MP4", "WebM"],
  },
  pet: {
    hint: "Add varied photos from different angles and lighting.",
    detail: "10+ shots recommended for reliable pet matching.",
    accept: "image/*,video/*,.jpg,.jpeg,.png,.webp,.mp4,.webm,.mov",
    formatTags: ["JPEG", "PNG", "WebM", "MP4"],
  },
  object: {
    hint: "Add clear photos of this object from multiple viewpoints.",
    detail: "Mix distances and backgrounds for robust matching.",
    accept: "image/*,video/*,.jpg,.jpeg,.png,.webp,.mp4,.webm,.mov",
    formatTags: ["JPEG", "PNG", "WebM", "MP4"],
  },
  sound: {
    hint: "Capture this sound event from a few representative clips.",
    detail: "Use guided enrollment or upload files directly.",
    accept: "audio/*,.wav,.mp3,.flac,.ogg,.m4a,.aac",
    formatTags: ["WAV", "MP3", "FLAC", "OGG", "WebM"],
  },
};

export function mediaConfigFor(type: EnrollmentType): EnrollmentMediaConfig {
  return enrollmentMediaByType[type];
}

export function sampleMethodsFor(type: EnrollmentType): SampleMethod[] {
  if (type === "person") {
    return [
      {
        id: "voice",
        title: "Voice",
        subtitle: "Speaker identification — guided phrases or audio files",
        formats: ["WAV", "MP3", "FLAC", "OGG", "WebM"],
      },
      {
        id: "files",
        title: "Photos & files",
        subtitle: "Face photos, voice clips, or trimmed video segments",
        formats: ["JPEG", "PNG", "WebP", "Audio", "MP4", "WebM"],
      },
    ];
  }
  if (type === "sound") {
    return [
      {
        id: "voice",
        title: "Sound clips",
        subtitle: "Guided capture or upload audio samples",
        formats: ["WAV", "MP3", "FLAC", "OGG"],
      },
    ];
  }
  return [
    {
      id: "files",
      title: type === "pet" ? "Pet photos" : "Object photos",
      subtitle: enrollmentMediaByType[type].detail,
      formats: enrollmentMediaByType[type].formatTags,
    },
  ];
}

/** Modality row from quality breakdown, keyed by gallery modality id. */
export function modalitySampleCount(
  modalities: { modality: string; sample_count: number }[] | undefined,
  key: string,
): number | null {
  if (!modalities) return null;
  const row = modalities.find((m) => m.modality === key);
  return row ? row.sample_count : null;
}

import { api } from "@/api/client";
import type { EnrollmentOut, SampleOut } from "@/types/api";

export type TestModality = "audio" | "image";

function counts(
  enrollment: EnrollmentOut,
  samples?: SampleOut[],
): { audio: number; image: number } {
  if (samples) {
    return {
      audio: samples.filter((s) => s.modality === "audio").length,
      image: samples.filter((s) => s.modality === "image").length,
    };
  }
  let audio = 0;
  let image = 0;
  for (const modality of enrollment.quality?.modalities ?? []) {
    if (modality.modality === "audio") audio = modality.sample_count;
    if (modality.modality === "image") image = modality.sample_count;
  }
  return { audio, image };
}

/** Which Test tab matches the samples already stored for this enrollment. */
export function resolveTestModality(
  enrollment: EnrollmentOut,
  samples?: SampleOut[],
): TestModality | "choose" {
  if (enrollment.type === "sound") return "audio";
  if (enrollment.type === "pet" || enrollment.type === "object") return "image";
  const { audio, image } = counts(enrollment, samples);
  if (audio > 0 && image > 0) return "choose";
  if (image > 0) return "image";
  return "audio";
}

export async function resolveTestModalityFor(
  enrollment: EnrollmentOut,
): Promise<TestModality | "choose"> {
  if (enrollment.type !== "person") return resolveTestModality(enrollment);
  const known = (enrollment.quality?.modalities ?? []).some((m) => m.sample_count > 0);
  if (known) return resolveTestModality(enrollment);
  try {
    const samples = await api<SampleOut[]>(`/v1/enrollments/${enrollment.id}/samples`);
    return resolveTestModality(enrollment, samples);
  } catch {
    return resolveTestModality(enrollment);
  }
}

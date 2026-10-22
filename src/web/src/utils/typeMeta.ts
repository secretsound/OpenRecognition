import {
  CubeOutline,
  MusicalNotesOutline,
  PawOutline,
  PersonOutline,
} from "@vicons/ionicons5";
import type { EnrollmentType } from "@/types/api";

export const typeMeta: Record<
  EnrollmentType,
  { label: string; icon: typeof PersonOutline }
> = {
  person: { label: "Person", icon: PersonOutline },
  pet: { label: "Pet", icon: PawOutline },
  object: { label: "Object", icon: CubeOutline },
  sound: { label: "Sound", icon: MusicalNotesOutline },
};

export function typeLabel(type: string): string {
  return typeMeta[type as EnrollmentType]?.label ?? type;
}

export function typeIcon(type: string) {
  return typeMeta[type as EnrollmentType]?.icon ?? CubeOutline;
}

export function initials(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

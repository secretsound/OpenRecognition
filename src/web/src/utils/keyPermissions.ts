export type KeyPreset = "default" | "mcp" | "integration";

export interface KeyPermission {
  id: "read" | "recognize" | "enroll" | "update" | "delete" | "admin";
  label: string;
  hint: string;
}

export const KEY_PERMISSIONS: KeyPermission[] = [
  {
    id: "read",
    label: "View",
    hint: "See the library, who was recognized, and whether the server is ready.",
  },
  {
    id: "recognize",
    label: "Recognize",
    hint: "Match a voice, photo, or video.",
  },
  {
    id: "enroll",
    label: "Add",
    hint: "Create profiles and add samples.",
  },
  {
    id: "update",
    label: "Update",
    hint: "Change names, thresholds, and samples on profiles that already exist.",
  },
  {
    id: "delete",
    label: "Delete",
    hint: "Remove profiles from the library.",
  },
  {
    id: "admin",
    label: "Full access",
    hint: "Users, keys, settings, and everything above.",
  },
];

const ORDER = ["read", "recognize", "enroll", "update", "delete", "admin"] as const;

export function canonicalScopes(scopes: string[]): string[] {
  if (scopes.includes("admin")) return ["admin"];
  return ORDER.filter((id) => id !== "admin" && scopes.includes(id));
}

export function permissionChips(scopes: string[]): { id: string; label: string; tone: "default" | "warning" }[] {
  const canonical = canonicalScopes(scopes);
  if (canonical.includes("admin")) {
    return [{ id: "admin", label: "Full access", tone: "warning" }];
  }
  return KEY_PERMISSIONS.filter((item) => canonical.includes(item.id)).map((item) => ({
    id: item.id,
    label: item.label,
    tone: "default" as const,
  }));
}

export function scopesForPreset(preset: KeyPreset): string[] {
  if (preset === "mcp") return ["read", "recognize"];
  if (preset === "integration") return ["recognize"];
  return [];
}

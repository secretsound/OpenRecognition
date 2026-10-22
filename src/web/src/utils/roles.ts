export type Role = "admin" | "operator" | "viewer";

export function canAdmin(role: string | null | undefined): boolean {
  return role === "admin";
}

export function canWrite(role: string | null | undefined): boolean {
  return role === "admin" || role === "operator";
}

export function roleFromScopes(scopes: string[] | null | undefined): Role {
  const set = new Set(scopes ?? []);
  if (set.has("admin")) return "admin";
  if (set.has("enroll") || set.has("recognize")) return "operator";
  return "viewer";
}

export { roleLabel } from "@/i18n";

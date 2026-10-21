/** In-app path only. Rejects protocol-relative and external redirects. */
export function safeAppPath(value: unknown): string | null {
  if (typeof value !== "string") return null;
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return null;
  return value;
}

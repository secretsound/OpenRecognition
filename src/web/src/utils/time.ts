const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

const absolute = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const timeOnly = new Intl.DateTimeFormat(undefined, { timeStyle: "short" });

export function parseDate(value: string | number | Date): Date | null {
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "just now", "3 min ago", "yesterday", "Oct 12" */
export function formatRelative(value: string | number | Date, now = Date.now()): string {
  const d = parseDate(value);
  if (!d) return "—";
  const diff = (d.getTime() - now) / 1000;
  const abs = Math.abs(diff);
  if (abs < 45) return "just now";
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  if (abs < 86400 * 7) return rtf.format(Math.round(diff / 86400), "day");
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: d.getFullYear() === new Date(now).getFullYear() ? undefined : "numeric",
  }).format(d);
}

export function formatAbsolute(value: string | number | Date): string {
  const d = parseDate(value);
  return d ? absolute.format(d) : "—";
}

export function formatTime(value: string | number | Date): string {
  const d = parseDate(value);
  return d ? timeOnly.format(d) : "—";
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${Math.round(s % 60)} s`;
}

export function formatBytes(n: number | null | undefined): string {
  if (n == null || n <= 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

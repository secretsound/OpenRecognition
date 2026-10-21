import type { AppSettingsOut, SystemInfoOut } from "@/types/api";

export interface HealthSnapshot {
  version?: string;
}

/** Backfill when API is older than the UI (missing `system` on settings). */
export function ensureSystemInfo(
  settings: AppSettingsOut,
  health: HealthSnapshot | null,
): AppSettingsOut {
  if (settings.system) return settings;
  const bind = `${settings.host}:${settings.port}`;
  const localHost =
    settings.host === "0.0.0.0" || settings.host === "::" ? "127.0.0.1" : settings.host;
  const fallback: SystemInfoOut = {
    server_version: health?.version ?? "—",
    python_version: "—",
    platform: "—",
    hostname: "—",
    lan_addresses: [],
    api_bind: bind,
    api_local_url: `http://${localHost}:${settings.port}`,
    web_origin: null,
  };
  return { ...settings, system: fallback };
}

export function lanApiUrls(settings: AppSettingsOut): string[] {
  const addrs = settings.system?.lan_addresses ?? [];
  if (!addrs.length) return [];
  return addrs.map((ip) => `http://${ip}:${settings.port}`);
}

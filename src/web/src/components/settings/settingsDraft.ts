import type { AppSettingsOut, AppSettingsPatch } from "@/types/api";

export interface SettingsDraft {
  maintenance_mode: boolean;
  enrollment_media_retention: string;
  feature_flags: Record<string, boolean>;
  default_min_confidence: number;
  default_return_unknown: boolean;
  default_include_sound_events: boolean;
  recognition_log_retention_days: number;
  session_ttl_minutes: number | null;
  model_idle_unload_minutes: number | null;
  public_url: string;
  behind_proxy: boolean;
  trusted_proxies: string;
  display_language: string;
  display_timezone: string;
  auth_rate_limit_per_minute: number | null;
  video_max_upload_mb: number | null;
  log_max_mb: number | null;
  log_backup_count: number | null;
  health_detail_public: boolean;
  metrics_token: string;
  clear_metrics_token: boolean;
  host: string;
  port: number | null;
  http_enabled: boolean;
  https_enabled: boolean;
  https_port: number | null;
  tls_cert_file: string;
  tls_key_file: string;
  tls_cert_pem: string;
  tls_key_pem: string;
  models_dir: string;
  model_packs_dir: string;
  logs_dir: string;
  log_level: string;
  log_to_file: boolean;
  sso_enabled: boolean;
  sso_protocol: string;
  sso_label: string;
  sso_auto_provision: boolean;
  sso_default_role: string;
  sso_link_existing: boolean;
  sso_username_claim: string;
  oidc_issuer: string;
  oidc_client_id: string;
  oidc_client_secret: string;
  clear_oidc_client_secret: boolean;
  oidc_scopes: string;
  oidc_groups_claim: string;
  saml_idp_entity_id: string;
  saml_idp_sso_url: string;
  saml_idp_x509_cert: string;
  saml_sp_entity_id: string;
  saml_username_attr: string;
  saml_groups_attr: string;
}

export function draftFrom(s: AppSettingsOut): SettingsDraft {
  return {
    maintenance_mode: s.maintenance_mode,
    enrollment_media_retention: s.enrollment_media_retention,
    feature_flags: { ...s.feature_flags },
    default_min_confidence: s.default_min_confidence,
    default_return_unknown: s.default_return_unknown,
    default_include_sound_events: s.default_include_sound_events,
    recognition_log_retention_days: s.recognition_log_retention_days,
    session_ttl_minutes: s.session_ttl_minutes,
    model_idle_unload_minutes: s.model_idle_unload_minutes,
    public_url: s.public_url ?? "",
    behind_proxy: s.behind_proxy ?? false,
    trusted_proxies: s.trusted_proxies ?? "",
    display_language: s.display_language ?? "en",
    display_timezone: s.display_timezone || "UTC",
    auth_rate_limit_per_minute: s.auth_rate_limit_per_minute,
    video_max_upload_mb: Math.max(1, Math.round((s.video_max_upload_bytes ?? 100 * 1024 * 1024) / (1024 * 1024))),
    log_max_mb: s.log_max_mb ?? 5,
    log_backup_count: s.log_backup_count ?? 5,
    health_detail_public: s.health_detail_public ?? true,
    metrics_token: "",
    clear_metrics_token: false,
    host: s.host,
    port: s.port,
    http_enabled: s.http_enabled ?? true,
    https_enabled: s.https_enabled ?? false,
    https_port: s.https_port ?? 8443,
    tls_cert_file: s.tls_cert_file ?? "",
    tls_key_file: s.tls_key_file ?? "",
    tls_cert_pem: "",
    tls_key_pem: "",
    models_dir: s.models_dir,
    model_packs_dir: s.model_packs_dir ?? "",
    logs_dir: s.logs_dir ?? "",
    log_level: s.log_level ?? "info",
    log_to_file: s.log_to_file ?? true,
    sso_enabled: s.sso_enabled ?? false,
    sso_protocol: s.sso_protocol ?? "oidc",
    sso_label: s.sso_label ?? "Single sign-on",
    sso_auto_provision: s.sso_auto_provision ?? false,
    sso_default_role: s.sso_default_role ?? "viewer",
    sso_link_existing: s.sso_link_existing ?? true,
    sso_username_claim: s.sso_username_claim ?? "preferred_username",
    oidc_issuer: s.oidc_issuer ?? "",
    oidc_client_id: s.oidc_client_id ?? "",
    oidc_client_secret: "",
    clear_oidc_client_secret: false,
    oidc_scopes: s.oidc_scopes ?? "openid profile email",
    oidc_groups_claim: s.oidc_groups_claim ?? "groups",
    saml_idp_entity_id: s.saml_idp_entity_id ?? "",
    saml_idp_sso_url: s.saml_idp_sso_url ?? "",
    saml_idp_x509_cert: s.saml_idp_x509_cert ?? "",
    saml_sp_entity_id: s.saml_sp_entity_id ?? "",
    saml_username_attr: s.saml_username_attr ?? "uid",
    saml_groups_attr: s.saml_groups_attr ?? "groups",
  };
}

function flagsDiffer(draft: SettingsDraft, server: AppSettingsOut): boolean {
  const keys = new Set([
    ...Object.keys(draft.feature_flags),
    ...Object.keys(server.feature_flags),
  ]);
  for (const key of keys) {
    if ((draft.feature_flags[key] ?? false) !== (server.feature_flags[key] ?? false)) return true;
  }
  return false;
}

export function draftDirty(draft: SettingsDraft, server: AppSettingsOut): boolean {
  const base = draftFrom(server);
  const keys = Object.keys(base) as (keyof SettingsDraft)[];
  for (const key of keys) {
    if (key === "feature_flags" || key === "tls_cert_pem" || key === "tls_key_pem") continue;
    if (key === "oidc_client_secret" || key === "clear_oidc_client_secret") continue;
    if (key === "metrics_token" || key === "clear_metrics_token") continue;
    if (draft[key] !== base[key]) return true;
  }
  if (flagsDiffer(draft, server)) return true;
  if (draft.tls_cert_pem.trim() || draft.tls_key_pem.trim()) return true;
  if (draft.oidc_client_secret.trim() || draft.clear_oidc_client_secret) return true;
  if (draft.metrics_token.trim() || draft.clear_metrics_token) return true;
  return false;
}

export function draftError(draft: SettingsDraft, secretSet: boolean): string | null {
  if (!draft.http_enabled && !draft.https_enabled) return "network.bothOff";
  if (
    draft.http_enabled &&
    draft.https_enabled &&
    draft.port != null &&
    draft.port === draft.https_port
  ) {
    return "network.samePort";
  }
  const cert = draft.tls_cert_pem.trim();
  const key = draft.tls_key_pem.trim();
  if ((cert && !key) || (!cert && key)) return "network.pemPair";
  const files = Boolean(draft.tls_cert_file.trim() && draft.tls_key_file.trim());
  if (draft.https_enabled && !files && !(cert && key)) return "network.httpsNeedsCert";
  if (draft.sso_enabled && draft.sso_protocol === "oidc") {
    if (!draft.oidc_issuer.trim() || !draft.oidc_client_id.trim()) return "oidc.incomplete";
    const scopes = draft.oidc_scopes.toLowerCase().split(/\s+/);
    if (!scopes.includes("openid")) return "oidc.scope";
    if (!secretSet && !draft.oidc_client_secret.trim()) return "oidc.secretMissing";
    if (draft.clear_oidc_client_secret && !draft.oidc_client_secret.trim()) return "oidc.secretMissing";
  }
  if (draft.sso_enabled && draft.sso_protocol === "saml") {
    if (
      !draft.saml_idp_entity_id.trim() ||
      !draft.saml_idp_sso_url.trim() ||
      !draft.saml_idp_x509_cert.trim()
    ) {
      return "saml.incomplete";
    }
  }
  if (
    draft.auth_rate_limit_per_minute == null ||
    draft.video_max_upload_mb == null ||
    draft.log_max_mb == null ||
    draft.log_backup_count == null
  ) {
    return "settings.incomplete";
  }
  return null;
}

export function draftPatch(draft: SettingsDraft): AppSettingsPatch {
  if (
    draft.port == null ||
    draft.https_port == null ||
    draft.session_ttl_minutes == null ||
    draft.model_idle_unload_minutes == null ||
    draft.auth_rate_limit_per_minute == null ||
    draft.video_max_upload_mb == null ||
    draft.log_max_mb == null ||
    draft.log_backup_count == null
  ) {
    throw new Error("incomplete settings");
  }
  const patch: AppSettingsPatch = {
    maintenance_mode: draft.maintenance_mode,
    enrollment_media_retention: draft.enrollment_media_retention,
    feature_flags: { ...draft.feature_flags },
    default_min_confidence: draft.default_min_confidence,
    default_return_unknown: draft.default_return_unknown,
    default_include_sound_events: draft.default_include_sound_events,
    recognition_log_retention_days: draft.recognition_log_retention_days,
    session_ttl_minutes: draft.session_ttl_minutes,
    model_idle_unload_minutes: draft.model_idle_unload_minutes,
    public_url: draft.public_url.trim(),
    behind_proxy: draft.behind_proxy,
    trusted_proxies: draft.trusted_proxies.trim(),
    display_language: draft.display_language,
    display_timezone: draft.display_timezone,
    auth_rate_limit_per_minute: draft.auth_rate_limit_per_minute,
    video_max_upload_bytes: draft.video_max_upload_mb * 1024 * 1024,
    log_max_mb: draft.log_max_mb,
    log_backup_count: draft.log_backup_count,
    health_detail_public: draft.health_detail_public,
    clear_metrics_token: draft.clear_metrics_token,
    host: draft.host.trim(),
    port: draft.port,
    http_enabled: draft.http_enabled,
    https_enabled: draft.https_enabled,
    https_port: draft.https_port,
    tls_cert_file: draft.tls_cert_file.trim(),
    tls_key_file: draft.tls_key_file.trim(),
    models_dir: draft.models_dir.trim(),
    model_packs_dir: draft.model_packs_dir.trim(),
    logs_dir: draft.logs_dir.trim(),
    log_level: draft.log_level,
    log_to_file: draft.log_to_file,
    sso_enabled: draft.sso_enabled,
    sso_protocol: draft.sso_protocol,
    sso_label: draft.sso_label.trim(),
    sso_auto_provision: draft.sso_auto_provision,
    sso_default_role: draft.sso_default_role,
    sso_link_existing: draft.sso_link_existing,
    sso_username_claim: draft.sso_username_claim.trim(),
    oidc_issuer: draft.oidc_issuer.trim(),
    oidc_client_id: draft.oidc_client_id.trim(),
    oidc_scopes: draft.oidc_scopes.trim(),
    oidc_groups_claim: draft.oidc_groups_claim.trim(),
    saml_idp_entity_id: draft.saml_idp_entity_id.trim(),
    saml_idp_sso_url: draft.saml_idp_sso_url.trim(),
    saml_idp_x509_cert: draft.saml_idp_x509_cert.trim(),
    saml_sp_entity_id: draft.saml_sp_entity_id.trim(),
    saml_username_attr: draft.saml_username_attr.trim(),
    saml_groups_attr: draft.saml_groups_attr.trim(),
    clear_oidc_client_secret: draft.clear_oidc_client_secret,
  };
  if (draft.oidc_client_secret.trim()) patch.oidc_client_secret = draft.oidc_client_secret.trim();
  if (draft.metrics_token.trim()) patch.metrics_token = draft.metrics_token.trim();
  if (draft.tls_cert_pem.trim() && draft.tls_key_pem.trim()) {
    patch.tls_cert_pem = draft.tls_cert_pem.trim();
    patch.tls_key_pem = draft.tls_key_pem.trim();
  }
  return patch;
}

export function callbackBase(publicUrl: string): string {
  const trimmed = publicUrl.trim().replace(/\/$/, "");
  if (trimmed) return trimmed;
  return typeof window !== "undefined" ? window.location.origin : "";
}

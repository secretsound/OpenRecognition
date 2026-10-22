export type EnrollmentType = "person" | "pet" | "object" | "sound";

export interface ModalityQuality {
  modality: string;
  label: string;
  sample_count: number;
  score: number;
  issues: string[];
  usable: boolean;
}

export interface QualityInfo {
  score: number;
  issues: string[];
  usable: boolean;
  modalities?: ModalityQuality[];
}

export interface EnrollmentOut {
  id: string;
  type: EnrollmentType;
  label: string;
  species_hint: string | null;
  enabled: boolean;
  threshold: number | null;
  learn_enabled?: boolean;
  learn_min_confidence?: number;
  learn_margin?: number;
  learn_daily_cap?: number;
  learn_max_samples?: number;
  wyoming_min_confidence?: number | null;
  external_ids?: Record<string, string>;
  sample_count: number;
  model_version: string | null;
  created_at: string;
  updated_at: string;
  quality: QualityInfo | null;
  duplicate_warning: string | null;
  last_seen_at?: string | null;
}

export interface EnrollmentPatch {
  label?: string;
  threshold?: number | null;
  enabled?: boolean;
  external_ids?: Record<string, string>;
  learn_enabled?: boolean;
  learn_min_confidence?: number;
  learn_margin?: number;
  learn_daily_cap?: number;
  learn_max_samples?: number;
  wyoming_min_confidence?: number | null;
}

export interface SampleOut {
  id: string;
  enrollment_id: string;
  modality: string;
  model_version: string;
  source: string;
  source_label: string;
  original_filename: string | null;
  content_type: string | null;
  size_bytes: number | null;
  duration_ms: number | null;
  phrase_index: number | null;
  phrase_text: string | null;
  created_at: string;
  centroid_similarity: number | null;
  media_stored: boolean;
  flags: string[];
}

export interface SamplePreviewOut {
  score: number;
  verdict: "keep" | "retry" | string;
  duration_ms: number | null;
  gate: string | null;
  reason: string | null;
  speech: number | null;
  centroid_similarity: number | null;
  issues: string[];
  advice: string;
}

export interface ApiKeyOut {
  id: string;
  name: string;
  scopes: string[];
  mcp_tool_allowlist: string[] | null;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface McpToolOut {
  name: string;
  description: string;
  scope: string;
}

export interface McpResourceOut {
  uri: string;
  name: string;
  description: string;
  scope: string;
}

export interface ApiKeyCreated extends ApiKeyOut {
  key: string;
  mcp_tools: McpToolOut[];
  mcp_resources: McpResourceOut[];
}

export interface InferenceStatus {
  requested: string;
  effective_summary: string;
  models: Record<string, string>;
  warnings: string[];
}

export interface HardwareOut {
  detected: string;
  override: string | null;
  effective: string;
  label: string;
  cpu_count: number;
  memory_mb: number;
  arch: string;
}

export interface ThreadsOut {
  value: number;
  automatic: number;
  overridden: boolean;
}

export interface KnobField {
  key: string;
  label: string;
  kind: "int" | "float";
  min: number;
  max: number;
  step: number;
  default: number;
  value: number;
  overridden: boolean;
}

export interface CapabilitiesOut {
  hardware: HardwareOut;
  version: string;
  recognition_types: string[];
  modalities: string[];
  models: Record<string, string>;
  inference?: InferenceStatus;
  endpoints: string[];
  video_limits?: VideoLimits;
}

export interface VideoLimits {
  recommended_sec: [number, number];
  enrollment_max_sec: number;
  recognize_sync_max_sec: number;
  recognize_async_max_sec: number;
  max_upload_bytes: number;
}

export interface GroupBriefOut {
  id: string;
  name: string;
}

export interface EnrollmentGrantOut {
  enrollment_id: string;
  can_add_samples: boolean;
  can_manage: boolean;
}

export interface GroupMemberOut {
  id: string;
  username: string;
  role: string;
}

export interface GroupEnrollmentOut {
  enrollment_id: string;
  label: string;
  type: string;
  can_add_samples: boolean;
  can_manage: boolean;
}

export interface GroupOut {
  id: string;
  name: string;
  description: string;
  grants_role: string | null;
  sso_name: string | null;
  system: boolean;
  created_at: string;
  member_count: number;
  enrollment_count: number;
  members: GroupMemberOut[];
  enrollments: GroupEnrollmentOut[];
}

export interface UserOut {
  id: string;
  username: string;
  role: string;
  created_at: string;
  groups?: GroupBriefOut[];
}

export interface LoginResponse {
  session_id: string;
  username: string;
  role: string;
}

export interface WebhookSubscriptionOut {
  id: string;
  url: string;
  name: string;
  title_template: string;
  message_template: string;
  events: string[];
  filters: Record<string, unknown>;
  debounce_seconds: number;
  include_details: boolean;
  created_at: string;
}

export interface MqttIntegrationOut {
  enabled: boolean;
  host: string;
  port: number;
  topic_prefix: string;
  username: string;
  password_set: boolean;
  client_id: string;
  use_tls: boolean;
  tls_insecure: boolean;
  qos: number;
  retain: boolean;
  connected: boolean;
  last_error: string | null;
}

export interface MqttIntegrationPatch {
  enabled?: boolean;
  host?: string;
  port?: number;
  topic_prefix?: string;
  username?: string;
  password?: string;
  client_id?: string;
  use_tls?: boolean;
  tls_insecure?: boolean;
  qos?: number;
  retain?: boolean;
}

export interface DiscoveredWyomingOut {
  name: string;
  host: string;
  port: number;
  uri: string;
}

export interface DiscoveredHomeAssistantOut {
  name: string;
  host: string;
  port: number;
  url: string;
}

export interface MdnsDiscoveryOut {
  available: boolean;
  wyoming: DiscoveredWyomingOut[];
  home_assistant: DiscoveredHomeAssistantOut[];
}

export interface IntegrationConnectivityOut {
  ok: boolean;
  message: string;
  languages: string[] | null;
}

export interface WyomingIntegrationOut {
  enabled: boolean;
  uri: string;
  upstream_uri: string;
  home_assistant_url: string | null;
  min_confidence: number;
  require_speaker_match: boolean;
  block_on_gate_reject: boolean;
  tag_speaker: boolean;
  include_confidence: boolean;
  include_candidates: boolean;
  include_sound_events: boolean;
  zeroconf_enabled: boolean;
  zeroconf_name: string;
  advertise_host: string | null;
  available: boolean;
  upstream_ready: boolean;
  zeroconf_registered: boolean;
  listen_error: string | null;
  ports_conflict: boolean;
  discovery: WyomingDiscoveryContextOut | null;
}

export interface WyomingDiscoveryContextOut {
  in_container: boolean;
  detected_host: string;
  listen_port: number | null;
  mdns_likely_limited: boolean;
  manual_ha_hint: string | null;
  message: string | null;
}

export interface WyomingIntegrationPatch {
  enabled?: boolean;
  uri?: string;
  upstream_uri?: string;
  home_assistant_url?: string | null;
  min_confidence?: number;
  require_speaker_match?: boolean;
  block_on_gate_reject?: boolean;
  tag_speaker?: boolean;
  include_confidence?: boolean;
  include_candidates?: boolean;
  include_sound_events?: boolean;
  zeroconf_enabled?: boolean;
  zeroconf_name?: string;
  advertise_host?: string | null;
}

export interface McpScopeGroupOut {
  id: string;
  label: string;
  description: string;
}

export interface McpHostConfigHintOut {
  host: string;
  config_path: string;
}

export interface McpIntegrationOut {
  available: boolean;
  api_base_url: string;
  server_ready: boolean;
  scope_groups: McpScopeGroupOut[];
  suggested_scopes: string[];
  tools: McpToolOut[];
  resources: McpResourceOut[];
  enabled_tools: McpToolOut[];
  enabled_resources: McpResourceOut[];
  host_config_json: string;
  host_config_hints: McpHostConfigHintOut[];
  install_hint: string | null;
}

export interface AuthMeOut {
  credential_type: string;
  name: string;
  scopes: string[];
  role?: string | null;
  mcp_tools: McpToolOut[];
  mcp_resources: McpResourceOut[];
  groups?: GroupBriefOut[];
  enrollment_grants?: EnrollmentGrantOut[];
  library_limited?: boolean;
}

export interface IntegrationsOverviewOut {
  mqtt: MqttIntegrationOut;
  wyoming: WyomingIntegrationOut;
  mcp: McpIntegrationOut;
  webhooks: WebhookSubscriptionOut[];
}

export type InferenceBackend = "auto" | "onnx" | "heuristic";

export type ModelTier = "essential" | "recommended" | "optional";

export interface ModelCategory {
  id: string;
  label: string;
  description: string;
  sort_order: number;
}

export interface ModelPreset {
  id: string;
  label: string;
  description: string;
  keys: string[];
  tier: ModelTier;
  sort_order: number;
  complete: boolean;
  missing_keys: string[];
}

export interface ModelCatalogEntry {
  key: string;
  filename: string;
  source: string;
  url: string;
  page_url?: string;
  description: string;
  disk_bytes?: number;
  memory_mb?: number;
  license: string;
  license_warning?: boolean;
  on_disk: boolean;
  size_bytes: number | null;
  category: string;
  use_for: string;
  label?: string;
  version?: string;
  onnx?: Record<string, string | number | boolean>;
  contract?: Record<string, string | number | boolean>;
  knobs?: KnobField[];
  origin?: "builtin" | "custom";
  active?: boolean;
  hardware?: "pi" | "mini" | "desktop" | "server";
  hardware_note?: string;
  fit?: "match" | "lighter" | "heavier";
  suggested?: boolean;
  reenroll_count?: number;
  enrollment_count?: number;
  tier: ModelTier;
  enables: string[];
  depends_on: string[];
  sort_order: number;
}

export interface ModelsStatusOut {
  models_dir: string;
  hardware: HardwareOut;
  threads: ThreadsOut;
  categories: ModelCategory[];
  presets: ModelPreset[];
  catalog: ModelCatalogEntry[];
  inference_backend: InferenceBackend;
  loaded_models: Record<string, string>;
  inference?: InferenceStatus;
}

export interface ModelDownloadResponse {
  results: Array<{
    key: string;
    status: string;
    message: string;
    path?: string | null;
    source?: string | null;
  }>;
  models: Record<string, string>;
  inference: InferenceStatus;
}

export interface SystemInfoOut {
  server_version: string;
  python_version: string;
  platform: string;
  hostname: string;
  lan_addresses: string[];
  api_bind: string;
  api_local_url: string;
  web_origin: string | null;
}

export interface AppSettingsOut {
  maintenance_mode: boolean;
  enrollment_media_retention: string;
  inference_backend: InferenceBackend;
  inference_status?: InferenceStatus;
  system: SystemInfoOut;
  feature_flags: Record<string, boolean>;
  default_min_confidence: number;
  default_return_unknown: boolean;
  default_include_sound_events: boolean;
  recognition_log_retention_days: number;
  hardware: HardwareOut;
  auth_required: boolean;
  docs_enabled: boolean;
  web_enabled: boolean;
  data_dir: string;
  models_dir: string;
  model_packs_dir?: string;
  session_ttl_minutes: number;
  mqtt_enabled: boolean;
  mqtt_host: string;
  mqtt_port: number;
  mqtt_topic_prefix: string;
  model_idle_unload_minutes: number;
  auth_rate_limit_per_minute: number;
  display_timezone?: string;
  log_max_mb?: number;
  log_backup_count?: number;
  video_max_upload_bytes?: number;
  health_detail_public?: boolean;
  metrics_token_set?: boolean;
  host: string;
  port: number;
  http_enabled?: boolean;
  https_enabled?: boolean;
  https_port?: number;
  tls_cert_file?: string;
  tls_key_file?: string;
  tls_configured?: boolean;
  tls_readable?: boolean;
  tls_subject?: string;
  tls_expires_at?: string;
  tls_error?: string;
  public_url?: string;
  behind_proxy?: boolean;
  trusted_proxies?: string;
  display_language?: string;
  logs_dir?: string;
  log_level?: string;
  log_to_file?: boolean;
  log_file?: string;
  sso_enabled?: boolean;
  sso_protocol?: string;
  sso_label?: string;
  sso_auto_provision?: boolean;
  sso_default_role?: string;
  sso_link_existing?: boolean;
  sso_username_claim?: string;
  oidc_issuer?: string;
  oidc_client_id?: string;
  oidc_client_secret_set?: boolean;
  oidc_scopes?: string;
  oidc_groups_claim?: string;
  saml_idp_entity_id?: string;
  saml_idp_sso_url?: string;
  saml_idp_x509_cert?: string;
  saml_sp_entity_id?: string;
  saml_username_attr?: string;
  saml_groups_attr?: string;
  sso_redirect_uri?: string;
  sso_acs_url?: string;
  sso_metadata_url?: string;
  sso_sp_entity_id?: string;
  runtime_settings_path: string;
  restart_required_for: string[];
  restart_pending?: string[];
  env_only?: string[];
}

export interface StorageUsageOut {
  data_bytes: number;
  models_bytes: number;
  logs_bytes: number;
}

export interface BackupRestoreOut {
  ok: boolean;
  message: string;
}

export interface ServerLogsOut {
  path: string;
  level: string;
  file_enabled: boolean;
  lines: string[];
}

export interface UiConfigOut {
  display_language: string;
  display_timezone?: string;
  sso_enabled: boolean;
  sso_protocol: string;
  sso_label: string;
}

export interface SelfSignedTlsOut {
  cert_pem: string;
  key_pem: string;
  subject: string;
  expires_at: string;
}

export interface OidcDiscoverOut {
  issuer: string;
  authorization_endpoint: string;
  token_endpoint: string;
  jwks_uri: string;
}

export interface SamlMetadataOut {
  saml_idp_entity_id: string;
  saml_idp_sso_url: string;
  saml_idp_x509_cert: string;
}

export interface ServiceRestartOut {
  ok: boolean;
  message: string;
  delay_seconds: number;
}

export interface AppSettingsPatch {
  maintenance_mode?: boolean;
  enrollment_media_retention?: string;
  inference_backend?: InferenceBackend;
  feature_flags?: Record<string, boolean>;
  default_min_confidence?: number;
  default_return_unknown?: boolean;
  default_include_sound_events?: boolean;
  recognition_log_retention_days?: number;
  session_ttl_minutes?: number;
  model_idle_unload_minutes?: number;
  onnx_intra_op_threads?: number | null;
  public_url?: string;
  behind_proxy?: boolean;
  trusted_proxies?: string;
  display_language?: string;
  display_timezone?: string;
  auth_rate_limit_per_minute?: number;
  video_max_upload_bytes?: number;
  log_max_mb?: number;
  log_backup_count?: number;
  health_detail_public?: boolean;
  metrics_token?: string;
  clear_metrics_token?: boolean;
  host?: string;
  port?: number;
  http_enabled?: boolean;
  https_enabled?: boolean;
  https_port?: number;
  tls_cert_file?: string;
  tls_key_file?: string;
  tls_cert_pem?: string;
  tls_key_pem?: string;
  models_dir?: string;
  model_packs_dir?: string;
  logs_dir?: string;
  log_level?: string;
  log_to_file?: boolean;
  sso_enabled?: boolean;
  sso_protocol?: string;
  sso_label?: string;
  sso_auto_provision?: boolean;
  sso_default_role?: string;
  sso_link_existing?: boolean;
  sso_username_claim?: string;
  oidc_issuer?: string;
  oidc_client_id?: string;
  oidc_client_secret?: string;
  clear_oidc_client_secret?: boolean;
  oidc_scopes?: string;
  oidc_groups_claim?: string;
  saml_idp_entity_id?: string;
  saml_idp_sso_url?: string;
  saml_idp_x509_cert?: string;
  saml_sp_entity_id?: string;
  saml_username_attr?: string;
  saml_groups_attr?: string;
}

export interface EntityResult {
  entity_id: string | null;
  label: string;
  type: string;
  recognition_type: string;
  confidence: number;
  modality: string;
  threshold_used: number | null;
  time_range: number[] | null;
  bbox: number[] | null;
  track_id: string | null;
  attributes: Record<string, unknown>;
}

export interface RecognizeMeta {
  hardware: string;
  latency_ms: number;
  request_id: string | null;
  camera_id: string | null;
  zone: string | null;
  dry_run: boolean;
}

export interface CandidateMatch {
  entity_id: string;
  label: string;
  type: string;
  recognition_type: string;
  confidence: number;
  modality: string;
  threshold_used: number | null;
  enrollment_threshold?: number | null;
  accepted: boolean;
}

export interface RecognizeDiagnostics {
  pipelines: string[];
  candidates: CandidateMatch[];
  notes: string[];
}

export interface RecognizeResponse {
  entities: EntityResult[];
  gate?: string | null;
  reason?: string | null;
  scores?: Record<string, number> | null;
  diagnostics?: RecognizeDiagnostics | null;
  meta: RecognizeMeta;
}

export interface GateResponse {
  gate: string;
  reason: string | null;
  scores: Record<string, number>;
  latency_ms: number;
}

export interface RecognitionLogOut {
  id: string;
  event: string;
  modality: string | null;
  label: string | null;
  entity_id: string | null;
  confidence: number | null;
  camera_id: string | null;
  zone: string | null;
  request_id: string | null;
  gate: string | null;
  reason: string | null;
  summary: string | null;
  actor_type: string | null;
  actor_id: string | null;
  actor_name: string | null;
  latency_ms: number | null;
  dry_run: boolean;
  details: RecognitionLogDetails | null;
  created_at: string;
}

export interface RecognitionLogGateScores {
  speech?: number;
  music?: number;
  noise?: number;
}

export interface RecognitionLogSpeakerCandidate {
  label: string;
  entity_id?: string | null;
  confidence: number;
  accepted?: boolean;
  /** Bar this enrollment had to clear on this match path. */
  threshold_used?: number | null;
}

export interface RecognitionLogDetails {
  audio_sec?: number;
  transcript?: string;
  block_reason?: string;
  upstream_skipped?: boolean;
  accepted?: boolean;
  min_confidence?: number;
  /** Request or server bar before a per-enrollment raise or Wyoming override. */
  default_min_confidence?: number;
  speaker_match_attempted?: boolean;
  gallery_count?: number;
  comparable_speaker_count?: number;
  speaker_model_version?: string;
  gate_scores?: RecognitionLogGateScores;
  speaker_candidates?: RecognitionLogSpeakerCandidate[];
  timing_ms?: {
    identify?: number;
    upstream?: number;
    total?: number;
  };
}

export interface RecognitionLogListOut {
  items: RecognitionLogOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface PresenceEntry {
  enrollment_id: string;
  label: string;
  type: string;
  last_seen_at: string;
  last_modality: string;
  last_camera_id: string | null;
  confidence: number | null;
}

export interface ConsoleOverviewOut {
  enrollments: EnrollmentOut[];
  ready_count: number;
  attention: EnrollmentOut[];
  recent_activity: RecognitionLogOut[];
  last_seen: PresenceEntry | null;
  models_ready: boolean;
  wyoming_enabled: boolean;
  webhook_count: number;
  has_recognition: boolean;
  hardware: string;
  models: Record<string, string>;
}

export interface ConsoleEvent {
  type: string;
  log?: RecognitionLogOut;
}

export interface JobOut {
  id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  result: RecognizeResponse | null;
  error: string | null;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  detail?: unknown;
}

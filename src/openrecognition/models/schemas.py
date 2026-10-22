"""Pydantic request/response models."""

from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EnrollmentType(str, Enum):
    person = "person"
    pet = "pet"
    object = "object"
    sound = "sound"


class MatchPolicy(BaseModel):
    match_policy: str = "enrolled_only"
    min_confidence: float = 0.75
    return_unknown: bool = True


class RequestContext(BaseModel):
    camera_id: str | None = None
    zone: str | None = None
    trigger: str | None = None
    client: str | None = None


class ModalityQuality(BaseModel):
    modality: str
    label: str
    sample_count: int
    score: float
    issues: list[str] = Field(default_factory=list)
    usable: bool = True


class QualityInfo(BaseModel):
    score: float
    issues: list[str] = Field(default_factory=list)
    usable: bool = True
    modalities: list[ModalityQuality] = Field(default_factory=list)


class EntityResult(BaseModel):
    entity_id: str | None = None
    label: str
    type: str
    recognition_type: str
    confidence: float
    modality: str
    threshold_used: float | None = None
    time_range: list[float] | None = None
    bbox: list[float] | None = None
    track_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class MetaInfo(BaseModel):
    hardware: str = ""
    latency_ms: float
    request_id: str | None = None
    camera_id: str | None = None
    zone: str | None = None
    dry_run: bool = False
    inference_backend: str | None = None
    inference_effective: str | None = None
    inference_warnings: list[str] | None = None


class CandidateMatch(BaseModel):
    entity_id: str
    label: str
    type: str
    recognition_type: str
    confidence: float
    modality: str
    threshold_used: float | None = None
    enrollment_threshold: float | None = None
    accepted: bool = False


class RecognizeDiagnostics(BaseModel):
    pipelines: list[str] = Field(default_factory=list)
    candidates: list[CandidateMatch] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RecognizeResponse(BaseModel):
    entities: list[EntityResult] = Field(default_factory=list)
    gate: str | None = None
    reason: str | None = None
    scores: dict[str, float] | None = None
    diagnostics: RecognizeDiagnostics | None = None
    meta: MetaInfo


class GateResponse(BaseModel):
    gate: str
    reason: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    latency_ms: float


class EnrollmentCreate(BaseModel):
    type: EnrollmentType
    label: str
    species_hint: str | None = None
    threshold: float | None = None
    enabled: bool = True


class EnrollmentOut(BaseModel):
    id: str
    type: EnrollmentType
    label: str
    species_hint: str | None = None
    enabled: bool = True
    threshold: float | None = None
    learn_enabled: bool = False
    learn_min_confidence: float = 0.9
    learn_margin: float = 0.05
    learn_daily_cap: int = 8
    learn_max_samples: int = 20
    wyoming_min_confidence: float | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    sample_count: int = 0
    model_version: str | None = None
    created_at: str
    updated_at: str
    quality: QualityInfo | None = None
    duplicate_warning: str | None = None
    last_seen_at: str | None = None


class EnrollmentPatch(BaseModel):
    label: str | None = None
    threshold: float | None = Field(default=None, ge=0, le=1)
    enabled: bool | None = None
    external_ids: dict[str, str] | None = None
    learn_enabled: bool | None = None
    learn_min_confidence: float | None = Field(default=None, ge=0.5, le=0.99)
    learn_margin: float | None = Field(default=None, ge=0.0, le=0.5)
    learn_daily_cap: int | None = Field(default=None, ge=1, le=100)
    learn_max_samples: int | None = Field(default=None, ge=1, le=200)
    wyoming_min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class SampleOut(BaseModel):
    id: str
    enrollment_id: str
    modality: str
    model_version: str
    source: str
    source_label: str
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    duration_ms: float | None = None
    phrase_index: int | None = None
    phrase_text: str | None = None
    created_at: str
    centroid_similarity: float | None = None
    media_stored: bool = False
    flags: list[str] = Field(default_factory=list)


class SamplePreviewOut(BaseModel):
    """Quality of one take without saving it."""

    score: float
    verdict: str
    duration_ms: float | None = None
    gate: str | None = None
    reason: str | None = None
    speech: float | None = None
    centroid_similarity: float | None = None
    issues: list[str] = Field(default_factory=list)
    advice: str


class McpToolOut(BaseModel):
    name: str
    description: str
    scope: str


class McpResourceOut(BaseModel):
    uri: str
    name: str
    description: str
    scope: str


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[str] | None = None
    """Permissions: read, recognize, enroll, update, delete, admin. Each one covers REST and MCP."""
    mcp_tools: list[str] | None = None
    """Deprecated. Used only when scopes is omitted, and then expanded to those permissions."""


class ApiKeyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    scopes: list[str] | None = None


class ApiKeyOut(BaseModel):
    id: str
    name: str
    scopes: list[str]
    mcp_tool_allowlist: list[str] | None = None
    """Always null. MCP tools follow scopes."""
    created_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None


class ApiKeyCreated(ApiKeyOut):
    key: str
    mcp_tools: list[McpToolOut] = Field(default_factory=list)
    mcp_resources: list[McpResourceOut] = Field(default_factory=list)


class VideoLimits(BaseModel):
    recommended_sec: list[int] = Field(default_factory=lambda: [10, 30])
    enrollment_max_sec: int = 60
    recognize_sync_max_sec: int = 120
    recognize_async_max_sec: int = 300
    max_upload_bytes: int = 100 * 1024 * 1024


class CapabilitiesOut(BaseModel):
    hardware: "HardwareOut"
    version: str
    recognition_types: list[str]
    modalities: list[str]
    models: dict[str, str]
    inference: dict[str, Any] | None = None
    endpoints: list[str]
    video_limits: VideoLimits | None = None


WEBHOOK_DEFAULT_TITLE = "{{label}} was recognized"
WEBHOOK_DEFAULT_MESSAGE = "{{label}} matched at {{confidence}} on {{modality}}"


class WebhookSubscriptionCreate(BaseModel):
    url: str
    name: str = Field("", max_length=80)
    title_template: str = Field(WEBHOOK_DEFAULT_TITLE, max_length=500)
    message_template: str = Field(WEBHOOK_DEFAULT_MESSAGE, max_length=2000)
    events: list[str] = Field(
        default_factory=lambda: ["recognition.match", "recognition.unknown"],
        min_length=1,
    )
    filters: dict[str, Any] = Field(default_factory=dict)
    debounce_seconds: int = Field(30, ge=0, le=3600)
    include_details: bool = True


class WebhookSubscriptionPatch(BaseModel):
    url: str | None = None
    name: str | None = Field(None, max_length=80)
    title_template: str | None = Field(None, max_length=500)
    message_template: str | None = Field(None, max_length=2000)
    events: list[str] | None = Field(None, min_length=1)
    filters: dict[str, Any] | None = None
    debounce_seconds: int | None = Field(None, ge=0, le=3600)
    include_details: bool | None = None


class WebhookSubscriptionOut(BaseModel):
    id: str
    url: str
    name: str = ""
    title_template: str = ""
    message_template: str = ""
    events: list[str]
    filters: dict[str, Any]
    debounce_seconds: int
    include_details: bool = True
    created_at: str


class MqttIntegrationOut(BaseModel):
    enabled: bool
    host: str
    port: int
    topic_prefix: str
    username: str = ""
    password_set: bool = False
    client_id: str = "openrecognition"
    use_tls: bool = False
    tls_insecure: bool = False
    qos: int = 0
    retain: bool = True
    connected: bool = False
    last_error: str | None = None


class MqttIntegrationPatch(BaseModel):
    enabled: bool | None = None
    host: str | None = Field(None, min_length=1, max_length=253)
    port: int | None = Field(None, ge=1, le=65535)
    topic_prefix: str | None = Field(None, min_length=1, max_length=128)
    username: str | None = Field(None, max_length=128)
    password: str | None = Field(None, max_length=256)
    client_id: str | None = Field(None, min_length=1, max_length=128)
    use_tls: bool | None = None
    tls_insecure: bool | None = None
    qos: int | None = Field(None, ge=0, le=2)
    retain: bool | None = None


class MqttIntegrationTestIn(BaseModel):
    host: str = Field(..., min_length=1, max_length=253)
    port: int = Field(1883, ge=1, le=65535)
    username: str = ""
    password: str | None = None
    client_id: str = Field("openrecognition", min_length=1, max_length=128)
    use_tls: bool = False
    tls_insecure: bool = False


class DiscoveredWyomingOut(BaseModel):
    name: str
    host: str
    port: int
    uri: str


class DiscoveredHomeAssistantOut(BaseModel):
    name: str
    host: str
    port: int
    url: str


class MdnsDiscoveryOut(BaseModel):
    available: bool
    wyoming: list[DiscoveredWyomingOut]
    home_assistant: list[DiscoveredHomeAssistantOut]


class WyomingDiscoveryContextOut(BaseModel):
    in_container: bool
    detected_host: str
    listen_port: int | None = None
    mdns_likely_limited: bool
    manual_ha_hint: str | None = None
    message: str | None = None


class WyomingUpstreamTestIn(BaseModel):
    uri: str = Field(min_length=1, max_length=256)


class WyomingHomeAssistantTestIn(BaseModel):
    url: str = Field(min_length=1, max_length=512)


class IntegrationConnectivityOut(BaseModel):
    ok: bool
    message: str
    languages: list[str] | None = None


class WyomingIntegrationOut(BaseModel):
    enabled: bool
    uri: str
    upstream_uri: str
    home_assistant_url: str | None = None
    min_confidence: float
    require_speaker_match: bool
    block_on_gate_reject: bool
    tag_speaker: bool
    include_confidence: bool = True
    include_candidates: bool = False
    include_sound_events: bool = False
    zeroconf_enabled: bool = True
    zeroconf_name: str = "openrecognition"
    advertise_host: str | None = None
    available: bool = True
    upstream_ready: bool = False
    zeroconf_registered: bool = False
    listen_error: str | None = None
    ports_conflict: bool = False
    discovery: WyomingDiscoveryContextOut | None = None


class WyomingIntegrationPatch(BaseModel):
    enabled: bool | None = None
    uri: str | None = Field(None, min_length=1, max_length=256)
    upstream_uri: str | None = Field(None, min_length=1, max_length=256)
    home_assistant_url: str | None = Field(None, max_length=512)
    min_confidence: float | None = Field(None, ge=0.0, le=1.0)
    require_speaker_match: bool | None = None
    block_on_gate_reject: bool | None = None
    tag_speaker: bool | None = None
    include_confidence: bool | None = None
    include_candidates: bool | None = None
    include_sound_events: bool | None = None
    zeroconf_enabled: bool | None = None
    zeroconf_name: str | None = Field(None, min_length=1, max_length=63)
    advertise_host: str | None = Field(None, max_length=128)


class McpScopeGroupOut(BaseModel):
    id: str
    label: str
    description: str


class McpHostConfigHintOut(BaseModel):
    host: str
    config_path: str


class McpIntegrationOut(BaseModel):
    available: bool
    api_base_url: str
    server_ready: bool
    scope_groups: list[McpScopeGroupOut]
    suggested_scopes: list[str]
    tools: list[McpToolOut]
    resources: list[McpResourceOut]
    enabled_tools: list[McpToolOut]
    enabled_resources: list[McpResourceOut]
    host_config_json: str
    host_config_hints: list[McpHostConfigHintOut]
    install_hint: str | None = None


class GroupBriefOut(BaseModel):
    id: str
    name: str


class EnrollmentGrantOut(BaseModel):
    enrollment_id: str
    can_add_samples: bool = False
    can_manage: bool = False


class AuthMeOut(BaseModel):
    credential_type: str
    name: str
    scopes: list[str]
    role: str | None = None
    mcp_tools: list[McpToolOut]
    mcp_resources: list[McpResourceOut]
    groups: list[GroupBriefOut] = Field(default_factory=list)
    enrollment_grants: list[EnrollmentGrantOut] = Field(default_factory=list)
    library_limited: bool = False


class IntegrationsOverviewOut(BaseModel):
    mqtt: MqttIntegrationOut
    wyoming: WyomingIntegrationOut
    mcp: McpIntegrationOut
    webhooks: list[WebhookSubscriptionOut]


class PresenceEntry(BaseModel):
    enrollment_id: str
    label: str
    type: str
    last_seen_at: str
    last_modality: str
    last_camera_id: str | None = None
    confidence: float | None = None


class JobOut(BaseModel):
    id: str
    status: str
    created_at: str
    completed_at: str | None = None
    result: RecognizeResponse | None = None
    error: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class SetupRequest(BaseModel):
    username: str = Field(default="admin", min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=72)
    email: str | None = None


class UserOut(BaseModel):
    id: str
    username: str
    email: str | None = None
    role: str
    created_at: str
    groups: list[GroupBriefOut] = Field(default_factory=list)


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"
    email: str | None = None
    group_ids: list[str] | None = None


class UserPatch(BaseModel):
    role: str | None = None
    password: str | None = None
    email: str | None = None
    group_ids: list[str] | None = None


class GroupMemberOut(BaseModel):
    id: str
    username: str
    role: str


class GroupEnrollmentOut(BaseModel):
    enrollment_id: str
    label: str
    type: str
    can_add_samples: bool = False
    can_manage: bool = False


class GroupOut(BaseModel):
    id: str
    name: str
    description: str = ""
    grants_role: str | None = None
    sso_name: str | None = None
    system: bool = False
    created_at: str
    member_count: int = 0
    enrollment_count: int = 0
    members: list[GroupMemberOut] = Field(default_factory=list)
    enrollments: list[GroupEnrollmentOut] = Field(default_factory=list)


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    sso_name: str | None = None


class GroupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None
    sso_name: str | None = None


class GroupMembersPut(BaseModel):
    user_ids: list[str] = Field(default_factory=list)


class GroupEnrollmentPut(BaseModel):
    enrollment_id: str
    can_add_samples: bool = False
    can_manage: bool = False


class GroupEnrollmentsPut(BaseModel):
    enrollments: list[GroupEnrollmentPut] = Field(default_factory=list)


class GalleryExportOut(BaseModel):
    version: str
    exported_at: str
    enrollment_count: int
    data: dict[str, Any]


class SystemInfoOut(BaseModel):
    server_version: str
    python_version: str
    platform: str
    hostname: str
    lan_addresses: list[str] = Field(default_factory=list)
    api_bind: str
    api_local_url: str
    web_origin: str | None = None


class AppSettingsOut(BaseModel):
    maintenance_mode: bool
    enrollment_media_retention: str
    inference_backend: str
    inference_status: dict[str, Any] | None = None
    system: SystemInfoOut
    feature_flags: dict[str, bool]
    default_min_confidence: float
    default_return_unknown: bool
    default_include_sound_events: bool
    recognition_log_retention_days: int
    hardware: "HardwareOut"
    auth_required: bool
    docs_enabled: bool
    web_enabled: bool
    data_dir: str
    models_dir: str
    model_packs_dir: str = ""
    session_ttl_minutes: int
    mqtt_enabled: bool
    mqtt_host: str
    mqtt_port: int
    mqtt_topic_prefix: str
    model_idle_unload_minutes: int
    auth_rate_limit_per_minute: int
    host: str
    port: int
    http_enabled: bool = True
    https_enabled: bool = False
    https_port: int = 8443
    tls_cert_file: str = ""
    tls_key_file: str = ""
    tls_configured: bool = False
    tls_readable: bool = False
    tls_subject: str = ""
    tls_expires_at: str = ""
    tls_error: str = ""
    public_url: str = ""
    behind_proxy: bool = False
    trusted_proxies: str = ""
    display_language: str = "en"
    display_timezone: str = "UTC"
    logs_dir: str = ""
    log_level: str = "info"
    log_to_file: bool = True
    log_max_mb: int = 5
    log_backup_count: int = 5
    log_file: str = ""
    video_max_upload_bytes: int = 100 * 1024 * 1024
    health_detail_public: bool = True
    metrics_token_set: bool = False
    sso_enabled: bool = False
    sso_protocol: str = "oidc"
    sso_label: str = "Single sign-on"
    sso_auto_provision: bool = False
    sso_default_role: str = "viewer"
    sso_link_existing: bool = True
    sso_match: Literal["username", "email"] = "username"
    sso_username_claim: str = "preferred_username"
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret_set: bool = False
    oidc_scopes: str = "openid profile email"
    oidc_groups_claim: str = "groups"
    saml_idp_entity_id: str = ""
    saml_idp_sso_url: str = ""
    saml_idp_x509_cert: str = ""
    saml_sp_entity_id: str = ""
    saml_username_attr: str = "uid"
    saml_groups_attr: str = "groups"
    sso_redirect_uri: str = ""
    sso_acs_url: str = ""
    sso_metadata_url: str = ""
    sso_sp_entity_id: str = ""
    runtime_settings_path: str
    restart_required_for: list[str] = Field(default_factory=list)
    restart_pending: list[str] = Field(default_factory=list)
    env_only: list[str] = Field(default_factory=list)


class ServerLogsOut(BaseModel):
    path: str
    level: str
    file_enabled: bool
    lines: list[str]


class UiConfigOut(BaseModel):
    display_language: str
    display_timezone: str = "UTC"
    sso_enabled: bool
    sso_protocol: str
    sso_label: str


class StorageUsageOut(BaseModel):
    data_bytes: int
    models_bytes: int
    logs_bytes: int


class BackupRestoreOut(BaseModel):
    ok: bool = True
    message: str


class SelfSignedTlsRequest(BaseModel):
    hostname: str = Field(min_length=1, max_length=253)


class SelfSignedTlsOut(BaseModel):
    cert_pem: str
    key_pem: str
    subject: str
    expires_at: str


class OidcDiscoverRequest(BaseModel):
    issuer: str = Field(min_length=8, max_length=500)


class OidcDiscoverOut(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


class SamlMetadataRequest(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class SamlMetadataOut(BaseModel):
    saml_idp_entity_id: str
    saml_idp_sso_url: str
    saml_idp_x509_cert: str


class ServiceRestartOut(BaseModel):
    ok: bool = True
    message: str
    delay_seconds: float = 0.75


class AppSettingsPatch(BaseModel):
    maintenance_mode: bool | None = None
    enrollment_media_retention: str | None = None
    inference_backend: Literal["auto", "onnx", "heuristic"] | None = None
    feature_flags: dict[str, bool] | None = None
    default_min_confidence: float | None = Field(None, ge=0.0, le=1.0)
    default_return_unknown: bool | None = None
    default_include_sound_events: bool | None = None
    recognition_log_retention_days: int | None = Field(None, ge=0, le=3650)
    session_ttl_minutes: int | None = Field(None, ge=5, le=10080)
    model_idle_unload_minutes: int | None = Field(None, ge=0, le=1440)
    onnx_intra_op_threads: int | None = Field(None, ge=1, le=8)
    public_url: str | None = Field(None, max_length=500)
    behind_proxy: bool | None = None
    trusted_proxies: str | None = Field(None, max_length=500)
    display_language: str | None = Field(None, max_length=32)
    display_timezone: str | None = Field(None, max_length=64)
    auth_rate_limit_per_minute: int | None = Field(None, ge=1, le=10000)
    video_max_upload_bytes: int | None = Field(None, ge=1024 * 1024, le=2 * 1024 * 1024 * 1024)
    log_max_mb: int | None = Field(None, ge=1, le=200)
    log_backup_count: int | None = Field(None, ge=1, le=30)
    health_detail_public: bool | None = None
    metrics_token: str | None = Field(None, max_length=128)
    clear_metrics_token: bool = False
    host: str | None = Field(None, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    http_enabled: bool | None = None
    https_enabled: bool | None = None
    https_port: int | None = Field(None, ge=1, le=65535)
    tls_cert_file: str | None = Field(None, max_length=500)
    tls_key_file: str | None = Field(None, max_length=500)
    tls_cert_pem: str | None = Field(None, max_length=20000)
    tls_key_pem: str | None = Field(None, max_length=20000)
    models_dir: str | None = Field(None, max_length=500)
    model_packs_dir: str | None = Field(None, max_length=500)
    logs_dir: str | None = Field(None, max_length=500)
    log_level: str | None = Field(None, max_length=16)
    log_to_file: bool | None = None
    sso_enabled: bool | None = None
    sso_protocol: str | None = Field(None, max_length=16)
    sso_label: str | None = Field(None, max_length=40)
    sso_auto_provision: bool | None = None
    sso_default_role: str | None = Field(None, max_length=16)
    sso_link_existing: bool | None = None
    sso_match: Literal["username", "email"] | None = None
    sso_username_claim: str | None = Field(None, max_length=80)
    oidc_issuer: str | None = Field(None, max_length=500)
    oidc_client_id: str | None = Field(None, max_length=200)
    oidc_client_secret: str | None = Field(None, max_length=500)
    clear_oidc_client_secret: bool = False
    oidc_scopes: str | None = Field(None, max_length=200)
    oidc_groups_claim: str | None = Field(None, max_length=80)
    saml_idp_entity_id: str | None = Field(None, max_length=500)
    saml_idp_sso_url: str | None = Field(None, max_length=500)
    saml_idp_x509_cert: str | None = Field(None, max_length=20000)
    saml_sp_entity_id: str | None = Field(None, max_length=500)
    saml_username_attr: str | None = Field(None, max_length=80)
    saml_groups_attr: str | None = Field(None, max_length=80)


class ModelCategoryOut(BaseModel):
    id: str
    label: str
    description: str
    sort_order: int = 0


class ModelPresetOut(BaseModel):
    id: str
    label: str
    description: str
    keys: list[str]
    tier: str
    sort_order: int = 0
    complete: bool = False
    missing_keys: list[str] = Field(default_factory=list)


class KnobFieldOut(BaseModel):
    key: str
    label: str
    kind: Literal["int", "float"]
    min: float
    max: float
    step: float
    default: float | int
    value: float | int
    overridden: bool = False


class HardwareOut(BaseModel):
    detected: str
    override: str | None = None
    effective: str
    label: str
    cpu_count: int
    memory_mb: int
    arch: str = ""


class ThreadsOut(BaseModel):
    value: int
    automatic: int
    overridden: bool = False


class ModelCatalogEntryOut(BaseModel):
    key: str
    filename: str
    source: str
    url: str
    page_url: str = ""
    description: str
    license: str
    disk_bytes: int = 0
    memory_mb: int = 0
    license_warning: bool = False
    on_disk: bool
    size_bytes: int | None = None
    category: str
    use_for: str
    label: str = ""
    version: str = ""
    onnx: dict[str, Any] = Field(default_factory=dict)
    contract: dict[str, Any] = Field(default_factory=dict)
    knobs: list[KnobFieldOut] = Field(default_factory=list)
    hardware: str = "pi"
    hardware_note: str = ""
    fit: str = "match"
    suggested: bool = False
    tier: str
    enables: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    sort_order: int = 0
    origin: str = "builtin"
    active: bool = False
    reenroll_count: int = 0
    enrollment_count: int = 0
    sha256_pinned: bool = False


class ModelsStatusOut(BaseModel):
    models_dir: str
    hardware: HardwareOut
    threads: ThreadsOut
    categories: list[ModelCategoryOut]
    presets: list[ModelPresetOut]
    catalog: list[ModelCatalogEntryOut]
    inference_backend: str
    loaded_models: dict[str, str]
    inference: dict[str, Any] | None = None


class HardwareUpdate(BaseModel):
    tier: Literal["pi", "mini", "desktop", "server"] | None = None


class ModelSettingsUpdate(BaseModel):
    overrides: dict[str, Any] = Field(default_factory=dict)


class ModelDownloadRequest(BaseModel):
    keys: list[str] | None = None
    force: bool = False


class CustomModelCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=40)
    version: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=8, max_length=2000)
    onnx: dict[str, Any] = Field(default_factory=dict)


class CustomModelUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=8, max_length=2000)
    onnx: dict[str, Any] = Field(default_factory=dict)


class CustomModelCreated(BaseModel):
    key: str


class ActiveModelRequest(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    key: str = Field(min_length=1, max_length=80)


class ModelActionResultOut(BaseModel):
    key: str
    status: str
    message: str
    path: str | None = None
    source: str | None = None


class ModelDownloadResponseOut(BaseModel):
    results: list[ModelActionResultOut]
    models: dict[str, str]
    inference: dict[str, Any]


class RecognitionLogOut(BaseModel):
    id: str
    event: str
    modality: str | None = None
    label: str | None = None
    entity_id: str | None = None
    confidence: float | None = None
    camera_id: str | None = None
    zone: str | None = None
    request_id: str | None = None
    gate: str | None = None
    reason: str | None = None
    summary: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None
    actor_name: str | None = None
    latency_ms: float | None = None
    dry_run: bool = False
    details: dict[str, Any] | None = None
    created_at: str


class RecognitionLogListOut(BaseModel):
    items: list[RecognitionLogOut]
    total: int
    limit: int
    offset: int


class ConsoleOverviewOut(BaseModel):
    enrollments: list[EnrollmentOut]
    ready_count: int
    attention: list[EnrollmentOut]
    recent_activity: list[RecognitionLogOut]
    last_seen: PresenceEntry | None = None
    models_ready: bool
    wyoming_enabled: bool
    webhook_count: int
    has_recognition: bool
    hardware: str
    models: dict[str, str] = Field(default_factory=dict)


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: Any = None


AppSettingsOut.model_rebuild()
CapabilitiesOut.model_rebuild()
ModelsStatusOut.model_rebuild()

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
    pack: str
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
    external_ids: dict[str, str] = Field(default_factory=dict)
    sample_count: int = 0
    model_version: str | None = None
    created_at: str
    updated_at: str
    quality: QualityInfo | None = None
    duplicate_warning: str | None = None


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
    name: str
    scopes: list[str] | None = None
    """REST API scopes (read, recognize, enroll, admin). Independent of MCP tools."""
    mcp_tools: list[str] | None = None
    """MCP tool allowlist. Use ``[]`` to disable MCP. Omitted = all tools allowed by scopes."""


class ApiKeyOut(BaseModel):
    id: str
    name: str
    scopes: list[str]
    mcp_tool_allowlist: list[str] | None = None
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
    pack: str
    version: str
    recognition_types: list[str]
    modalities: list[str]
    models: dict[str, str]
    inference: dict[str, Any] | None = None
    endpoints: list[str]
    video_limits: VideoLimits | None = None


class WebhookSubscriptionCreate(BaseModel):
    url: str
    events: list[str] = Field(default_factory=lambda: ["recognition.match"])
    filters: dict[str, Any] = Field(default_factory=dict)
    debounce_seconds: int = 30


class WebhookSubscriptionOut(BaseModel):
    id: str
    url: str
    events: list[str]
    filters: dict[str, Any]
    debounce_seconds: int
    created_at: str


class MqttIntegrationOut(BaseModel):
    enabled: bool
    host: str
    port: int
    topic_prefix: str


class MqttIntegrationPatch(BaseModel):
    enabled: bool | None = None
    host: str | None = Field(None, min_length=1, max_length=253)
    port: int | None = Field(None, ge=1, le=65535)
    topic_prefix: str | None = Field(None, min_length=1, max_length=128)


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


class AuthMeOut(BaseModel):
    credential_type: str
    name: str
    scopes: list[str]
    mcp_tools: list[McpToolOut]
    mcp_resources: list[McpResourceOut]


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


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    created_at: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"


class UserPatch(BaseModel):
    role: str | None = None
    password: str | None = None


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
    pack: str
    auth_required: bool
    docs_enabled: bool
    web_enabled: bool
    data_dir: str
    model_packs_dir: str
    session_ttl_minutes: int
    mqtt_enabled: bool
    mqtt_host: str
    mqtt_port: int
    mqtt_topic_prefix: str
    model_idle_unload_minutes: int
    auth_rate_limit_per_minute: int
    host: str
    port: int
    runtime_settings_path: str
    restart_required_for: list[str] = Field(default_factory=list)


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


class ModelCatalogEntryOut(BaseModel):
    key: str
    filename: str
    source: str
    url: str
    description: str
    license: str
    packs: list[str]
    on_disk: bool
    size_bytes: int | None = None
    category: str
    use_for: str
    label: str = ""
    version: str = ""
    onnx: dict[str, Any] = Field(default_factory=dict)
    hardware: str = "pi"
    hardware_note: str = ""
    tier: str
    enables: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    sort_order: int = 0
    origin: str = "builtin"
    active: bool = False


class ModelRecommendationOut(BaseModel):
    id: str
    label: str
    description: str = ""
    sort_order: int = 0
    keys: list[str] = Field(default_factory=list)


class ModelsStatusOut(BaseModel):
    pack: str
    pack_dir: str
    categories: list[ModelCategoryOut]
    presets: list[ModelPresetOut]
    recommendations: list[ModelRecommendationOut] = Field(default_factory=list)
    catalog: list[ModelCatalogEntryOut]
    inference_backend: str
    loaded_models: dict[str, str]
    inference: dict[str, Any] | None = None


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


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: Any = None

"""Shared application state."""

from dataclasses import dataclass, field
from typing import Any

from openrecognition.auth.keys import ApiKeyService
from openrecognition.auth.rate_limit import LoginRateLimiter
from openrecognition.auth.sessions import SessionService
from openrecognition.bootstrap import run_bootstrap
from openrecognition.config import Settings
from openrecognition.gallery.db import Database
from openrecognition.gallery.store import GalleryStore
from openrecognition.inference.audio_gate import AudioGateEngine
from openrecognition.inference.inference_policy import InferencePolicy
from openrecognition.inference.session_pool import ModelSessionPool
from openrecognition.inference.speaker import SpeakerEngine
from openrecognition.inference.vision import VisionEngine
from openrecognition.integrator.debounce import DebounceService
from openrecognition.integrator.mqtt import MqttBridge
from openrecognition.integrator.wyoming import WyomingBridge
from openrecognition.integrator.recognition_log import RecognitionLogService
from openrecognition.integrator.webhooks import WebhookService
from openrecognition.runtime_settings import RuntimeSettingsStore

RESTART_REQUIRED_KEYS = (
    "pack",
    "data_dir",
    "model_packs_dir",
    "host",
    "port",
    "auth_required",
    "web_enabled",
    "docs_enabled",
    "web_origin",
)


@dataclass
class AppState:
    settings: Settings
    db: Database
    gallery: GalleryStore
    api_keys: ApiKeyService
    sessions: SessionService
    pool: ModelSessionPool
    inference_policy: InferencePolicy
    gate: AudioGateEngine
    speaker: SpeakerEngine
    vision: VisionEngine
    debounce: DebounceService
    webhooks: WebhookService
    recognition_logs: RecognitionLogService
    mqtt: MqttBridge
    wyoming: WyomingBridge
    maintenance_mode: bool = False
    default_min_confidence: float = 0.75
    default_return_unknown: bool = True
    default_include_sound_events: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "biometrics.face_enabled": True,
            "biometrics.speaker_enabled": True,
            "biometrics.pet_enabled": True,
        }
    )
    _runtime_store: RuntimeSettingsStore | None = field(default=None, repr=False)
    login_limiter: LoginRateLimiter = field(default_factory=LoginRateLimiter)

    def runtime_snapshot(self) -> dict[str, Any]:
        s = self.settings
        return {
            "inference_backend": self.inference_policy.backend,
            "maintenance_mode": self.maintenance_mode,
            "enrollment_media_retention": s.enrollment_media_retention,
            "feature_flags": dict(self.feature_flags),
            "default_min_confidence": self.default_min_confidence,
            "default_return_unknown": self.default_return_unknown,
            "default_include_sound_events": self.default_include_sound_events,
            "recognition_log_retention_days": self.recognition_logs.retention_days,
            "session_ttl_minutes": s.session_ttl_minutes,
            "mqtt_enabled": s.mqtt_enabled,
            "mqtt_host": s.mqtt_host,
            "mqtt_port": s.mqtt_port,
            "mqtt_topic_prefix": s.mqtt_topic_prefix,
            "wyoming_enabled": s.wyoming_enabled,
            "wyoming_uri": s.wyoming_uri,
            "wyoming_upstream_uri": s.wyoming_upstream_uri,
            "wyoming_min_confidence": s.wyoming_min_confidence,
            "wyoming_require_speaker_match": s.wyoming_require_speaker_match,
            "wyoming_block_on_gate_reject": s.wyoming_block_on_gate_reject,
            "wyoming_tag_speaker": s.wyoming_tag_speaker,
            "wyoming_zeroconf_enabled": s.wyoming_zeroconf_enabled,
            "wyoming_zeroconf_name": s.wyoming_zeroconf_name,
            "wyoming_advertise_host": s.wyoming_advertise_host,
            "wyoming_home_assistant_url": s.wyoming_home_assistant_url,
            "model_idle_unload_minutes": s.model_idle_unload_minutes,
        }

    def apply_runtime_snapshot(self, data: dict[str, Any]) -> None:
        if not data:
            return
        s = self.settings
        if "inference_backend" in data:
            backend = data["inference_backend"]
            if backend in ("auto", "onnx", "heuristic"):
                s.inference_backend = backend  # type: ignore[assignment]
                self.inference_policy.set_backend(backend)
        if "maintenance_mode" in data:
            self.maintenance_mode = bool(data["maintenance_mode"])
        if "enrollment_media_retention" in data:
            s.enrollment_media_retention = data["enrollment_media_retention"]  # type: ignore[assignment]
        if "feature_flags" in data and isinstance(data["feature_flags"], dict):
            self.feature_flags.update({k: bool(v) for k, v in data["feature_flags"].items()})
        if "default_min_confidence" in data:
            self.default_min_confidence = float(data["default_min_confidence"])
        if "default_return_unknown" in data:
            self.default_return_unknown = bool(data["default_return_unknown"])
        if "default_include_sound_events" in data:
            self.default_include_sound_events = bool(data["default_include_sound_events"])
        if "recognition_log_retention_days" in data:
            self.recognition_logs.set_retention_days(int(data["recognition_log_retention_days"]))
        if "session_ttl_minutes" in data:
            ttl = int(data["session_ttl_minutes"])
            s.session_ttl_minutes = ttl
            self.sessions.ttl_minutes = ttl
        mqtt_changed = False
        if "mqtt_enabled" in data:
            s.mqtt_enabled = bool(data["mqtt_enabled"])
            mqtt_changed = True
        if "mqtt_host" in data:
            s.mqtt_host = str(data["mqtt_host"])
            mqtt_changed = True
        if "mqtt_port" in data:
            s.mqtt_port = int(data["mqtt_port"])
            mqtt_changed = True
        if "mqtt_topic_prefix" in data:
            s.mqtt_topic_prefix = str(data["mqtt_topic_prefix"])
            mqtt_changed = True
        if mqtt_changed:
            self.mqtt.configure(
                host=s.mqtt_host,
                port=s.mqtt_port,
                prefix=s.mqtt_topic_prefix,
                enabled=s.mqtt_enabled,
            )
        wyoming_changed = False
        for key in (
            "wyoming_enabled",
            "wyoming_uri",
            "wyoming_upstream_uri",
            "wyoming_min_confidence",
            "wyoming_require_speaker_match",
            "wyoming_block_on_gate_reject",
            "wyoming_tag_speaker",
            "wyoming_zeroconf_enabled",
            "wyoming_zeroconf_name",
            "wyoming_advertise_host",
            "wyoming_home_assistant_url",
        ):
            if key in data:
                wyoming_changed = True
                setattr(s, key, data[key])
        if wyoming_changed:
            self.wyoming.configure(
                enabled=s.wyoming_enabled,
                uri=s.wyoming_uri,
                upstream_uri=s.wyoming_upstream_uri,
                min_confidence=s.wyoming_min_confidence,
                require_speaker_match=s.wyoming_require_speaker_match,
                block_on_gate_reject=s.wyoming_block_on_gate_reject,
                tag_speaker=s.wyoming_tag_speaker,
                zeroconf_enabled=s.wyoming_zeroconf_enabled,
                zeroconf_name=s.wyoming_zeroconf_name,
                advertise_host=s.wyoming_advertise_host,
            )
        if "model_idle_unload_minutes" in data:
            s.model_idle_unload_minutes = int(data["model_idle_unload_minutes"])
            self.pool.idle_unload_minutes = s.model_idle_unload_minutes

    def persist_runtime(self) -> None:
        if self._runtime_store is not None:
            self._runtime_store.save(self.runtime_snapshot())

    def resolve_embedding_model_version(self, modality: str, enrollment_type: str) -> str:
        """Model version used for new enrollments given pack + inference backend."""
        from openrecognition.inference.speaker import HEURISTIC_MODEL_VERSION
        from openrecognition.inference.vision import FACE_MODEL_VERSION, VISUAL_MODEL_VERSION

        def effective(slot: str, heuristic: str) -> str:
            ver = self.pool.model_version(slot)
            if ver and self.inference_policy.should_use_onnx(slot):
                return ver
            return heuristic

        if modality == "audio":
            return effective("speaker_embedding", HEURISTIC_MODEL_VERSION)
        if enrollment_type in ("pet", "object"):
            return effective("visual_reid", VISUAL_MODEL_VERSION)
        return effective("face_embedding", FACE_MODEL_VERSION)

    @classmethod
    def create(cls, settings: Settings) -> "AppState":
        run_bootstrap(settings)
        db = Database(settings.db_path)
        gallery = GalleryStore(db, settings.data_dir)
        api_keys = ApiKeyService(db)
        sessions = SessionService(db, settings.session_ttl_minutes)
        pool = ModelSessionPool(settings.pack_dir, settings.model_idle_unload_minutes)
        pool.load()
        policy = InferencePolicy(pool, settings.inference_backend)
        debounce = DebounceService(db)
        state = cls(
            settings=settings,
            db=db,
            gallery=gallery,
            api_keys=api_keys,
            sessions=sessions,
            pool=pool,
            inference_policy=policy,
            gate=AudioGateEngine(pool, policy),
            speaker=SpeakerEngine(pool, policy),
            vision=VisionEngine(pool, policy),
            debounce=debounce,
            webhooks=WebhookService(db, debounce),
            recognition_logs=RecognitionLogService(db),
            mqtt=MqttBridge(
                settings.mqtt_host,
                settings.mqtt_port,
                settings.mqtt_topic_prefix,
                settings.mqtt_enabled,
            ),
            wyoming=WyomingBridge(
                enabled=settings.wyoming_enabled,
                uri=settings.wyoming_uri,
                upstream_uri=settings.wyoming_upstream_uri,
                min_confidence=settings.wyoming_min_confidence,
                require_speaker_match=settings.wyoming_require_speaker_match,
                block_on_gate_reject=settings.wyoming_block_on_gate_reject,
                tag_speaker=settings.wyoming_tag_speaker,
                zeroconf_enabled=settings.wyoming_zeroconf_enabled,
                zeroconf_name=settings.wyoming_zeroconf_name,
                advertise_host=settings.wyoming_advertise_host,
            ),
            maintenance_mode=settings.maintenance_mode,
            default_include_sound_events=settings.pack == "home",
        )
        state._runtime_store = RuntimeSettingsStore(settings.data_dir / "runtime_settings.json")
        state.apply_runtime_snapshot(state._runtime_store.load())
        state.gallery.set_version_resolver(state.resolve_embedding_model_version)
        from openrecognition.gallery.custom_models import apply_overrides

        apply_overrides(state.pool, state.db)
        state.mqtt.connect()
        return state

    def video_limits(self) -> dict[str, int | list[int]]:
        s = self.settings
        return {
            "recommended_sec": [s.video_recommended_min_sec, s.video_recommended_max_sec],
            "enrollment_max_sec": s.video_enrollment_max_sec,
            "recognize_sync_max_sec": s.video_recognize_sync_max_sec,
            "recognize_async_max_sec": s.video_recognize_async_max_sec,
            "max_upload_bytes": s.video_max_upload_bytes,
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "pack": self.settings.pack,
            "version": "0.1.0",
            "recognition_types": [
                "gate",
                "speaker",
                "face",
                "pet_identity",
                "object_identity",
                "sound_event",
            ],
            "modalities": ["audio", "image", "video"],
            "models": self.pool.list_models(),
            "inference": self.inference_policy.status(),
            "endpoints": [
                "/v1/recognize/audio",
                "/v1/recognize/image",
                "/v1/recognize/video",
                "/v1/audio/gate",
                "/v1/enrollments",
                "/v1/presence",
                "/v1/events/stream",
                "/v1/admin/logs",
                "/v1/integrations",
                "/v1/integrations/mqtt",
                "/v1/integrations/wyoming",
                "/v1/integrations/mcp",
                "/v1/auth/me",
                "/v1/integrations/webhooks",
                "/v1/jobs",
            ],
            "video_limits": self.video_limits(),
        }

"""Application configuration."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENRECOGNITION_",
        env_file=".env",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8080
    data_dir: Path = Path("./data")
    models_dir: Path = Path("./models")
    # Older installs kept weights under model-packs/<pack>/. Those folders are
    # still searched. New downloads go to models_dir.
    model_packs_dir: Path = Path("./model-packs")
    auth_required: bool = True
    auth_rate_limit_per_minute: int = 60
    enrollment_media_retention: Literal["keep", "embeddings_only"] = "embeddings_only"
    maintenance_mode: bool = False
    web_enabled: bool = True
    docs_enabled: bool = True
    # Set in the container image. A source checkout uses src/web/dist.
    web_dist: Path | None = None
    web_origin: str | None = None
    session_ttl_minutes: int = 60
    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic_prefix: str = "openrecognition"
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_client_id: str = "openrecognition"
    mqtt_use_tls: bool = False
    mqtt_tls_insecure: bool = False
    mqtt_qos: int = 0
    mqtt_retain: bool = True
    wyoming_enabled: bool = False
    wyoming_uri: str = "tcp://0.0.0.0:10301"
    wyoming_upstream_uri: str = "tcp://127.0.0.1:10300"
    wyoming_min_confidence: float = 0.75
    wyoming_require_speaker_match: bool = False
    wyoming_block_on_gate_reject: bool = False
    wyoming_tag_speaker: bool = True
    wyoming_include_confidence: bool = True
    wyoming_include_candidates: bool = False
    wyoming_zeroconf_enabled: bool = True
    wyoming_zeroconf_name: str = "openrecognition"
    wyoming_advertise_host: str = ""
    wyoming_home_assistant_url: str = ""
    model_idle_unload_minutes: int = 0
    inference_backend: Literal["auto", "onnx", "heuristic"] = "auto"
    video_recommended_min_sec: int = 10
    video_recommended_max_sec: int = 30
    video_enrollment_max_sec: int = 60
    video_recognize_sync_max_sec: int = 120
    video_recognize_async_max_sec: int = 300
    video_max_upload_bytes: int = 100 * 1024 * 1024

    @property
    def db_path(self) -> Path:
        return self.data_dir / "openrecognition.db"

    @property
    def bootstrap_key_path(self) -> Path:
        return self.data_dir / "bootstrap.key"

    @property
    def admin_password_path(self) -> Path:
        return self.data_dir / "admin.password"

    @property
    def model_search_dirs(self) -> list[Path]:
        names = ("edge", "standard", "home", "pro")
        ordered = [self.models_dir]
        ordered.extend(self.models_dir / name for name in names)
        if self.model_packs_dir != self.models_dir:
            ordered.append(self.model_packs_dir)
            ordered.extend(self.model_packs_dir / name for name in names)
        unique: list[Path] = []
        seen: set[str] = set()
        for path in ordered:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            unique.append(path)
        return unique


settings = Settings()

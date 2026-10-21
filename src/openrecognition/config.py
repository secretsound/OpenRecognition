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
    pack: Literal["edge", "standard", "pro", "home"] = "edge"
    model_packs_dir: Path = Path("./model-packs")
    auth_required: bool = True
    auth_rate_limit_per_minute: int = 60
    enrollment_media_retention: Literal["keep", "embeddings_only"] = "embeddings_only"
    maintenance_mode: bool = False
    web_enabled: bool = True
    docs_enabled: bool = True
    # Set in the container image. A source checkout resolves web/dist from the repo root.
    web_dist: Path | None = None
    web_origin: str | None = None
    session_ttl_minutes: int = 60
    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic_prefix: str = "openrecognition"
    wyoming_enabled: bool = False
    wyoming_uri: str = "tcp://0.0.0.0:10301"
    wyoming_upstream_uri: str = "tcp://127.0.0.1:10300"
    wyoming_min_confidence: float = 0.75
    wyoming_require_speaker_match: bool = True
    wyoming_block_on_gate_reject: bool = True
    wyoming_tag_speaker: bool = False
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
    def pack_dir(self) -> Path:
        return self.model_packs_dir / self.pack


settings = Settings()

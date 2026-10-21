"""Shared MQTT integration settings apply logic."""

from openrecognition.app_state import AppState
from openrecognition.models.schemas import MqttIntegrationPatch


def mqtt_settings_out(state: AppState) -> dict:
    s = state.settings
    return {
        "enabled": s.mqtt_enabled,
        "host": s.mqtt_host,
        "port": s.mqtt_port,
        "topic_prefix": s.mqtt_topic_prefix,
    }


def apply_mqtt_patch(state: AppState, body: MqttIntegrationPatch) -> None:
    s = state.settings
    if body.enabled is not None:
        s.mqtt_enabled = body.enabled
    if body.host is not None:
        s.mqtt_host = body.host.strip()
    if body.port is not None:
        s.mqtt_port = body.port
    if body.topic_prefix is not None:
        s.mqtt_topic_prefix = body.topic_prefix.strip().rstrip("/")
    if any(v is not None for v in (body.enabled, body.host, body.port, body.topic_prefix)):
        state.mqtt.configure(
            host=s.mqtt_host,
            port=s.mqtt_port,
            prefix=s.mqtt_topic_prefix,
            enabled=s.mqtt_enabled,
        )
    state.persist_runtime()

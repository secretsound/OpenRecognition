"""Shared MQTT integration settings apply logic."""

from openrecognition.app_state import AppState
from openrecognition.integrator.mqtt import probe_mqtt
from openrecognition.models.schemas import MqttIntegrationPatch, MqttIntegrationTestIn


def mqtt_settings_out(state: AppState) -> dict:
    s = state.settings
    return {
        "enabled": s.mqtt_enabled,
        "host": s.mqtt_host,
        "port": s.mqtt_port,
        "topic_prefix": s.mqtt_topic_prefix,
        "username": s.mqtt_username,
        "password_set": bool(s.mqtt_password),
        "client_id": s.mqtt_client_id or "openrecognition",
        "use_tls": s.mqtt_use_tls,
        "tls_insecure": s.mqtt_tls_insecure,
        "qos": s.mqtt_qos,
        "retain": s.mqtt_retain,
        "connected": bool(s.mqtt_enabled and state.mqtt.connected),
        "last_error": state.mqtt.last_error if s.mqtt_enabled else None,
    }


def _reconfigure(state: AppState) -> None:
    s = state.settings
    state.mqtt.configure(
        host=s.mqtt_host,
        port=s.mqtt_port,
        prefix=s.mqtt_topic_prefix,
        enabled=s.mqtt_enabled,
        username=s.mqtt_username,
        password=s.mqtt_password,
        client_id=s.mqtt_client_id,
        use_tls=s.mqtt_use_tls,
        tls_insecure=s.mqtt_tls_insecure,
        qos=s.mqtt_qos,
        retain=s.mqtt_retain,
    )


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
    if body.username is not None:
        s.mqtt_username = body.username.strip()
    if body.password is not None:
        s.mqtt_password = body.password
    if body.client_id is not None:
        s.mqtt_client_id = body.client_id.strip() or "openrecognition"
    if body.use_tls is not None:
        s.mqtt_use_tls = body.use_tls
    if body.tls_insecure is not None:
        s.mqtt_tls_insecure = body.tls_insecure
    if body.qos is not None:
        s.mqtt_qos = body.qos
    if body.retain is not None:
        s.mqtt_retain = body.retain
    _reconfigure(state)
    state.persist_runtime()


def test_mqtt_settings(state: AppState, body: MqttIntegrationTestIn) -> dict:
    password = body.password if body.password is not None else state.settings.mqtt_password
    return probe_mqtt(
        host=body.host,
        port=body.port,
        username=body.username,
        password=password,
        client_id=body.client_id,
        use_tls=body.use_tls,
        tls_insecure=body.tls_insecure,
    )

"""Optional MQTT publisher for Home Assistant."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None  # type: ignore


class MqttBridge:
    def __init__(self, host: str, port: int, prefix: str, enabled: bool):
        self.host = host
        self.port = port
        self.prefix = prefix.rstrip("/")
        self.enabled = enabled and mqtt is not None
        self._client = None

    def configure(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        prefix: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port
        if prefix is not None:
            self.prefix = prefix.rstrip("/")
        if enabled is not None:
            self.enabled = enabled and mqtt is not None
        self.disconnect()
        self.connect()

    def connect(self) -> None:
        if not self.enabled or mqtt is None:
            return
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        try:
            self._client.connect(self.host, self.port, 60)
            self._client.loop_start()
            logger.info("MQTT connected to %s:%s", self.host, self.port)
        except Exception as e:
            logger.warning("MQTT connect failed: %s", e)
            self._client = None

    def publish_recognition(self, label: str, etype: str, payload: dict[str, Any]) -> None:
        if not self._client:
            return
        topic = f"{self.prefix}/{etype}/{label}/state"
        try:
            self._client.publish(topic, json.dumps(payload), retain=True)
        except Exception as e:
            logger.warning("MQTT publish failed: %s", e)

    def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

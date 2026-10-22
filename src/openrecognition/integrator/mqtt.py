"""Optional MQTT publisher for Home Assistant and other brokers."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None  # type: ignore


def _apply_auth(client: Any, username: str, password: str) -> None:
    if username or password:
        client.username_pw_set(username or None, password or None)


def _apply_tls(client: Any, use_tls: bool, tls_insecure: bool) -> None:
    if not use_tls:
        return
    client.tls_set()
    if tls_insecure:
        client.tls_insecure_set(True)


def probe_mqtt(
    *,
    host: str,
    port: int,
    username: str = "",
    password: str = "",
    client_id: str = "openrecognition-test",
    use_tls: bool = False,
    tls_insecure: bool = False,
    timeout: float = 5.0,
) -> dict[str, Any]:
    if mqtt is None:
        return {"ok": False, "message": "MQTT support is not installed", "languages": None}
    host = host.strip()
    if not host:
        return {"ok": False, "message": "Broker address is required", "languages": None}

    outcome = {"ok": False, "message": f"Timed out waiting for {host}:{port}", "languages": None}
    done = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties) -> None:  # noqa: ANN001
        if int(reason_code) == 0:
            outcome["ok"] = True
            outcome["message"] = f"Connected to {host}:{port}"
        else:
            outcome["ok"] = False
            outcome["message"] = f"Broker refused the connection ({reason_code})"
        done.set()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id or "openrecognition-test",
    )
    _apply_auth(client, username, password)
    try:
        _apply_tls(client, use_tls, tls_insecure)
    except Exception as exc:
        return {"ok": False, "message": f"TLS setup failed: {exc}", "languages": None}
    client.on_connect = on_connect
    try:
        client.connect(host, port, keepalive=20)
        client.loop_start()
        done.wait(timeout)
    except Exception as exc:
        return {"ok": False, "message": str(exc), "languages": None}
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
    return outcome


class MqttBridge:
    def __init__(
        self,
        host: str,
        port: int,
        prefix: str,
        enabled: bool,
        *,
        username: str = "",
        password: str = "",
        client_id: str = "openrecognition",
        use_tls: bool = False,
        tls_insecure: bool = False,
        qos: int = 0,
        retain: bool = True,
    ):
        self.host = host
        self.port = port
        self.prefix = prefix.rstrip("/")
        self.username = username
        self.password = password
        self.client_id = client_id or "openrecognition"
        self.use_tls = use_tls
        self.tls_insecure = tls_insecure
        self.qos = qos
        self.retain = retain
        self.enabled = enabled and mqtt is not None
        self.connected = False
        self.last_error: str | None = None
        self._client = None

    def configure(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        prefix: str | None = None,
        enabled: bool | None = None,
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
        use_tls: bool | None = None,
        tls_insecure: bool | None = None,
        qos: int | None = None,
        retain: bool | None = None,
    ) -> None:
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port
        if prefix is not None:
            self.prefix = prefix.rstrip("/")
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password
        if client_id is not None:
            self.client_id = client_id or "openrecognition"
        if use_tls is not None:
            self.use_tls = use_tls
        if tls_insecure is not None:
            self.tls_insecure = tls_insecure
        if qos is not None:
            self.qos = qos
        if retain is not None:
            self.retain = retain
        if enabled is not None:
            self.enabled = enabled and mqtt is not None
        self.disconnect()
        self.connect()

    def connect(self) -> None:
        self.connected = False
        if not self.enabled or mqtt is None:
            return
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )
        _apply_auth(client, self.username, self.password)
        try:
            _apply_tls(client, self.use_tls, self.tls_insecure)
        except Exception as exc:
            self.last_error = f"TLS setup failed: {exc}"
            logger.warning("MQTT TLS setup failed: %s", exc)
            return

        def on_connect(client, userdata, flags, reason_code, properties) -> None:  # noqa: ANN001
            if int(reason_code) == 0:
                self.connected = True
                self.last_error = None
            else:
                self.connected = False
                self.last_error = f"Broker refused the connection ({reason_code})"

        def on_disconnect(client, userdata, disconnect_flags, reason_code, properties) -> None:  # noqa: ANN001
            self.connected = False
            if int(reason_code) != 0:
                self.last_error = f"Disconnected ({reason_code})"

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        self._client = client
        try:
            client.connect(self.host, self.port, 60)
            client.loop_start()
            logger.info("MQTT connecting to %s:%s", self.host, self.port)
        except Exception as e:
            self.last_error = str(e)
            logger.warning("MQTT connect failed: %s", e)
            self._client = None

    def publish_recognition(self, label: str, etype: str, payload: dict[str, Any]) -> None:
        if not self._client:
            return
        topic = f"{self.prefix}/{etype}/{label}/state"
        body = {"label": label, "type": etype, **payload}
        try:
            self._client.publish(topic, json.dumps(body), qos=self.qos, retain=self.retain)
        except Exception as e:
            logger.warning("MQTT publish failed: %s", e)

    def disconnect(self) -> None:
        self.connected = False
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

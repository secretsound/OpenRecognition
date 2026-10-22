"""HTTP and HTTPS listeners."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass

from uvicorn import Config, Server

from openrecognition.config import Settings
from openrecognition.tls_material import certs_readable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ListenerSpec:
    host: str
    port: int
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None


def plan_listeners(settings: Settings) -> list[ListenerSpec]:
    """Listeners the next process start will bind. Falls back to HTTP if TLS will not load."""
    host = settings.host
    https_ok = bool(
        settings.https_enabled
        and certs_readable(settings.tls_cert_file, settings.tls_key_file)
    )
    if settings.https_enabled and not https_ok:
        logger.error("HTTPS is enabled but the certificate or key could not be loaded")
    specs: list[ListenerSpec] = []
    if https_ok:
        specs.append(
            ListenerSpec(
                host,
                int(settings.https_port),
                settings.tls_cert_file,
                settings.tls_key_file,
            )
        )
    http_port = int(settings.port)
    https_port = int(settings.https_port)
    if settings.http_enabled or not https_ok:
        if https_ok and http_port == https_port:
            logger.error("HTTP and HTTPS ports match; HTTP was not started")
        else:
            specs.append(ListenerSpec(host, http_port))
    if not specs:
        specs.append(ListenerSpec(host, http_port))
    return specs


def _config(app, spec: ListenerSpec, *, lifespan: str, log_level: str) -> Config:
    return Config(
        app,
        host=spec.host,
        port=spec.port,
        log_level=log_level,
        proxy_headers=False,
        forwarded_allow_ips="",
        lifespan=lifespan,
        ssl_certfile=spec.ssl_certfile,
        ssl_keyfile=spec.ssl_keyfile,
    )


def _log_level(settings: Settings) -> str:
    level = (settings.log_level or "info").lower()
    if level not in {"debug", "info", "warning", "error", "critical"}:
        return "info"
    return level


async def _serve(settings: Settings) -> None:
    from openrecognition.api.app import create_app

    app = create_app()
    specs = plan_listeners(settings)
    level = _log_level(settings)
    primary = Server(_config(app, specs[0], lifespan="on", log_level=level))
    extras: list[Server] = []
    threads: list[threading.Thread] = []
    for spec in specs[1:]:
        server = Server(_config(app, spec, lifespan="off", log_level=level))
        extras.append(server)

        def run(bound: Server = server) -> None:
            asyncio.run(bound.serve())

        threads.append(threading.Thread(target=run, name=f"listener-{spec.port}", daemon=True))

    async def start_extras() -> None:
        while not primary.started and not primary.should_exit:
            await asyncio.sleep(0.05)
        if primary.should_exit:
            return
        for thread in threads:
            thread.start()

    watcher = asyncio.create_task(start_extras())
    try:
        await primary.serve()
    finally:
        watcher.cancel()
        for server in extras:
            server.should_exit = True
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=3)


def serve(settings: Settings) -> None:
    for spec in plan_listeners(settings):
        scheme = "https" if spec.ssl_certfile else "http"
        logger.info("Listening on %s://%s:%s", scheme, spec.host, spec.port)
    uvicorn_level = _log_level(settings)
    if uvicorn_level:
        logging.getLogger("uvicorn.error").setLevel(uvicorn_level.upper())
    asyncio.run(_serve(settings))

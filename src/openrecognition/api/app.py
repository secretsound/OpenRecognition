"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from openrecognition import __version__
from openrecognition.api.errors import (
    APIError,
    api_error_handler,
    audio_decode_error_handler,
    http_exception_handler,
)
from openrecognition.api.request_logging import RequestLoggingMiddleware
from openrecognition.inference.audio_gate import AudioDecodeError
from openrecognition.api.routes import (
    admin,
    models_admin,
    auth_routes,
    capabilities,
    enrollments,
    events,
    gallery_routes,
    health,
    jobs,
    metrics,
    presence,
    recognize,
    integrations,
    webhooks_routes,
)
from openrecognition.api.openapi import configure_openapi
from openrecognition.api.routes import docs as docs_routes
from openrecognition.app_state import AppState
from openrecognition.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = AppState.create(settings)
    app.state.app_state = state
    await state.wyoming.start(state)
    yield
    await state.wyoming.stop()
    state.mqtt.disconnect()


def create_app() -> FastAPI:
    docs_url = "/docs" if settings.docs_enabled else None
    redoc_url = "/redoc" if settings.docs_enabled else None
    openapi_url = "/openapi.json" if settings.docs_enabled else None

    app = FastAPI(
        title="OpenRecognition",
        version=__version__,
        description="API-first multi-modal recognition service",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "filter": True,
        },
    )
    if settings.docs_enabled:
        configure_openapi(app)

    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(AudioDecodeError, audio_decode_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    app.add_middleware(RequestLoggingMiddleware)

    if settings.web_origin:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.web_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if settings.docs_enabled:
        app.include_router(docs_routes.router)

    app.include_router(health.router)
    app.include_router(auth_routes.router)
    app.include_router(capabilities.router)
    app.include_router(enrollments.router)
    app.include_router(recognize.router)
    app.include_router(integrations.router)
    app.include_router(webhooks_routes.router)
    app.include_router(presence.router)
    app.include_router(events.router)
    app.include_router(jobs.router)
    app.include_router(gallery_routes.router)
    app.include_router(admin.router)
    app.include_router(models_admin.router)
    app.include_router(metrics.router)

    if settings.web_dist is not None:
        web_dist = settings.web_dist
    else:
        web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if settings.web_enabled and web_dist.is_dir():
        index_path = web_dist / "index.html"
        assets_dir = web_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="web-assets")

        def _spa_index() -> FileResponse:
            if not index_path.is_file():
                raise HTTPException(
                    status_code=404,
                    detail="Web UI not built — run: cd src/web && npm run build",
                )
            return FileResponse(index_path)

        @app.get("/")
        def ui_root():
            return _spa_index()

        _SPA_EXCLUDE = (
            "v1/",
            "health",
            "metrics",
            "docs",
            "redoc",
            "openapi.json",
            "api/",
            "assets/",
        )

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str):
            if any(full_path.startswith(prefix) for prefix in _SPA_EXCLUDE):
                raise HTTPException(status_code=404)
            asset = web_dist / full_path
            if asset.is_file():
                return FileResponse(asset)
            return _spa_index()

    return app

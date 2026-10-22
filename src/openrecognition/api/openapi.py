"""OpenAPI schema customization for Swagger UI and ReDoc."""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from openrecognition import __version__

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Liveness and readiness probes (no authentication).",
    },
    {
        "name": "auth",
        "description": "API keys and web session login.",
    },
    {
        "name": "capabilities",
        "description": "Discover models and supported recognition types.",
    },
    {
        "name": "enrollments",
        "description": "Create and manage enrolled people, pets, objects, and sounds.",
    },
    {
        "name": "recognize",
        "description": "Run audio gate, speaker ID, image/video recognition.",
    },
    {
        "name": "integrations",
        "description": "Webhooks, MQTT, and other external connectors.",
    },
    {
        "name": "webhooks",
        "description": "Deprecated — use /v1/integrations/webhooks.",
    },
    {
        "name": "presence",
        "description": "Last-seen timestamps per enrolled identity.",
    },
    {
        "name": "events",
        "description": "Server-sent events stream for live matches.",
    },
    {
        "name": "jobs",
        "description": "Async processing for long video files.",
    },
    {
        "name": "gallery",
        "description": "Export and import enrollment galleries.",
    },
    {
        "name": "admin",
        "description": "Maintenance mode, feature flags, config reload, recognition audit log.",
    },
    {
        "name": "metrics",
        "description": "Prometheus-style metrics.",
    },
]

PUBLIC_PATHS = {
    "/health",
    "/health/live",
    "/health/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api",
}

API_DESCRIPTION = """
OpenRecognition is an API-first service for **speaker identification**, **audio gating**,
**face and pet recognition**, and **video timelines** — designed for homelab and Home Assistant.

The web console at `/` is the day-to-day UI: **Library** for enrollments, **Recognize**
for a clip or photo, **Activity** for the audit log, and **Connections** for webhooks,
MQTT, Wyoming, and MCP.

## Interactive documentation

| UI | URL |
|----|-----|
| **Swagger UI** | [`/docs`](/docs) |
| **ReDoc** | [`/redoc`](/redoc) |
| OpenAPI JSON | [`/openapi.json`](/openapi.json) |

## Authentication

Most endpoints require an API key:

- `Authorization: Bearer <api_key>`, or
- `X-API-Key: <api_key>`

Use **Authorize** in Swagger UI to set your key. Create a key in the console; only its hash is stored.

Scopes: `recognize`, `enroll`, `read`, `admin`.
"""


def configure_openapi(app: FastAPI) -> None:
    """Attach a customized OpenAPI schema (security schemes, tags, public routes)."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=API_DESCRIPTION,
            routes=app.routes,
            tags=OPENAPI_TAGS,
        )

        schema.setdefault("components", {})
        schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "API key as Bearer token (e.g. `or_...`)",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key header (Home Assistant friendly)",
            },
        }

        default_security = [{"BearerAuth": []}, {"ApiKeyAuth": []}]

        for path, methods in schema.get("paths", {}).items():
            if path in PUBLIC_PATHS or path.rstrip("/") in PUBLIC_PATHS:
                continue
            for operation in methods.values():
                if isinstance(operation, dict) and "security" not in operation:
                    operation["security"] = default_security

        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

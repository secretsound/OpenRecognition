"""Static MCP tool/resource metadata (shared by server, API, and web UI)."""

from __future__ import annotations

from typing import TypedDict


class McpToolMeta(TypedDict):
    name: str
    description: str
    scope: str


class McpResourceMeta(TypedDict):
    uri: str
    name: str
    description: str
    scope: str


MCP_TOOLS: list[McpToolMeta] = [
    {
        "name": "get_health",
        "description": "Server version, model pack, loaded models, and maintenance flag.",
        "scope": "read",
    },
    {
        "name": "get_capabilities",
        "description": "Modalities, recognition types, and enabled endpoints for this pack.",
        "scope": "read",
    },
    {
        "name": "list_enrollments",
        "description": "List enrolled identities (people, pets, objects, sounds).",
        "scope": "read",
    },
    {
        "name": "get_presence",
        "description": "Last-seen summary per enrolled label (who was detected recently).",
        "scope": "read",
    },
    {
        "name": "audio_gate",
        "description": "Fast speech vs noise gate; use before full speaker identification.",
        "scope": "recognize",
    },
    {
        "name": "recognize_audio",
        "description": "Speaker ID on a local audio file (WAV/FLAC/MP3). Optional gate-only mode.",
        "scope": "recognize",
    },
    {
        "name": "recognize_image",
        "description": "Face, pet, and object recognition on a local image file.",
        "scope": "recognize",
    },
    {
        "name": "recognize_image_url",
        "description": "Recognize from an HTTP(S) image URL (e.g. Frigate snapshot).",
        "scope": "recognize",
    },
    {
        "name": "enroll_from_paths",
        "description": "Create an enrollment from one or more local media file paths.",
        "scope": "enroll",
    },
]

MCP_RESOURCES: list[McpResourceMeta] = [
    {
        "uri": "openrecognition://health",
        "name": "health",
        "description": "JSON from GET /health",
        "scope": "read",
    },
    {
        "uri": "openrecognition://capabilities",
        "name": "capabilities",
        "description": "JSON from GET /v1/capabilities",
        "scope": "read",
    },
    {
        "uri": "openrecognition://enrollments",
        "name": "enrollments",
        "description": "JSON list from GET /v1/enrollments",
        "scope": "read",
    },
]

SUGGESTED_MCP_SCOPES = ["read", "recognize", "enroll"]

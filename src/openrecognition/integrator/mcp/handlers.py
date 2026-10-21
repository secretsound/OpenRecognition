"""MCP tool and resource handlers (HTTP bridge to OpenRecognition API)."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from openrecognition.integrator.mcp.client import OpenRecognitionApiError, OpenRecognitionClient

Handler = Callable[[OpenRecognitionClient], Awaitable[str]]


def _json_text(data: Any) -> str:
    return json.dumps(data, indent=2)


def _api_error_message(exc: OpenRecognitionApiError) -> str:
    if exc.detail:
        return f"{exc.message}\n{json.dumps(exc.detail, indent=2)}"
    return exc.message


async def _wrap(client: OpenRecognitionClient, coro: Awaitable[Any]) -> str:
    try:
        return _json_text(await coro)
    except OpenRecognitionApiError as exc:
        return _api_error_message(exc)
    except FileNotFoundError as exc:
        return str(exc)


async def get_health(client: OpenRecognitionClient) -> str:
    return await _wrap(client, client.get_json("/health"))


async def get_capabilities(client: OpenRecognitionClient) -> str:
    await client.ensure_ready()
    return await _wrap(client, client.get_json("/v1/capabilities"))


async def list_enrollments(client: OpenRecognitionClient) -> str:
    return await _wrap(client, client.get_json("/v1/enrollments"))


async def get_presence(client: OpenRecognitionClient) -> str:
    return await _wrap(client, client.get_json("/v1/presence"))


async def audio_gate(client: OpenRecognitionClient, file_path: str) -> str:
    await client.ensure_ready()
    return await _wrap(client, client.post_file("/v1/audio/gate", file_path))


async def recognize_audio(
    client: OpenRecognitionClient,
    file_path: str,
    mode: str = "full",
    dry_run: bool = False,
    min_confidence: float | None = None,
) -> str:
    await client.ensure_ready()
    if mode == "gate":
        return await _wrap(client, client.post_file("/v1/audio/gate", file_path))
    params: dict[str, str | float | bool] = {"mode": mode, "dry_run": dry_run}
    if min_confidence is not None:
        params["min_confidence"] = min_confidence
    return await _wrap(
        client,
        client.post_file("/v1/recognize/audio", file_path, params=params),
    )


async def recognize_image(
    client: OpenRecognitionClient,
    file_path: str,
    dry_run: bool = False,
    min_confidence: float | None = None,
    camera_id: str | None = None,
    zone: str | None = None,
) -> str:
    await client.ensure_ready()
    params: dict[str, str | float | bool] = {"dry_run": dry_run}
    if min_confidence is not None:
        params["min_confidence"] = min_confidence
    if camera_id:
        params["camera_id"] = camera_id
    if zone:
        params["zone"] = zone
    return await _wrap(
        client,
        client.post_file("/v1/recognize/image", file_path, params=params),
    )


async def recognize_image_url(
    client: OpenRecognitionClient,
    url: str,
    dry_run: bool = False,
    min_confidence: float | None = None,
) -> str:
    await client.ensure_ready()
    body: dict[str, Any] = {"url": url}
    if min_confidence is not None:
        body["match_policy"] = {"min_confidence": min_confidence}
    return await _wrap(
        client,
        client.post_json("/v1/recognize/image/url", body, params={"dry_run": dry_run}),
    )


async def enroll_from_paths(
    client: OpenRecognitionClient,
    enrollment_type: str,
    label: str,
    file_paths: list[str],
    species_hint: str | None = None,
) -> str:
    await client.ensure_ready()
    return await _wrap(
        client,
        client.post_files_enroll(
            enrollment_type=enrollment_type,
            label=label,
            file_paths=file_paths,
            species_hint=species_hint,
        ),
    )


async def resource_health(client: OpenRecognitionClient) -> str:
    return await get_health(client)


async def resource_capabilities(client: OpenRecognitionClient) -> str:
    return await get_capabilities(client)


async def resource_enrollments(client: OpenRecognitionClient) -> str:
    return await list_enrollments(client)

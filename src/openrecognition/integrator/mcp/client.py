"""HTTP client for MCP tools calling the running OpenRecognition API."""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path

import httpx

from openrecognition.config import settings


class OpenRecognitionApiError(Exception):
    """API returned a non-success status."""

    def __init__(self, status: int, message: str, detail: object | None = None):
        self.status = status
        self.message = message
        self.detail = detail
        super().__init__(f"{status}: {message}")


class OpenRecognitionClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> OpenRecognitionClient:
        host = os.environ.get("OPENRECOGNITION_HOST", settings.host)
        port = int(os.environ.get("OPENRECOGNITION_PORT", str(settings.port)))
        base = os.environ.get("OPENRECOGNITION_API_URL", f"http://{host}:{port}")
        key = os.environ.get("OPENRECOGNITION_API_KEY")
        if not key and settings.bootstrap_key_path.exists():
            key = settings.bootstrap_key_path.read_text().strip()
        return cls(base, key)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def _raise(self, response: httpx.Response) -> None:
        try:
            body = response.json()
            message = body.get("message") or body.get("detail") or response.text
            detail = body
        except json.JSONDecodeError:
            message = response.text or response.reason_phrase
            detail = None
        raise OpenRecognitionApiError(response.status_code, str(message), detail)

    async def get_json(self, path: str) -> dict | list:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.base_url}{path}", headers=self._headers())
            if r.status_code >= 400:
                self._raise(r)
            return r.json()

    async def post_json(
        self,
        path: str,
        body: dict,
        *,
        params: dict | None = None,
    ) -> dict | list:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}{path}",
                headers=self._headers(),
                json=body,
                params=params or {},
            )
            if r.status_code >= 400:
                self._raise(r)
            return r.json()

    async def post_file(
        self,
        path: str,
        file_path: str,
        *,
        field_name: str = "file",
        params: dict | None = None,
    ) -> dict | list:
        p = Path(file_path).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Media file not found: {p}")
        mime, _ = mimetypes.guess_type(p.name)
        content_type = mime or "application/octet-stream"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with p.open("rb") as fh:
                r = await client.post(
                    f"{self.base_url}{path}",
                    headers=self._headers(),
                    params=params or {},
                    files={field_name: (p.name, fh, content_type)},
                )
            if r.status_code >= 400:
                self._raise(r)
            return r.json()

    async def post_files_enroll(
        self,
        *,
        enrollment_type: str,
        label: str,
        file_paths: list[str],
        species_hint: str | None = None,
    ) -> dict:
        paths = [Path(p).expanduser().resolve() for p in file_paths]
        for p in paths:
            if not p.is_file():
                raise FileNotFoundError(f"Media file not found: {p}")
        data: dict[str, str] = {"type": enrollment_type, "label": label}
        if species_hint:
            data["species_hint"] = species_hint
        files = []
        for p in paths:
            mime, _ = mimetypes.guess_type(p.name)
            files.append(
                ("files", (p.name, p.read_bytes(), mime or "application/octet-stream"))
            )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/v1/enrollments",
                headers=self._headers(),
                data=data,
                files=files,
            )
            if r.status_code >= 400:
                self._raise(r)
            return r.json()

    async def fetch_auth_me(self) -> dict:
        return await self.get_json("/v1/auth/me")  # type: ignore[return-value]

    async def ensure_ready(self) -> None:
        data = await self.get_json("/health/ready")
        if not data.get("models_loaded"):
            raise OpenRecognitionApiError(
                503,
                "OpenRecognition models are still loading — retry after GET /health/ready is ready",
                data,
            )

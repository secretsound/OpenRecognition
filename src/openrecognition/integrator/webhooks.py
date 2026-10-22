"""Webhook subscription delivery."""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from openrecognition.gallery.db import Database, json_dumps, json_loads
from openrecognition.integrator.debounce import DebounceService
from openrecognition.models.schemas import WEBHOOK_DEFAULT_MESSAGE, WEBHOOK_DEFAULT_TITLE
from openrecognition.outbound import UnsafeUrlError, validate_outbound_url

logger = logging.getLogger(__name__)

_TEMPLATE_VAR = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}|\{([a-zA-Z0-9_]+)\}")

EVENT_LABELS = {
    "recognition.match": "Someone matched",
    "recognition.unknown": "Nobody matched",
    "recognition.no_match": "Nothing found",
    "recognition.gate_reject": "Speech check failed",
}

MODALITY_LABELS = {
    "audio": "voice",
    "image": "photo",
    "video": "video",
    "voice": "voice",
    "photo": "photo",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_template(template: str, context: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1) or match.group(2)
        return context.get(key, "")

    return _TEMPLATE_VAR.sub(repl, template)


def _top_entity(payload: dict[str, Any]) -> dict[str, Any]:
    entities = payload.get("entities") or []
    if entities and isinstance(entities[0], dict):
        return entities[0]
    return {
        "label": payload.get("label") or "unknown",
        "confidence": payload.get("confidence"),
        "entity_id": payload.get("enrollment_id") or payload.get("entity_id"),
        "type": payload.get("type") or "person",
        "modality": payload.get("modality") or "",
        "threshold_used": payload.get("threshold_used"),
    }


def _fmt_confidence(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{round(float(value) * 100)}%"
    return ""


def _fmt_raw(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.3f}"
    return ""


def event_context(event: str, payload: dict[str, Any]) -> dict[str, str]:
    top = _top_entity(payload)
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    modality = str(top.get("modality") or payload.get("modality") or "")
    return {
        "label": str(top.get("label") or "unknown"),
        "event": event,
        "event_label": EVENT_LABELS.get(event, event.replace("recognition.", "").replace("_", " ")),
        "confidence": _fmt_confidence(top.get("confidence")),
        "confidence_raw": _fmt_raw(top.get("confidence")),
        "type": str(top.get("type") or ""),
        "modality": MODALITY_LABELS.get(modality, modality),
        "mode": str(payload.get("mode") or ""),
        "gate": str(payload.get("gate") or ""),
        "reason": str(payload.get("reason") or ""),
        "camera": str(meta.get("camera_id") or payload.get("camera_id") or ""),
        "zone": str(meta.get("zone") or payload.get("zone") or ""),
        "transcript": str(payload.get("transcript") or ""),
        "entity_id": str(top.get("entity_id") or ""),
    }


def _omit_empty(value: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, item in value.items():
        if item is None or item == "" or item == [] or item == {}:
            continue
        out[key] = item
    return out


def event_details(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    top = _top_entity(payload)
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
    return _omit_empty(
        {
            "mode": payload.get("mode"),
            "label": top.get("label"),
            "entity_id": top.get("entity_id"),
            "type": top.get("type"),
            "modality": top.get("modality") or payload.get("modality"),
            "confidence": top.get("confidence"),
            "threshold": top.get("threshold_used"),
            "gate": payload.get("gate"),
            "reason": payload.get("reason"),
            "scores": payload.get("scores"),
            "accepted": payload.get("accepted"),
            "transcript": payload.get("transcript"),
            "camera_id": meta.get("camera_id"),
            "zone": meta.get("zone"),
            "candidates": payload.get("candidates") or diagnostics.get("candidates"),
            "pipelines": diagnostics.get("pipelines"),
        }
    )


def render_webhook_body(sub: dict[str, Any], event: str, payload: dict[str, Any]) -> dict[str, Any]:
    context = event_context(event, payload)
    body: dict[str, Any] = {
        "title": render_template(sub.get("title_template") or WEBHOOK_DEFAULT_TITLE, context),
        "message": render_template(sub.get("message_template") or WEBHOOK_DEFAULT_MESSAGE, context),
        "event": event,
    }
    if sub.get("include_details", True):
        body["details"] = event_details(event, payload)
    return body


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        keys = row.keys()
    except Exception:
        return default
    if key not in keys:
        return default
    value = row[key]
    return default if value is None else value


class WebhookService:
    def __init__(self, db: Database, debounce: DebounceService):
        self.db = db
        self.debounce = debounce

    def create(
        self,
        url: str,
        events: list[str],
        filters: dict,
        debounce_seconds: int,
        *,
        name: str = "",
        title_template: str = "",
        message_template: str = "",
        include_details: bool = True,
    ) -> dict:
        url = validate_outbound_url(url, allow_loopback=True, allow_unresolved=True)
        wid = str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO webhook_subscriptions
               (id, url, name, title_template, message_template, events, filters,
                debounce_seconds, include_details, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                wid,
                url,
                name.strip(),
                title_template,
                message_template,
                json_dumps(events),
                json_dumps(filters),
                debounce_seconds,
                1 if include_details else 0,
                _now(),
            ),
        )
        return self.get(wid)

    def get(self, wid: str) -> dict | None:
        row = self.db.fetchone("SELECT * FROM webhook_subscriptions WHERE id = ?", (wid,))
        if not row:
            return None
        return {
            "id": row["id"],
            "url": row["url"],
            "name": _row_get(row, "name", ""),
            "title_template": _row_get(row, "title_template", ""),
            "message_template": _row_get(row, "message_template", ""),
            "events": json_loads(row["events"]),
            "filters": json_loads(row["filters"]),
            "debounce_seconds": row["debounce_seconds"],
            "include_details": bool(_row_get(row, "include_details", 1)),
            "created_at": row["created_at"],
        }

    def list_all(self) -> list[dict]:
        rows = self.db.fetchall(
            "SELECT id FROM webhook_subscriptions ORDER BY created_at DESC"
        )
        return [sub for r in rows if (sub := self.get(r["id"]))]

    def update(
        self,
        wid: str,
        *,
        url: str | None = None,
        name: str | None = None,
        title_template: str | None = None,
        message_template: str | None = None,
        events: list[str] | None = None,
        filters: dict | None = None,
        debounce_seconds: int | None = None,
        include_details: bool | None = None,
    ) -> dict | None:
        if not self.get(wid):
            return None
        fields: list[str] = []
        values: list[Any] = []
        if url is not None:
            fields.append("url = ?")
            values.append(validate_outbound_url(url, allow_loopback=True, allow_unresolved=True))
        if name is not None:
            fields.append("name = ?")
            values.append(name.strip())
        if title_template is not None:
            fields.append("title_template = ?")
            values.append(title_template)
        if message_template is not None:
            fields.append("message_template = ?")
            values.append(message_template)
        if events is not None:
            fields.append("events = ?")
            values.append(json_dumps(events))
        if filters is not None:
            fields.append("filters = ?")
            values.append(json_dumps(filters))
        if debounce_seconds is not None:
            fields.append("debounce_seconds = ?")
            values.append(debounce_seconds)
        if include_details is not None:
            fields.append("include_details = ?")
            values.append(1 if include_details else 0)
        if fields:
            values.append(wid)
            self.db.execute(
                f"UPDATE webhook_subscriptions SET {', '.join(fields)} WHERE id = ?",
                values,
            )
        return self.get(wid)

    def delete(self, wid: str) -> bool:
        row = self.db.fetchone("SELECT id FROM webhook_subscriptions WHERE id = ?", (wid,))
        if not row:
            return False
        self.db.execute("DELETE FROM webhook_subscriptions WHERE id = ?", (wid,))
        return True

    async def dispatch_recognition(
        self,
        event: str,
        payload: dict[str, Any],
        dry_run: bool = False,
        *,
        debounce: bool = True,
    ) -> None:
        if dry_run:
            return
        subs = self.list_all()
        for sub in subs:
            if event not in sub["events"] and "recognition.*" not in sub["events"]:
                continue
            top = _top_entity(payload)
            filters = sub["filters"]
            if filters.get("min_confidence"):
                confidence = top.get("confidence") or 0
                if confidence < filters["min_confidence"]:
                    continue
            if filters.get("types"):
                if top.get("type") not in filters["types"]:
                    continue
            label = top.get("label") or "unknown"
            meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
            camera = meta.get("camera_id") or payload.get("camera_id") or ""
            debounce_key = f"{sub['id']}:{label}:{camera}"
            if debounce and not self.debounce.should_fire(debounce_key, sub["debounce_seconds"]):
                continue
            asyncio.create_task(self._post(sub["url"], render_webhook_body(sub, event, payload)))

    async def _post(self, url: str, body: dict) -> None:
        try:
            target = validate_outbound_url(url, allow_loopback=True, allow_unresolved=True)
        except UnsafeUrlError as exc:
            logger.warning("Webhook URL blocked (%s): %s", url, exc)
            return
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                await client.post(target, json=body)
        except Exception as e:
            logger.warning("Webhook delivery failed to %s: %s", url, e)

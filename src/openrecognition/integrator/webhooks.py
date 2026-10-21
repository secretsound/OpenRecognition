"""Webhook subscription delivery."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from openrecognition.gallery.db import Database, json_dumps, json_loads
from openrecognition.integrator.debounce import DebounceService
from openrecognition.outbound import UnsafeUrlError, validate_outbound_url

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WebhookService:
    def __init__(self, db: Database, debounce: DebounceService):
        self.db = db
        self.debounce = debounce

    def create(self, url: str, events: list[str], filters: dict, debounce_seconds: int) -> dict:
        url = validate_outbound_url(url, allow_loopback=True, allow_unresolved=True)
        wid = str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO webhook_subscriptions
               (id, url, events, filters, debounce_seconds, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (wid, url, json_dumps(events), json_dumps(filters), debounce_seconds, _now()),
        )
        return self.get(wid)

    def get(self, wid: str) -> dict | None:
        row = self.db.fetchone("SELECT * FROM webhook_subscriptions WHERE id = ?", (wid,))
        if not row:
            return None
        return {
            "id": row["id"],
            "url": row["url"],
            "events": json_loads(row["events"]),
            "filters": json_loads(row["filters"]),
            "debounce_seconds": row["debounce_seconds"],
            "created_at": row["created_at"],
        }

    def list_all(self) -> list[dict]:
        rows = self.db.fetchall("SELECT * FROM webhook_subscriptions")
        return [self.get(r["id"]) for r in rows if self.get(r["id"])]

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
            filters = sub["filters"]
            if filters.get("min_confidence"):
                entities = payload.get("entities", [])
                if entities and entities[0].get("confidence", 0) < filters["min_confidence"]:
                    continue
            if filters.get("types"):
                entities = payload.get("entities", [])
                if entities and entities[0].get("type") not in filters["types"]:
                    continue
            label = "unknown"
            camera = payload.get("meta", {}).get("camera_id", "")
            entities = payload.get("entities", [])
            if entities:
                label = entities[0].get("label", "unknown")
            debounce_key = f"{sub['id']}:{label}:{camera}"
            if debounce and not self.debounce.should_fire(debounce_key, sub["debounce_seconds"]):
                continue
            asyncio.create_task(self._post(sub["url"], {"event": event, **payload}))

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

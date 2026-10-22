"""Recognition and enrollment audit log (no raw media)."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from openrecognition.gallery.db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _actor_from_auth(auth: dict[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    if not auth:
        return None, None, None
    if auth.get("user_id"):
        return "user", str(auth["user_id"]), auth.get("name")
    if auth.get("id"):
        return "api_key", str(auth["id"]), auth.get("name")
    if auth.get("name") == "dev":
        return "dev", None, "dev"
    return None, auth.get("name"), auth.get("name")


class RecognitionLogService:
    def __init__(self, db: Database):
        self.db = db
        self.retention_days: int = 0

    def set_retention_days(self, days: int) -> None:
        self.retention_days = max(0, int(days))

    def prune_old(self) -> None:
        if self.retention_days <= 0:
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        self.db.execute("DELETE FROM recognition_logs WHERE created_at < ?", (cutoff,))

    def record(
        self,
        *,
        event: str,
        modality: str | None = None,
        label: str | None = None,
        entity_id: str | None = None,
        confidence: float | None = None,
        camera_id: str | None = None,
        zone: str | None = None,
        request_id: str | None = None,
        gate: str | None = None,
        reason: str | None = None,
        summary: str | None = None,
        latency_ms: float | None = None,
        dry_run: bool = False,
        auth: dict[str, Any] | None = None,
        actor_type: str | None = None,
        actor_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from_auth_type, from_auth_id, from_auth_name = _actor_from_auth(auth)
        actor_type = actor_type or from_auth_type
        actor_id = from_auth_id
        actor_name = actor_name or from_auth_name
        details_json = json.dumps(details) if details else None
        log_id = str(uuid.uuid4())
        created_at = _now()
        self.db.execute(
            """INSERT INTO recognition_logs (
                id, event, modality, label, entity_id, confidence,
                camera_id, zone, request_id, gate, reason, summary,
                actor_type, actor_id, actor_name, latency_ms, dry_run, details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                log_id,
                event,
                modality,
                label,
                entity_id,
                confidence,
                camera_id,
                zone,
                request_id,
                gate,
                reason,
                summary,
                actor_type,
                actor_id,
                actor_name,
                latency_ms,
                1 if dry_run else 0,
                details_json,
                created_at,
            ),
        )
        self.prune_old()
        payload = {
            "id": log_id,
            "event": event,
            "modality": modality,
            "label": label,
            "entity_id": entity_id,
            "confidence": confidence,
            "camera_id": camera_id,
            "zone": zone,
            "request_id": request_id,
            "gate": gate,
            "reason": reason,
            "summary": summary,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "latency_ms": latency_ms,
            "dry_run": dry_run,
            "details": details,
            "created_at": created_at,
        }
        try:
            from openrecognition.api.routes.events import publish_event

            publish_event({"type": "recognition.log", "log": payload})
        except Exception:
            pass
        return payload

    def append(
        self,
        *,
        event: str,
        response_meta: dict[str, Any],
        entities: list[dict[str, Any]],
        gate: str | None = None,
        reason: str | None = None,
        dry_run: bool = False,
        auth: dict[str, Any] | None = None,
    ) -> None:
        """Log a recognition API response (match / unknown with optional entity)."""
        primary = entities[0] if entities else {}
        self.record(
            event=event,
            modality=primary.get("modality"),
            label=primary.get("label"),
            entity_id=primary.get("entity_id"),
            confidence=primary.get("confidence"),
            camera_id=response_meta.get("camera_id"),
            zone=response_meta.get("zone"),
            request_id=response_meta.get("request_id"),
            gate=gate,
            reason=reason,
            latency_ms=response_meta.get("latency_ms"),
            dry_run=dry_run,
            auth=auth,
        )

    def has_recognition(self) -> bool:
        row = self.db.fetchone(
            "SELECT 1 AS ok FROM recognition_logs "
            "WHERE event LIKE 'recognition.%' OR dry_run = 1 LIMIT 1"
        )
        return row is not None

    def list_logs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        event: str | None = None,
        modality: str | None = None,
        label: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        where: list[str] = []
        params: list[Any] = []
        if event:
            where.append("event = ?")
            params.append(event)
        if modality:
            where.append("modality = ?")
            params.append(modality)
        if label:
            where.append("label LIKE ?")
            params.append(f"%{label}%")
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        total_row = self.db.fetchone(
            f"SELECT COUNT(*) AS c FROM recognition_logs{clause}",
            tuple(params),
        )
        total = int(total_row["c"]) if total_row else 0
        rows = self.db.fetchall(
            f"""SELECT id, event, modality, label, entity_id, confidence,
                       camera_id, zone, request_id, gate, reason, summary,
                       actor_type, actor_id, actor_name, latency_ms, dry_run, details, created_at
                FROM recognition_logs{clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?""",
            tuple(params) + (limit, offset),
        )
        items = []
        for r in rows:
            raw_details = _row_get(r, "details")
            parsed_details = None
            if raw_details:
                try:
                    parsed_details = json.loads(raw_details)
                except json.JSONDecodeError:
                    parsed_details = None
            items.append(
            {
                "id": r["id"],
                "event": r["event"],
                "modality": r["modality"],
                "label": r["label"],
                "entity_id": r["entity_id"],
                "confidence": r["confidence"],
                "camera_id": r["camera_id"],
                "zone": r["zone"],
                "request_id": r["request_id"],
                "gate": r["gate"],
                "reason": _row_get(r, "reason"),
                "summary": _row_get(r, "summary"),
                "actor_type": r["actor_type"],
                "actor_id": r["actor_id"],
                "actor_name": r["actor_name"],
                "latency_ms": r["latency_ms"],
                "dry_run": bool(_row_get(r, "dry_run", 0)),
                "details": parsed_details,
                "created_at": r["created_at"],
            }
            )
        return items, total


def _row_get(row, key: str, default=None):
    return row[key] if key in row.keys() else default

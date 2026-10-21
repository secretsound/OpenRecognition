"""API key hashing and verification."""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

import bcrypt

from openrecognition.gallery.db import Database, json_dumps, json_loads


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_key(key: str) -> str:
    digest = hashlib.sha256(key.encode()).hexdigest()
    return f"sha256:{digest}"


def _verify_legacy_bcrypt(key: str, key_hash: str) -> bool:
    if not key_hash.startswith("$2"):
        return False
    try:
        return bcrypt.checkpw(key.encode(), key_hash.encode())
    except ValueError:
        return False


class ApiKeyService:
    def __init__(self, db: Database):
        self.db = db

    def bootstrap_admin(self, path) -> str | None:
        row = self.db.fetchone(
            "SELECT id FROM api_keys WHERE revoked_at IS NULL LIMIT 1"
        )
        if row:
            return None
        key = f"or_{secrets.token_urlsafe(32)}"
        self.create_key("bootstrap-admin", ["admin", "read", "enroll", "recognize"], key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(key)
        path.chmod(0o600)
        return key

    def create_key(
        self,
        name: str,
        scopes: list[str],
        plaintext: str | None = None,
        *,
        mcp_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        key = plaintext or f"or_{secrets.token_urlsafe(32)}"
        kid = str(uuid.uuid4())
        now = _now()
        mcp_json = json_dumps(mcp_tools) if mcp_tools is not None else None
        self.db.execute(
            """INSERT INTO api_keys (id, name, key_hash, scopes, mcp_tools, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (kid, name, hash_key(key), json_dumps(scopes), mcp_json, now),
        )
        return {
            "id": kid,
            "name": name,
            "scopes": scopes,
            "mcp_tool_allowlist": mcp_tools,
            "key": key,
            "created_at": now,
            "last_used_at": None,
            "revoked_at": None,
        }

    def list_keys(self, *, include_revoked: bool = False) -> list[dict[str, Any]]:
        sql = (
            "SELECT id, name, scopes, mcp_tools, created_at, last_used_at, revoked_at "
            "FROM api_keys"
        )
        if not include_revoked:
            sql += " WHERE revoked_at IS NULL"
        sql += " ORDER BY created_at DESC"
        rows = self.db.fetchall(sql)
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "scopes": json_loads(r["scopes"]),
                "mcp_tool_allowlist": json_loads(r["mcp_tools"])
                if r["mcp_tools"]
                else None,
                "created_at": r["created_at"],
                "last_used_at": r["last_used_at"],
                "revoked_at": r["revoked_at"],
            }
            for r in rows
        ]

    def revoke_key(self, kid: str) -> bool:
        """Permanently remove an API key (UI labels this Delete)."""
        row = self.db.fetchone("SELECT id FROM api_keys WHERE id = ?", (kid,))
        if not row:
            return False
        self.db.execute("DELETE FROM api_keys WHERE id = ?", (kid,))
        return True

    def authenticate(self, raw_key: str) -> dict[str, Any] | None:
        digest = hash_key(raw_key)
        row = self.db.fetchone(
            "SELECT * FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
            (digest,),
        )
        if row:
            self._touch(row["id"])
            return self._auth_from_row(row)
        legacy = self.db.fetchall(
            "SELECT * FROM api_keys WHERE revoked_at IS NULL AND key_hash LIKE '$2%'"
        )
        for old in legacy:
            if _verify_legacy_bcrypt(raw_key, old["key_hash"]):
                self.db.execute(
                    "UPDATE api_keys SET key_hash = ?, last_used_at = ? WHERE id = ?",
                    (digest, _now(), old["id"]),
                )
                return self._auth_from_row(old)
        return None

    def _touch(self, key_id: str) -> None:
        self.db.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
            (_now(), key_id),
        )

    def _auth_from_row(self, row) -> dict[str, Any]:
        mcp_raw = row["mcp_tools"]
        return {
            "id": row["id"],
            "name": row["name"],
            "scopes": json_loads(row["scopes"]),
            "mcp_tool_allowlist": json_loads(mcp_raw) if mcp_raw else None,
        }

    def has_scope(self, auth: dict[str, Any] | None, scope: str) -> bool:
        if not auth:
            return False
        scopes = auth.get("scopes", [])
        if "admin" in scopes:
            return True
        return scope in scopes

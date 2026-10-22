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

    def create_key(
        self,
        name: str,
        scopes: list[str],
        plaintext: str | None = None,
    ) -> dict[str, Any]:
        key = plaintext or f"or_{secrets.token_urlsafe(32)}"
        kid = str(uuid.uuid4())
        now = _now()
        self.db.execute(
            """INSERT INTO api_keys (id, name, key_hash, scopes, mcp_tools, created_at)
               VALUES (?, ?, ?, ?, NULL, ?)""",
            (kid, name, hash_key(key), json_dumps(scopes), now),
        )
        return {
            "id": kid,
            "name": name,
            "scopes": scopes,
            "mcp_tool_allowlist": None,
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
        return [self._public_from_row(r) for r in rows]

    def get_key(self, kid: str) -> dict[str, Any] | None:
        row = self.db.fetchone(
            """SELECT id, name, scopes, created_at, last_used_at, revoked_at
               FROM api_keys WHERE id = ?""",
            (kid,),
        )
        if not row or row["revoked_at"]:
            return None
        return self._public_from_row(row)

    def update_key(
        self,
        kid: str,
        *,
        name: str | None = None,
        scopes: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if self.get_key(kid) is None:
            return None
        sets: list[str] = []
        params: list[Any] = []
        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if scopes is not None:
            sets.append("scopes = ?")
            params.append(json_dumps(scopes))
            sets.append("mcp_tools = NULL")
        if sets:
            params.append(kid)
            self.db.execute(
                f"UPDATE api_keys SET {', '.join(sets)} WHERE id = ?",
                tuple(params),
            )
        return self.get_key(kid)

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

    def _public_from_row(self, row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "scopes": json_loads(row["scopes"]),
            "mcp_tool_allowlist": None,
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "revoked_at": row["revoked_at"],
        }

    def _auth_from_row(self, row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "scopes": json_loads(row["scopes"]),
        }

    def has_scope(self, auth: dict[str, Any] | None, scope: str) -> bool:
        if not auth:
            return False
        scopes = auth.get("scopes", [])
        if "admin" in scopes:
            return True
        return scope in scopes

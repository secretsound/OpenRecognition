"""Web UI session and local user accounts."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt

from openrecognition.gallery.db import Database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


_BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    raw = password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password must be at most 72 bytes")
    return raw


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode()


def _is_default_password(password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(b"admin", password_hash.encode())
    except ValueError:
        return False


VALID_ROLES = frozenset({"viewer", "operator", "admin"})

ROLE_SCOPES = {
    "viewer": ["read"],
    "operator": ["read", "enroll", "recognize"],
    "admin": ["admin", "read", "enroll", "recognize"],
}


def role_from_scopes(scopes: list[str] | None) -> str:
    """Map API-key or session scopes to the same roles the console uses."""
    have = set(scopes or [])
    if "admin" in have:
        return "admin"
    if "enroll" in have or "recognize" in have:
        return "operator"
    return "viewer"


class SessionService:
    def __init__(self, db: Database, ttl_minutes: int = 60):
        self.db = db
        self.ttl_minutes = ttl_minutes

    def ensure_default_admin(
        self, username: str = "admin", password: str | None = None
    ) -> str | None:
        """Create the first admin, or replace a leftover admin/admin password.

        Returns the plaintext password only when it was just written.
        """
        row = self.db.fetchone(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username,),
        )
        if row:
            if not _is_default_password(row["password_hash"]):
                return None
            new_password = password or secrets.token_urlsafe(18)
            self.db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (_hash_password(new_password), row["id"]),
            )
            self.delete_sessions_for_user(row["id"])
            return new_password
        if self.db.fetchone("SELECT id FROM users LIMIT 1"):
            return None
        new_password = password or secrets.token_urlsafe(18)
        uid = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (uid, username, _hash_password(new_password), "admin", _now_iso()),
        )
        return new_password

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT id, username, role, created_at FROM users ORDER BY username"
        )
        return [dict(r) for r in rows]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone(
            "SELECT id, username, role, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        return dict(row) if row else None

    def has_users(self) -> bool:
        return self.db.fetchone("SELECT id FROM users LIMIT 1") is not None

    def count_admins(self) -> int:
        row = self.db.fetchone(
            "SELECT COUNT(*) as c FROM users WHERE role = ?", ("admin",)
        )
        return int(row["c"]) if row else 0

    def create_user(self, username: str, password: str, role: str) -> dict[str, Any]:
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")
        existing = self.db.fetchone("SELECT id FROM users WHERE username = ?", (username,))
        if existing:
            raise ValueError("Username already exists")
        uid = str(uuid.uuid4())
        pw_hash = _hash_password(password)
        created_at = _now_iso()
        self.db.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (uid, username, pw_hash, role, created_at),
        )
        return {"id": uid, "username": username, "role": role, "created_at": created_at}

    def update_user(
        self,
        user_id: str,
        *,
        role: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any] | None:
        user = self.get_user(user_id)
        if not user:
            return None
        if role is not None:
            if role not in VALID_ROLES:
                raise ValueError(f"Invalid role: {role}")
            if user["role"] == "admin" and role != "admin" and self.count_admins() <= 1:
                raise ValueError("Cannot remove the last admin user")
            self.db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            user["role"] = role
        if password:
            pw_hash = _hash_password(password)
            self.db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id)
            )
            self.delete_sessions_for_user(user_id)
        return self.get_user(user_id)

    def delete_user(self, user_id: str, *, actor_user_id: str | None = None) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        if actor_user_id and user_id == actor_user_id:
            raise ValueError("Cannot delete your own account")
        if user["role"] == "admin" and self.count_admins() <= 1:
            raise ValueError("Cannot delete the last admin user")
        self.delete_sessions_for_user(user_id)
        self.db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return True

    def delete_sessions_for_user(self, user_id: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM users WHERE username = ?", (username,))
        if not row:
            return None
        try:
            ok = bcrypt.checkpw(_password_bytes(password), row["password_hash"].encode())
        except ValueError:
            return None
        if not ok:
            return None
        return {"id": row["id"], "username": row["username"], "role": row["role"]}

    def create_session(self, user_id: str) -> str:
        sid = secrets.token_urlsafe(32)
        expires = _now() + timedelta(minutes=self.ttl_minutes)
        self.db.execute(
            "INSERT INTO sessions (id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (sid, user_id, expires.isoformat(), _now_iso()),
        )
        return sid

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if not row:
            return None
        expires = datetime.fromisoformat(row["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if _now() > expires:
            self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return None
        user = self.db.fetchone("SELECT * FROM users WHERE id = ?", (row["user_id"],))
        if not user:
            return None
        scopes = ROLE_SCOPES.get(user["role"], ["read"])
        return {
            "session_id": session_id,
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "scopes": scopes,
        }

    def delete_session(self, session_id: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

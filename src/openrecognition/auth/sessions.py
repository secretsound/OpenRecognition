"""Web UI session and local user accounts."""

import re
import secrets
import sqlite3
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


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().lower()
    if not text:
        return None
    if len(text) > 254 or _EMAIL_RE.fullmatch(text) is None:
        raise ValueError("Enter a valid email address")
    return text


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
        self.groups = None

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
            "SELECT id, username, email, role, created_at FROM users ORDER BY username"
        )
        return [dict(r) for r in rows]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone(
            "SELECT id, username, email, role, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        return dict(row) if row else None

    def has_users(self) -> bool:
        return self.db.fetchone("SELECT id FROM users LIMIT 1") is not None

    def count_admins(self) -> int:
        if self.groups is not None:
            return self.groups.count_effective_admins()
        row = self.db.fetchone(
            "SELECT COUNT(*) as c FROM users WHERE role = ?", ("admin",)
        )
        return int(row["c"]) if row else 0

    def effective_role(self, user_id: str, base_role: str) -> str:
        if self.groups is not None:
            return self.groups.effective_role(user_id, base_role)
        return base_role if base_role in VALID_ROLES else "viewer"

    def _find_email(self, email: str | None) -> dict[str, Any] | None:
        if not email:
            return None
        row = self.db.fetchone(
            "SELECT id, username, email, role, sso_subject FROM users WHERE email = ?",
            (email,),
        )
        return dict(row) if row else None

    def _attach_sso(
        self,
        user: dict[str, Any],
        *,
        subject: str,
        protocol: str,
        email: str | None,
    ) -> None:
        existing_subject = user.get("sso_subject")
        if existing_subject and existing_subject != subject:
            raise ValueError("Account is linked to a different identity")
        if email:
            owner = self._find_email(email)
            if owner is not None and owner["id"] != user["id"]:
                raise ValueError("Email is linked to a different identity")
        sets = ["sso_subject = ?", "sso_protocol = ?"]
        params: list[Any] = [subject, protocol]
        if email and not user.get("email"):
            sets.append("email = ?")
            params.append(email)
        params.append(user["id"])
        self.db.execute(
            f"UPDATE users SET {', '.join(sets)} WHERE id = ?",
            tuple(params),
        )

    def provision_sso_user(
        self,
        *,
        username: str,
        subject: str,
        protocol: str,
        role: str,
        link_existing: bool,
        auto_provision: bool,
        email: str | None = None,
        match: str = "username",
    ) -> dict[str, Any]:
        if role not in VALID_ROLES:
            role = "viewer"
        if not subject:
            raise ValueError("Missing identity")
        cleaned_email = normalize_email(email)
        linked = self.db.fetchone(
            "SELECT id, username, email, role, sso_subject FROM users WHERE sso_subject = ?",
            (subject,),
        )
        if linked is not None:
            linked = dict(linked)
            self._attach_sso(linked, subject=subject, protocol=protocol, email=cleaned_email)
        elif link_existing:
            if match == "email":
                chosen = self._find_email(cleaned_email)
            else:
                by_name = self.db.fetchone(
                    "SELECT id, username, email, role, sso_subject FROM users WHERE username = ?",
                    (username,),
                )
                chosen = dict(by_name) if by_name is not None else None
            if chosen is not None:
                self._attach_sso(chosen, subject=subject, protocol=protocol, email=cleaned_email)
                linked = chosen
        if linked is None:
            if not auto_provision:
                raise ValueError("No account on this server matches that identity")
            if cleaned_email and self._find_email(cleaned_email):
                raise ValueError("Email is linked to a different identity")
            uid = str(uuid.uuid4())
            created_at = _now_iso()
            try:
                self.db.execute(
                    """INSERT INTO users
                       (id, username, password_hash, role, created_at, sso_subject, sso_protocol, email)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uid,
                        username,
                        _hash_password(secrets.token_urlsafe(24)),
                        role,
                        created_at,
                        subject,
                        protocol,
                        cleaned_email,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Username is linked to a different identity") from exc
            return {
                "id": uid,
                "username": username,
                "email": cleaned_email,
                "role": role,
                "created_at": created_at,
            }
        return {
            "id": linked["id"],
            "username": linked["username"],
            "email": cleaned_email or linked.get("email"),
            "role": linked["role"],
        }

    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        email: str | None = None,
    ) -> dict[str, Any]:
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")
        cleaned_email = normalize_email(email)
        existing = self.db.fetchone("SELECT id FROM users WHERE username = ?", (username,))
        if existing:
            raise ValueError("Username already exists")
        if cleaned_email and self._find_email(cleaned_email):
            raise ValueError("Email already exists")
        uid = str(uuid.uuid4())
        pw_hash = _hash_password(password)
        created_at = _now_iso()
        self.db.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, email)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (uid, username, pw_hash, role, created_at, cleaned_email),
        )
        return {
            "id": uid,
            "username": username,
            "email": cleaned_email,
            "role": role,
            "created_at": created_at,
        }

    def update_user(
        self,
        user_id: str,
        *,
        role: str | None = None,
        password: str | None = None,
        email: str | None = None,
        email_set: bool = False,
    ) -> dict[str, Any] | None:
        user = self.get_user(user_id)
        if not user:
            return None
        if role is not None:
            if role not in VALID_ROLES:
                raise ValueError(f"Invalid role: {role}")
            next_effective = self.effective_role(user_id, role)
            if (
                self.effective_role(user_id, user["role"]) == "admin"
                and next_effective != "admin"
                and self.count_admins() <= 1
            ):
                raise ValueError("Cannot remove the last admin user")
            self.db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            user["role"] = role
        if password:
            pw_hash = _hash_password(password)
            self.db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id)
            )
            self.delete_sessions_for_user(user_id)
        if email_set:
            cleaned_email = normalize_email(email)
            owner = self._find_email(cleaned_email)
            if owner is not None and owner["id"] != user_id:
                raise ValueError("Email already exists")
            self.db.execute("UPDATE users SET email = ? WHERE id = ?", (cleaned_email, user_id))
        return self.get_user(user_id)

    def delete_user(self, user_id: str, *, actor_user_id: str | None = None) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        if actor_user_id and user_id == actor_user_id:
            raise ValueError("Cannot delete your own account")
        if self.effective_role(user_id, user["role"]) == "admin" and self.count_admins() <= 1:
            raise ValueError("Cannot delete the last admin user")
        self.delete_sessions_for_user(user_id)
        self.db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return True

    def delete_sessions_for_user(self, user_id: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        ident = username.strip()
        row = self.db.fetchone("SELECT * FROM users WHERE username = ?", (ident,))
        if row is None and "@" in ident:
            row = self.db.fetchone("SELECT * FROM users WHERE email = ?", (ident.lower(),))
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
        role = self.effective_role(user["id"], user["role"])
        scopes = ROLE_SCOPES.get(role, ["read"])
        return {
            "session_id": session_id,
            "user_id": user["id"],
            "username": user["username"],
            "role": role,
            "base_role": user["role"],
            "scopes": scopes,
        }

    def delete_session(self, session_id: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

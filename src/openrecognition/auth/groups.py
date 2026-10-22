"""Access groups: role grants and per-enrollment rights."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from openrecognition.auth.sessions import ROLE_SCOPES, VALID_ROLES
from openrecognition.gallery.db import Database

ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}

SYSTEM_GROUPS = (
    {
        "id": "sys-administrators",
        "name": "Administrators",
        "description": "Members can see every enrollment and manage the server.",
        "grants_role": "admin",
        "sso_name": "admin",
    },
    {
        "id": "sys-operators",
        "name": "Operators",
        "description": "Members can create enrollments and manage the ones they created.",
        "grants_role": "operator",
        "sso_name": "operator",
    },
    {
        "id": "sys-viewers",
        "name": "Viewers",
        "description": "Members can look through the library without changing it.",
        "grants_role": "viewer",
        "sso_name": "viewer",
    },
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _role_rank(role: str | None) -> int:
    return ROLE_RANK.get(role or "", -1)


def higher_role(a: str, b: str | None) -> str:
    if b is None or _role_rank(b) > _role_rank(a):
        return b or a
    return a


def seed_system_groups(conn: sqlite3.Connection) -> None:
    now = _now_iso()
    for spec in SYSTEM_GROUPS:
        row = conn.execute(
            "SELECT id, description FROM groups WHERE system = 1 AND grants_role = ?",
            (spec["grants_role"],),
        ).fetchone()
        if row:
            description = row["description"] if isinstance(row, sqlite3.Row) else row[1]
            if description is None or "sso" in str(description).lower():
                gid = row["id"] if isinstance(row, sqlite3.Row) else row[0]
                conn.execute(
                    "UPDATE groups SET description = ? WHERE id = ?",
                    (spec["description"], gid),
                )
            continue
        taken = conn.execute("SELECT id FROM groups WHERE id = ?", (spec["id"],)).fetchone()
        gid = spec["id"] if not taken else str(uuid.uuid4())
        conn.execute(
            """INSERT INTO groups
               (id, name, description, grants_role, sso_name, system, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (
                gid,
                spec["name"],
                spec["description"],
                spec["grants_role"],
                spec["sso_name"],
                now,
            ),
        )


def _effective_role_conn(conn: sqlite3.Connection, user_id: str, base_role: str) -> str:
    best = base_role if base_role in VALID_ROLES else "viewer"
    rows = conn.execute(
        """SELECT g.grants_role FROM groups g
           JOIN group_members m ON m.group_id = g.id
           WHERE m.user_id = ? AND g.grants_role IS NOT NULL""",
        (user_id,),
    ).fetchall()
    for row in rows:
        role = row["grants_role"] if isinstance(row, sqlite3.Row) else row[0]
        best = higher_role(best, role)
    return best


def _count_effective_admins_conn(conn: sqlite3.Connection) -> int:
    users = conn.execute("SELECT id, role FROM users").fetchall()
    count = 0
    for user in users:
        uid = user["id"] if isinstance(user, sqlite3.Row) else user[0]
        role = user["role"] if isinstance(user, sqlite3.Row) else user[1]
        if _effective_role_conn(conn, uid, role) == "admin":
            count += 1
    return count


class GroupStore:
    def __init__(self, db: Database):
        self.db = db

    def effective_role(self, user_id: str, base_role: str) -> str:
        with self.db.connect() as conn:
            return _effective_role_conn(conn, user_id, base_role)

    def count_effective_admins(self) -> int:
        with self.db.connect() as conn:
            return _count_effective_admins_conn(conn)

    def scopes_for_user(self, user_id: str, base_role: str) -> list[str]:
        role = self.effective_role(user_id, base_role)
        return list(ROLE_SCOPES.get(role, ["read"]))

    def briefs_for_user(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """SELECT g.id, g.name FROM groups g
               JOIN group_members m ON m.group_id = g.id
               WHERE m.user_id = ?
               ORDER BY g.system DESC, g.name""",
            (user_id,),
        )
        return [{"id": r["id"], "name": r["name"]} for r in rows]

    def enrollment_grants_for_user(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """SELECT ge.enrollment_id, ge.can_add_samples, ge.can_manage
               FROM group_enrollments ge
               JOIN group_members gm ON gm.group_id = ge.group_id
               WHERE gm.user_id = ?""",
            (user_id,),
        )
        merged: dict[str, dict[str, Any]] = {}
        for row in rows:
            eid = row["enrollment_id"]
            current = merged.setdefault(
                eid,
                {"enrollment_id": eid, "can_add_samples": False, "can_manage": False},
            )
            if row["can_add_samples"]:
                current["can_add_samples"] = True
            if row["can_manage"]:
                current["can_manage"] = True
        return list(merged.values())

    def is_library_limited(self, user_id: str, effective_role: str) -> bool:
        if effective_role in {"admin", "operator"}:
            return False
        row = self.db.fetchone(
            """SELECT 1 FROM group_enrollments ge
               JOIN group_members gm ON gm.group_id = ge.group_id
               WHERE gm.user_id = ? LIMIT 1""",
            (user_id,),
        )
        return row is not None

    def limited_enrollment_ids(self, user_id: str) -> set[str]:
        rows = self.db.fetchall(
            """SELECT DISTINCT ge.enrollment_id
               FROM group_enrollments ge
               JOIN group_members gm ON gm.group_id = ge.group_id
               WHERE gm.user_id = ?""",
            (user_id,),
        )
        return {row["enrollment_id"] for row in rows}

    def enrollment_rights(self, user_id: str, enrollment_id: str) -> dict[str, bool] | None:
        rows = self.db.fetchall(
            """SELECT ge.can_add_samples, ge.can_manage
               FROM group_enrollments ge
               JOIN group_members gm ON gm.group_id = ge.group_id
               WHERE gm.user_id = ? AND ge.enrollment_id = ?""",
            (user_id, enrollment_id),
        )
        if not rows:
            return None
        return {
            "view": True,
            "can_add_samples": any(row["can_add_samples"] for row in rows),
            "can_manage": any(row["can_manage"] for row in rows),
        }

    def list_groups(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """SELECT g.id, g.name, g.description, g.grants_role, g.sso_name, g.system, g.created_at,
                      (SELECT COUNT(*) FROM group_members m WHERE m.group_id = g.id) AS member_count,
                      (SELECT COUNT(*) FROM group_enrollments e WHERE e.group_id = g.id) AS enrollment_count
               FROM groups g
               ORDER BY g.system DESC, g.name"""
        )
        return [self._group_row(row, members=None, enrollments=None) for row in rows]

    def get_group(self, group_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone(
            """SELECT g.id, g.name, g.description, g.grants_role, g.sso_name, g.system, g.created_at,
                      (SELECT COUNT(*) FROM group_members m WHERE m.group_id = g.id) AS member_count,
                      (SELECT COUNT(*) FROM group_enrollments e WHERE e.group_id = g.id) AS enrollment_count
               FROM groups g WHERE g.id = ?""",
            (group_id,),
        )
        if not row:
            return None
        members = self.db.fetchall(
            """SELECT u.id, u.username, u.role
               FROM group_members m
               JOIN users u ON u.id = m.user_id
               WHERE m.group_id = ?
               ORDER BY u.username""",
            (group_id,),
        )
        enrollments = self.db.fetchall(
            """SELECT ge.enrollment_id, e.label, e.type, ge.can_add_samples, ge.can_manage
               FROM group_enrollments ge
               JOIN enrollments e ON e.id = ge.enrollment_id
               WHERE ge.group_id = ?
               ORDER BY e.label""",
            (group_id,),
        )
        return self._group_row(row, members=members, enrollments=enrollments)

    def create_group(
        self,
        name: str,
        description: str = "",
        sso_name: str | None = None,
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("Name is required")
        sso = _clean_sso(sso_name)
        gid = str(uuid.uuid4())
        try:
            self.db.execute(
                """INSERT INTO groups
                   (id, name, description, grants_role, sso_name, system, created_at)
                   VALUES (?, ?, ?, NULL, ?, 0, ?)""",
                (gid, name, description.strip(), sso, _now_iso()),
            )
        except Exception as exc:
            raise ValueError(_unique_error(exc)) from exc
        created = self.get_group(gid)
        if not created:
            raise ValueError("Could not create group")
        return created

    def patch_group(
        self,
        group_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        sso_name: str | None = None,
        sso_name_set: bool = False,
    ) -> dict[str, Any] | None:
        group = self.get_group(group_id)
        if not group:
            return None
        fields: list[str] = []
        params: list[Any] = []
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("Name is required")
            fields.append("name = ?")
            params.append(cleaned)
        if description is not None:
            fields.append("description = ?")
            params.append(description.strip())
        if sso_name_set:
            fields.append("sso_name = ?")
            params.append(_clean_sso(sso_name))
        if not fields:
            return group
        params.append(group_id)
        try:
            self.db.execute(
                f"UPDATE groups SET {', '.join(fields)} WHERE id = ?",
                tuple(params),
            )
        except Exception as exc:
            raise ValueError(_unique_error(exc)) from exc
        return self.get_group(group_id)

    def delete_group(self, group_id: str) -> bool:
        group = self.get_group(group_id)
        if not group:
            return False
        if group["system"]:
            raise ValueError("Cannot delete a built-in group")
        self.db.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        return True

    def set_members(self, group_id: str, user_ids: list[str]) -> dict[str, Any]:
        group = self.get_group(group_id)
        if not group:
            raise KeyError("Group not found")
        unique_ids = list(dict.fromkeys(user_ids))
        with self.db.connect() as conn:
            for uid in unique_ids:
                row = conn.execute("SELECT id FROM users WHERE id = ?", (uid,)).fetchone()
                if not row:
                    raise ValueError("Unknown user")
            conn.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
            for uid in unique_ids:
                conn.execute(
                    "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                    (group_id, uid),
                )
            if _count_effective_admins_conn(conn) < 1:
                raise ValueError("Cannot remove the last admin user")
            conn.commit()
        result = self.get_group(group_id)
        if not result:
            raise KeyError("Group not found")
        return result

    def set_enrollments(
        self,
        group_id: str,
        enrollments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        group = self.get_group(group_id)
        if not group:
            raise KeyError("Group not found")
        seen: set[str] = set()
        cleaned: list[dict[str, Any]] = []
        for item in enrollments:
            eid = str(item.get("enrollment_id") or "")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            cleaned.append(
                {
                    "enrollment_id": eid,
                    "can_add_samples": bool(item.get("can_add_samples")),
                    "can_manage": bool(item.get("can_manage")),
                }
            )
        with self.db.connect() as conn:
            for item in cleaned:
                row = conn.execute(
                    "SELECT id FROM enrollments WHERE id = ?",
                    (item["enrollment_id"],),
                ).fetchone()
                if not row:
                    raise ValueError("Unknown enrollment")
            conn.execute("DELETE FROM group_enrollments WHERE group_id = ?", (group_id,))
            for item in cleaned:
                conn.execute(
                    """INSERT INTO group_enrollments
                       (group_id, enrollment_id, can_add_samples, can_manage)
                       VALUES (?, ?, ?, ?)""",
                    (
                        group_id,
                        item["enrollment_id"],
                        1 if item["can_add_samples"] else 0,
                        1 if item["can_manage"] else 0,
                    ),
                )
            conn.commit()
        result = self.get_group(group_id)
        if not result:
            raise KeyError("Group not found")
        return result

    def sync_sso_membership(self, user_id: str, provider_groups: list[str]) -> None:
        """Match provider group names to each group's SSO name. Manual groups are left alone."""
        wanted = {item.strip().casefold() for item in provider_groups if item and item.strip()}
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, sso_name FROM groups WHERE sso_name IS NOT NULL AND sso_name != ''"
            ).fetchall()
            for row in rows:
                group_id = row["id"]
                name = (row["sso_name"] or "").strip().casefold()
                member = conn.execute(
                    "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                ).fetchone()
                if name in wanted and member is None:
                    conn.execute(
                        "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                        (group_id, user_id),
                    )
                elif member is not None and name not in wanted:
                    conn.execute(
                        "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
                        (group_id, user_id),
                    )
            if _count_effective_admins_conn(conn) < 1:
                raise ValueError("Cannot remove the last admin user")
            conn.commit()

    def set_user_groups(self, user_id: str, group_ids: list[str]) -> list[dict[str, Any]]:
        unique_ids = list(dict.fromkeys(group_ids))
        with self.db.connect() as conn:
            user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                raise KeyError("User not found")
            for gid in unique_ids:
                row = conn.execute("SELECT id FROM groups WHERE id = ?", (gid,)).fetchone()
                if not row:
                    raise ValueError("Unknown group")
            conn.execute("DELETE FROM group_members WHERE user_id = ?", (user_id,))
            for gid in unique_ids:
                conn.execute(
                    "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                    (gid, user_id),
                )
            if _count_effective_admins_conn(conn) < 1:
                raise ValueError("Cannot remove the last admin user")
            conn.commit()
        return self.briefs_for_user(user_id)

    def _group_row(
        self,
        row: sqlite3.Row,
        *,
        members: list[sqlite3.Row] | None,
        enrollments: list[sqlite3.Row] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"] or "",
            "grants_role": row["grants_role"],
            "sso_name": row["sso_name"],
            "system": bool(row["system"]),
            "created_at": row["created_at"],
            "member_count": int(row["member_count"] or 0),
            "enrollment_count": int(row["enrollment_count"] or 0),
            "members": [],
            "enrollments": [],
        }
        if members is not None:
            payload["members"] = [
                {"id": m["id"], "username": m["username"], "role": m["role"]} for m in members
            ]
            payload["member_count"] = len(payload["members"])
        if enrollments is not None:
            payload["enrollments"] = [
                {
                    "enrollment_id": e["enrollment_id"],
                    "label": e["label"],
                    "type": e["type"],
                    "can_add_samples": bool(e["can_add_samples"]),
                    "can_manage": bool(e["can_manage"]),
                }
                for e in enrollments
            ]
            payload["enrollment_count"] = len(payload["enrollments"])
        return payload


def _clean_sso(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _unique_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "sso_name" in text:
        return "SSO name already in use"
    if "name" in text:
        return "A group with that name already exists"
    return "Could not save group"

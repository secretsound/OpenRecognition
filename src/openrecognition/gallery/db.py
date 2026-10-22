"""SQLite schema and connection."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    scopes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    sso_subject TEXT,
    sso_protocol TEXT,
    email TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    label TEXT NOT NULL,
    species_hint TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    threshold REAL,
    model_version TEXT,
    centroid BLOB,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT
);

CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    enrollment_id TEXT NOT NULL,
    modality TEXT NOT NULL,
    model_version TEXT NOT NULL,
    vector BLOB NOT NULL,
    dim INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS enrollment_media (
    id TEXT PRIMARY KEY,
    enrollment_id TEXT NOT NULL,
    path TEXT,
    modality TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    title_template TEXT NOT NULL DEFAULT '',
    message_template TEXT NOT NULL DEFAULT '',
    events TEXT NOT NULL,
    filters TEXT NOT NULL,
    debounce_seconds INTEGER NOT NULL DEFAULT 30,
    include_details INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS presence (
    enrollment_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    type TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_modality TEXT NOT NULL,
    last_camera_id TEXT,
    confidence REAL,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload TEXT,
    result TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS debounce_state (
    key TEXT PRIMARY KEY,
    last_fired_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    grants_role TEXT,
    sso_name TEXT UNIQUE,
    system INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_enrollments (
    group_id TEXT NOT NULL,
    enrollment_id TEXT NOT NULL,
    can_add_samples INTEGER NOT NULL DEFAULT 0,
    can_manage INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_id, enrollment_id),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_embeddings_enrollment ON embeddings(enrollment_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_type ON enrollments(type);
CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);
CREATE INDEX IF NOT EXISTS idx_group_enrollments_enrollment ON group_enrollments(enrollment_id);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            from openrecognition.gallery.migrations import run_migrations

            run_migrations(conn)
            conn.commit()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, params)
            conn.commit()

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()


def json_dumps(obj: Any) -> str:
    return json.dumps(obj)


def json_loads(s: str | None) -> Any:
    if not s:
        return {}
    return json.loads(s)

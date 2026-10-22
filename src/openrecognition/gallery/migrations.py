"""SQLite schema migrations (additive)."""

import json
import sqlite3

_SCOPE_ORDER = ("read", "recognize", "enroll", "update", "delete", "admin")


def _expand_legacy_enroll_scopes(conn: sqlite3.Connection) -> None:
    """Older enroll keys could also change and remove profiles. Keep that ability."""
    rows = conn.execute("SELECT id, scopes FROM api_keys").fetchall()
    for row in rows:
        try:
            scopes = json.loads(row["scopes"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(scopes, list) or "admin" in scopes or "enroll" not in scopes:
            continue
        merged = set(scopes)
        merged.update(("update", "delete"))
        ordered = [scope for scope in _SCOPE_ORDER if scope in merged]
        current = [scope for scope in _SCOPE_ORDER if scope in scopes]
        extras = [scope for scope in scopes if scope not in _SCOPE_ORDER]
        if ordered == current and not extras:
            continue
        conn.execute(
            "UPDATE api_keys SET scopes = ? WHERE id = ?",
            (json.dumps(ordered + extras), row["id"]),
        )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def run_migrations(conn: sqlite3.Connection) -> None:
    emb_cols = _columns(conn, "embeddings")
    additions = [
        ("source", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("original_filename", "TEXT"),
        ("content_type", "TEXT"),
        ("size_bytes", "INTEGER"),
        ("duration_ms", "REAL"),
        ("phrase_index", "INTEGER"),
        ("phrase_text", "TEXT"),
    ]
    for name, ddl in additions:
        if name not in emb_cols:
            conn.execute(f"ALTER TABLE embeddings ADD COLUMN {name} {ddl}")

    media_cols = _columns(conn, "enrollment_media")
    if "embedding_id" not in media_cols:
        conn.execute("ALTER TABLE enrollment_media ADD COLUMN embedding_id TEXT")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS recognition_logs (
            id TEXT PRIMARY KEY,
            event TEXT NOT NULL,
            modality TEXT,
            label TEXT,
            entity_id TEXT,
            confidence REAL,
            camera_id TEXT,
            zone TEXT,
            request_id TEXT,
            gate TEXT,
            actor_type TEXT,
            actor_id TEXT,
            actor_name TEXT,
            latency_ms REAL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_recognition_logs_created ON recognition_logs(created_at)"
    )

    log_cols = _columns(conn, "recognition_logs")
    log_additions = [
        ("reason", "TEXT"),
        ("summary", "TEXT"),
        ("dry_run", "INTEGER NOT NULL DEFAULT 0"),
        ("details", "TEXT"),
    ]
    for name, ddl in log_additions:
        if name not in log_cols:
            conn.execute(f"ALTER TABLE recognition_logs ADD COLUMN {name} {ddl}")

    enroll_cols = _columns(conn, "enrollments")
    if "external_ids" not in enroll_cols:
        conn.execute("ALTER TABLE enrollments ADD COLUMN external_ids TEXT")
    learn_columns = [
        ("learn_enabled", "INTEGER NOT NULL DEFAULT 0"),
        ("learn_min_confidence", "REAL NOT NULL DEFAULT 0.9"),
        ("learn_margin", "REAL NOT NULL DEFAULT 0.05"),
        ("learn_daily_cap", "INTEGER NOT NULL DEFAULT 8"),
        ("learn_max_samples", "INTEGER NOT NULL DEFAULT 20"),
        ("wyoming_min_confidence", "REAL"),
        ("created_by", "TEXT"),
    ]
    enroll_cols = _columns(conn, "enrollments")
    for name, ddl in learn_columns:
        if name not in enroll_cols:
            conn.execute(f"ALTER TABLE enrollments ADD COLUMN {name} {ddl}")

    key_cols = _columns(conn, "api_keys")
    if "mcp_tools" not in key_cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN mcp_tools TEXT")
    # Permissions are scopes. A scope covers the REST API and the MCP tools for that action.
    conn.execute("UPDATE api_keys SET mcp_tools = NULL WHERE mcp_tools IS NOT NULL")
    _expand_legacy_enroll_scopes(conn)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS model_recommendations (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS model_recommendation_models (
            recommendation_id TEXT NOT NULL,
            model_key TEXT NOT NULL,
            PRIMARY KEY (recommendation_id, model_key),
            FOREIGN KEY (recommendation_id) REFERENCES model_recommendations(id) ON DELETE CASCADE
        )"""
    )

    conn.execute(
        """CREATE TABLE IF NOT EXISTS custom_models (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            category TEXT NOT NULL,
            version TEXT NOT NULL,
            url TEXT NOT NULL,
            filename TEXT NOT NULL,
            use_for TEXT NOT NULL DEFAULT '',
            onnx_json TEXT NOT NULL DEFAULT '{}',
            sort_order INTEGER NOT NULL DEFAULT 50,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS active_models (
            category TEXT PRIMARY KEY,
            model_key TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS catalog_models (
            key TEXT PRIMARY KEY,
            origin TEXT NOT NULL,
            label TEXT NOT NULL,
            category TEXT NOT NULL,
            version TEXT NOT NULL,
            url TEXT NOT NULL,
            filename TEXT NOT NULL,
            license TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'other',
            use_for TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            hardware TEXT NOT NULL DEFAULT 'pi',
            hardware_note TEXT NOT NULL DEFAULT '',
            tier TEXT NOT NULL DEFAULT 'recommended',
            depends_on_json TEXT NOT NULL DEFAULT '[]',
            enables_json TEXT NOT NULL DEFAULT '[]',
            contract_json TEXT NOT NULL DEFAULT '{}',
            defaults_json TEXT NOT NULL DEFAULT '{}',
            sha256 TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS model_settings (
            model_key TEXT PRIMARY KEY,
            overrides_json TEXT NOT NULL DEFAULT '{}'
        )"""
    )

    conn.execute(
        """CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            grants_role TEXT,
            sso_name TEXT UNIQUE,
            system INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS group_members (
            group_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            PRIMARY KEY (group_id, user_id),
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS group_enrollments (
            group_id TEXT NOT NULL,
            enrollment_id TEXT NOT NULL,
            can_add_samples INTEGER NOT NULL DEFAULT 0,
            can_manage INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (group_id, enrollment_id),
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
            FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_group_enrollments_enrollment ON group_enrollments(enrollment_id)"
    )
    from openrecognition.auth.groups import seed_system_groups

    seed_system_groups(conn)

    webhook_cols = _columns(conn, "webhook_subscriptions")
    webhook_additions = [
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("title_template", "TEXT NOT NULL DEFAULT ''"),
        ("message_template", "TEXT NOT NULL DEFAULT ''"),
        ("include_details", "INTEGER NOT NULL DEFAULT 1"),
    ]
    for name, ddl in webhook_additions:
        if name not in webhook_cols:
            conn.execute(f"ALTER TABLE webhook_subscriptions ADD COLUMN {name} {ddl}")

    user_cols = _columns(conn, "users")
    for name, ddl in (
        ("sso_subject", "TEXT"),
        ("sso_protocol", "TEXT"),
        ("email", "TEXT"),
    ):
        if name not in user_cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_sso_subject ON users(sso_subject)"
    )
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sso_login_states (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )"""
    )

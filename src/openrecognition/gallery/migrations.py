"""SQLite schema migrations (additive)."""

import sqlite3


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
    ]
    enroll_cols = _columns(conn, "enrollments")
    for name, ddl in learn_columns:
        if name not in enroll_cols:
            conn.execute(f"ALTER TABLE enrollments ADD COLUMN {name} {ddl}")

    key_cols = _columns(conn, "api_keys")
    if "mcp_tools" not in key_cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN mcp_tools TEXT")

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

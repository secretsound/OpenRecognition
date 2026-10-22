"""Gallery database and settings backup for the console."""

from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from openrecognition import __version__
from openrecognition.app_state import AppState
from openrecognition.logging_config import resolved_logs_dir

_DB_NAME = "openrecognition.db"
_SETTINGS_NAME = "runtime_settings.json"
_MANIFEST = "manifest.json"
_MAX_ZIP = 1024 * 1024 * 1024
_MAX_DB = 2 * 1024 * 1024 * 1024
_ALLOWED = {_DB_NAME, _SETTINGS_NAME, _MANIFEST}


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


def storage_usage(state: AppState) -> dict[str, int]:
    settings = state.settings
    return {
        "data_bytes": directory_size(Path(settings.data_dir)),
        "models_bytes": directory_size(Path(settings.models_dir)),
        "logs_bytes": directory_size(resolved_logs_dir(settings)),
    }


def build_backup(state: AppState) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = {
            "version": __version__,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "contents": [_DB_NAME, _SETTINGS_NAME],
        }
        archive.writestr(_MANIFEST, json.dumps(manifest, indent=2) + "\n")
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / _DB_NAME
            _snapshot_database(Path(state.db.path), snapshot)
            archive.write(snapshot, _DB_NAME)
        store = state._runtime_store
        if store is not None and store.path.is_file():
            archive.write(store.path, _SETTINGS_NAME)
        else:
            archive.writestr(_SETTINGS_NAME, json.dumps(state.runtime_snapshot(), indent=2) + "\n")
    return buffer.getvalue()


def restore_backup(state: AppState, payload: bytes) -> None:
    if len(payload) > _MAX_ZIP:
        raise ValueError("Backup is too large")
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValueError("Backup is not a zip file") from exc
    names = set(archive.namelist())
    extra = [name for name in names if name not in _ALLOWED and not name.endswith("/")]
    if extra:
        raise ValueError("Backup contains unexpected files")
    if _DB_NAME not in names:
        raise ValueError("Backup is missing the gallery database")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / _DB_NAME
        _extract(archive, _DB_NAME, db_path, _MAX_DB)
        _assert_database(db_path)
        settings_data = None
        if _SETTINGS_NAME in names:
            settings_path = Path(tmp) / _SETTINGS_NAME
            _extract(archive, _SETTINGS_NAME, settings_path, 2 * 1024 * 1024)
            settings_data = _parse_settings(settings_path.read_text(encoding="utf-8"))
        _install_database(state, db_path)
        if settings_data is not None:
            _install_settings(state, settings_data)


def _extract(archive: zipfile.ZipFile, name: str, dest: Path, limit: int) -> None:
    info = archive.getinfo(name)
    if info.file_size > limit:
        raise ValueError("Backup is too large")
    written = 0
    with archive.open(info) as src, dest.open("wb") as out:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > limit:
                raise ValueError("Backup is too large")
            out.write(chunk)


def _snapshot_database(source: Path, dest: Path) -> None:
    origin = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(dest)
        try:
            origin.backup(target)
        finally:
            target.close()
    finally:
        origin.close()


def _assert_database(path: Path) -> None:
    header = path.read_bytes()[:16]
    if header != b"SQLite format 3\x00":
        raise ValueError("Gallery file is not a SQLite database")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        check = conn.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0] != "ok":
            raise ValueError("Gallery database failed its integrity check")
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        conn.close()
    if "users" not in tables or "enrollments" not in tables:
        raise ValueError("Gallery database is not an OpenRecognition database")


def _install_database(state: AppState, source: Path) -> None:
    dest = Path(state.db.path)
    try:
        with state.db.connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.Error:
        pass
    os.replace(source, dest)
    for suffix in ("-wal", "-shm"):
        extra = Path(str(dest) + suffix)
        if extra.exists():
            extra.unlink()


def _parse_settings(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Saved settings are not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Saved settings must be an object")
    return data


def _install_settings(state: AppState, data: dict) -> None:
    store = state._runtime_store
    if store is None:
        raise ValueError("This server has nowhere to store settings")
    store.save(data)
    state.apply_runtime_snapshot(data)
    from openrecognition.logging_config import apply_runtime_logging

    apply_runtime_logging(state.settings)

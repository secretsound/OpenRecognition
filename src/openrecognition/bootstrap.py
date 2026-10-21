"""Initialize data directory, database, and bootstrap API key without starting the server."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openrecognition.auth.keys import ApiKeyService
from openrecognition.auth.sessions import SessionService
from openrecognition.config import Settings, settings
from openrecognition.gallery.db import Database

logger = logging.getLogger(__name__)


@dataclass
class BootstrapResult:
    api_key: str | None = None
    admin_password: str | None = None


def run_bootstrap(cfg: Settings | None = None) -> BootstrapResult:
    """Ensure data dir, SQLite schema, default web admin, and bootstrap API key exist.

    The API key and admin password are returned only when they were just created
    (or when a leftover admin/admin password was replaced).
    """
    cfg = cfg or settings
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    db = Database(cfg.db_path)
    sessions = SessionService(db, cfg.session_ttl_minutes)
    admin_password = sessions.ensure_default_admin()
    if admin_password:
        path = cfg.admin_password_path
        path.write_text(admin_password + "\n")
        path.chmod(0o600)
        logger.warning("Admin password for user 'admin' written to %s", path)

    api_keys = ApiKeyService(db)
    created = api_keys.bootstrap_admin(cfg.bootstrap_key_path)
    if created:
        logger.warning("Bootstrap admin API key written to %s", cfg.bootstrap_key_path)

    return BootstrapResult(api_key=created, admin_password=admin_password)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = run_bootstrap()
    if result.api_key:
        print(f"API key ready (also in {settings.bootstrap_key_path}):")
        print(result.api_key)
    else:
        print("Bootstrap API key already configured. See", settings.bootstrap_key_path)
    if result.admin_password:
        print(f"Admin password for user 'admin' (also in {settings.admin_password_path}):")
        print(result.admin_password)


if __name__ == "__main__":
    main()

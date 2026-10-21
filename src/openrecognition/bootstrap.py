"""Initialize the data directory and database without starting the server."""

from __future__ import annotations

import logging

from openrecognition.config import Settings, settings
from openrecognition.gallery.db import Database

logger = logging.getLogger(__name__)


def run_bootstrap(cfg: Settings | None = None) -> None:
    """Create the data directory and SQLite schema.

    The first admin account is created in the console. API keys are created
    there too, and only their hashes are stored.
    """
    cfg = cfg or settings
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    Database(cfg.db_path)
    logger.info("Data directory ready at %s", cfg.data_dir)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_bootstrap()
    print("Data directory is ready. Open the console to create the admin account.")


if __name__ == "__main__":
    main()

"""Application logging setup."""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Ensure openrecognition loggers emit to stderr alongside uvicorn."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
        )
    else:
        root.setLevel(level)

    for name in ("openrecognition", "openrecognition.request", "openrecognition.wyoming"):
        logging.getLogger(name).setLevel(level)

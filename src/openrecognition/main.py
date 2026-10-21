"""Entry point for uvicorn."""

import logging

import uvicorn

from openrecognition.config import settings
from openrecognition.logging_config import configure_logging


def run():
    configure_logging(logging.INFO)
    uvicorn.run(
        "openrecognition.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()

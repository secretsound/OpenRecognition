"""Entry point for the API server."""

from openrecognition.boot_settings import apply_boot_overrides
from openrecognition.config import settings
from openrecognition.logging_config import apply_runtime_logging
from openrecognition.server import serve


def run():
    apply_boot_overrides(settings)
    apply_runtime_logging(settings)
    serve(settings)


if __name__ == "__main__":
    run()

"""Graceful in-process service restart for admin UI."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time

logger = logging.getLogger(__name__)

_RESTART_DELAY = 0.75


def _restart_argv() -> list[str]:
    """Command line used to replace the current process.

    A console script such as ``openrecognition serve`` must be re-executed as
    that script. ``sys.argv`` after ``python -m`` no longer contains ``-m``, so
    that path is rebuilt as ``python -m openrecognition.cli``.
    """
    argv0 = sys.argv[0] if sys.argv else ""
    if os.path.basename(argv0).startswith("openrecognition"):
        return [argv0, *sys.argv[1:]]
    tail = list(sys.argv[1:]) if len(sys.argv) > 1 else ["serve"]
    if tail and tail[0] == "-m":
        return [sys.executable, *sys.argv[1:]]
    return [sys.executable, "-m", "openrecognition.cli", *tail]


def _restart_process() -> None:
    """Replace this process or exit so systemd/Docker can restart it."""
    argv = _restart_argv()
    logger.info("Restarting OpenRecognition (pid %s): %s", os.getpid(), " ".join(argv))
    try:
        os.execv(argv[0], argv)
    except OSError as e:
        logger.warning("execv failed (%s); exiting for external supervisor", e)
        os._exit(0)


def schedule_restart(delay_seconds: float = _RESTART_DELAY) -> None:
    """Schedule restart after the HTTP response is sent (runs in a background thread)."""

    def _run() -> None:
        time.sleep(delay_seconds)
        _restart_process()

    threading.Thread(target=_run, daemon=True).start()

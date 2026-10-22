"""Application logging setup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from openrecognition.config import Settings

_HANDLER_MARK = "_or_file_handler"
_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING, "error": logging.ERROR}


def resolved_logs_dir(settings: Settings) -> Path:
    raw = (settings.logs_dir or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(settings.data_dir) / "logs"


def log_file_path(settings: Settings) -> Path:
    return resolved_logs_dir(settings) / "openrecognition.log"


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

    for name in ("openrecognition", "openrecognition.request", "openrecognition.wyoming", "openrecognition.sso"):
        logging.getLogger(name).setLevel(level)


def apply_runtime_logging(settings: Settings) -> None:
    level = _LEVELS.get((settings.log_level or "info").lower(), logging.INFO)
    configure_logging(level)
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARK, False):
            root.removeHandler(handler)
            handler.close()
    if not settings.log_to_file:
        return
    try:
        directory = resolved_logs_dir(settings)
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_file_path(settings),
            maxBytes=max(1, int(settings.log_max_mb)) * 1_000_000,
            backupCount=max(1, int(settings.log_backup_count)),
            encoding="utf-8",
        )
    except OSError:
        logging.getLogger(__name__).warning("Could not open the log file")
        return
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s:%(name)s: %(message)s"))
    setattr(handler, _HANDLER_MARK, True)
    root.addHandler(handler)


def tail_log(settings: Settings, lines: int = 200) -> tuple[Path, list[str]]:
    path = log_file_path(settings)
    if not path.is_file():
        return path, []
    try:
        data = path.read_bytes()[-200_000:]
    except OSError:
        return path, []
    text = data.decode("utf-8", errors="replace")
    if not text.startswith("20") and "\n" in text:
        text = text.split("\n", 1)[1]
    return path, text.splitlines()[-lines:]

"""ONNX Runtime session pool with optional idle unload."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any

from openrecognition.models_download import (
    resolve_weight,
    runtime_filename,
    runtime_settings,
    runtime_version,
)

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort
except ImportError:
    ort = None  # type: ignore


class ModelSessionPool:
    def __init__(
        self,
        model_dir: Path,
        idle_unload_minutes: int = 0,
        search_dirs: list[Path] | None = None,
    ):
        self.model_dir = model_dir
        self.pack_dir = model_dir
        self.search_dirs = list(search_dirs) if search_dirs else [model_dir]
        self.idle_unload_minutes = idle_unload_minutes
        self.intra_op_threads = 2
        self._sessions: dict[str, Any] = {}
        self._last_used: dict[str, float] = {}
        self._lock = Lock()
        self._loaded = False
        self._active: dict[str, dict[str, Any]] = {}

    def set_active_models(self, active: dict[str, dict[str, Any]]) -> None:
        self._active = dict(active)

    def set_slot_overrides(self, overrides: dict) -> None:
        """Older callers passed download specs. Accept that shape too."""
        active: dict[str, dict[str, Any]] = {}
        for slot, spec in overrides.items():
            filename = getattr(spec, "onnx_filename", None) or getattr(spec, "filename", "")
            settings = getattr(spec, "onnx", None) or getattr(spec, "effective", {})
            active[slot] = {
                "key": getattr(spec, "key", slot),
                "version": getattr(spec, "version", "") or "",
                "filename": filename,
                "settings": dict(settings),
            }
        self._active = active

    def set_intra_op_threads(self, count: int) -> None:
        count = max(1, min(8, int(count)))
        if count == self.intra_op_threads:
            return
        self.intra_op_threads = count
        with self._lock:
            self._sessions.clear()
            self._last_used.clear()

    def _active_row(self, name: str) -> dict[str, Any] | None:
        return self._active.get(name)

    def model_version(self, name: str) -> str | None:
        row = self._active_row(name)
        if row is not None and row.get("version"):
            return str(row["version"])
        return runtime_version(name)

    def onnx_config(self, name: str) -> dict[str, Any]:
        row = self._active_row(name)
        if row is not None:
            return dict(row.get("settings") or {})
        return runtime_settings(name)

    def onnx_path(self, name: str) -> Path | None:
        row = self._active_row(name)
        filename = str(row["filename"]) if row and row.get("filename") else runtime_filename(name)
        return resolve_weight(filename, self.search_dirs)

    @property
    def models_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        with self._lock:
            self.model_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Models directory at %s", self.model_dir)
            self._loaded = True

    def drop_session(self, name: str) -> None:
        """Unload one ONNX session from memory (e.g. after deleting the file)."""
        with self._lock:
            self._sessions.pop(name, None)
            self._last_used.pop(name, None)

    def session_for_file(self, filename: str) -> Any | None:
        """Load a model file that is not the active one for its category.

        Enrollments keep matching with the file that created them until those
        samples are replaced.
        """
        for slot, row in self._active.items():
            if row.get("filename") == filename:
                return self.get_session(slot)
        path = resolve_weight(filename, self.search_dirs)
        if ort is None or path is None:
            return None
        key = f"file:{filename}"
        with self._lock:
            if key not in self._sessions:
                opts = ort.SessionOptions()
                opts.inter_op_num_threads = 1
                opts.intra_op_num_threads = self.intra_op_threads
                self._sessions[key] = ort.InferenceSession(
                    str(path), opts, providers=["CPUExecutionProvider"]
                )
                logger.info("Loaded retained ONNX model %s from %s", filename, path)
            self._last_used[key] = time.time()
            return self._sessions[key]

    def drop_file(self, filename: str) -> None:
        key = f"file:{filename}"
        with self._lock:
            self._sessions.pop(key, None)
            self._last_used.pop(key, None)

    def unload_idle(self) -> None:
        if self.idle_unload_minutes <= 0:
            return
        cutoff = time.time() - self.idle_unload_minutes * 60
        with self._lock:
            for name, last in list(self._last_used.items()):
                if last < cutoff and name in self._sessions:
                    del self._sessions[name]
                    logger.info("Unloaded idle model %s", name)

    def get_session(self, name: str) -> Any | None:
        path = self.onnx_path(name)
        if ort is None or path is None:
            return None
        with self._lock:
            if name not in self._sessions:
                opts = ort.SessionOptions()
                opts.inter_op_num_threads = 1
                opts.intra_op_num_threads = self.intra_op_threads
                self._sessions[name] = ort.InferenceSession(
                    str(path), opts, providers=["CPUExecutionProvider"]
                )
                logger.info("Loaded ONNX model %s from %s", name, path)
            self._last_used[name] = time.time()
            return self._sessions[name]

    def list_models(self) -> dict[str, str]:
        models: dict[str, str] = {}
        versions_by_file = {
            str(row.get("filename")): str(row.get("version") or "")
            for row in self._active.values()
            if row.get("filename")
        }
        seen: set[str] = set()
        for directory in self.search_dirs:
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.onnx")):
                if path.name in seen:
                    continue
                seen.add(path.name)
                ver = versions_by_file.get(path.name) or runtime_version(path.stem)
                models[path.stem] = f"onnx ({ver})" if ver else "onnx"
        if not models:
            models["heuristic"] = "builtin"
        return models

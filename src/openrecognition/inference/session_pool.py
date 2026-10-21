"""ONNX Runtime session pool with optional idle unload."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any

from openrecognition.models_download import (
    ModelDownloadSpec,
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
    def __init__(self, pack_dir: Path, idle_unload_minutes: int = 0):
        self.pack_dir = pack_dir
        self.idle_unload_minutes = idle_unload_minutes
        self._sessions: dict[str, Any] = {}
        self._last_used: dict[str, float] = {}
        self._lock = Lock()
        self._loaded = False
        self._slot_overrides: dict[str, ModelDownloadSpec] = {}

    def set_slot_overrides(self, overrides: dict[str, ModelDownloadSpec]) -> None:
        self._slot_overrides = dict(overrides)

    def _override(self, name: str) -> ModelDownloadSpec | None:
        return self._slot_overrides.get(name)

    def model_version(self, name: str) -> str | None:
        spec = self._override(name)
        if spec is not None:
            return spec.version or None
        return runtime_version(name)

    def onnx_config(self, name: str) -> dict[str, Any]:
        spec = self._override(name)
        if spec is not None:
            return dict(spec.onnx)
        return runtime_settings(name)

    def onnx_path(self, name: str) -> Path | None:
        spec = self._override(name)
        filename = spec.onnx_filename if spec is not None else runtime_filename(name)
        path = self.pack_dir / filename
        return path if path.exists() else None

    @property
    def models_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        with self._lock:
            if self.pack_dir.exists():
                logger.info("Model pack at %s", self.pack_dir)
            self._loaded = True

    def drop_session(self, name: str) -> None:
        """Unload one ONNX session from memory (e.g. after deleting the file)."""
        with self._lock:
            self._sessions.pop(name, None)
            self._last_used.pop(name, None)

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
                opts.intra_op_num_threads = 2
                self._sessions[name] = ort.InferenceSession(
                    str(path), opts, providers=["CPUExecutionProvider"]
                )
                logger.info("Loaded ONNX model %s from %s", name, path)
            self._last_used[name] = time.time()
            return self._sessions[name]

    def list_models(self) -> dict[str, str]:
        models: dict[str, str] = {}
        if not self.pack_dir.exists():
            return models
        versions_by_file = {
            spec.onnx_filename: spec.version for spec in self._slot_overrides.values() if spec.version
        }
        for path in sorted(self.pack_dir.glob("*.onnx")):
            ver = versions_by_file.get(path.name) or runtime_version(path.stem)
            models[path.stem] = f"onnx ({ver})" if ver else "onnx"
        if not models:
            models["heuristic"] = "builtin"
        return models

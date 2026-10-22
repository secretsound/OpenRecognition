"""Persisted runtime overrides (survive process restart)."""

import json
import os
from pathlib import Path
from typing import Any


class RuntimeSettingsStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(payload)
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

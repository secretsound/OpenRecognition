"""Server-side recognition debounce."""

from datetime import datetime, timezone

from openrecognition.gallery.db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DebounceService:
    def __init__(self, db: Database):
        self.db = db

    def should_fire(self, key: str, debounce_seconds: int) -> bool:
        if debounce_seconds <= 0:
            return True
        row = self.db.fetchone("SELECT last_fired_at FROM debounce_state WHERE key = ?", (key,))
        if not row:
            self._mark(key)
            return True
        last = datetime.fromisoformat(row["last_fired_at"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if (now - last).total_seconds() >= debounce_seconds:
            self._mark(key)
            return True
        return False

    def _mark(self, key: str) -> None:
        self.db.execute(
            """INSERT INTO debounce_state (key, last_fired_at) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET last_fired_at=excluded.last_fired_at""",
            (key, _now()),
        )

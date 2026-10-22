"""What this machine can comfortably run, and the thread count that follows."""

from __future__ import annotations

import os
import platform
from pathlib import Path

TIER_LABELS = {
    "pi": "Raspberry Pi",
    "mini": "Mini PC",
    "desktop": "Desktop",
}
TIER_RANK = {"pi": 0, "mini": 1, "desktop": 2}


def _memory_mb() -> int:
    """Physical memory, or the container limit when that is smaller."""
    limit: int | None = None
    for path in (
        Path("/sys/fs/cgroup/memory.max"),
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    ):
        try:
            text = path.read_text().strip()
        except OSError:
            continue
        if not text or text == "max":
            continue
        try:
            value = int(text)
        except ValueError:
            continue
        if value <= 0 or value >= 1 << 60:
            continue
        limit = value // (1024 * 1024)
        break
    total: int | None = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) // 1024
                break
    except OSError:
        pass
    if limit and total:
        return min(limit, total)
    return limit or total or 0


def detect_hardware() -> dict:
    cores = os.cpu_count() or 1
    memory_mb = _memory_mb()
    arch = platform.machine() or ""
    arm = arch.lower() in {"aarch64", "arm64", "armv7l"}
    if memory_mb and memory_mb <= 6 * 1024:
        tier = "pi"
    elif arm and cores <= 4 and (not memory_mb or memory_mb <= 8 * 1024):
        tier = "pi"
    elif memory_mb and memory_mb <= 16 * 1024:
        tier = "mini"
    elif not memory_mb and cores <= 4:
        tier = "pi"
    else:
        tier = "desktop"
    return {
        "tier": tier,
        "cpu_count": cores,
        "memory_mb": memory_mb,
        "arch": arch,
    }


def automatic_threads(cpu_count: int | None = None) -> int:
    cores = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    return max(1, min(4, cores))


def tier_label(tier: str) -> str:
    return TIER_LABELS.get(tier, tier)

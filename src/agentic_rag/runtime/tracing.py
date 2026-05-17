"""启动与回合 profiling checkpoint。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceCollector:
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter)

    def mark(self, name: str, **extra: Any) -> None:
        elapsed_ms = int((time.perf_counter() - self._t0) * 1000)
        row = {"name": name, "elapsed_ms": elapsed_ms, **extra}
        self.checkpoints.append(row)

    def as_events(self) -> list[dict[str, Any]]:
        return list(self.checkpoints)

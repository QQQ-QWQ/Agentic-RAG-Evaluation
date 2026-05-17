"""AppStateStore：get / set / subscribe + 变更追踪。"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from agentic_rag.runtime.state.app_state import AppState
from agentic_rag.runtime.state.effects import on_change_app_state


class AppStateStore:
    def __init__(self, initial: AppState | None = None) -> None:
        self._state = initial or AppState()
        if not self._state.session.session_id:
            self._state.session.session_id = uuid.uuid4().hex[:12]
        self._listeners: list[Callable[[AppState, AppState, str], None]] = []
        self._changelog: list[dict[str, Any]] = []

    def get_state(self) -> AppState:
        return self._state

    def set_state(self, new_state: AppState, *, reason: str = "set") -> None:
        old = self._state
        self._state = new_state
        self._changelog.append(
            {
                "reason": reason,
                "at_ms": int(time.time() * 1000),
                "tier": new_state.tier,
                "mode": new_state.mode,
            }
        )
        on_change_app_state(old, new_state, reason=reason)
        for fn in self._listeners:
            fn(old, new_state, reason)

    def update(self, **fields: Any) -> None:
        """浅更新顶层字段（嵌套对象请用 replace）。"""
        ns = replace(self._state, **fields)
        self.set_state(ns, reason="update")

    def subscribe(self, listener: Callable[[AppState, AppState, str], None]) -> None:
        self._listeners.append(listener)

    def changelog(self) -> list[dict[str, Any]]:
        return list(self._changelog)

"""运行时事件、停止条件与追踪结构（供 REPL / headless / UI 消费）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

RuntimeEventKind = Literal[
    "checkpoint",
    "system",
    "user",
    "assistant",
    "tool_start",
    "tool_end",
    "plan",
    "judge",
    "progress",
    "error",
    "usage",
    "complete",
]

StopReason = Literal[
    "complete",
    "budget",
    "error",
    "aborted",
    "max_rounds",
]


@dataclass
class RuntimeEvent:
    """统一事件流条目。"""

    kind: RuntimeEventKind
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int | None = None


@dataclass
class ToolCallRecord:
    name: str
    started_ms: int
    ended_ms: int | None = None
    ok: bool = True
    error: str = ""
    latency_ms: int = 0


@dataclass
class TurnUsage:
    """单回合用量汇总（从编排结果与消息中尽力提取）。"""

    latency_ms: int = 0
    token_usage: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


@dataclass
class SubmitResult:
    """``QueryEngine.submit_message`` 返回值。"""

    assistant_text: str
    events: list[RuntimeEvent]
    usage: TurnUsage
    stop_reason: StopReason = "complete"
    raw_state: dict[str, Any] | None = None
    transcript: str = ""

"""集中式 AppState（单一真源）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

RuntimeMode = Literal["repl", "headless", "gradio"]
C34Tier = Literal["c3", "c4"]


@dataclass
class PermissionState:
    enable_c4_tools: bool = False
    enable_sandbox: bool = False
    denied_tool_names: list[str] = field(default_factory=list)


@dataclass
class SessionState:
    session_id: str = ""
    cwd: str = ""
    project_root: str = ""
    cli_doc: Path | None = None


@dataclass
class StatsState:
    turn_count: int = 0
    total_latency_ms: int = 0
    token_usage_aggregate: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppState:
    """运行时全局状态；业务策略不写入 UI 组件。"""

    mode: RuntimeMode = "repl"
    tier: C34Tier = "c3"
    session: SessionState = field(default_factory=SessionState)
    permissions: PermissionState = field(default_factory=PermissionState)
    messages_log: list[dict[str, Any]] = field(default_factory=list)
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    stats: StatsState = field(default_factory=StatsState)
    ui_hint: str = ""
    last_error: str = ""
    # 扩展槽（MCP 等后置）
    extensions: dict[str, Any] = field(default_factory=dict)

"""
扩展点：钩子与可选替换实现。

后续可将 ``OrchestrationHooks`` 传入 ``run_cli_agent_session``，接入日志、观测（LangSmith）、
自定义研判模型或替换第一层 / 第三层实现。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class OrchestrationHooks:
    """编排生命周期回调（均可选）。"""

    planning_context_enricher: Callable[[Any], str | None] | None = None
    """接收 ``PlanningEnrichInput``（见 ``planning_extensions``），返回附加到第一层用户消息前的文本。"""
    on_plan: Callable[[Any], None] | None = None
    """接收 ``SessionPlan``。"""
    on_execute_state: Callable[[dict[str, Any]], None] | None = None
    """接收第二层 ``invoke`` 返回的 state 字典。"""
    on_judge: Callable[[Any], None] | None = None
    """接收 ``JudgeVerdict``。"""
    on_round_start: Callable[[int], None] | None = None
    """外层编排轮次从 1 开始。"""
    extend_agent_tools: Callable[[], list[Any]] | None = None
    """返回若干 LangChain 工具，在创建第二层 Agent 时与内置 Topic4 工具合并（每创建一次 Agent 调用一次）。"""

"""编排钩子合并 + 将 L1/L2/L3 事件转发到 RuntimeEvent（供流式 UI / 批量 JSONL）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentic_rag.orchestration.registry import OrchestrationHooks
from agentic_rag.runtime.types import RuntimeEvent
from agentic_rag.telemetry.audit_payload import plan_to_payload, truncate_text, verdict_to_payload


def safe_print_console(text: str) -> None:
    """Print best-effort text without failing on narrow Windows encodings."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(str(text).encode("utf-8", errors="replace").decode("utf-8"), flush=True)


def merge_orchestration_hooks(*parts: OrchestrationHooks) -> OrchestrationHooks:
    """合并多个钩子；同名字段按顺序链式调用。"""

    def _chain(name: str) -> Callable[..., None] | None:
        fns = [getattr(p, name) for p in parts if getattr(p, name, None)]
        if not fns:
            return None

        def _wrapped(*args: Any, **kwargs: Any) -> None:
            for fn in fns:
                fn(*args, **kwargs)

        return _wrapped

    return OrchestrationHooks(
        planning_context_enricher=_chain("planning_context_enricher"),
        on_plan=_chain("on_plan"),
        on_execute_state=_chain("on_execute_state"),
        on_judge=_chain("on_judge"),
        on_round_start=_chain("on_round_start"),
        extend_agent_tools=_chain("extend_agent_tools"),
    )


def hooks_with_runtime_events(
    base: OrchestrationHooks,
    on_event: Callable[[RuntimeEvent], None],
    *,
    tier: str = "c3",
) -> OrchestrationHooks:
    """在既有审计等钩子之外，向 ``on_event`` 推送结构化进度。"""

    def on_round_start(n: int) -> None:
        on_event(
            RuntimeEvent(
                kind="progress",
                message=f"编排轮次 {n} 开始",
                payload={"round": n, "tier": tier},
            )
        )
        if base.on_round_start:
            base.on_round_start(n)

    def on_plan(plan: Any) -> None:
        summary = getattr(plan, "task_summary", "") or ""
        on_event(
            RuntimeEvent(
                kind="plan",
                message=f"第一层规划：{truncate_text(str(summary), max_len=240)}",
                payload=plan_to_payload(plan),
            )
        )
        if base.on_plan:
            base.on_plan(plan)

    def on_execute_state(state: dict[str, Any]) -> None:
        from agentic_rag.deep_planning.agent_runner import format_agent_print

        transcript = format_agent_print(state) if isinstance(state, dict) else ""
        msgs = state.get("messages") if isinstance(state, dict) else []
        n_msgs = len(msgs) if isinstance(msgs, list) else 0
        on_event(
            RuntimeEvent(
                kind="tool_end",
                message=f"第二层执行完成（messages={n_msgs}）",
                payload={
                    "message_count": n_msgs,
                    "transcript_preview": truncate_text(transcript, max_len=1200),
                },
            )
        )
        if base.on_execute_state:
            base.on_execute_state(state)

    def on_judge(verdict: Any) -> None:
        label = getattr(verdict, "verdict", "") or ""
        brief = getattr(verdict, "reasoning_brief", "") or ""
        on_event(
            RuntimeEvent(
                kind="judge",
                message=f"第三层研判：{label} — {truncate_text(str(brief), max_len=200)}",
                payload=verdict_to_payload(verdict),
            )
        )
        if base.on_judge:
            base.on_judge(verdict)

    return OrchestrationHooks(
        planning_context_enricher=base.planning_context_enricher,
        on_plan=on_plan,
        on_execute_state=on_execute_state,
        on_judge=on_judge,
        on_round_start=on_round_start,
        extend_agent_tools=base.extend_agent_tools,
    )


def format_runtime_event_line(ev: RuntimeEvent) -> str:
    """Gradio / 终端流式展示用单行摘要。"""
    icons = {
        "progress": "⏳",
        "plan": "📋",
        "tool_start": "🔧",
        "tool_end": "✅",
        "judge": "⚖️",
        "error": "❌",
        "complete": "✔️",
        "assistant": "💬",
    }
    icon = icons.get(ev.kind, "·")
    return f"{icon} [{ev.kind}] {ev.message}"

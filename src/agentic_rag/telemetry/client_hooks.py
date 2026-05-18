"""C3/C4 客户端编排审计钩子（只写 audit，不改模型输入）。"""

from __future__ import annotations

from typing import Any

from agentic_rag.orchestration.registry import OrchestrationHooks
from agentic_rag.telemetry.audit_log import audit_record, get_audit_session_id
from agentic_rag.telemetry.audit_payload import (
    plan_to_payload,
    serialize_agent_messages,
    truncate_text,
    verdict_to_payload,
)


def build_client_audit_hooks(
    *,
    tier: str = "c3",
    session_id: str | None = None,
) -> OrchestrationHooks:
    """构造 ``OrchestrationHooks``，将各层事件写入 global_audit + session trace。"""

    def _sid() -> str:
        return (session_id or get_audit_session_id()).strip() or "anonymous"

    def on_round_start(n: int) -> None:
        audit_record(
            "orchestration_round_start",
            session_id=_sid(),
            payload={"round": n, "tier": tier},
        )

    def on_plan(plan: Any) -> None:
        audit_record(
            "layer1_plan",
            session_id=_sid(),
            payload=plan_to_payload(plan),
        )

    def on_execute_state(state: dict[str, Any]) -> None:
        msgs = state.get("messages") or []
        transcript = ""
        if isinstance(state, dict):
            from agentic_rag.deep_planning.agent_runner import format_agent_print

            transcript = format_agent_print(state)
        audit_record(
            "layer2_execute_done",
            session_id=_sid(),
            payload={
                "message_count": len(msgs) if isinstance(msgs, list) else 0,
                "messages": serialize_agent_messages(
                    msgs if isinstance(msgs, list) else [],
                    tail=48,
                ),
                "execution_transcript": truncate_text(transcript, max_len=20_000),
            },
        )

    def on_judge(verdict: Any) -> None:
        audit_record(
            "layer3_judge",
            session_id=_sid(),
            payload=verdict_to_payload(verdict),
        )

    return OrchestrationHooks(
        on_round_start=on_round_start,
        on_plan=on_plan,
        on_execute_state=on_execute_state,
        on_judge=on_judge,
    )


def log_turn_result(
    *,
    user_text: str,
    stop_reason: str,
    latency_ms: int,
    transcript_len: int,
    assistant_text: str = "",
    kb_doc_ids: list[str] | None = None,
    tier: str = "c3",
    orchestration_rounds: int | None = None,
    session_id: str | None = None,
) -> dict[str, str]:
    """
    审计摘要 + 会话 ``chat.jsonl`` + ``trace.jsonl`` 事件。

    返回 ``{"chat": path, "global": path, "trace": path}``。
    """
    sid = (session_id or get_audit_session_id()).strip() or "anonymous"
    paths = audit_record(
        "client_turn_complete",
        session_id=sid,
        payload={
            "user": user_text,
            "user_preview": user_text[:500],
            "assistant_preview": truncate_text(assistant_text, max_len=2000),
            "stop_reason": stop_reason,
            "latency_ms": latency_ms,
            "transcript_chars": transcript_len,
            "kb_doc_ids": kb_doc_ids or [],
            "tier": tier,
            "orchestration_rounds": orchestration_rounds,
        },
    )
    from agentic_rag.telemetry.chat_transcript import append_chat_turn

    chat_path = append_chat_turn(
        sid,
        user_text=user_text,
        assistant_text=assistant_text,
        extra={
            "stop_reason": stop_reason,
            "latency_ms": latency_ms,
            "tier": tier,
            "trace_log": paths.get("trace"),
        },
    )
    paths["chat"] = chat_path
    return paths

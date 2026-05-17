"""C3/C4 客户端编排审计钩子（只写 audit_log，不改模型输入）。"""

from __future__ import annotations

from typing import Any

from agentic_rag.orchestration.registry import OrchestrationHooks
from agentic_rag.telemetry.audit_log import audit_log, get_audit_session_id


def build_client_audit_hooks(*, tier: str = "c3") -> OrchestrationHooks:
    """构造 ``OrchestrationHooks``，将各层事件写入全局审计 JSONL。"""

    def on_round_start(n: int) -> None:
        audit_log("orchestration_round_start", payload={"round": n, "tier": tier})

    def on_plan(plan: Any) -> None:
        audit_log(
            "layer1_plan",
            payload={
                "task_summary": getattr(plan, "task_summary", ""),
                "document_path": getattr(plan, "document_path", None),
                "needs_retrieval_tools": getattr(plan, "needs_retrieval_tools", None),
                "kb_mutation_intent": getattr(plan, "kb_mutation_intent", None),
            },
        )

    def on_execute_state(state: dict[str, Any]) -> None:
        msgs = state.get("messages") or []
        audit_log(
            "layer2_execute_done",
            payload={
                "message_count": len(msgs) if isinstance(msgs, list) else 0,
            },
        )

    def on_judge(verdict: Any) -> None:
        audit_log(
            "layer3_judge",
            payload={
                "verdict": getattr(verdict, "verdict", ""),
                "summary": (getattr(verdict, "summary_for_user", "") or "")[:2000],
            },
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
    kb_doc_ids: list[str] | None = None,
) -> None:
    audit_log(
        "client_turn_complete",
        payload={
            "user_preview": user_text[:500],
            "stop_reason": stop_reason,
            "latency_ms": latency_ms,
            "transcript_chars": transcript_len,
            "kb_doc_ids": kb_doc_ids or [],
            "session_id": get_audit_session_id(),
        },
    )

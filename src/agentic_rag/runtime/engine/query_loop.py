"""单回合 query 循环：包装既有编排，产出统一事件流。"""

from __future__ import annotations

import contextlib
import io
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agentic_rag.orchestration.registry import OrchestrationHooks
from agentic_rag.orchestration.types import OrchestrationConfig
from agentic_rag.runtime.tracing import TraceCollector
from agentic_rag.runtime.types import RuntimeEvent, StopReason, SubmitResult, TurnUsage


def run_orchestration_turn(
    user_text: str,
    *,
    config: OrchestrationConfig,
    cli_doc: Path | None = None,
    kb_doc_ids: list[str] | None = None,
    cli_documents_hint: str | None = None,
    hooks: OrchestrationHooks | None = None,
    reuse_agent: Any | None = None,
    reuse_doc_path: Path | None = None,
    temperature: float = 0.35,
    trace: TraceCollector | None = None,
    on_event: Callable[[RuntimeEvent], None] | None = None,
    abort_check: Callable[[], bool] | None = None,
) -> SubmitResult:
    """执行一轮编排；stdout 捕获为 assistant 文本，并发出结构化事件。"""
    from agentic_rag.orchestration.loop import orchestrate_user_turn

    tr = trace or TraceCollector()
    events: list[RuntimeEvent] = []
    t0 = time.perf_counter()

    def emit(kind: str, message: str, **payload: Any) -> None:
        ev = RuntimeEvent(kind=kind, message=message, payload=dict(payload))
        events.append(ev)
        if on_event:
            on_event(ev)

    if abort_check and abort_check():
        return SubmitResult(
            assistant_text="",
            events=events,
            usage=TurnUsage(),
            stop_reason="aborted",
        )

    tr.mark("orchestration_start")
    emit("progress", "开始多层级编排（规划 → 执行 → 研判）")

    buf = io.StringIO()
    stop: StopReason = "complete"
    raw_state: dict[str, Any] | None = None
    try:
        with contextlib.redirect_stdout(buf):
            if abort_check and abort_check():
                stop = "aborted"
            else:
                agent, doc_out, last_state = orchestrate_user_turn(
                    user_text.strip(),
                    cli_doc=cli_doc,
                    kb_doc_ids=kb_doc_ids,
                    cli_documents_hint=cli_documents_hint,
                    hooks=hooks,
                    config=config,
                    reuse_agent=reuse_agent,
                    reuse_doc_path=reuse_doc_path,
                    temperature=temperature,
                )
                raw_state = {
                    "agent": agent,
                    "doc_resolved": doc_out,
                    "last_state": last_state,
                }
    except Exception as exc:
        stop = "error"
        emit("error", str(exc))
        tr.mark("orchestration_error", error=str(exc))
        latency = int((time.perf_counter() - t0) * 1000)
        return SubmitResult(
            assistant_text=buf.getvalue(),
            events=events,
            usage=TurnUsage(latency_ms=latency),
            stop_reason=stop,
            raw_state=raw_state,
            transcript=buf.getvalue(),
        )

    tr.mark("orchestration_end")
    transcript = buf.getvalue()
    if transcript.strip():
        emit("assistant", transcript.strip())
    emit("complete", "回合结束", stop_reason=stop)
    latency = int((time.perf_counter() - t0) * 1000)
    usage = TurnUsage(latency_ms=latency)
    return SubmitResult(
        assistant_text=transcript.strip(),
        events=events,
        usage=usage,
        stop_reason=stop,
        raw_state=raw_state,
        transcript=transcript,
    )

"""QueryEngine：会话级调度，供 REPL / Gradio / headless 复用。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_rag.orchestration.registry import OrchestrationHooks
from agentic_rag.orchestration.types import OrchestrationConfig
from agentic_rag.runtime.engine.query_loop import run_orchestration_turn
from agentic_rag.runtime.state.app_state import AppState, PermissionState, SessionState
from agentic_rag.runtime.state.store import AppStateStore
from agentic_rag.runtime.tracing import TraceCollector
from agentic_rag.runtime.types import RuntimeEvent, SubmitResult


@dataclass
class QueryEngineConfig:
    orchestration: OrchestrationConfig = field(default_factory=OrchestrationConfig)
    max_turns: int = 50
    temperature: float = 0.35
    cli_doc: Path | None = None
    kb_doc_ids: list[str] | None = None
    cli_documents_hint: str | None = None
    hooks: OrchestrationHooks | None = None


class QueryEngine:
    """一个引擎实例对应一个会话；多轮 ``submit_message``。"""

    def __init__(
        self,
        *,
        store: AppStateStore | None = None,
        config: QueryEngineConfig | None = None,
    ) -> None:
        self.store = store or AppStateStore()
        self.config = config or QueryEngineConfig()
        self._agent: Any | None = None
        self._doc_resolved: Path | None = None
        self._abort = False
        self._turn = 0
        self._trace = TraceCollector()

    def abort(self) -> None:
        self._abort = True

    def reset_abort(self) -> None:
        self._abort = False

    @property
    def agent(self) -> Any | None:
        return self._agent

    @property
    def doc_resolved(self) -> Path | None:
        return self._doc_resolved

    def submit_message(
        self,
        user_text: str,
        *,
        on_event: Any | None = None,
    ) -> SubmitResult:
        text = (user_text or "").strip()
        if not text:
            return SubmitResult(
                assistant_text="",
                events=[],
                usage=self._empty_usage(),
                stop_reason="complete",
            )

        st = self.store.get_state()
        if self._turn >= self.config.max_turns:
            return SubmitResult(
                assistant_text="",
                events=[
                    RuntimeEvent(
                        kind="error",
                        message=f"已达最大回合数 {self.config.max_turns}",
                    )
                ],
                usage=self._empty_usage(),
                stop_reason="max_rounds",
            )

        self._turn += 1
        self._trace.mark("submit_message", turn=self._turn)

        def abort_check() -> bool:
            return self._abort

        result = run_orchestration_turn(
            text,
            config=self.config.orchestration,
            cli_doc=self.config.cli_doc,
            kb_doc_ids=self.config.kb_doc_ids,
            cli_documents_hint=self.config.cli_documents_hint,
            hooks=self.config.hooks,
            reuse_agent=self._agent,
            reuse_doc_path=self._doc_resolved,
            temperature=self.config.temperature,
            trace=self._trace,
            on_event=on_event,
            abort_check=abort_check,
        )

        if result.raw_state:
            self._agent = result.raw_state.get("agent")
            doc = result.raw_state.get("doc_resolved")
            if doc is not None:
                self._doc_resolved = doc

        self._persist_turn(text, result)
        self._abort = False
        return result

    def _persist_turn(self, user_text: str, result: SubmitResult) -> None:
        old = self.store.get_state()
        messages = list(old.messages_log)
        messages.append({"role": "user", "content": user_text})
        if result.assistant_text:
            messages.append({"role": "assistant", "content": result.assistant_text})

        stats = old.stats
        stats.turn_count += 1
        stats.total_latency_ms += result.usage.latency_ms

        tier = "c4" if self.config.orchestration.enable_c4_tools else "c3"
        perms = PermissionState(
            enable_c4_tools=self.config.orchestration.enable_c4_tools,
            enable_sandbox=self.config.orchestration.enable_sandbox_tools,
        )
        new = AppState(
            mode=old.mode,
            tier=tier,
            session=SessionState(
                session_id=old.session.session_id,
                cwd=old.session.cwd,
                project_root=old.session.project_root,
                cli_doc=self.config.cli_doc,
            ),
            permissions=perms,
            messages_log=messages,
            tool_trace=list(old.tool_trace),
            stats=stats,
            ui_hint=old.ui_hint,
            last_error=result.stop_reason if result.stop_reason == "error" else "",
        )
        self.store.set_state(new, reason="turn_complete")

    @staticmethod
    def _empty_usage():
        from agentic_rag.runtime.types import TurnUsage

        return TurnUsage()

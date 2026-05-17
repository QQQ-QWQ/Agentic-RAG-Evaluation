"""REPL 交互壳：采集输入、展示事件、转发 QueryEngine（不含检索策略）。"""

from __future__ import annotations

import sys
from pathlib import Path

from agentic_rag.orchestration.types import OrchestrationConfig
from agentic_rag.runtime.engine.query_engine import QueryEngine, QueryEngineConfig
from agentic_rag.runtime.entrypoints.main import RuntimeLaunchOptions
from agentic_rag.runtime.setup import SetupResult
from agentic_rag.runtime.state.app_state import AppState, SessionState
from agentic_rag.runtime.state.store import AppStateStore
from agentic_rag.runtime.types import RuntimeEvent


def _require_agent_group() -> None:
    try:
        import deepagents  # noqa: F401
        import langchain_openai  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "未安装 Agent 依赖组。请在项目根执行：\n"
            "  uv sync --group agent\n"
            f"原始错误：{e}"
        ) from e


def _read_multiline(prompt: str, *, end_sentinel: str = "END") -> str:
    print(prompt)
    lines: list[str] = []
    end_lower = end_sentinel.strip().lower()
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().lower() == end_lower:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _print_event(ev: RuntimeEvent) -> None:
    if ev.kind in ("assistant", "complete"):
        return
    if ev.kind == "error":
        print(f"\n[错误] {ev.message}\n", file=sys.stderr)
    elif ev.kind == "progress":
        print(f"\n[{ev.kind}] {ev.message}")


def launch_repl(opts: RuntimeLaunchOptions, *, setup: SetupResult) -> None:
    _require_agent_group()

    tier_label = "C4 Tool-Augmented" if opts.tier == "c4" else "C3 Agentic Retrieval"
    orch = OrchestrationConfig(
        enable_c4_tools=opts.tier == "c4",
        enable_sandbox_tools=opts.tier == "c4" and opts.enable_sandbox,
    )

    store = AppStateStore(
        AppState(
            mode="repl",
            tier=opts.tier,  # type: ignore[arg-type]
            session=SessionState(
                session_id=setup.session_id,
                cwd=str(setup.cwd),
                project_root=str(setup.project_root),
                cli_doc=opts.doc_path,
            ),
        )
    )
    engine = QueryEngine(
        store=store,
        config=QueryEngineConfig(
            orchestration=orch,
            cli_doc=opts.doc_path,
        ),
    )

    print(
        "\n"
        "============================================================\n"
        f"  Agent Runtime REPL · {tier_label}\n"
        "  输入问题；多行以单独一行 END 结束。\n"
        "  斜杠命令：/quit /retry /hint\n"
        "============================================================\n"
    )
    if opts.doc_path:
        print(f"  绑定文档：{opts.doc_path}\n")

    last_user: str = ""

    while True:
        try:
            raw = _read_multiline("> 请输入（END 提交）：\n")
        except KeyboardInterrupt:
            print("\n已中断。")
            break

        if not raw:
            continue
        if raw.startswith("/"):
            cmd = raw.split()[0].lower()
            if cmd in ("/quit", "/exit"):
                break
            if cmd == "/hint":
                print(store.get_state().ui_hint or "（无提示）")
                continue
            if cmd == "/retry":
                if not last_user:
                    print("无上一条可重试。")
                    continue
                raw = last_user
            else:
                print(f"未知命令：{cmd}")
                continue

        last_user = raw

        def on_event(ev: RuntimeEvent) -> None:
            _print_event(ev)

        result = engine.submit_message(raw, on_event=on_event)
        if result.assistant_text:
            print("\n--- 答复 ---\n")
            print(result.assistant_text)
        elif result.stop_reason == "error":
            print("本回合未产生有效输出。", file=sys.stderr)

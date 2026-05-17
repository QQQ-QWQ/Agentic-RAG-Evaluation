"""
C3/C4 统一客户端：先选档位（C3 仅检索编排 / C4 工具增强），再进入多层级编排交互。

- C3：``enable_c4_tools=False``，第二层仅 ``topic4_rag_query`` 等检索工具。
- C4：``enable_c4_tools=True``，另可入库、MarkItDown、可选沙箱。

依赖：``uv sync --group agent``；Gradio 见 ``main.py client``，终端见 ``--console``。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.documents.ingest_inspector import (
    format_ingest_report_markdown,
    inspect_document_paths,
)
from agentic_rag.documents.multi_doc import (
    SessionDocumentScope,
    build_session_document_scope,
)
from agentic_rag.telemetry.audit_log import (
    audit_log,
    audit_log_path_hint,
    new_audit_session_id,
    set_audit_session_id,
)
from agentic_rag.telemetry.client_hooks import build_client_audit_hooks, log_turn_result
from agentic_rag.orchestration.types import OrchestrationConfig


def _require_agent_group() -> None:
    try:
        import deepagents  # noqa: F401
        import langchain_openai  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "未安装 Agent 依赖组。请在项目根执行：\n"
            "  uv sync --group agent\n"
            f"原始错误：{e}"
        ) from None


def orchestration_config_for_mode(
    *,
    enable_c4: bool,
    enable_sandbox: bool = True,
) -> OrchestrationConfig:
    """按 C3/C4 档位构造编排配置。"""
    return OrchestrationConfig(
        enable_c4_tools=enable_c4,
        enable_sandbox_tools=enable_c4 and enable_sandbox,
    )


def _normalize_chat_history(history: list | None) -> list[dict[str, str]]:
    """兼容旧版 (user, bot) 元组与 Gradio 6 messages 格式（role/content）。"""
    if not history:
        return []
    out: list[dict[str, str]] = []
    for item in history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            role = str(item["role"])
            if role not in ("user", "assistant", "system"):
                role = "assistant"
            out.append({"role": role, "content": str(item.get("content") or "")})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append({"role": "user", "content": str(item[0] or "")})
            out.append({"role": "assistant", "content": str(item[1] or "")})
    return out


def _chat_history_append(
    history: list | None,
    user_text: str,
    assistant_text: str,
) -> list:
    """Gradio 6 Chatbot 使用 messages 格式（role/content）。"""
    out = _normalize_chat_history(history)
    out.append({"role": "user", "content": user_text})
    out.append({"role": "assistant", "content": assistant_text})
    return out


def prepare_document_scope_from_input(
    *,
    paths_text: str | None = None,
    extra_doc_paths: list[str] | None = None,
    ingest_to_chroma: bool = True,
    audit_session_id: str | None = None,
) -> SessionDocumentScope:
    """
    解析 CLI/Gradio 中的多路径或自然语言描述，批量入库 Chroma 并返回会话范围。
    """
    parts: list[str] = []
    if paths_text and str(paths_text).strip():
        parts.append(str(paths_text).strip())
    if extra_doc_paths:
        parts.extend(p for p in extra_doc_paths if str(p).strip())
    merged = "\n".join(parts)

    inspect = inspect_document_paths(
        paths_text=merged or None,
        explicit_paths=extra_doc_paths,
    )
    audit_log(
        "ingest_inspect",
        session_id=audit_session_id,
        payload=inspect.to_audit_payload(),
    )

    if not merged.strip():
        scope = SessionDocumentScope()
        scope.inspect_markdown = format_ingest_report_markdown(inspect)
        return scope

    scope = build_session_document_scope(
        paths_text=merged,
        ingest_to_chroma=ingest_to_chroma,
    )
    scope.inspect_markdown = format_ingest_report_markdown(inspect)
    if inspect.warnings:
        scope.ingest_report.setdefault("warnings", []).extend(inspect.warnings)

    audit_log(
        "ingest_complete",
        session_id=audit_session_id,
        payload={
            "doc_ids": scope.doc_ids,
            "paths": [str(p) for p in scope.source_paths],
            "ingest_ok": scope.ingest_report.get("ok"),
        },
    )
    return scope


@dataclass
class C34UiSession:
    """Gradio 会话状态。"""

    started: bool = False
    enable_c4: bool = False
    audit_session_id: str = ""
    cli_doc: Path | None = None
    doc_scope: SessionDocumentScope | None = None
    config: OrchestrationConfig = field(
        default_factory=lambda: orchestration_config_for_mode(enable_c4=False)
    )
    agent: Any | None = None
    doc_resolved: Path | None = None
    engine: Any | None = None


def _engine_for_turn(
    *,
    config: OrchestrationConfig,
    cli_doc: Path | None,
    kb_doc_ids: list[str] | None,
    cli_documents_hint: str | None,
    agent: Any | None,
    doc_resolved: Path | None,
    temperature: float,
    engine: Any | None,
    hooks: Any | None = None,
) -> Any:
    from agentic_rag.runtime.engine.query_engine import QueryEngine, QueryEngineConfig

    if engine is not None:
        qe = engine
        qe.config.orchestration = config
        qe.config.cli_doc = cli_doc
        qe.config.kb_doc_ids = kb_doc_ids
        qe.config.cli_documents_hint = cli_documents_hint
        qe.config.hooks = hooks
        qe.config.temperature = temperature
        if agent is not None:
            qe._agent = agent
        if doc_resolved is not None:
            qe._doc_resolved = doc_resolved
        return qe

    return QueryEngine(
        config=QueryEngineConfig(
            orchestration=config,
            cli_doc=cli_doc,
            kb_doc_ids=kb_doc_ids,
            cli_documents_hint=cli_documents_hint,
            hooks=hooks,
            temperature=temperature,
        ),
    )


def run_c34_turn(
    user_text: str,
    *,
    config: OrchestrationConfig,
    cli_doc: Path | None = None,
    kb_doc_ids: list[str] | None = None,
    cli_documents_hint: str | None = None,
    agent: Any | None = None,
    doc_resolved: Path | None = None,
    temperature: float = 0.35,
    engine: Any | None = None,
    audit_session_id: str | None = None,
    enable_c4: bool = False,
) -> tuple[Any | None, Path | None, str, Any]:
    """
    执行一轮完整编排（规划→执行→研判），捕获终端输出为字符串。

    返回 ``(agent, doc_resolved, transcript, engine)`` 供 UI 多轮复用。
    内部统一走 ``QueryEngine``（与 REPL / headless 共用）。
    """
    hooks = build_client_audit_hooks(tier="c4" if enable_c4 else "c3")
    qe = _engine_for_turn(
        config=config,
        cli_doc=cli_doc,
        kb_doc_ids=kb_doc_ids,
        cli_documents_hint=cli_documents_hint,
        agent=agent,
        doc_resolved=doc_resolved,
        temperature=temperature,
        engine=engine,
        hooks=hooks,
    )
    audit_log(
        "client_turn_start",
        session_id=audit_session_id,
        payload={"user_preview": user_text.strip()[:500]},
    )
    result = qe.submit_message(user_text.strip())
    transcript = result.transcript or result.assistant_text
    log_turn_result(
        user_text=user_text.strip(),
        stop_reason=result.stop_reason,
        latency_ms=result.usage.latency_ms,
        transcript_len=len(transcript),
        kb_doc_ids=kb_doc_ids,
    )
    return qe.agent, qe.doc_resolved, transcript, qe


def _prompt_c34_mode_console() -> tuple[bool, bool]:
    print(
        "\n"
        "============================================================\n"
        "  C3 / C4 统一客户端（多层级编排）\n"
        "============================================================\n"
        "  [1] C3 — Agentic Retrieval（仅知识库检索工具，无外部工具）\n"
        "  [2] C4 — Tool-Augmented（入库 / MarkItDown / 可选沙箱 + 检索）\n"
    )
    while True:
        try:
            choice = input("请选择档位 (1/2，默认 1): ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            raise SystemExit(0) from None
        if choice in ("1", "c3", "C3"):
            enable_c4 = False
            break
        if choice in ("2", "c4", "C4"):
            enable_c4 = True
            break
        print("无效选项，请输入 1 或 2。")

    enable_sandbox = False
    if enable_c4:
        try:
            ans = input("C4：是否启用 Python 沙箱 sandbox_exec_python？(y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        enable_sandbox = ans in ("y", "yes", "1")
        if enable_sandbox and not config.SANDBOX_ENABLED:
            print(
                "[提示] .env 中 SANDBOX_ENABLED 未为 true，沙箱工具可能不会注册。\n"
            )
    return enable_c4, enable_sandbox


def run_c34_console_client(
    *,
    doc_path: str | None = None,
    extra_doc_paths: list[str] | None = None,
    enable_c4: bool | None = None,
    enable_sandbox: bool | None = None,
) -> None:
    """终端：选档位后进入与 ``main.py agent`` 相同的多行交互。"""
    _require_agent_group()
    from agentic_rag.orchestration.loop import run_cli_agent_session

    if enable_c4 is None:
        enable_c4, enable_sbx = _prompt_c34_mode_console()
    else:
        enable_sbx = bool(enable_sandbox) if enable_sandbox is not None else enable_c4

    cfg = orchestration_config_for_mode(enable_c4=enable_c4, enable_sandbox=enable_sbx)
    sid = new_audit_session_id()
    set_audit_session_id(sid)
    scope = prepare_document_scope_from_input(
        paths_text=doc_path,
        extra_doc_paths=extra_doc_paths,
        audit_session_id=sid,
    )
    audit_log("session_start_console", session_id=sid, payload={"enable_c4": enable_c4})
    if scope.ingest_report.get("errors") and not scope.doc_ids:
        raise SystemExit(
            "文档入库失败：\n" + "\n".join(scope.ingest_report.get("errors", []))
        )
    if scope.ingest_report.get("warnings"):
        for w in scope.ingest_report["warnings"]:
            print(f"[警告] {w}")

    mode_label = "C4 Tool-Augmented" if enable_c4 else "C3 Agentic Retrieval"
    print(f"\n[客户端] 已选档位：{mode_label}\n")
    if scope.inspect_markdown:
        print(scope.inspect_markdown + "\n")
    print(scope.summary_for_ui() + "\n")
    print(f"[审计日志] {audit_log_path_hint()}\n")

    run_cli_agent_session(
        cli_doc=None,
        kb_doc_ids=scope.doc_ids or None,
        cli_documents_hint=scope.summary_for_ui() if scope.doc_ids else None,
        skip_layer1=False,
        once_text=None,
        temperature=0.35,
        json_debug=False,
        config=cfg,
        hooks=build_client_audit_hooks(tier="c4" if enable_c4 else "c3"),
        multiline_interactive=True,
    )


def launch_c34_gradio_client(*, host: str = "127.0.0.1") -> None:
    """浏览器客户端：选档位 → 开始会话 → 聊天。"""
    _require_agent_group()
    import gradio as gr

    def _start_session(
        mode: str,
        doc_path: str,
        use_sandbox: bool,
    ) -> tuple[C34UiSession, str, list]:
        enable_c4 = mode.strip().lower().startswith("c4")
        cfg = orchestration_config_for_mode(
            enable_c4=enable_c4,
            enable_sandbox=use_sandbox,
        )
        sid = new_audit_session_id()
        set_audit_session_id(sid)
        doc_scope: SessionDocumentScope | None = None
        if doc_path and str(doc_path).strip():
            doc_scope = prepare_document_scope_from_input(
                paths_text=doc_path,
                audit_session_id=sid,
            )
            if doc_scope.ingest_report.get("errors") and not doc_scope.doc_ids:
                errs = doc_scope.ingest_report.get("errors", [])
                return C34UiSession(), f"**无法开始会话**：\n" + "\n".join(errs), []

        label = "C4 工具增强" if enable_c4 else "C3 仅检索编排"
        scope_msg = (
            doc_scope.summary_for_ui()
            if doc_scope and doc_scope.doc_ids
            else "默认 Chroma 全库（data/processed/documents.csv）"
        )
        sb = "已请求沙箱" if (enable_c4 and use_sandbox) else "未启用沙箱"
        inspect_block = ""
        if doc_scope and doc_scope.inspect_markdown:
            inspect_block = doc_scope.inspect_markdown + "\n\n"
        msg = (
            f"**会话已开始 · {label}**（审计 id: `{sid}`）\n\n"
            f"{inspect_block}"
            f"- {scope_msg}\n"
            f"- {sb}\n"
            f"- 全局审计日志（不参与模型）：`{audit_log_path_hint()}`\n\n"
            "请在下方输入问题；多轮对话会复用同一 Agent 状态。"
        )
        audit_log(
            "session_start_gradio",
            session_id=sid,
            payload={"enable_c4": enable_c4, "doc_ids": doc_scope.doc_ids if doc_scope else []},
        )

        return (
            C34UiSession(
                started=True,
                enable_c4=enable_c4,
                audit_session_id=sid,
                doc_scope=doc_scope,
                config=cfg,
            ),
            msg,
            [],
        )

    def _chat(
        message: str,
        history: list,
        session: C34UiSession,
    ) -> tuple[list, C34UiSession, str]:
        history = _normalize_chat_history(history)
        if not session.started:
            return _chat_history_append(
                history,
                message or "",
                "请先在上方选择 C3/C4 并点击「开始会话」。",
            ), session, ""

        text = (message or "").strip()
        if not text:
            return history or [], session, ""

        if not config.DEEPSEEK_API_KEY or not config.ARK_API_KEY:
            return _chat_history_append(
                history,
                text,
                "请先在项目根 `.env` 配置 DEEPSEEK_API_KEY 与 ARK_API_KEY。",
            ), session, ""

        try:
            kb_ids = session.doc_scope.doc_ids if session.doc_scope else None
            hint = (
                session.doc_scope.summary_for_ui()
                if session.doc_scope and session.doc_scope.doc_ids
                else None
            )
            agent, doc_resolved, transcript, qe = run_c34_turn(
                text,
                config=session.config,
                cli_doc=session.cli_doc,
                kb_doc_ids=kb_ids,
                cli_documents_hint=hint,
                agent=session.agent,
                doc_resolved=session.doc_resolved,
                engine=session.engine,
                audit_session_id=session.audit_session_id,
                enable_c4=session.enable_c4,
            )
            session.agent = agent
            session.doc_resolved = doc_resolved
            session.engine = qe
            reply = transcript.strip() or "（无输出）"
        except Exception as exc:
            reply = f"执行出错：{exc}"

        return _chat_history_append(history, text, reply), session, ""

    with gr.Blocks(title="Topic4 C3/C4 客户端") as demo:
        gr.Markdown(
            "# Topic4 C3 / C4 统一客户端\n\n"
            "先选择实验档位并开始会话，再输入自然语言问题。"
            "系统将按 **第一层规划 → 第二层工具执行 → 第三层研判** 流程处理。\n\n"
            "需 `uv sync --group agent` 与 `.env` 中的 `DEEPSEEK_API_KEY`、`ARK_API_KEY`。"
        )
        with gr.Row():
            mode_radio = gr.Radio(
                ["C3 — 仅检索编排", "C4 — 工具增强"],
                value="C3 — 仅检索编排",
                label="实验档位",
            )
            sandbox_cb = gr.Checkbox(
                label="C4 时启用 Python 沙箱",
                value=False,
            )
        doc_in = gr.Textbox(
            label="可选：多文档路径（Chroma 持久化入库）",
            placeholder=(
                "每行一个路径，或用自然语言，例如：\n"
                "data/raw/tech_docs/dify_readme.md\n"
                "data/raw/tech_docs/langchain_intro.md\n"
                "或：请分析 dify_readme.md 和 langchain_intro.md，路径在 data/raw/tech_docs/"
            ),
            lines=5,
        )
        start_btn = gr.Button("开始会话", variant="primary")
        session_state = gr.State(C34UiSession())
        start_msg = gr.Markdown("")
        chat = gr.Chatbot(label="对话", height=420)
        msg_in = gr.Textbox(
            label="输入问题",
            lines=4,
            placeholder="输入后点击发送或按 Enter",
        )
        send_btn = gr.Button("发送", variant="secondary")

        start_btn.click(
            _start_session,
            inputs=[mode_radio, doc_in, sandbox_cb],
            outputs=[session_state, start_msg, chat],
        )
        send_btn.click(
            _chat,
            inputs=[msg_in, chat, session_state],
            outputs=[chat, session_state, msg_in],
        ).then(lambda: "", outputs=msg_in)
        msg_in.submit(
            _chat,
            inputs=[msg_in, chat, session_state],
            outputs=[chat, session_state, msg_in],
        ).then(lambda: "", outputs=msg_in)

    demo.launch(server_name=host)


def cmd_c34_client(args: argparse.Namespace) -> None:
    enable_c4: bool | None = None
    if getattr(args, "c4", False):
        enable_c4 = True
    elif getattr(args, "c3", False):
        enable_c4 = False

    if getattr(args, "console", False):
        run_c34_console_client(
            doc_path=getattr(args, "docs_text", None),
            extra_doc_paths=getattr(args, "doc_paths", None) or [],
            enable_c4=enable_c4,
            enable_sandbox=bool(getattr(args, "sandbox", False)),
        )
    else:
        launch_c34_gradio_client(host=getattr(args, "host", "127.0.0.1"))


def build_c34_client_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        add_help=add_help,
        description="C3/C4 统一客户端：选档位后多层级编排（默认 Gradio 网页）",
    )
    p.add_argument(
        "--console",
        action="store_true",
        help="使用终端交互（多行输入，单独一行 END 结束）",
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Gradio 监听地址（默认 127.0.0.1）",
    )
    p.add_argument(
        "doc_paths",
        nargs="*",
        default=None,
        metavar="PATH",
        help="可选：一个或多个文档路径（将入库 Chroma 并限定本会话检索范围）",
    )
    p.add_argument(
        "--docs-text",
        default=None,
        metavar="TEXT",
        help="可选：自然语言或多行路径文本（与 doc_paths 可并用）",
    )
    p.add_argument(
        "--c4",
        action="store_true",
        help="终端模式下直接选 C4（跳过档位菜单）",
    )
    p.add_argument(
        "--c3",
        action="store_true",
        help="终端模式下直接选 C3",
    )
    p.add_argument(
        "--sandbox",
        action="store_true",
        help="与 --c4 联用：启用沙箱工具",
    )
    return p

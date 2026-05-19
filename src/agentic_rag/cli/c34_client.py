"""
C3/C4 统一客户端：先选档位（C3 仅检索编排 / C4 工具增强），再进入多层级编排交互。

- C3：``enable_c4_tools=False``，第二层仅 ``topic4_rag_query`` 等检索工具。
- C4：``enable_c4_tools=True``，另可入库、MarkItDown、可选沙箱。

依赖：``uv sync --group agent``；Gradio 见 ``main.py client``，终端见 ``--console``。
"""

from __future__ import annotations

import argparse
import json
import queue
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_rag import config
from agentic_rag.documents.ingest_inspector import (
    format_ingest_report_markdown,
    inspect_document_paths,
)
from agentic_rag.documents.multi_doc import (
    RETRIEVAL_EPHEMERAL_ONLY,
    RETRIEVAL_FULL_KB,
    RETRIEVAL_FULL_KB_AND_EPHEMERAL,
    RETRIEVAL_MODE_LABELS,
    SessionDocumentScope,
    build_session_document_scope,
    normalize_retrieval_mode,
)
from agentic_rag.telemetry.audit_log import (
    audit_log,
    audit_log_path_hint,
    get_audit_session_id,
    new_audit_session_id,
    set_audit_session_id,
)
from agentic_rag.telemetry.chat_transcript import (
    load_chat_turns,
    session_chat_log_path,
    turns_to_gradio_messages,
)
from agentic_rag.telemetry.session_trace import session_trace_path
from agentic_rag.telemetry.client_hooks import build_client_audit_hooks, log_turn_result
from agentic_rag.telemetry.streaming_hooks import (
    format_runtime_event_line,
    hooks_with_runtime_events,
    merge_orchestration_hooks,
)
from agentic_rag.orchestration.types import OrchestrationConfig
from agentic_rag.runtime.types import RuntimeEvent, SubmitResult


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


def apply_session_scope_to_runtime(scope: SessionDocumentScope) -> None:
    """将会话范围注册到 RAG 上下文（临时索引或全库/子集）。"""
    from agentic_rag.experiment.session_rag import (
        set_combine_ephemeral_with_kb,
        set_ephemeral_session_index,
    )

    if scope.use_ephemeral and scope.ephemeral_index is not None:
        set_ephemeral_session_index(scope.ephemeral_index)
    else:
        set_ephemeral_session_index(None)
    set_combine_ephemeral_with_kb(scope.combine_ephemeral_with_full_kb)


def prepare_document_scope_from_input(
    *,
    paths_text: str | None = None,
    extra_doc_paths: list[str] | None = None,
    ingest_to_chroma: bool = False,
    retrieval_mode: str | None = None,
    audit_session_id: str | None = None,
) -> SessionDocumentScope:
    """
    解析 CLI/Gradio 多路径：默认 **会话临时索引**（不写全库）；``ingest_to_chroma=True`` 为旧版全库入库。
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
        retrieval_mode=retrieval_mode,
        session_id=audit_session_id,
    )
    scope.inspect_markdown = format_ingest_report_markdown(inspect)
    if inspect.warnings:
        scope.ingest_report.setdefault("warnings", []).extend(inspect.warnings)

    apply_session_scope_to_runtime(scope)
    audit_log(
        "session_scope_ready",
        session_id=audit_session_id,
        payload={
            "mode": scope.retrieval_mode
            if scope.use_ephemeral
            else ("kb_subset" if scope.doc_ids else "full_kb"),
            "retrieval_mode": scope.retrieval_mode,
            "doc_ids": scope.doc_ids,
            "paths": [str(p) for p in scope.source_paths],
            "ephemeral": scope.ephemeral_meta if scope.use_ephemeral else None,
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
    retrieval_mode: str = RETRIEVAL_FULL_KB
    cli_doc: Path | None = None
    doc_scope: SessionDocumentScope | None = None
    config: OrchestrationConfig = field(
        default_factory=lambda: orchestration_config_for_mode(enable_c4=False)
    )
    agent: Any | None = None
    doc_resolved: Path | None = None
    engine: Any | None = None


def build_resumed_ui_session(
    session_id: str,
    *,
    enable_c4: bool = True,
    enable_sandbox: bool = False,
    retrieval_mode: str = RETRIEVAL_FULL_KB,
) -> tuple[C34UiSession, str, list[dict[str, str]]]:
    """
    从 ``chat.jsonl`` 恢复 Gradio 对话历史；复用同一审计 session_id 追加日志。

    不恢复 LangGraph Agent 内部状态，新消息将使用新 Agent 实例。
    """
    sid = (session_id or "").strip()
    if not sid:
        raise ValueError("session_id 不能为空")
    turns = load_chat_turns(sid)
    if not turns:
        raise FileNotFoundError(
            f"未找到会话 `{sid}` 的对话记录：{session_chat_log_path(sid)}"
        )
    set_audit_session_id(sid)
    cfg = orchestration_config_for_mode(
        enable_c4=enable_c4,
        enable_sandbox=enable_sandbox,
    )
    tier = "c4" if enable_c4 else "c3"
    last_tier = str(turns[-1].get("tier") or tier)
    if last_tier in ("c3", "c4"):
        cfg = orchestration_config_for_mode(
            enable_c4=(last_tier == "c4"),
            enable_sandbox=enable_sandbox and last_tier == "c4",
        )
    session = C34UiSession(
        started=True,
        enable_c4=cfg.enable_c4_tools,
        audit_session_id=sid,
        retrieval_mode=retrieval_mode,
        config=cfg,
    )
    history = turns_to_gradio_messages(turns)
    msg = (
        f"**已从日志恢复会话**（审计 id: `{sid}`，共 {len(turns)} 轮）\n\n"
        "- 上方聊天框为历史记录，可直接继续提问。\n"
        "- **Agent 内部状态未恢复**（新消息使用新 Agent；模型可能不记得上轮工具细节）。\n"
        "- 新轮次仍写入同目录 `chat.jsonl` / `trace.jsonl`。\n"
    )
    audit_log("session_resume_gradio", session_id=sid, payload={"turn_count": len(turns)})
    return session, msg, history


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


def _build_turn_hooks(
    *,
    tier: str,
    session_id: str,
    on_event: Any | None = None,
) -> Any:
    audit = build_client_audit_hooks(tier=tier, session_id=session_id)
    if on_event is None:
        return audit
    return hooks_with_runtime_events(
        merge_orchestration_hooks(audit),
        on_event,
        tier=tier,
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
    on_event: Any | None = None,
) -> tuple[Any | None, Path | None, str, Any]:
    """
    执行一轮完整编排（规划→执行→研判），捕获终端输出为字符串。

    返回 ``(agent, doc_resolved, transcript, engine)`` 供 UI 多轮复用。
    内部统一走 ``QueryEngine``（与 REPL / headless / 批量评测共用）。
    """
    tier = "c4" if enable_c4 else "c3"
    sid = (audit_session_id or get_audit_session_id()).strip() or new_audit_session_id()
    set_audit_session_id(sid)
    hooks = _build_turn_hooks(tier=tier, session_id=sid, on_event=on_event)
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
        session_id=sid,
        payload={"user_preview": user_text.strip()[:500], "tier": tier},
    )
    result = qe.submit_message(user_text.strip(), on_event=on_event)
    transcript = result.transcript or result.assistant_text
    log_turn_result(
        user_text=user_text.strip(),
        stop_reason=result.stop_reason,
        latency_ms=result.usage.latency_ms,
        transcript_len=len(transcript),
        assistant_text=transcript,
        kb_doc_ids=kb_doc_ids,
        tier=tier,
        session_id=sid,
    )
    return qe.agent, qe.doc_resolved, transcript, qe


def _compose_streaming_reply(progress_lines: list[str], final_text: str) -> str:
    body = "\n".join(progress_lines).strip()
    final = (final_text or "").strip() or "（无输出）"
    if not body:
        return final
    return f"{body}\n\n---\n\n{final}"


def iter_c34_turn_stream(
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
) -> Iterator[tuple[Any | None, Path | None, str, Any]]:
    """
    Gradio 流式：后台线程跑编排，按 L1/L2/L3 事件增量刷新 assistant 气泡。
    """
    tier = "c4" if enable_c4 else "c3"
    sid = (audit_session_id or get_audit_session_id()).strip() or new_audit_session_id()
    set_audit_session_id(sid)
    event_q: queue.Queue[tuple[str, Any]] = queue.Queue()
    result_box: dict[str, Any] = {}

    def on_event(ev: RuntimeEvent) -> None:
        event_q.put(("event", ev))

    def worker() -> None:
        try:
            result_box["ok"] = run_c34_turn(
                user_text,
                config=config,
                cli_doc=cli_doc,
                kb_doc_ids=kb_doc_ids,
                cli_documents_hint=cli_documents_hint,
                agent=agent,
                doc_resolved=doc_resolved,
                temperature=temperature,
                engine=engine,
                audit_session_id=sid,
                enable_c4=enable_c4,
                on_event=on_event,
            )
        except Exception as exc:
            result_box["err"] = exc
        finally:
            event_q.put(("done", None))

    threading.Thread(target=worker, daemon=True).start()
    progress: list[str] = [f"⏳ [{tier.upper()}] 编排进行中…"]
    yield agent, doc_resolved, _compose_streaming_reply(progress, ""), engine

    while True:
        try:
            kind, item = event_q.get(timeout=0.35)
        except queue.Empty:
            yield agent, doc_resolved, _compose_streaming_reply(progress, ""), engine
            continue
        if kind == "done":
            break
        if kind == "event" and isinstance(item, RuntimeEvent):
            line = format_runtime_event_line(item)
            if not progress or progress[-1] != line:
                progress.append(line)
            yield agent, doc_resolved, _compose_streaming_reply(progress, ""), engine

    if "err" in result_box:
        err = result_box["err"]
        assert isinstance(err, Exception)
        progress.append(f"❌ {type(err).__name__}: {err}")
        yield agent, doc_resolved, _compose_streaming_reply(progress, ""), engine
        raise err

    pack = result_box.get("ok")
    if not pack:
        yield agent, doc_resolved, _compose_streaming_reply(progress, "（无结果）"), engine
        return
    out_agent, out_doc, transcript, out_engine = pack
    yield out_agent, out_doc, _compose_streaming_reply(progress, transcript), out_engine


def _prompt_retrieval_scope_console(*, has_attachments: bool) -> str:
    if not has_attachments:
        return RETRIEVAL_FULL_KB
    print(
        "\n"
        "------------------------------------------------------------\n"
        "  检索范围（有附加文件时）\n"
        "------------------------------------------------------------\n"
        f"  [1] {RETRIEVAL_MODE_LABELS[RETRIEVAL_FULL_KB_AND_EPHEMERAL]}（默认）\n"
        f"  [2] {RETRIEVAL_MODE_LABELS[RETRIEVAL_EPHEMERAL_ONLY]}\n"
        f"  [3] {RETRIEVAL_MODE_LABELS[RETRIEVAL_FULL_KB]}（忽略附加，仅全库）\n"
    )
    mapping = {
        "1": RETRIEVAL_FULL_KB_AND_EPHEMERAL,
        "": RETRIEVAL_FULL_KB_AND_EPHEMERAL,
        "2": RETRIEVAL_EPHEMERAL_ONLY,
        "3": RETRIEVAL_FULL_KB,
        "combined": RETRIEVAL_FULL_KB_AND_EPHEMERAL,
        "ephemeral": RETRIEVAL_EPHEMERAL_ONLY,
        "full": RETRIEVAL_FULL_KB,
    }
    while True:
        try:
            choice = input("请选择检索范围 (1/2/3，默认 1): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            raise SystemExit(0) from None
        if choice in mapping:
            return mapping[choice]
        print("无效选项，请输入 1、2 或 3。")


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
    retrieval_mode: str | None = None,
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
    has_paths = bool(
        (doc_path and str(doc_path).strip())
        or (extra_doc_paths and any(str(p).strip() for p in extra_doc_paths))
    )
    if retrieval_mode is None and has_paths:
        retrieval_mode = _prompt_retrieval_scope_console(has_attachments=True)
    elif retrieval_mode is None:
        retrieval_mode = RETRIEVAL_FULL_KB
    else:
        retrieval_mode = normalize_retrieval_mode(
            retrieval_mode,
            has_attachments=has_paths,
        )
    scope = prepare_document_scope_from_input(
        paths_text=doc_path,
        extra_doc_paths=extra_doc_paths,
        retrieval_mode=retrieval_mode,
        audit_session_id=sid,
    )
    audit_log("session_start_console", session_id=sid, payload={"enable_c4": enable_c4})
    if scope.ingest_report.get("errors") and not scope.doc_ids and not scope.use_ephemeral:
        raise SystemExit(
            "文档绑定失败：\n" + "\n".join(scope.ingest_report.get("errors", []))
        )
    apply_session_scope_to_runtime(scope)
    if scope.ingest_report.get("warnings"):
        for w in scope.ingest_report["warnings"]:
            print(f"[警告] {w}")

    mode_label = "C4 Tool-Augmented" if enable_c4 else "C3 Agentic Retrieval"
    print(f"\n[客户端] 已选档位：{mode_label}\n")
    if scope.inspect_markdown:
        print(scope.inspect_markdown + "\n")
    print(scope.summary_for_ui() + "\n")
    print(f"[审计日志] {audit_log_path_hint()}")
    print(f"[对话全文] {session_chat_log_path(sid)}")
    print(f"[追踪 trace] {session_trace_path(sid)}\n")

    kb_ids: list[str] | None = None
    if scope.doc_ids:
        kb_ids = scope.doc_ids
    elif scope.use_ephemeral and not scope.combine_ephemeral_with_full_kb:
        kb_ids = None
    run_cli_agent_session(
        cli_doc=None,
        kb_doc_ids=kb_ids,
        cli_documents_hint=scope.summary_for_ui()
        if (scope.doc_ids or scope.use_ephemeral)
        else None,
        skip_layer1=False,
        once_text=None,
        temperature=0.35,
        json_debug=False,
        config=cfg,
        hooks=build_client_audit_hooks(tier="c4" if enable_c4 else "c3"),
        multiline_interactive=True,
    )


def launch_c34_gradio_client(
    *,
    host: str = "127.0.0.1",
    default_enable_c4: bool = False,
    default_enable_sandbox: bool = False,
    default_retrieval_mode: str | None = None,
    default_doc_paths_text: str = "",
    resume_session_id: str | None = None,
) -> None:
    """浏览器客户端：选档位 → 开始会话 → 聊天。"""
    _require_agent_group()
    import gradio as gr

    mode_default = "C4 — 工具增强" if default_enable_c4 else "C3 — 仅检索编排"
    retrieval_key = normalize_retrieval_mode(
        default_retrieval_mode,
        has_attachments=bool(str(default_doc_paths_text).strip()),
    )
    retrieval_default = RETRIEVAL_MODE_LABELS.get(
        retrieval_key,
        RETRIEVAL_MODE_LABELS[RETRIEVAL_FULL_KB_AND_EPHEMERAL],
    )

    initial_session = C34UiSession()
    initial_chat: list = []
    initial_start_msg = ""
    resume_err = ""
    if resume_session_id and str(resume_session_id).strip():
        try:
            initial_session, initial_start_msg, initial_chat = build_resumed_ui_session(
                str(resume_session_id).strip(),
                enable_c4=default_enable_c4,
                enable_sandbox=default_enable_sandbox,
                retrieval_mode=retrieval_key,
            )
        except (FileNotFoundError, ValueError) as exc:
            resume_err = f"**恢复会话失败**：{exc}"

    def _start_session(
        mode: str,
        retrieval_scope: str,
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
        scope_mode = normalize_retrieval_mode(
            retrieval_scope,
            has_attachments=bool(doc_path and str(doc_path).strip()),
        )
        if doc_path and str(doc_path).strip():
            doc_scope = prepare_document_scope_from_input(
                paths_text=doc_path,
                retrieval_mode=scope_mode,
                audit_session_id=sid,
            )
            if (
                doc_scope.ingest_report.get("errors")
                and not doc_scope.doc_ids
                and not doc_scope.use_ephemeral
            ):
                errs = doc_scope.ingest_report.get("errors", [])
                return C34UiSession(), "**无法开始会话**：\n" + "\n".join(errs), []

        label = "C4 工具增强" if enable_c4 else "C3 仅检索编排"
        if doc_scope and (doc_scope.doc_ids or doc_scope.use_ephemeral):
            scope_msg = doc_scope.summary_for_ui()
        else:
            scope_msg = (
                "默认 **系统知识库** Chroma 全库（由 `main.py kb sync` 维护 documents.csv）"
            )
        sb = "已请求沙箱" if (enable_c4 and use_sandbox) else "未启用沙箱"
        fc_hint = "（C4 网页/本地文件工具见档位说明）"
        if enable_c4:
            from agentic_rag.tools.firecrawl_tool import firecrawl_configured

            fc_hint = (
                "C4：已配置 Firecrawl（可从对话中识别 URL 并抓取）"
                if firecrawl_configured()
                else "C4：未配置 FIRECRAWL_API_KEY（无网页抓取；仍可用 topic4_file_read / topic4_file_ingest）"
            )
        else:
            fc_hint = "C3：仅知识库检索，无 Firecrawl / 读本地文件工具"
        inspect_block = ""
        if doc_scope and doc_scope.inspect_markdown:
            inspect_block = doc_scope.inspect_markdown + "\n\n"
        msg = (
            f"**会话已开始 · {label}**（审计 id: `{sid}`）\n\n"
            f"{inspect_block}"
            f"- {scope_msg}\n"
            f"- {sb}\n"
            f"- {fc_hint}\n"
            f"- 全局审计：`{audit_log_path_hint()}`\n"
            f"- **对话全文**：`{session_chat_log_path(sid)}`\n"
            f"- **编排/工具追踪**：`{session_trace_path(sid)}`"
            "（刷新网页 UI 会清空，磁盘日志保留）\n\n"
            "请在下方输入问题；多轮对话会复用同一 Agent 状态。"
        )
        audit_log(
            "session_start_gradio",
            session_id=sid,
            payload={
                "enable_c4": enable_c4,
                "doc_ids": doc_scope.doc_ids if doc_scope else [],
                "ephemeral": doc_scope.use_ephemeral if doc_scope else False,
                "retrieval_mode": doc_scope.retrieval_mode if doc_scope else scope_mode,
            },
        )

        return (
            C34UiSession(
                started=True,
                enable_c4=enable_c4,
                audit_session_id=sid,
                doc_scope=doc_scope,
                retrieval_mode=scope_mode,
                config=cfg,
            ),
            msg,
            [],
        )

    def _chat_stream(
        message: str,
        history: list,
        session: C34UiSession,
    ):
        """Gradio 生成器：C3/C4 均流式展示编排进度（与批量评测共用事件钩子）。"""
        history = _normalize_chat_history(history)
        if not session.started:
            yield (
                _chat_history_append(
                    history,
                    message or "",
                    "请先在上方选择 C3/C4 并点击「开始会话」。",
                ),
                session,
                "",
            )
            return

        if session.audit_session_id:
            set_audit_session_id(session.audit_session_id)

        text = (message or "").strip()
        if not text:
            yield history or [], session, ""
            return

        if not config.DEEPSEEK_API_KEY or not config.ARK_API_KEY:
            yield (
                _chat_history_append(
                    history,
                    text,
                    "请先在项目根 `.env` 配置 DEEPSEEK_API_KEY 与 ARK_API_KEY。",
                ),
                session,
                "",
            )
            return

        scope = session.doc_scope
        if scope and (scope.use_ephemeral or scope.doc_ids):
            apply_session_scope_to_runtime(scope)
            kb_ids = scope.doc_ids or None
            if scope.use_ephemeral and not scope.combine_ephemeral_with_full_kb:
                kb_ids = None
            hint = scope.summary_for_ui()
        else:
            apply_session_scope_to_runtime(SessionDocumentScope())
            kb_ids = None
            hint = None

        partial_history = _chat_history_append(history, text, "⏳ 编排进行中…")
        yield partial_history, session, ""

        try:
            for agent, doc_resolved, reply, qe in iter_c34_turn_stream(
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
            ):
                session.agent = agent
                session.doc_resolved = doc_resolved
                session.engine = qe
                yield _chat_history_append(history, text, reply), session, ""
        except Exception as exc:
            yield (
                _chat_history_append(history, text, f"执行出错：{exc}"),
                session,
                "",
            )

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
                value=mode_default,
                label="实验档位",
            )
            sandbox_cb = gr.Checkbox(
                label="C4 时启用 Python 沙箱",
                value=default_enable_sandbox,
            )
        retrieval_radio = gr.Radio(
            [
                RETRIEVAL_MODE_LABELS[RETRIEVAL_FULL_KB_AND_EPHEMERAL],
                RETRIEVAL_MODE_LABELS[RETRIEVAL_EPHEMERAL_ONLY],
                RETRIEVAL_MODE_LABELS[RETRIEVAL_FULL_KB],
            ],
            value=retrieval_default,
            label="检索范围（填写附加文件时生效）",
        )
        doc_in = gr.Textbox(
            label="可选：本会话附加文件（临时索引，默认与全库组合检索）",
            value=default_doc_paths_text or "",
            placeholder=(
                "每行一个路径（可含盘外文件），例如：\n"
                "D:\\Downloads\\report.pdf\n"
                "data/raw/session_upload/my_notes.md\n"
                "留空则仅检索系统全库（main.py kb sync 维护）"
            ),
            lines=5,
        )
        start_btn = gr.Button("开始会话", variant="primary")
        session_state = gr.State(initial_session)
        start_msg = gr.Markdown(resume_err or initial_start_msg)
        chat = gr.Chatbot(label="对话", height=420, value=initial_chat)
        msg_in = gr.Textbox(
            label="输入问题",
            lines=4,
            placeholder="输入后点击发送或按 Enter",
        )
        send_btn = gr.Button("发送", variant="secondary")

        def _retrieval_mode_from_label(label: str) -> str:
            for key, text in RETRIEVAL_MODE_LABELS.items():
                if text == label:
                    return key
            return normalize_retrieval_mode(label, has_attachments=True)

        def _start_session_wrapped(
            mode: str,
            retrieval_label: str,
            doc_path: str,
            use_sandbox: bool,
        ) -> tuple[C34UiSession, str, list]:
            return _start_session(
                mode,
                _retrieval_mode_from_label(retrieval_label),
                doc_path,
                use_sandbox,
            )

        start_btn.click(
            _start_session_wrapped,
            inputs=[mode_radio, retrieval_radio, doc_in, sandbox_cb],
            outputs=[session_state, start_msg, chat],
        )
        send_btn.click(
            _chat_stream,
            inputs=[msg_in, chat, session_state],
            outputs=[chat, session_state, msg_in],
        ).then(lambda: "", outputs=msg_in)
        msg_in.submit(
            _chat_stream,
            inputs=[msg_in, chat, session_state],
            outputs=[chat, session_state, msg_in],
        ).then(lambda: "", outputs=msg_in)

    demo.launch(server_name=host)


def cmd_c34_client(args: argparse.Namespace) -> None:
    if getattr(args, "sync_kb", False):
        from agentic_rag.experiment.kb_sync import reset_system_kb
        from agentic_rag.telemetry.audit_log import audit_log

        audit_log("kb_reset_start", payload={"via": "client --sync-kb"})
        r = reset_system_kb()
        audit_log("kb_reset_complete", payload=r)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        if not r.get("ok"):
            raise SystemExit(1)

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
            retrieval_mode=getattr(args, "retrieval_mode", None),
        )
    else:
        launch_c34_gradio_client(
            host=getattr(args, "host", "127.0.0.1"),
            default_enable_c4=bool(enable_c4) if enable_c4 is not None else False,
            default_enable_sandbox=bool(getattr(args, "sandbox", False)),
            default_retrieval_mode=getattr(args, "retrieval_mode", None),
            resume_session_id=getattr(args, "resume_session", None),
        )


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
        help="可选：附加文件路径（本会话临时索引，不写全库 Chroma）",
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
    p.add_argument(
        "--retrieval-mode",
        default=None,
        choices=[
            RETRIEVAL_FULL_KB,
            RETRIEVAL_EPHEMERAL_ONLY,
            RETRIEVAL_FULL_KB_AND_EPHEMERAL,
        ],
        help=(
            "检索范围：full_kb | ephemeral_only | full_kb_and_ephemeral；"
            "有附加路径且未指定时，控制台会交互选择（默认组合）"
        ),
    )
    p.add_argument(
        "--sync-kb",
        action="store_true",
        help="启动客户端前先执行 kb reset（清空 Chroma 并按 data/raw 系统目录重建全库）",
    )
    p.add_argument(
        "--resume-session",
        metavar="ID",
        default=None,
        help="从 runs/logs/audit/sessions/<ID>/chat.jsonl 恢复 Gradio 对话（追加同一会话日志）",
    )
    return p

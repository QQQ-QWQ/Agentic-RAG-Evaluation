"""
审计与对话日志查看：Gradio 界面 + 终端摘要。

- 全局审计：``runs/logs/audit/global_audit.jsonl``
- 会话对话：``sessions/<id>/chat.jsonl``
- 会话追踪：``sessions/<id>/trace.jsonl``（L1/L2/L3、工具调用、RAG 检索详情）
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config
from agentic_rag.experiment.kb_index_builder import kb_fingerprint, read_csv_rows
from agentic_rag.experiment.kb_paths import iter_system_raw_files
from agentic_rag.rag.chroma_store import try_load_kb_index
from agentic_rag.telemetry.audit_log import default_audit_log_path
from agentic_rag.telemetry.chat_transcript import (
    load_chat_turns,
    session_chat_log_path,
    turns_to_gradio_messages,
)
from agentic_rag.telemetry.session_trace import (
    filter_trace_events,
    load_session_trace,
    session_trace_path,
)


def _audit_root(project_root: Path | None = None) -> Path:
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    return root / "runs" / "logs" / "audit"


def _sessions_dir(project_root: Path | None = None) -> Path:
    return _audit_root(project_root) / "sessions"


def list_session_ids(*, project_root: Path | None = None) -> list[str]:
    base = _sessions_dir(project_root)
    if not base.is_dir():
        return []
    ids = [p.name for p in base.iterdir() if p.is_dir()]
    ids.sort(reverse=True)
    return ids


def kb_status_markdown(*, project_root: Path | None = None) -> str:
    """系统知识库：扫描数、清单、切块、Chroma 是否可加载。"""
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    scanned = iter_system_raw_files(root)
    csv_path = root / "data" / "processed" / "documents.csv"
    chunks_path = root / "data" / "processed" / "chunks.jsonl"
    rows = read_csv_rows(csv_path) if csv_path.is_file() else []
    chunk_lines = 0
    if chunks_path.is_file():
        chunk_lines = sum(1 for _ in chunks_path.open(encoding="utf-8"))

    chroma_dir = app_config.CHROMA_PERSIST_DIRECTORY or "（未配置）"
    chroma_ok = False
    chroma_n = 0
    if csv_path.is_file() and app_config.CHROMA_PERSIST_DIRECTORY:
        fp = kb_fingerprint(csv_path, root)
        idx = try_load_kb_index(fp)
        if idx is not None:
            chroma_ok = True
            chroma_n = len(idx.chunks)

    scan_set = {p.relative_to(root).as_posix() for p in scanned}
    csv_set = {r["file_path"].replace("\\", "/") for r in rows}
    missing = sorted(scan_set - csv_set)
    extra = sorted(csv_set - scan_set)

    lines = [
        "## 系统知识库状态",
        "",
        f"- **data/raw 系统扫描**：{len(scanned)} 个文件（已排除 `session_upload/`、`user_docs/`、`web_snapshots/`、`readme.md`）",
        f"- **documents.csv**：{len(rows)} 条",
        f"- **chunks.jsonl**：{chunk_lines} 块",
        f"- **Chroma 目录**：`{chroma_dir}`",
        f"- **Chroma 全库向量**：{'已加载 ' + str(chroma_n) + ' 块' if chroma_ok else '未命中（请执行 `main.py kb sync` 或 `kb reset`）'}",
        "",
        "**说明**：不是 `data/raw` 下每个文件都会入库；见 `data/raw/README.md`。",
    ]
    if missing:
        lines.append(f"- ⚠ 扫描到但未在 CSV：{', '.join(missing[:8])}")
    if extra:
        lines.append(f"- ⚠ CSV 有但扫描无：{', '.join(extra[:8])}")
    return "\n".join(lines)


def format_chat_turns(turns: list[dict[str, Any]]) -> str:
    if not turns:
        return "（该会话尚无 chat.jsonl 或为空）"
    parts: list[str] = []
    for i, t in enumerate(turns, 1):
        parts.append(f"### 第 {i} 轮 · {t.get('logged_at', '')}")
        parts.append(f"**用户**\n\n{t.get('user', '')}\n")
        parts.append(f"**助手**\n\n{t.get('assistant', '')}\n")
        meta = {
            k: v
            for k, v in t.items()
            if k not in ("user", "assistant", "logged_at", "session_id")
        }
        if meta:
            parts.append(f"_元数据：{json.dumps(meta, ensure_ascii=False)}_\n")
    return "\n".join(parts)


def load_audit_events(
    *,
    session_id: str | None = None,
    tail: int = 200,
    project_root: Path | None = None,
) -> list[dict[str, Any]]:
    path = default_audit_log_path(project_root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if session_id:
        sid = session_id.strip()
        rows = [r for r in rows if str(r.get("session_id", "")) == sid]
    return rows[-tail:]


def format_trace_timeline(rows: list[dict[str, Any]], *, max_events: int = 80) -> str:
    if not rows:
        return "（该会话尚无 trace.jsonl 或为空）"
    lines: list[str] = []
    for row in rows[-max_events:]:
        ev = row.get("event", "")
        ts = row.get("logged_at", "")
        payload = row.get("payload") or {}
        preview = json.dumps(payload, ensure_ascii=False, default=str)
        if len(preview) > 1200:
            preview = preview[:1200] + "…"
        lines.append(f"### `{ev}` · {ts}\n\n```json\n{preview}\n```\n")
    return "\n".join(lines)


def format_tools_and_rag(rows: list[dict[str, Any]]) -> str:
    tool_events = filter_trace_events(
        rows,
        events={
            "tool_invoke_start",
            "tool_invoke_end",
            "tool_invoke_error",
            "rag_query_result",
        },
    )
    if not tool_events:
        return "（无工具/RAG 追踪记录；请用新版 client 重新对话）"
    parts: list[str] = []
    for row in tool_events:
        ev = row.get("event", "")
        ts = row.get("logged_at", "")
        payload = row.get("payload") or {}
        parts.append(f"#### {ev} · {ts}\n")
        if ev == "rag_query_result":
            chunks = payload.get("retrieved_chunks") or []
            parts.append(
                f"- pipeline: `{payload.get('pipeline')}` · "
                f"config: `{payload.get('config')}` · "
                f"chunks: {payload.get('chunk_count', len(chunks))}\n"
            )
            if payload.get("answer"):
                parts.append(
                    f"**答案预览**\n\n{str(payload.get('answer'))[:1500]}\n"
                )
            for i, ch in enumerate(chunks[:12], 1):
                if isinstance(ch, dict):
                    parts.append(
                        f"{i}. `{ch.get('doc_id')}` `{ch.get('chunk_id')}` "
                        f"score={ch.get('score')}\n"
                        f"   {str(ch.get('text_preview', ''))[:400]}\n"
                    )
        elif ev.startswith("tool_invoke"):
            parts.append(
                f"- tool: `{payload.get('tool')}`\n"
                f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)[:3000]}\n```\n"
            )
        else:
            parts.append(
                f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)[:2000]}\n```\n"
            )
    return "\n".join(parts)


def format_orchestration_layers(rows: list[dict[str, Any]]) -> str:
    layer_events = filter_trace_events(
        rows,
        events={
            "orchestration_round_start",
            "layer1_plan",
            "layer2_execute_done",
            "layer3_judge",
            "client_turn_start",
            "client_turn_complete",
        },
    )
    if not layer_events:
        return "（无编排层记录）"
    return format_trace_timeline(layer_events, max_events=50)


def resume_client_command(session_id: str, *, tier: str = "c4") -> str:
    """生成在**新终端**恢复对话并继续提问的命令（非本页内嵌客户端）。"""
    sid = (session_id or "").strip()
    if not sid or sid.startswith("（"):
        return ""
    flag = "--c4" if tier == "c4" else "--c3"
    return f"uv run python main.py client {flag} --resume-session {sid}"


def format_audit_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "（无匹配审计记录）"
    lines: list[str] = []
    for e in events:
        payload = e.get("payload") or {}
        preview = json.dumps(payload, ensure_ascii=False, default=str)
        if len(preview) > 800:
            preview = preview[:800] + "…"
        lines.append(
            f"- `{e.get('logged_at', '')}` **{e.get('event', '')}** "
            f"(session={e.get('session_id', '')})\n  {preview}"
        )
    return "\n".join(lines)


def cmd_logs(args: argparse.Namespace) -> None:
    if getattr(args, "status", False):
        print(kb_status_markdown())
        return
    sid = getattr(args, "session", None)
    if sid:
        turns = load_chat_turns(sid)
        print(format_chat_turns(turns))
        return
    launch_logs_gradio(host=getattr(args, "host", "127.0.0.1"))


def launch_logs_gradio(*, host: str = "127.0.0.1") -> None:
    import gradio as gr

    def _refresh_sessions() -> gr.Dropdown:
        ids = list_session_ids()
        choices = ids or ["（暂无会话目录）"]
        return gr.Dropdown(choices=choices, value=choices[0])

    def _show_session(session_id: str) -> tuple[str, str, str, str, list, str]:
        empty = "请选择有效会话 id"
        if not session_id or session_id.startswith("（"):
            return empty, empty, empty, empty, [], ""
        chat_path = session_chat_log_path(session_id)
        trace_path = session_trace_path(session_id)
        turns = load_chat_turns(session_id)
        trace_rows = load_session_trace(session_id)
        chat_md = f"**chat.jsonl** · `{chat_path}`\n\n" + format_chat_turns(turns)
        trace_md = (
            f"**trace.jsonl** · `{trace_path}`\n\n"
            + format_trace_timeline(trace_rows)
        )
        tools_md = format_tools_and_rag(trace_rows)
        orch_md = format_orchestration_layers(trace_rows)
        preview = turns_to_gradio_messages(turns)
        cmd = resume_client_command(session_id, tier="c4")
        return chat_md, trace_md, tools_md, orch_md, preview, cmd

    with gr.Blocks(title="Topic4 日志查看") as demo:
        gr.Markdown(
            "# Topic4 审计与对话日志\n\n"
            "会话目录：`runs/logs/audit/sessions/<id>/` · "
            "含 `chat.jsonl`（用户可见轮次）与 `trace.jsonl`（编排+工具+RAG）。\n\n"
            "**说明**：本页为**只读查看**；要在 Gradio 里**继续对话**，请复制下方命令到**新终端**执行 "
            "（`main.py client --resume-session <id>`）。"
        )
        gr.Markdown(kb_status_markdown())
        with gr.Row():
            refresh_btn = gr.Button("刷新会话列表", variant="secondary")
            session_dd = gr.Dropdown(
                label="会话 ID（runs/logs/audit/sessions/）",
                choices=list_session_ids() or ["（暂无）"],
                value=(list_session_ids() or ["（暂无）"])[0],
            )
        with gr.Tab("对话预览 (Chatbot)"):
            chat_preview = gr.Chatbot(label="历史轮次（只读预览）", height=360)
        with gr.Tab("对话全文 (Markdown)"):
            chat_out = gr.Markdown()
        with gr.Tab("继续对话"):
            resume_cmd = gr.Textbox(
                label="在新终端执行（会打开 C3/C4 客户端并恢复上方历史）",
                lines=2,
                interactive=True,
            )
            gr.Markdown(
                "刷新浏览器**不会**删除磁盘日志；恢复后新消息写入**同一** `sessions/<id>/`。"
                " Agent 内部工具状态不恢复，仅 UI 与日志文件连续。"
            )
        with gr.Tab("追踪时间线 (trace)"):
            trace_out = gr.Markdown()
        with gr.Tab("工具与 RAG 检索"):
            tools_out = gr.Markdown()
        with gr.Tab("编排 L1/L2/L3"):
            orch_out = gr.Markdown()
        gr.Markdown(f"全局审计：`{default_audit_log_path()}`")
        load_btn = gr.Button("查看选中会话", variant="primary")
        refresh_btn.click(_refresh_sessions, outputs=session_dd)
        outs = [chat_out, trace_out, tools_out, orch_out, chat_preview, resume_cmd]
        load_btn.click(_show_session, inputs=session_dd, outputs=outs)
        session_dd.change(_show_session, inputs=session_dd, outputs=outs)

    demo.launch(server_name=host)


def build_logs_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        add_help=add_help,
        description="查看知识库状态、会话 chat.jsonl 与 global_audit.jsonl",
    )
    p.add_argument("--host", default="127.0.0.1", help="Gradio 监听地址")
    p.add_argument(
        "--session",
        metavar="ID",
        help="终端模式：打印该会话的 chat.jsonl 全文后退出",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="终端模式：仅打印知识库/Chroma 状态后退出",
    )
    return p

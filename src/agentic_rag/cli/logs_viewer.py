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


def _session_last_activity_mtime(session_id: str, *, project_root: Path | None = None) -> float:
    """用于排序：优先 trace.jsonl，其次 chat.jsonl。"""
    root = (project_root or app_config.PROJECT_ROOT).resolve()
    mtimes: list[float] = []
    for path in (
        session_trace_path(session_id, project_root=root),
        session_chat_log_path(session_id, project_root=root),
    ):
        if path.is_file():
            mtimes.append(path.stat().st_mtime)
    return max(mtimes) if mtimes else 0.0


def is_session_in_progress(session_id: str, *, project_root: Path | None = None) -> bool:
    """最后一轮已 client_turn_start 但尚未 client_turn_complete。"""
    rows = load_session_trace(session_id, project_root=project_root)
    if not rows:
        return False
    last_start = -1
    last_complete = -1
    for i, row in enumerate(rows):
        ev = str(row.get("event") or "")
        if ev == "client_turn_start":
            last_start = i
        elif ev == "client_turn_complete":
            last_complete = i
    return last_start > last_complete


def list_session_ids(*, project_root: Path | None = None) -> list[str]:
    """按最近活动时间倒序（便于在 logs 页找到正在进行的对话）。"""
    base = _sessions_dir(project_root)
    if not base.is_dir():
        return []
    ids = [p.name for p in base.iterdir() if p.is_dir()]
    ids.sort(
        key=lambda sid: _session_last_activity_mtime(sid, project_root=project_root),
        reverse=True,
    )
    return ids


def session_status_banner(session_id: str, *, project_root: Path | None = None) -> str:
    if not session_id or session_id.startswith("（"):
        return ""
    in_prog = is_session_in_progress(session_id, project_root=project_root)
    trace_p = session_trace_path(session_id, project_root=project_root)
    chat_p = session_chat_log_path(session_id, project_root=project_root)
    lines = [
        f"**会话 ID**：`{session_id}`",
        f"- trace：`{trace_p}`" + (" · **进行中**（编排/工具事件会实时追加）" if in_prog else ""),
        f"- chat：`{chat_p}`" + (" · 本轮结束后才写入完整问答" if in_prog else ""),
    ]
    if in_prog:
        lines.append(
            "- 进行中请优先看 **「工具与 RAG 检索」** 或 **「追踪时间线」** Tab；"
            "勾选自动刷新或点「刷新会话列表」。"
        )
    return "\n".join(lines)


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


def format_chat_turns(turns: list[dict[str, Any]], *, session_id: str = "") -> str:
    banner = session_status_banner(session_id) if session_id else ""
    if not turns:
        body = "（该会话尚无 chat.jsonl 或为空）"
        if session_id and is_session_in_progress(session_id):
            body += (
                "\n\n**说明**：当前轮次仍在编排中，`chat.jsonl` 在本轮结束后才写入。"
                "请查看 **trace** / **工具与 RAG** Tab。"
            )
        return (banner + "\n\n" + body) if banner else body
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
    body = "\n".join(parts)
    if banner:
        return banner + "\n\n" + body
    return body


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
            "layer1_plan_start",
            "layer1_plan",
            "layer1_plan_error",
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
    follow = (getattr(args, "follow", None) or "").strip()
    if follow:
        follow_session_trace(follow, interval_sec=float(getattr(args, "follow_interval", 2.0)))
        return
    sid = getattr(args, "session", None)
    if sid:
        turns = load_chat_turns(sid)
        print(format_chat_turns(turns, session_id=sid))
        return
    launch_logs_gradio(
        host=getattr(args, "host", "127.0.0.1"),
        port=int(getattr(args, "port", 0) or 0) or None,
    )


def follow_session_trace(session_id: str, *, interval_sec: float = 2.0) -> None:
    """终端实时跟踪 trace.jsonl（进行中对话）。"""
    import time

    sid = (session_id or "").strip()
    if not sid:
        raise SystemExit("follow 需要 session id")
    path = session_trace_path(sid)
    print(f"跟踪 trace（Ctrl+C 退出）：{path}\n")
    if not path.is_file():
        print("（文件尚未创建，等待 client 侧「开始会话」并发送问题…）")
    seen = 0
    try:
        while True:
            if path.is_file():
                rows = load_session_trace(sid)
                if len(rows) > seen:
                    for row in rows[seen:]:
                        ev = row.get("event", "")
                        ts = row.get("logged_at", "")
                        preview = json.dumps(row.get("payload") or {}, ensure_ascii=False, default=str)
                        if len(preview) > 600:
                            preview = preview[:600] + "…"
                        print(f"[{ts}] {ev} {preview}")
                    seen = len(rows)
            time.sleep(max(0.5, interval_sec))
    except KeyboardInterrupt:
        print("\n已停止跟踪。")


def launch_logs_gradio(
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
) -> None:
    from agentic_rag.cli.gradio_launch import (
        DEFAULT_GRADIO_CLIENT_PORT,
        DEFAULT_GRADIO_LOGS_PORT,
        launch_topic4_gradio,
    )

    listen_port = port if port is not None else DEFAULT_GRADIO_LOGS_PORT
    import gradio as gr

    def _show_session(session_id: str, selected_turn: str = "", *, light_refresh: bool = False) -> tuple[Any, ...]:
        from agentic_rag.cli.gradio_analytics import build_analytics_bundle, bundle_outputs

        empty = "请选择有效会话 id"
        if not session_id or session_id.startswith("（"):
            return (empty, empty, empty, empty, [], "", *bundle_outputs(build_analytics_bundle("")))

        turns = load_chat_turns(session_id)
        trace_rows = load_session_trace(session_id)
        banner = session_status_banner(session_id)
        chat_md = format_chat_turns(turns, session_id=session_id)
        trace_md = (banner + "\n\n" if banner else "") + format_trace_timeline(trace_rows)
        tools_md = (banner + "\n\n" if banner else "") + format_tools_and_rag(trace_rows)
        orch_md = format_orchestration_layers(trace_rows)
        preview = turns_to_gradio_messages(turns)
        cmd = resume_client_command(session_id, tier="c4")
        bundle = build_analytics_bundle(
            session_id, selected_turn=selected_turn, light_refresh=light_refresh
        )
        return (chat_md, trace_md, tools_md, orch_md, preview, cmd, *bundle_outputs(bundle))

    def _refresh_sessions_keep(current: str) -> tuple[gr.Dropdown, str]:
        ids = list_session_ids()
        choices = ids or ["（暂无会话目录）"]
        cur = (current or "").strip()
        if cur in ids:
            value = cur
        else:
            value = choices[0]
        return gr.Dropdown(choices=choices, value=value), value

    def _refresh_and_show(
        current: str,
        selected_turn: str = "",
        *,
        light_refresh: bool = False,
    ) -> tuple[Any, str, tuple[Any, ...]]:
        dd, sid = _refresh_sessions_keep(current)
        show = _show_session(sid, selected_turn, light_refresh=light_refresh)
        return dd, sid, show

    def _jump_to_pasted(
        pasted: str, current: str, selected_turn: str = ""
    ) -> tuple[gr.Dropdown, *tuple[Any, ...]]:
        sid = (pasted or "").strip() or (current or "").strip()
        ids = list_session_ids()
        if sid and sid not in ids:
            ids = [sid, *ids]
        choices = ids or ["（暂无会话目录）"]
        if sid not in choices:
            sid = choices[0]
        show = _show_session(sid, selected_turn)
        return gr.Dropdown(choices=choices, value=sid), *show

    with gr.Blocks(title="Topic4 日志查看") as demo:
        gr.Markdown(
            f"# Topic4 审计与对话日志（只读 · 端口 {listen_port}）\n\n"
            f"**本页仅查看日志**，与 C3/C4 对话客户端（默认端口 **{DEFAULT_GRADIO_CLIENT_PORT}**）"
            f" 分离，可同时开两个浏览器标签，互不挤占。\n\n"
            "会话目录：`runs/logs/audit/sessions/<id>/` · "
            "含 `chat.jsonl`（用户可见轮次）与 `trace.jsonl`（编排+工具+RAG）。\n\n"
            "**进行中对话**：client 页「开始会话」后复制 **Session ID** 到下方粘贴框；"
            "trace / 工具 Tab 会随编排实时更新（需勾选自动刷新）。"
            "`chat.jsonl` 在本轮问答结束后才写入完整内容。\n\n"
            "**继续对话**：复制「继续对话」Tab 中的命令到**新终端**执行 "
            "（`main.py client --resume-session <id>`，勿在本页提问）。"
        )
        gr.Markdown(kb_status_markdown())
        with gr.Row():
            refresh_btn = gr.Button("刷新会话列表", variant="secondary")
            auto_refresh_cb = gr.Checkbox(
                label="自动刷新（每 4 秒，跟踪进行中对话）",
                value=True,
            )
        with gr.Row():
            session_dd = gr.Dropdown(
                label="会话 ID（最近活动排在最前）",
                choices=list_session_ids() or ["（暂无）"],
                value=(list_session_ids() or ["（暂无）"])[0],
            )
            paste_id = gr.Textbox(
                label="粘贴 client 页 Session ID 并定位",
                placeholder="开始会话后 client 页会显示 audit id",
                scale=2,
            )
            jump_btn = gr.Button("定位", variant="secondary")
        status_out = gr.Markdown("")
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
        with gr.Tab("可视化仪表盘"):
            gr.Markdown(
                "按 **每一轮用户输入** 切分 trace，KPI、图表、L1/L2/L3 详情均整合在下方单一仪表盘中。"
                "勾选「自动刷新」可实时跟踪进行中对话。"
            )
            turn_dd = gr.Dropdown(
                label="选择轮次（精确到每次用户问题）",
                choices=[],
                value=None,
                interactive=True,
                allow_custom_value=False,
            )
            dashboard_html = gr.HTML(label="会话仪表盘")
            export_hint = gr.Markdown("")
            with gr.Row():
                export_btn = gr.Button("导出 JSON / HTML", variant="secondary")
                export_out = gr.Markdown("")
        gr.Markdown(f"全局审计：`{default_audit_log_path()}`")
        load_btn = gr.Button("查看选中会话", variant="primary")
        view_outs = [
            chat_out,
            trace_out,
            tools_out,
            orch_out,
            chat_preview,
            resume_cmd,
            dashboard_html,
            turn_dd,
            export_hint,
        ]
        analytics_turn_outs = [
            dashboard_html,
            export_hint,
        ]
        all_outs = [session_dd, *view_outs, status_out]

        def _on_refresh(current: str, auto: bool, selected_turn: str):
            if not auto:
                return tuple([gr.skip()] * len(all_outs))
            dd, sid, show = _refresh_and_show(current, selected_turn, light_refresh=True)
            status = (
                session_status_banner(sid)
                if sid and not str(sid).startswith("（")
                else ""
            )
            return dd, *show, status

        refresh_btn.click(
            _on_refresh,
            inputs=[session_dd, auto_refresh_cb, turn_dd],
            outputs=all_outs,
        )
        jump_btn.click(
            _jump_to_pasted,
            inputs=[paste_id, session_dd, turn_dd],
            outputs=[session_dd, *view_outs],
        ).then(
            lambda sid: session_status_banner(sid) if sid and not str(sid).startswith("（") else "",
            inputs=session_dd,
            outputs=status_out,
        )
        load_btn.click(
            _show_session,
            inputs=[session_dd, turn_dd],
            outputs=view_outs,
        ).then(
            lambda sid: session_status_banner(sid) if sid and not str(sid).startswith("（") else "",
            inputs=session_dd,
            outputs=status_out,
        )
        session_dd.change(
            _show_session,
            inputs=[session_dd, turn_dd],
            outputs=view_outs,
        ).then(
            lambda sid: session_status_banner(sid) if sid and not str(sid).startswith("（") else "",
            inputs=session_dd,
            outputs=status_out,
        )
        demo.load(_on_refresh, inputs=[session_dd, auto_refresh_cb, turn_dd], outputs=all_outs)

        tick = gr.Timer(value=4.0, active=True)
        tick.tick(
            fn=_on_refresh,
            inputs=[session_dd, auto_refresh_cb, turn_dd],
            outputs=all_outs,
            show_progress="hidden",
        )

        def _toggle_timer(enabled: bool):
            return gr.Timer(active=bool(enabled))

        auto_refresh_cb.change(_toggle_timer, inputs=auto_refresh_cb, outputs=tick)

        from agentic_rag.cli.gradio_analytics import export_analytics_files, on_turn_select

        turn_dd.change(
            on_turn_select,
            inputs=[session_dd, turn_dd],
            outputs=analytics_turn_outs,
        )
        export_btn.click(export_analytics_files, inputs=session_dd, outputs=export_out)

    launch_topic4_gradio(
        demo,
        host=host,
        port=listen_port,
        service_label="Topic4 日志查看（只读）",
        peer_hint=(
            f"对话客户端请另开终端：uv run python main.py client "
            f"（默认 http://{host}:{DEFAULT_GRADIO_CLIENT_PORT}）"
        ),
    )


def build_logs_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        add_help=add_help,
        description="查看知识库状态、会话 chat.jsonl 与 global_audit.jsonl",
    )
    from agentic_rag.cli.gradio_launch import DEFAULT_GRADIO_LOGS_PORT

    p.add_argument("--host", default="127.0.0.1", help="Gradio 监听地址")
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_GRADIO_LOGS_PORT,
        help=f"Gradio 端口（默认 {DEFAULT_GRADIO_LOGS_PORT}，与 client 默认 7860 分离）",
    )
    p.add_argument(
        "--session",
        metavar="ID",
        help="终端模式：打印该会话的 chat.jsonl 全文后退出",
    )
    p.add_argument(
        "--follow",
        metavar="ID",
        help="终端模式：实时跟踪该 session 的 trace.jsonl（进行中对话）",
    )
    p.add_argument(
        "--follow-interval",
        type=float,
        default=2.0,
        help="--follow 轮询间隔秒数（默认 2）",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="终端模式：仅打印知识库/Chroma 状态后退出",
    )
    return p

"""
会话 trace / chat 解析：按用户每轮输入切分，汇总指标并生成交互式 Chart.js 图表 HTML。

供 logs 页、C3/C4 客户端、legacy RAG UI 共用。
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_rag import config as app_config
from agentic_rag.telemetry.chart_svg import (
    C_TEXT,
    alerts_html,
    banner_html,
    dashboard_shell_close,
    dashboard_shell_open,
    detail_block_html,
    html_escape as _html_escape,
    kv_grid_html,
    kpi_grid_html,
    live_line_html,
    metrics_table_html,
    static_charts_block,
    sub_text_html,
    svg_horizontal_bars,
    table_row_html,
    tag_html,
    tool_bars_html,
    turn_detail_panel_html,
)
from agentic_rag.telemetry.chat_transcript import load_chat_turns, session_chat_log_path
from agentic_rag.telemetry.session_trace import load_session_trace, session_trace_path


def _project_root() -> Path:
    return app_config.PROJECT_ROOT.resolve()


def _safe_float(v: Any, default: float = 0.0) -> float:
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass
class TurnMetrics:
    turn_index: int
    user_text: str = ""
    user_preview: str = ""
    assistant_preview: str = ""
    logged_at: str = ""
    completed: bool = True
    tier: str = ""
    stop_reason: str = ""
    latency_ms: int = 0
    orchestration_rounds: int | None = None
    kb_doc_ids: list[str] = field(default_factory=list)
    rag_count: int = 0
    rag_pipelines: list[str] = field(default_factory=list)
    tool_counts: dict[str, int] = field(default_factory=dict)
    verdicts: list[str] = field(default_factory=list)
    plan_params: dict[str, Any] = field(default_factory=dict)
    param_events: list[dict[str, Any]] = field(default_factory=list)
    rag_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SessionAnalytics:
    session_id: str
    module: str = "c34"
    session_params: dict[str, Any] = field(default_factory=dict)
    turns: list[TurnMetrics] = field(default_factory=list)
    in_progress: bool = False

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def completed_turns(self) -> int:
        return sum(1 for t in self.turns if t.completed)

    def summary(self) -> dict[str, Any]:
        done = [t for t in self.turns if t.completed]
        latencies = [t.latency_ms for t in done if t.latency_ms]
        rags = [t.rag_count for t in self.turns]
        return {
            "session_id": self.session_id,
            "module": self.module,
            "turn_count": len(self.turns),
            "completed_turns": len(done),
            "in_progress": self.in_progress,
            "mean_latency_s": round(statistics.mean(latencies) / 1000, 1) if latencies else 0,
            "total_rag": sum(rags),
            "mean_rag": round(statistics.mean(rags), 1) if rags else 0,
            "session_params": self.session_params,
        }


def _summarize_turn_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    plan: dict[str, Any] = {}
    rag_events: list[dict[str, Any]] = []
    tool_counts: dict[str, int] = {}
    verdicts: list[str] = []
    param_events: list[dict[str, Any]] = []
    pipelines: list[str] = []

    param_event_names = {
        "layer1_plan",
        "layer1_plan_start",
        "rag_query_result",
        "tool_invoke_start",
        "tool_invoke_end",
        "layer3_judge",
        "orchestration_round_start",
    }

    for row in events:
        ev = str(row.get("event") or "")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        ts = str(row.get("logged_at") or "")

        if ev in param_event_names:
            param_events.append({"event": ev, "logged_at": ts, "payload": payload})

        if ev == "layer1_plan" and not plan:
            plan = dict(payload)
        elif ev == "rag_query_result":
            rag_events.append(payload)
            pipe = str(payload.get("pipeline") or "").strip()
            if pipe:
                pipelines.append(pipe)
        elif ev == "tool_invoke_start":
            tname = str(payload.get("tool") or payload.get("name") or "").strip()
            if tname:
                tool_counts[tname] = tool_counts.get(tname, 0) + 1
        elif ev == "layer3_judge":
            v = str(payload.get("verdict") or "").strip()
            if v:
                verdicts.append(v)

    orch_rounds = sum(
        1 for row in events if str(row.get("event") or "") == "orchestration_round_start"
    )

    return {
        "plan_params": plan,
        "rag_events": rag_events,
        "rag_count": len(rag_events),
        "rag_pipelines": list(dict.fromkeys(pipelines)),
        "tool_counts": tool_counts,
        "tool_total": sum(tool_counts.values()),
        "verdicts": verdicts,
        "param_events": param_events,
        "orchestration_rounds": orch_rounds,
    }


def segment_trace_by_turns(rows: list[dict[str, Any]]) -> tuple[list[list[dict[str, Any]]], bool]:
    """
    按用户轮次切分 trace。

    - 标准客户端：client_turn_start … client_turn_complete
    - 批量评测（仅 complete）：从会话头累计到 complete
    """
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    prelude: list[dict[str, Any]] = []
    in_progress = False

    for row in rows:
        ev = str(row.get("event") or "")
        if ev == "client_turn_start":
            if current:
                groups.append(current)
            current = prelude + [row]
            prelude = []
            in_progress = True
        elif ev == "client_turn_complete":
            if not current and prelude:
                current = prelude
                prelude = []
            current.append(row)
            groups.append(current)
            current = []
            in_progress = False
        else:
            if current or groups:
                current.append(row)
            else:
                prelude.append(row)

    if current:
        groups.append(current)
        in_progress = not any(str(r.get("event") or "") == "client_turn_complete" for r in current)

    return groups, in_progress


def _session_start_params(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        ev = str(row.get("event") or "")
        if ev in ("session_start_gradio", "session_start", "legacy_rag_session_start"):
            payload = row.get("payload")
            return dict(payload) if isinstance(payload, dict) else {}
    return {}


def _detect_module(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        ev = str(row.get("event") or "")
        if ev.startswith("legacy_rag"):
            return "legacy_rag"
        payload = row.get("payload") or {}
        if isinstance(payload, dict) and payload.get("module"):
            return str(payload["module"])
    return "c34"


def build_session_analytics(
    session_id: str,
    *,
    project_root: Path | None = None,
) -> SessionAnalytics:
    sid = (session_id or "").strip()
    rows = load_session_trace(sid, project_root=project_root)
    chat_turns = load_chat_turns(sid, project_root=project_root)
    groups, in_progress = segment_trace_by_turns(rows)

    analytics = SessionAnalytics(
        session_id=sid,
        module=_detect_module(rows),
        session_params=_session_start_params(rows),
        in_progress=in_progress,
    )

    for i, group in enumerate(groups, start=1):
        start_row = group[0] if group else {}
        complete_row = next(
            (r for r in group if str(r.get("event")) == "client_turn_complete"),
            None,
        )
        start_payload = start_row.get("payload") if isinstance(start_row.get("payload"), dict) else {}
        complete_payload = (
            complete_row.get("payload") if complete_row and isinstance(complete_row.get("payload"), dict) else {}
        )

        chat = chat_turns[i - 1] if i - 1 < len(chat_turns) else {}
        summary = _summarize_turn_events(group)

        orch_rounds = complete_payload.get("orchestration_rounds")
        if orch_rounds is None:
            orch_rounds = summary.get("orchestration_rounds")

        user_text = str(chat.get("user") or complete_payload.get("user") or start_payload.get("user_preview") or "")
        if not user_text and str(start_row.get("event") or "") != "client_turn_start":
            for r in group:
                if str(r.get("event") or "") == "client_turn_complete":
                    p = r.get("payload") if isinstance(r.get("payload"), dict) else {}
                    user_text = str(p.get("user") or p.get("user_preview") or "")
                    break

        turn = TurnMetrics(
            turn_index=i,
            user_text=user_text,
            user_preview=str(start_payload.get("user_preview") or user_text[:500]),
            assistant_preview=str(
                complete_payload.get("assistant_preview") or chat.get("assistant", "")[:2000]
            ),
            logged_at=str(complete_row.get("logged_at") if complete_row else start_row.get("logged_at") or ""),
            completed=complete_row is not None,
            tier=str(complete_payload.get("tier") or start_payload.get("tier") or chat.get("tier") or ""),
            stop_reason=str(complete_payload.get("stop_reason") or chat.get("stop_reason") or ""),
            latency_ms=int(_safe_float(complete_payload.get("latency_ms") or chat.get("latency_ms"))),
            orchestration_rounds=int(orch_rounds) if orch_rounds is not None else None,
            kb_doc_ids=list(complete_payload.get("kb_doc_ids") or chat.get("kb_doc_ids") or []),
            rag_count=summary["rag_count"],
            rag_pipelines=summary["rag_pipelines"],
            tool_counts=summary["tool_counts"],
            verdicts=summary["verdicts"],
            plan_params=summary["plan_params"],
            param_events=summary["param_events"],
            rag_events=summary["rag_events"],
        )
        analytics.turns.append(turn)

    return analytics


def turn_choice_label(turn: TurnMetrics) -> str:
    status = "OK" if turn.completed else ".."
    preview = _clean_user_question(turn.user_preview or turn.user_text or "（无问题）")[:48]
    lat = f"{turn.latency_ms / 1000:.1f}s" if turn.latency_ms else "-"
    return f"轮{turn.turn_index} {status} · {preview} · {lat} · RAGx{turn.rag_count}"


def _clean_user_question(text: str) -> str:
    """去掉 batch 前缀 Q001, 等，便于展示。"""
    import re

    t = (text or "").strip()
    t = re.sub(r"^Q\d+\s*,?\s*", "", t, flags=re.IGNORECASE)
    return t.strip() or text.strip()


def render_turn_detail_html(turn: TurnMetrics, analytics: SessionAnalytics) -> str:
    """选中轮次的 L1/L2/L3 与工具详情，嵌入 logs 仪表盘。"""
    plan = turn.plan_params or {}
    user_q = _clean_user_question(turn.user_preview or turn.user_text or "-")
    lat = f"{turn.latency_ms / 1000:.1f}s" if turn.latency_ms else "-"
    verdict = " -> ".join(turn.verdicts) or "-"
    pipelines = ", ".join(turn.rag_pipelines) or "-"

    summary_rows = [
        ("用户问题", user_q[:200]),
        ("tier", turn.tier or "-"),
        ("stop_reason", turn.stop_reason or "-"),
        ("耗时", lat),
        ("RAG 次数", str(turn.rag_count)),
        ("编排轮数", str(turn.orchestration_rounds if turn.orchestration_rounds is not None else "-")),
        ("L3 verdict", verdict),
        ("RAG pipelines", pipelines),
    ]
    inner = kv_grid_html(summary_rows)

    l1_fields = [
        ("任务摘要", str(plan.get("task_summary") or "-")),
        ("需要检索", "是" if plan.get("needs_retrieval_tools") else "否"),
        ("建议管线", ", ".join(plan.get("suggested_pipelines") or []) or "-"),
        ("网页工具", "是" if plan.get("needs_web_tools") else "否"),
        ("入库意图", str(plan.get("kb_mutation_intent") or "-")),
    ]
    inner += detail_block_html(
        "L1 规划",
        kv_grid_html(l1_fields, columns=1)
        + (
            f'<p style="margin:6px 0 0;color:{C_TEXT};font-size:13px;">'
            f"<b style=\"color:#8b949e;\">二层计划：</b>{_html_escape(str(plan.get('plan_for_layer2') or '-'))}</p>"
            if plan.get("plan_for_layer2")
            else ""
        )
        + (
            f'<p style="margin:4px 0 0;color:#8b949e;font-size:12px;">'
            f"{_html_escape(str(plan.get('reasoning_brief') or ''))}</p>"
            if plan.get("reasoning_brief")
            else ""
        ),
    )

    inner += detail_block_html("L2 工具调用", tool_bars_html(turn.tool_counts))

    if turn.kb_doc_ids:
        inner += detail_block_html("知识库 doc_ids", _html_escape(", ".join(turn.kb_doc_ids)))

    if analytics.session_params and turn.turn_index == 1:
        sp = analytics.session_params
        sess_rows = [
            ("模块", str(sp.get("module") or analytics.module)),
            ("C4", "是" if sp.get("enable_c4") else "否"),
            ("检索模式", str(sp.get("retrieval_mode") or "-")),
        ]
        inner += detail_block_html("会话启动参数", kv_grid_html(sess_rows))

    title = f"轮次 {turn.turn_index} 详情"
    if not turn.completed:
        title += " [进行中]"
    return turn_detail_panel_html(title, inner)


def format_turn_params_markdown(analytics: SessionAnalytics, turn_index: int | None = None) -> str:
    if not analytics.turns:
        return "（尚无对话轮次）"
    idx = (turn_index or len(analytics.turns)) - 1
    idx = max(0, min(idx, len(analytics.turns) - 1))
    turn = analytics.turns[idx]

    lines = [
        f"### 轮次 {turn.turn_index} · 参数与传递",
        "",
        f"- **用户输入**：{turn.user_preview or turn.user_text[:300]}",
        f"- **档位 tier**：`{turn.tier or '—'}`",
        f"- **stop_reason**：`{turn.stop_reason or '—'}`",
        f"- **耗时**：{turn.latency_ms} ms",
        f"- **RAG 次数**：{turn.rag_count}",
        f"- **编排轮数**：{turn.orchestration_rounds if turn.orchestration_rounds is not None else '—'}",
        f"- **kb_doc_ids**：`{', '.join(turn.kb_doc_ids) or '—'}`",
        "",
    ]
    if analytics.session_params:
        lines.append("**会话级参数（session_start）**")
        lines.append(f"```json\n{json.dumps(analytics.session_params, ensure_ascii=False, indent=2)[:4000]}\n```\n")
    if turn.plan_params:
        lines.append("**L1 规划参数**")
        lines.append(f"```json\n{json.dumps(turn.plan_params, ensure_ascii=False, indent=2)[:4000]}\n```\n")
    if turn.tool_counts:
        lines.append(f"**工具调用**：`{json.dumps(turn.tool_counts, ensure_ascii=False)}`")
    if turn.verdicts:
        lines.append(f"**L3 verdicts**：`{' → '.join(turn.verdicts)}`")
    if turn.rag_pipelines:
        lines.append(f"**RAG pipelines**：`{', '.join(turn.rag_pipelines)}`")
    return "\n".join(lines)


def build_plot_dataframe(analytics: SessionAnalytics):
    """Gradio Dataframe / 导出用表格。"""
    import pandas as pd

    rows = []
    for t in analytics.turns:
        q = (t.user_preview or t.user_text or "")[:40].replace("\n", " ")
        rows.append(
            {
                "轮次": t.turn_index,
                "用户问题": q,
                "耗时_s": round(t.latency_ms / 1000, 1) if t.latency_ms else 0.0,
                "RAG": t.rag_count,
                "工具": sum(t.tool_counts.values()),
                "编排轮": t.orchestration_rounds or 0,
                "verdict": " → ".join(t.verdicts) or "—",
                "状态": "完成" if t.completed else "进行中",
            }
        )
    cols = ["轮次", "用户问题", "耗时_s", "RAG", "工具", "编排轮", "verdict", "状态"]
    if not rows:
        return pd.DataFrame({c: [] for c in cols})
    return pd.DataFrame(rows)


def format_bar_charts_markdown(analytics: SessionAnalytics) -> str:
    """Unicode 条形图 —— 不依赖 JS / Vega，Gradio Markdown 必显。"""
    if not analytics.turns:
        return "（尚无图表数据）"
    turns = analytics.turns
    max_lat = max((t.latency_ms for t in turns), default=1) / 1000 or 1
    max_rag = max((t.rag_count for t in turns), default=1) or 1
    max_tool = max((sum(t.tool_counts.values()) for t in turns), default=1) or 1
    width = 24

    def _bar(val: float, max_v: float) -> str:
        n = max(1, int(val / max_v * width)) if val > 0 else 0
        return "█" * n

    lines = ["### 指标条形图（逐轮）", ""]
    lines.append("**耗时 (秒)**")
    for t in turns:
        v = t.latency_ms / 1000 if t.latency_ms else 0
        lines.append(f"- 轮{t.turn_index}: `{_bar(v, max_lat)}` **{v:.1f}s**")
    lines.append("")
    lines.append("**RAG 次数**")
    for t in turns:
        lines.append(f"- 轮{t.turn_index}: `{_bar(float(t.rag_count), float(max_rag))}` **{t.rag_count}**")
    lines.append("")
    lines.append("**工具调用**")
    for t in turns:
        tv = float(sum(t.tool_counts.values()))
        lines.append(f"- 轮{t.turn_index}: `{_bar(tv, float(max_tool))}` **{int(tv)}**")
    return "\n".join(lines)


def _session_chart_labels(analytics: SessionAnalytics) -> list[str]:
    return [f"轮{t.turn_index}" for t in analytics.turns]


def _session_chart_series(analytics: SessionAnalytics) -> tuple[list[float], list[float], list[float], list[float]]:
    latencies = [round(t.latency_ms / 1000, 1) if t.latency_ms else 0.0 for t in analytics.turns]
    rags = [float(t.rag_count) for t in analytics.turns]
    tools = [float(sum(t.tool_counts.values())) for t in analytics.turns]
    orch = [float(t.orchestration_rounds or 0) for t in analytics.turns]
    return latencies, rags, tools, orch


def _snapshot_path(session_id: str, *, project_root: Path | None = None) -> Path:
    root = project_root or _project_root()
    sid = (session_id or "").strip()
    return session_trace_path(sid, project_root=root).parent / "exports" / "analytics_snapshot.json"


def _turn_signature(t: TurnMetrics) -> dict[str, Any]:
    return {
        "i": t.turn_index,
        "rag": t.rag_count,
        "tools": sum(t.tool_counts.values()),
        "lat_s": round(t.latency_ms / 1000, 1) if t.latency_ms else 0,
        "orch": t.orchestration_rounds or 0,
        "done": t.completed,
        "verdict": " → ".join(t.verdicts),
    }


def _load_analytics_snapshot(session_id: str, *, project_root: Path | None = None) -> dict[str, Any]:
    path = _snapshot_path(session_id, project_root=project_root)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_analytics_snapshot(analytics: SessionAnalytics, *, project_root: Path | None = None) -> None:
    path = _snapshot_path(analytics.session_id, project_root=project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    sigs = [_turn_signature(t) for t in analytics.turns]
    path.write_text(
        json.dumps(
            {
                "turn_count": len(analytics.turns),
                "completed_turns": analytics.completed_turns,
                "in_progress": analytics.in_progress,
                "turns": sigs,
                "trace_rows": _trace_row_count(analytics.session_id, project_root=project_root),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _trace_row_count(session_id: str, *, project_root: Path | None = None) -> int:
    return len(load_session_trace(session_id, project_root=project_root))


def _live_elapsed_ms_for_turn(session_id: str, turn_index: int, *, project_root: Path | None = None) -> int:
    """进行中轮次：从 client_turn_start 到当前的毫秒数。"""
    rows = load_session_trace(session_id, project_root=project_root)
    groups, _ = segment_trace_by_turns(rows)
    if turn_index < 1 or turn_index > len(groups):
        return 0
    group = groups[turn_index - 1]
    start_ts = ""
    for row in group:
        if str(row.get("event") or "") == "client_turn_start":
            start_ts = str(row.get("logged_at") or "")
            break
    if not start_ts:
        return 0
    try:
        start = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0, int((now - start).total_seconds() * 1000))
    except ValueError:
        return 0


@dataclass
class SessionInsights:
    generated_at: str
    trace_rows: int
    change_banner: str
    live_line: str
    alerts: list[tuple[str, str, str]]
    hero_kpis: list[tuple[str, str, str, str]]
    row_tone: dict[int, str]
    peak_latency_idx: int | None
    peak_rag_idx: int | None
    active_turn_idx: int | None
    latest_delta: str


def build_session_insights(
    analytics: SessionAnalytics,
    *,
    project_root: Path | None = None,
    prev_snapshot: dict[str, Any] | None = None,
) -> SessionInsights:
    prev = prev_snapshot if prev_snapshot is not None else _load_analytics_snapshot(
        analytics.session_id, project_root=project_root
    )
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    trace_rows = _trace_row_count(analytics.session_id, project_root=project_root)
    turns = analytics.turns
    summary = analytics.summary()

    active_idx: int | None = None
    if analytics.in_progress and turns:
        active_idx = turns[-1].turn_index

    peak_lat_idx: int | None = None
    peak_rag_idx: int | None = None
    if turns:
        done_lat = [(t.turn_index, t.latency_ms) for t in turns if t.latency_ms]
        if done_lat:
            peak_lat_idx = max(done_lat, key=lambda x: x[1])[0]
        peak_rag_idx = max(turns, key=lambda t: t.rag_count).turn_index

    alerts: list[tuple[str, str, str]] = []
    if analytics.in_progress:
        t = turns[-1]
        live_ms = _live_elapsed_ms_for_turn(analytics.session_id, t.turn_index, project_root=project_root)
        alerts.append(
            (
                "info",
                "本轮进行中",
                f"实时 RAG×{t.rag_count} · 工具×{sum(t.tool_counts.values())} · "
                f"编排{t.orchestration_rounds or 0}轮 · 已耗时 {live_ms / 1000:.1f}s",
            )
        )
        if live_ms > 120_000:
            alerts.append(("warn", "耗时偏高", f"本轮已运行 {live_ms / 1000:.0f}s，请关注是否卡住"))
        if t.rag_count >= 6:
            alerts.append(("warn", "RAG 密集", f"本轮已检索 {t.rag_count} 次，成本与延迟可能升高"))

    for t in turns:
        if t.completed and t.latency_ms > 90_000:
            alerts.append(("warn", f"轮{t.turn_index} 慢响应", f"耗时 {t.latency_ms / 1000:.1f}s"))
        if t.rag_count >= 8:
            alerts.append(("crit", f"轮{t.turn_index} RAG 过多", f"共 {t.rag_count} 次检索"))
        if any(v in ("replan", "continue_execute") for v in t.verdicts):
            alerts.append(
                ("info", f"轮{t.turn_index} 编排未一次完成", f"verdict: {' → '.join(t.verdicts)}"),
            )
        if t.stop_reason and t.stop_reason not in ("complete", ""):
            alerts.append(("warn", f"轮{t.turn_index} stop", t.stop_reason))

    prev_turns = prev.get("turns") or []
    prev_count = int(prev.get("turn_count") or 0)
    prev_rows = int(prev.get("trace_rows") or 0)
    change_banner = ""
    latest_delta = ""

    if len(turns) > prev_count:
        change_banner = f"[新增] 第 {turns[-1].turn_index} 轮用户问题（共 {len(turns)} 轮）"
    elif trace_rows > prev_rows and analytics.in_progress:
        change_banner = f"[更新] trace +{trace_rows - prev_rows} 行，本轮指标刷新中"
    elif prev_rows and trace_rows != prev_rows:
        change_banner = f"[更新] trace {prev_rows} -> {trace_rows} 行"

    if turns and prev_turns:
        cur = _turn_signature(turns[-1])
        if analytics.in_progress and len(turns) == len(prev_turns):
            p = prev_turns[-1]
            dr = cur["rag"] - int(p.get("rag") or 0)
            dt = cur["tools"] - int(p.get("tools") or 0)
            parts = []
            if dr:
                parts.append(f"RAG {'+' if dr > 0 else ''}{dr}")
            if dt:
                parts.append(f"工具 {'+' if dt > 0 else ''}{dt}")
            if parts:
                latest_delta = "本轮变化：" + " · ".join(parts)
        elif len(turns) > len(prev_turns) and len(turns) >= 2:
            a, b = _turn_signature(turns[-2]), cur
            latest_delta = (
                f"较上轮：耗时 {b['lat_s'] - a['lat_s']:+.1f}s · "
                f"RAG {b['rag'] - a['rag']:+.0f} · 工具 {b['tools'] - a['tools']:+.0f}"
            )

    live_inner = f"<strong style=\"color:#58a6ff;\">实时</strong> {now} UTC · trace {trace_rows} 行"
    if analytics.in_progress:
        live_inner = (
            f"<strong style=\"color:#f0883e;\">进行中</strong> · 更新 {now} UTC · trace {trace_rows} 行"
        )
    live_line = live_line_html(live_inner, in_progress=analytics.in_progress)

    last = turns[-1] if turns else None
    live_rag = str(last.rag_count) if last else "0"
    live_tools = str(sum(last.tool_counts.values())) if last else "0"
    live_lat = "—"
    if last:
        if last.completed and last.latency_ms:
            live_lat = f"{last.latency_ms / 1000:.1f}s"
        elif analytics.in_progress:
            live_lat = f"{_live_elapsed_ms_for_turn(analytics.session_id, last.turn_index, project_root=project_root) / 1000:.1f}s*"

    verdict_last = " → ".join(last.verdicts) if last and last.verdicts else "—"
    hero_kpis: list[tuple[str, str, str, str]] = [
        (str(summary["turn_count"]), "总轮次", "accent", ""),
        (str(summary["completed_turns"]), "已完成", "good", ""),
        (
            live_lat,
            "当前/最新耗时",
            "warn" if analytics.in_progress else "accent",
            "实时" if analytics.in_progress else "",
        ),
        (live_rag, "当前 RAG", "warn" if last and last.rag_count >= 5 else "accent", "NEW" if change_banner else ""),
        (live_tools, "当前工具", "accent", ""),
        (str(summary["total_rag"]), "累计 RAG", "accent", ""),
        (verdict_last[:12] + ("…" if len(verdict_last) > 12 else ""), "最新 verdict", "good" if verdict_last == "complete" else "warn", ""),
    ]
    if peak_lat_idx is not None and turns:
        pt = next(t for t in turns if t.turn_index == peak_lat_idx)
        hero_kpis.append(
            (
                f"{pt.latency_ms / 1000:.1f}s",
                f"峰值耗时·轮{peak_lat_idx}",
                "crit" if pt.latency_ms > 90_000 else "warn",
                "峰值",
            )
        )

    row_tone: dict[int, str] = {}
    for t in turns:
        if t.turn_index == active_idx:
            row_tone[t.turn_index] = "active"
        elif change_banner and t.turn_index == turns[-1].turn_index:
            row_tone[t.turn_index] = "new"
        elif t.turn_index == peak_lat_idx and t.latency_ms > 60_000:
            row_tone[t.turn_index] = "crit"
        elif t.turn_index == peak_rag_idx and t.rag_count >= 5:
            row_tone[t.turn_index] = "warn"

    return SessionInsights(
        generated_at=now,
        trace_rows=trace_rows,
        change_banner=change_banner,
        live_line=live_line,
        alerts=alerts[:8],
        hero_kpis=hero_kpis,
        row_tone=row_tone,
        peak_latency_idx=peak_lat_idx,
        peak_rag_idx=peak_rag_idx,
        active_turn_idx=active_idx,
        latest_delta=latest_delta,
    )


def render_session_dashboard_fragment(
    analytics: SessionAnalytics,
    *,
    selected_turn: int | None = None,
    title: str | None = None,
    project_root: Path | None = None,
    insights: SessionInsights | None = None,
) -> str:
    """深色仪表盘：关键 KPI、告警、变更横幅、峰值高亮、实时进行中状态。"""
    if not analytics.turns:
        return sub_text_html("尚无 trace 数据；发送问题后将实时更新。")

    sel = selected_turn or len(analytics.turns)
    sel = max(1, min(sel, len(analytics.turns)))
    ins = insights or build_session_insights(analytics, project_root=project_root)
    turn = analytics.turns[sel - 1]
    labels = _session_chart_labels(analytics)
    latencies, rags, tools, orch = _session_chart_series(analytics)

    if analytics.in_progress and analytics.turns:
        lt = analytics.turns[-1]
        live_s = _live_elapsed_ms_for_turn(analytics.session_id, lt.turn_index, project_root=project_root) / 1000
        if not lt.completed:
            latencies = latencies[:-1] + [round(live_s, 1)]

    hi_lat = {ins.peak_latency_idx - 1} if ins.peak_latency_idx else set()
    hi_rag = {ins.peak_rag_idx - 1} if ins.peak_rag_idx else set()
    active_i = (ins.active_turn_idx - 1) if ins.active_turn_idx else None

    dash_title = title or f"会话仪表盘 · {analytics.session_id[:12]}…"
    banner = ""
    if ins.change_banner:
        banner = banner_html(ins.change_banner, kind="new")
    elif ins.latest_delta:
        banner = banner_html(ins.latest_delta, kind="delta")

    charts = static_charts_block(
        [
            svg_horizontal_bars(
                "逐轮耗时 (s)", labels, latencies, "#58a6ff",
                highlight_indices=hi_lat, active_index=active_i,
            ),
            svg_horizontal_bars(
                "逐轮 RAG 次数", labels, rags, "#f0883e",
                highlight_indices=hi_rag, active_index=active_i,
            ),
            svg_horizontal_bars("逐轮工具调用", labels, tools, "#a371f7", active_index=active_i),
            svg_horizontal_bars("逐轮编排轮数", labels, orch, "#3fb950", active_index=active_i),
        ],
        subtitle="峰值轮标红/橙 · 蓝色条=进行中 · 随 trace 自动刷新",
    )

    row_parts = []
    for t in analytics.turns:
        q = _html_escape(_clean_user_question(t.user_preview or t.user_text or "")[:36])
        st = "OK" if t.completed else ".."
        tone = ins.row_tone.get(t.turn_index, "")
        lat = str(round(t.latency_ms / 1000, 1)) if t.latency_ms else "-"
        if not t.completed and t.turn_index == ins.active_turn_idx:
            lat = f"{_live_elapsed_ms_for_turn(analytics.session_id, t.turn_index, project_root=project_root) / 1000:.1f}*"
        tags = ""
        if t.turn_index == ins.active_turn_idx:
            tags += tag_html("进行中", kind="live")
        if t.turn_index == ins.peak_latency_idx and t.latency_ms:
            tags += tag_html("慢", kind="peak")
        if t.turn_index == ins.peak_rag_idx and t.rag_count >= 3:
            tags += tag_html("RAG高", kind="peak")
        if ins.change_banner and t.turn_index == analytics.turns[-1].turn_index:
            tags += tag_html("最新", kind="new")
        verdict = _html_escape(" -> ".join(t.verdicts) or "-")
        row_parts.append(
            table_row_html(
                [
                    f"{t.turn_index}{tags}",
                    st,
                    lat,
                    str(t.rag_count),
                    str(sum(t.tool_counts.values())),
                    str(t.orchestration_rounds if t.orchestration_rounds is not None else "-"),
                    verdict,
                    q,
                ],
                tone=tone,
            )
        )
    table = metrics_table_html(
        ["轮次", "状态", "耗时(s)", "RAG", "工具", "编排轮", "verdict", "用户问题"],
        "".join(row_parts),
    )

    delta_line = ""
    if ins.latest_delta and ins.change_banner:
        delta_line = sub_text_html(ins.latest_delta)

    turn_detail = render_turn_detail_html(turn, analytics)

    return (
        dashboard_shell_open(title=dash_title)
        + ins.live_line
        + banner
        + delta_line
        + alerts_html(ins.alerts)
        + kpi_grid_html(ins.hero_kpis)
        + charts
        + table
        + turn_detail
        + dashboard_shell_close()
    )


def render_session_dashboard_page(
    analytics: SessionAnalytics,
    *,
    session_id: str | None = None,
    project_root: Path | None = None,
) -> str:
    """完整 HTML 页（可浏览器直接打开）。"""
    sid = (session_id or analytics.session_id).strip()
    root = project_root or _project_root()
    body = render_session_dashboard_fragment(analytics, title=f"会话追溯 · {sid}")
    params_blocks = "<hr/>".join(
        format_turn_params_markdown(analytics, turn_index=t.turn_index) for t in analytics.turns
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Session { _html_escape(sid) }</title>
</head>
<body style="background:#0f1419;margin:0;padding:16px">
{body}
<div class="t4-dash" style="margin-top:12px">
<h2>参数传递明细</h2>
<div style="color:#e6edf3;font-size:14px">{params_blocks}</div>
<p class="t4-sub">chat: {_html_escape(str(session_chat_log_path(sid, project_root=root)))}<br/>
trace: {_html_escape(str(session_trace_path(sid, project_root=root)))}</p>
</div>
</body></html>"""


def write_session_chart_image(
    analytics: SessionAnalytics,
    session_id: str,
    *,
    project_root: Path | None = None,
    write_files: bool = True,
) -> str | None:
    """写入 live_chart.png、live_dashboard.html；刷新后更新 snapshot。"""
    if not analytics.turns:
        return None
    root = project_root or _project_root()
    sid = (session_id or analytics.session_id).strip()
    out_dir = session_trace_path(sid, project_root=root).parent / "exports"
    if write_files:
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / "live_dashboard.html"
        html_path.write_text(
            render_session_dashboard_page(analytics, session_id=sid, project_root=root),
            encoding="utf-8",
        )
        png_path = out_dir / "live_chart.png"
        img = render_session_chart_png(analytics)
        if img is None:
            return None
        img.save(png_path, format="PNG")
        _save_analytics_snapshot(analytics, project_root=root)
        return str(png_path.resolve())
    _save_analytics_snapshot(analytics, project_root=root)
    png_path = out_dir / "live_chart.png"
    return str(png_path.resolve()) if png_path.is_file() else None


def render_session_chart_png(analytics: SessionAnalytics):
    """深色主题横向条形图 PNG（与批量评测仪表盘视觉一致）。"""
    if not analytics.turns:
        return None
    from PIL import Image, ImageDraw, ImageFont

    labels = _session_chart_labels(analytics)
    latencies, rags, tools, orch = _session_chart_series(analytics)
    series: list[tuple[str, list[float], str]] = [
        ("逐轮耗时 (s)", latencies, "#58a6ff"),
        ("逐轮 RAG 次数", rags, "#f0883e"),
        ("逐轮工具调用", tools, "#a371f7"),
        ("逐轮编排轮数", orch, "#3fb950"),
    ]

    chart_w = 920
    label_w = 56
    bar_x = label_w + 8
    bar_area = chart_w - bar_x - 48
    row_h = 22
    panel_pad = 36
    panel_heights = [panel_pad + len(labels) * row_h for _ in series]
    summary = analytics.summary()
    kpi_h = 72
    height = kpi_h + sum(panel_heights) + 24
    img = Image.new("RGB", (chart_w, height), "#0f1419")
    draw = ImageDraw.Draw(img)

    def _font(size: int):
        for name in ("segoeui.ttf", "arial.ttf", "Arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    font_title = _font(14)
    font_kpi = _font(18)
    font_kpi_lbl = _font(10)
    font_row = _font(10)

    draw.text((12, 10), f"会话 {analytics.session_id[:12]}…", fill="#58a6ff", font=font_title)
    kpi_items = [
        (str(summary["turn_count"]), "轮次"),
        (f"{summary['mean_latency_s']}s", "均耗时"),
        (str(summary["total_rag"]), "总 RAG"),
        (str(summary["mean_rag"]), "均 RAG"),
    ]
    kw = chart_w // len(kpi_items)
    for i, (val, lbl) in enumerate(kpi_items):
        x0 = 8 + i * kw
        draw.rounded_rectangle([x0, 32, x0 + kw - 8, 64], radius=6, fill="#21262d", outline="#30363d")
        draw.text((x0 + (kw - 8) // 2, 42), val, fill="#58a6ff", font=font_kpi, anchor="mm")
        draw.text((x0 + (kw - 8) // 2, 58), lbl, fill="#8b949e", font=font_kpi_lbl, anchor="mm")

    y = kpi_h
    for pi, (title, values, color) in enumerate(series):
        ph = panel_heights[pi]
        max_v = max(values) or 1.0
        draw.rounded_rectangle([8, y, chart_w - 8, y + ph], radius=8, fill="#1a2332", outline="#30363d")
        draw.text((20, y + 14), title, fill="#58a6ff", font=font_title)
        base_y = y + panel_pad - 8
        for i, (lab, val) in enumerate(zip(labels, values, strict=False)):
            ry = base_y + i * row_h
            draw.text((16, ry + 12), lab, fill="#8b949e", font=font_row, anchor="ls")
            bw = int(bar_area * (val / max_v)) if val > 0 else 0
            draw.rounded_rectangle(
                [bar_x, ry + 4, bar_x + bw, ry + row_h - 4],
                radius=2,
                fill=color,
            )
            val_text = f"{val:.1f}" if isinstance(val, float) and val != int(val) else str(int(val))
            draw.text((bar_x + bw + 6, ry + 12), val_text, fill="#e6edf3", font=font_row, anchor="ls")
        y += ph + 8
    return img


def format_kpi_markdown(analytics: SessionAnalytics, *, turn_index: int | None = None) -> str:
    if not analytics.turns:
        return "（尚无轮次数据）"
    summary = analytics.summary()
    idx = (turn_index or len(analytics.turns)) - 1
    idx = max(0, min(idx, len(analytics.turns) - 1))
    t = analytics.turns[idx]
    status = "进行中" if not t.completed else "已完成"
    sp = analytics.session_params
    session_line = ""
    if sp:
        session_line = (
            f"\n- **会话参数**：tier=`{sp.get('tier', sp.get('enable_c4', '—'))}` · "
            f"retrieval=`{sp.get('retrieval_mode', '—')}` · "
            f"doc_ids={len(sp.get('doc_ids') or [])}"
        )
    return (
        f"### 会话 KPI · `{analytics.session_id[:12]}…`\n\n"
        f"| 指标 | 会话汇总 | 当前轮（轮{t.turn_index}） |\n"
        f"| --- | ---: | ---: |\n"
        f"| 轮次数 | {summary['turn_count']} | {status} |\n"
        f"| 均耗时 | {summary['mean_latency_s']} s | {round(t.latency_ms/1000,1) if t.latency_ms else '—'} s |\n"
        f"| RAG | 总 {summary['total_rag']} / 均 {summary['mean_rag']} | {t.rag_count} |\n"
        f"| 工具调用 | — | {sum(t.tool_counts.values())} |\n"
        f"| 编排轮数 | — | {t.orchestration_rounds if t.orchestration_rounds is not None else '—'} |\n"
        f"| L3 verdict | — | {' → '.join(t.verdicts) or '—'} |\n"
        f"| stop_reason | — | `{t.stop_reason or '—'}` |"
        f"{session_line}"
    )


def format_metrics_table_markdown(analytics: SessionAnalytics) -> str:
    if not analytics.turns:
        return "（尚无逐轮指标）"
    lines = [
        "### 逐轮指标总览（每次用户输入一行）",
        "",
        "| 轮次 | 状态 | 耗时(s) | RAG | 工具 | 编排轮 | verdict | 用户问题 |",
        "| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for t in analytics.turns:
        st = "✓" if t.completed else "…"
        q = (t.user_preview or t.user_text or "")[:36].replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {t.turn_index} | {st} | "
            f"{round(t.latency_ms/1000,1) if t.latency_ms else '—'} | "
            f"{t.rag_count} | {sum(t.tool_counts.values())} | "
            f"{t.orchestration_rounds if t.orchestration_rounds is not None else '—'} | "
            f"{' → '.join(t.verdicts) or '—'} | {q} |"
        )
    return "\n".join(lines)


def render_session_svg_html(
    analytics: SessionAnalytics,
    *,
    selected_turn: int | None = None,
    title: str | None = None,
) -> str:
    """兼容旧名：返回与批量评测同风格的仪表盘 HTML 片段。"""
    return render_session_dashboard_fragment(
        analytics, selected_turn=selected_turn, title=title
    )


def render_session_chart_html(
    analytics: SessionAnalytics,
    *,
    selected_turn: int | None = None,
    title: str | None = None,
    compact: bool = False,
) -> str:
    """生成交互式 Chart.js 片段，供 Gradio ``gr.HTML`` 嵌入。"""
    if not analytics.turns:
        return "<p style='color:#8b949e;padding:1rem'>尚无 trace 数据；发送问题后将自动生成图表。</p>"

    sel = selected_turn or len(analytics.turns)
    sel = max(1, min(sel, len(analytics.turns)))
    summary = analytics.summary()
    turn = analytics.turns[sel - 1]

    labels = json.dumps([f"轮{t.turn_index}" for t in analytics.turns], ensure_ascii=False)
    latencies = json.dumps([round(t.latency_ms / 1000, 1) for t in analytics.turns])
    rags = json.dumps([t.rag_count for t in analytics.turns])
    tools = json.dumps([sum(t.tool_counts.values()) for t in analytics.turns])

    turn_verdicts: dict[str, int] = {}
    for v in turn.verdicts:
        turn_verdicts[v] = turn_verdicts.get(v, 0) + 1
    verdict_labels = json.dumps(list(turn_verdicts.keys()), ensure_ascii=False)
    verdict_vals = json.dumps(list(turn_verdicts.values()))


    dash_title = title or f"会话 {analytics.session_id[:8]}… · {analytics.module.upper()}"
    height = 220 if compact else 260
    chart_h = 180 if compact else 220

    return f"""
<div class="topic4-session-dash" style="font-family:Segoe UI,system-ui,sans-serif;color:#e6edf3;background:#0f1419;padding:12px;border-radius:8px;border:1px solid #30363d">
  <div style="margin-bottom:10px;font-size:14px;font-weight:600;color:#58a6ff">{_html_escape(dash_title)}</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:8px;margin-bottom:12px">
    <div style="background:#1a2332;padding:8px;border-radius:6px;text-align:center"><div style="font-size:18px;color:#58a6ff">{summary['turn_count']}</div><div style="font-size:11px;color:#8b949e">轮次</div></div>
    <div style="background:#1a2332;padding:8px;border-radius:6px;text-align:center"><div style="font-size:18px;color:#3fb950">{summary['mean_latency_s']}s</div><div style="font-size:11px;color:#8b949e">均耗时</div></div>
    <div style="background:#1a2332;padding:8px;border-radius:6px;text-align:center"><div style="font-size:18px;color:#f0883e">{summary['total_rag']}</div><div style="font-size:11px;color:#8b949e">总 RAG</div></div>
    <div style="background:#1a2332;padding:8px;border-radius:6px;text-align:center"><div style="font-size:18px;color:#a371f7">{summary['mean_rag']}</div><div style="font-size:11px;color:#8b949e">均 RAG</div></div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px">
    <div style="background:#1a2332;padding:8px;border-radius:6px;height:{height}px"><canvas id="t4-lat-{analytics.session_id}" style="max-height:{chart_h}px"></canvas></div>
    <div style="background:#1a2332;padding:8px;border-radius:6px;height:{height}px"><canvas id="t4-rag-{analytics.session_id}" style="max-height:{chart_h}px"></canvas></div>
    <div style="background:#1a2332;padding:8px;border-radius:6px;height:{height}px"><canvas id="t4-tool-{analytics.session_id}" style="max-height:{chart_h}px"></canvas></div>
    <div style="background:#1a2332;padding:8px;border-radius:6px;height:{height}px"><canvas id="t4-ver-{analytics.session_id}" style="max-height:{chart_h}px"></canvas></div>
  </div>
  <div style="margin-top:8px;font-size:11px;color:#8b949e">选中：轮{sel} · RAG×{turn.rag_count} · {turn.latency_ms}ms · verdict: {' → '.join(turn.verdicts) or '—'}</div>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
(function() {{
  const sid = "{analytics.session_id}";
  const grid = 'rgba(139,148,158,.2)';
  const mk = (id, type, cfg) => {{
    const el = document.getElementById(id);
    if (!el) return;
    if (el._t4Chart) {{ el._t4Chart.destroy(); }}
    el._t4Chart = new Chart(el, {{ type, data: cfg.data, options: Object.assign({{ responsive:true, plugins:{{ legend:{{ labels:{{ color:'#8b949e' }} }} }} }}, cfg.options||{{}}) }});
  }};
  Chart.defaults.color = '#8b949e';
  Chart.defaults.borderColor = grid;
  mk('t4-lat-'+sid, 'bar', {{ data: {{ labels:{labels}, datasets:[{{ label:'耗时(s)', data:{latencies}, backgroundColor:'#58a6ff88' }}] }}, options: {{ plugins:{{ title:{{ display:true, text:'逐轮耗时', color:'#e6edf3' }} }}, scales:{{ y:{{ beginAtZero:true }} }} }} }});
  mk('t4-rag-'+sid, 'bar', {{ data: {{ labels:{labels}, datasets:[{{ label:'RAG', data:{rags}, backgroundColor:'#f0883e88' }}] }}, options: {{ plugins:{{ title:{{ display:true, text:'逐轮 RAG', color:'#e6edf3' }} }}, scales:{{ y:{{ beginAtZero:true }} }} }} }});
  mk('t4-tool-'+sid, 'bar', {{ data: {{ labels:{labels}, datasets:[{{ label:'工具调用', data:{tools}, backgroundColor:'#a371f788' }}] }}, options: {{ plugins:{{ title:{{ display:true, text:'逐轮工具总数', color:'#e6edf3' }} }}, scales:{{ y:{{ beginAtZero:true }} }} }} }});
  mk('t4-ver-'+sid, 'doughnut', {{ data: {{ labels:{verdict_labels}, datasets:[{{ data:{verdict_vals}, backgroundColor:['#3fb950','#f0883e','#58a6ff','#f85149'] }}] }}, options: {{ plugins:{{ title:{{ display:true, text:'轮{sel} L3 verdict', color:'#e6edf3' }} }} }} }});
}})();
</script>
"""


def export_session_bundle(
    session_id: str,
    *,
    project_root: Path | None = None,
    out_dir: Path | None = None,
) -> dict[str, str]:
    """导出 JSON + HTML 到 sessions/<id>/exports/，返回路径 dict。"""
    root = project_root or _project_root()
    sid = (session_id or "").strip()
    analytics = build_session_analytics(sid, project_root=root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = out_dir or (session_trace_path(sid, project_root=root).parent / "exports")
    base.mkdir(parents=True, exist_ok=True)

    json_path = base / f"session_{sid}_{stamp}.json"
    html_path = base / f"session_{sid}_{stamp}.html"
    turns_path = base / f"session_{sid}_{stamp}_turns.jsonl"

    payload = {
        "exported_at": stamp,
        "summary": analytics.summary(),
        "turns": [asdict(t) for t in analytics.turns],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with turns_path.open("w", encoding="utf-8") as f:
        for t in analytics.turns:
            f.write(json.dumps(asdict(t), ensure_ascii=False) + "\n")

    full_html = render_session_dashboard_page(analytics, session_id=sid, project_root=root)
    html_path.write_text(full_html, encoding="utf-8")

    return {"json": str(json_path), "html": str(html_path), "turns_jsonl": str(turns_path)}


def log_legacy_rag_turn(
    session_id: str,
    *,
    user_text: str,
    assistant_text: str,
    params: dict[str, Any],
    latency_ms: int,
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> None:
    """legacy 单文档 RAG Gradio：写入 trace + chat，供可视化与导出。"""
    from agentic_rag.telemetry.audit_log import audit_record, set_audit_session_id
    from agentic_rag.telemetry.chat_transcript import append_chat_turn

    sid = (session_id or "").strip()
    set_audit_session_id(sid)
    audit_record(
        "client_turn_start",
        session_id=sid,
        payload={
            "user_preview": user_text[:500],
            "tier": "legacy_rag",
            "module": "legacy_rag",
            **params,
        },
    )
    if retrieved_chunks:
        for i, ch in enumerate(retrieved_chunks[:20]):
            audit_record(
                "rag_query_result",
                session_id=sid,
                payload={
                    "pipeline": params.get("pipeline", "c0_naive"),
                    "config": params.get("config", "legacy_ui"),
                    "chunk_count": len(retrieved_chunks),
                    "retrieved_chunks": [ch],
                    "query_index": i,
                },
            )
    audit_record(
        "client_turn_complete",
        session_id=sid,
        payload={
            "user": user_text,
            "user_preview": user_text[:500],
            "assistant_preview": assistant_text[:2000],
            "stop_reason": "complete",
            "latency_ms": latency_ms,
            "tier": "legacy_rag",
            "module": "legacy_rag",
            "params": params,
        },
    )
    append_chat_turn(
        sid,
        user_text=user_text,
        assistant_text=assistant_text,
        extra={"tier": "legacy_rag", "latency_ms": latency_ms, **params},
    )

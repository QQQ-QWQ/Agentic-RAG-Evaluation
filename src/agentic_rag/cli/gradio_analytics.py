"""Gradio 会话可视化：仅 logs 页「可视化仪表盘」Tab 使用。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gradio as gr

from agentic_rag.telemetry.session_analytics import (
    _load_analytics_snapshot,
    build_session_analytics,
    build_session_insights,
    export_session_bundle,
    render_session_dashboard_fragment,
    turn_choice_label,
)


@dataclass
class AnalyticsBundle:
    dashboard_html: str
    turn_update: Any
    export_hint: str


def _resolve_turn_index(analytics, turn_label: str) -> int:
    if not analytics.turns:
        return 0
    choices = [turn_choice_label(t) for t in analytics.turns]
    if turn_label and turn_label in choices:
        return choices.index(turn_label) + 1
    if turn_label:
        for i, c in enumerate(choices, 1):
            if turn_label.startswith(f"轮{i}"):
                return i
    return len(analytics.turns)


def _pick_turn_value(choices: list[str], preferred: str) -> str | None:
    if preferred and preferred in choices:
        return preferred
    return choices[-1] if choices else None


def build_analytics_bundle(
    session_id: str,
    *,
    selected_turn: str = "",
    light_refresh: bool = False,
) -> AnalyticsBundle:
    del light_refresh  # 保留参数以兼容旧调用；不再生成 PNG
    sid = (session_id or "").strip()

    if not sid or sid.startswith("（"):
        return AnalyticsBundle(
            dashboard_html=(
                '<div style="font-family:Microsoft YaHei,Segoe UI,sans-serif;color:#8b949e;'
                'padding:8px;font-size:14px;">请选择有效 Session ID</div>'
            ),
            turn_update=gr.update(choices=[], value=None, interactive=True, allow_custom_value=False),
            export_hint="",
        )

    prev = _load_analytics_snapshot(sid)
    analytics = build_session_analytics(sid)
    if not analytics.turns:
        return AnalyticsBundle(
            dashboard_html=(
                '<div style="font-family:Microsoft YaHei,Segoe UI,sans-serif;color:#8b949e;'
                'padding:8px;font-size:14px;">trace 已就绪，首轮问答开始后将<strong style="color:#58a6ff;">'
                "实时</strong>刷新 KPI、图表与轮次详情。</div>"
            ),
            turn_update=gr.update(choices=[], value=None, interactive=True, allow_custom_value=False),
            export_hint=f"trace 路径已就绪 · session `{sid[:12]}…` · 自动刷新已启用",
        )

    choices = [turn_choice_label(t) for t in analytics.turns]
    turn_idx = _resolve_turn_index(analytics, selected_turn)
    turn_value = _pick_turn_value(choices, selected_turn)
    insights = build_session_insights(analytics, prev_snapshot=prev)
    in_prog = " · **进行中**" if analytics.in_progress else ""

    hint_parts = [
        f"**{insights.generated_at} UTC** 刷新",
        f"trace **{insights.trace_rows}** 行",
        f"共 **{len(analytics.turns)}** 轮{in_prog}",
    ]
    if insights.change_banner:
        hint_parts.insert(0, insights.change_banner)
    elif insights.latest_delta:
        hint_parts.insert(0, insights.latest_delta)
    hint_parts.append(f"`sessions/{sid}/exports/live_dashboard.html`")

    return AnalyticsBundle(
        dashboard_html=render_session_dashboard_fragment(
            analytics, selected_turn=turn_idx, insights=insights
        ),
        turn_update=gr.update(
            choices=choices,
            value=turn_value,
            interactive=True,
            allow_custom_value=False,
        ),
        export_hint=" · ".join(hint_parts),
    )


def bundle_outputs(bundle: AnalyticsBundle) -> tuple[Any, ...]:
    """logs 页统一输出：仪表盘 HTML、轮次下拉、导出提示。"""
    return (
        bundle.dashboard_html,
        bundle.turn_update,
        bundle.export_hint,
    )


def on_turn_select(session_id: str, turn_label: str) -> tuple[Any, ...]:
    b = build_analytics_bundle(session_id, selected_turn=turn_label or "")
    return b.dashboard_html, b.export_hint


def export_analytics_files(session_id: str) -> str:
    sid = (session_id or "").strip()
    if not sid or sid.startswith("（"):
        return "请先选择有效 Session ID"
    try:
        paths = export_session_bundle(sid)
        return (
            "**导出完成**\n\n"
            f"- JSON：`{paths['json']}`\n"
            f"- HTML：`{paths['html']}`\n"
            f"- 逐轮 JSONL：`{paths['turns_jsonl']}`\n"
            f"- 实时仪表盘 HTML：`runs/logs/audit/sessions/{sid}/exports/live_dashboard.html`"
        )
    except Exception as exc:
        return f"导出失败：{exc}"

"""session_analytics 单测。"""

from __future__ import annotations

import json
from pathlib import Path

from agentic_rag.telemetry.session_analytics import (
    build_session_analytics,
    build_session_insights,
    export_session_bundle,
    render_session_dashboard_fragment,
    render_session_svg_html,
    render_turn_detail_html,
    segment_trace_by_turns,
    write_session_chart_image,
)
from agentic_rag.telemetry.session_trace import append_session_trace, load_session_trace


def test_segment_trace_by_turns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("agentic_rag.config.PROJECT_ROOT", tmp_path)
    sid = "test_sess_01"
    append_session_trace(sid, "session_start_gradio", {"enable_c4": False}, project_root=tmp_path)
    append_session_trace(sid, "client_turn_start", {"user_preview": "Q1", "tier": "c3"}, project_root=tmp_path)
    append_session_trace(
        sid,
        "layer1_plan",
        {"needs_retrieval_tools": True},
        project_root=tmp_path,
    )
    append_session_trace(
        sid,
        "rag_query_result",
        {"pipeline": "c2_stage3_context"},
        project_root=tmp_path,
    )
    append_session_trace(
        sid,
        "client_turn_complete",
        {"user": "Q1", "latency_ms": 1200, "tier": "c3", "stop_reason": "complete"},
        project_root=tmp_path,
    )
    append_session_trace(sid, "client_turn_start", {"user_preview": "Q2", "tier": "c3"}, project_root=tmp_path)
    append_session_trace(sid, "layer3_judge", {"verdict": "complete"}, project_root=tmp_path)

    rows = load_session_trace(sid, project_root=tmp_path)
    groups, in_progress = segment_trace_by_turns(rows)
    assert len(groups) == 2
    assert in_progress is True

    analytics = build_session_analytics(sid, project_root=tmp_path)
    assert analytics.turn_count == 2
    assert analytics.turns[0].rag_count == 1
    assert analytics.turns[0].completed is True
    assert analytics.turns[1].completed is False
    assert analytics.in_progress is True

    html = render_session_dashboard_fragment(analytics)
    assert "Microsoft YaHei" in html and "逐轮耗时" in html
    assert "轮次 1 详情" in html or "轮次 2 详情" in html
    assert "<style>" not in html
    assert "display:grid" in html
    ins = build_session_insights(analytics)
    assert ins.hero_kpis
    assert analytics.turns[0].turn_index == 1

    png = write_session_chart_image(analytics, sid, project_root=tmp_path)
    assert png and Path(png).suffix == ".png" and Path(png).is_file()
    dash = tmp_path / "runs" / "logs" / "audit" / "sessions" / sid / "exports" / "live_dashboard.html"
    assert dash.is_file()

    paths = export_session_bundle(sid, project_root=tmp_path)
    assert Path(paths["json"]).is_file()
    data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert data["summary"]["turn_count"] == 2


def test_segment_complete_only_batch_trace(tmp_path: Path, monkeypatch) -> None:
    """批量评测旧 trace 仅有 client_turn_complete、无 start。"""
    monkeypatch.setattr("agentic_rag.config.PROJECT_ROOT", tmp_path)
    sid = "batch_only_complete"
    append_session_trace(sid, "orchestration_round_start", {"round": 1}, project_root=tmp_path)
    append_session_trace(sid, "layer1_plan", {"needs_retrieval_tools": True}, project_root=tmp_path)
    append_session_trace(
        sid,
        "rag_query_result",
        {"pipeline": "c2_stage3_context"},
        project_root=tmp_path,
    )
    append_session_trace(
        sid,
        "client_turn_complete",
        {
            "user": "测试问题",
            "user_preview": "测试问题",
            "latency_ms": 5000,
            "tier": "c3",
            "stop_reason": "complete",
        },
        project_root=tmp_path,
    )
    analytics = build_session_analytics(sid, project_root=tmp_path)
    assert analytics.turn_count == 1
    assert analytics.turns[0].rag_count == 1
    assert analytics.turns[0].user_text == "测试问题"
    svg = render_session_svg_html(analytics)
    assert "逐轮耗时" in svg
    from agentic_rag.telemetry.session_analytics import write_session_chart_image

    img = write_session_chart_image(analytics, sid, project_root=tmp_path)
    assert img and Path(img).is_file() and Path(img).suffix == ".png"


def test_render_turn_detail_strips_q_prefix(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("agentic_rag.config.PROJECT_ROOT", tmp_path)
    sid = "detail_q_prefix"
    append_session_trace(
        sid,
        "client_turn_start",
        {"user_preview": "Q001,LangChain RAG 框架包含哪些核心组件？", "tier": "c4"},
        project_root=tmp_path,
    )
    append_session_trace(
        sid,
        "layer1_plan",
        {
            "task_summary": "回答 LangChain RAG 框架的核心组件",
            "needs_retrieval_tools": True,
            "suggested_pipelines": ["c0_naive", "c1_rewrite"],
            "plan_for_layer2": "检索知识库",
            "reasoning_brief": "单题知识问答",
        },
        project_root=tmp_path,
    )
    append_session_trace(
        sid,
        "client_turn_complete",
        {
            "user": "Q001,LangChain RAG 框架包含哪些核心组件？",
            "user_preview": "Q001,LangChain RAG 框架包含哪些核心组件？",
            "latency_ms": 39592,
            "tier": "c4",
            "stop_reason": "complete",
        },
        project_root=tmp_path,
    )
    analytics = build_session_analytics(sid, project_root=tmp_path)
    turn = analytics.turns[0]
    detail = render_turn_detail_html(turn, analytics)
    assert "Q001," not in detail
    assert "LangChain RAG" in detail
    assert "L1 规划" in detail
    assert "c0_naive" in detail

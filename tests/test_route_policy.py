"""任务路由策略单测。"""

from __future__ import annotations

from agentic_rag.orchestration.route_policy import resolve_route


def test_expected_path_c0_goes_c2_kb():
    r = resolve_route(
        task_type="simple_qa",
        difficulty="easy",
        expected_path="C0",
        tier="c3",
    )
    assert r.mode == "c2_kb"
    assert r.rag_preset == "c0_naive"


def test_expected_path_c3_goes_orchestrated():
    r = resolve_route(
        task_type="insufficient_evidence",
        difficulty="hard",
        expected_path="C3",
        tier="c3",
    )
    assert r.mode == "c3_orchestrated"
    assert r.max_total_rag_calls == 2


def test_tool_on_c4_tier():
    r = resolve_route(
        task_type="calculation",
        difficulty="hard",
        expected_path="C4",
        required_tool="calculator",
        tier="c4",
    )
    assert r.mode == "c4_orchestrated"


def test_tool_on_c3_tier_fallback_c2():
    r = resolve_route(
        task_type="calculation",
        difficulty="hard",
        expected_path="C4",
        required_tool="calculator",
        tier="c3",
    )
    assert r.mode == "c2_kb"
    assert "fallback" in r.reason


def test_adaptive_disabled_forces_c3():
    r = resolve_route(
        task_type="simple_qa",
        difficulty="easy",
        expected_path="C0",
        tier="c3",
        enable_adaptive_routing=False,
    )
    assert r.mode == "c3_orchestrated"
    assert r.max_total_rag_calls == 1


def test_simple_qa_routes_to_c2_when_adaptive_enabled():
    r = resolve_route(
        task_type="simple_qa",
        difficulty="easy",
        expected_path="C3",
        tier="c3",
    )
    assert r.mode == "c2_kb"
    assert r.rag_preset == "c0_naive"


def test_multi_doc_c3_budget_is_three_calls():
    r = resolve_route(
        task_type="multi_doc",
        difficulty="hard",
        expected_path="C3",
        tier="c3",
    )
    assert r.mode == "c3_orchestrated"
    assert r.max_total_rag_calls == 3

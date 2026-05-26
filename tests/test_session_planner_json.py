"""session_planner JSON 抽取（无 API）。"""

import json

import pytest

from agentic_rag.deep_planning import session_planner


def test_extract_json_plain() -> None:
    text = '{"a": 1, "b": "x"}'
    d = session_planner._extract_json_object(text)
    assert d["a"] == 1


def test_extract_json_fence() -> None:
    text = 'Sure\n```json\n{"document_path": "E:\\\\a.pdf"}\n```'
    d = session_planner._extract_json_object(text)
    assert "document_path" in d


def test_extract_json_embedded() -> None:
    text = 'prefix {"task_summary": "hi"} suffix'
    d = session_planner._extract_json_object(text)
    assert d["task_summary"] == "hi"


def test_extract_invalid() -> None:
    with pytest.raises((ValueError, json.JSONDecodeError)):
        session_planner._extract_json_object("no json here")


def test_c3_conservative_message_contains_citation_and_claim_rules() -> None:
    plan = session_planner.SessionPlan(
        document_path=None,
        task_summary="回答测试问题",
        needs_retrieval_tools=True,
        suggested_pipelines=["c2_stage2_rerank"],
        plan_for_layer2="检索后作答",
        reasoning_brief="test",
        raw={},
    )
    msg = session_planner.compose_layer2_user_message(
        user_original="测试问题",
        plan=plan,
        enable_c4_tools=False,
        enable_c3_conservative_optimization=True,
    )
    assert "C3 conservative execution rules" in msg
    assert "required-item coverage checklist" in msg
    assert "internal evidence table" in msg
    assert "claim-first" in msg
    assert "Citation budget" in msg
    assert "insufficient evidence instead of omitting it" in msg

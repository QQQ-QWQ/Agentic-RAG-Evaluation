from agentic_rag.deep_planning.presets import run_profile_for_preset
from agentic_rag.deep_planning.session_planner import SessionPlan, compose_layer2_user_message
from agentic_rag.deep_planning.tools_factory import build_topic4_rag_tools
from agentic_rag.orchestration.required_items import (
    c3_final_rag_budget,
    extract_required_items,
)
from agentic_rag.rag.evidence_grader import EvidenceGrade, filter_hits_by_grades
from agentic_rag.schemas import EvidenceChunk


def test_required_items_extracts_known_comparison_targets() -> None:
    items = extract_required_items(
        "比较 Self-RAG、CRAG、A-RAG、TeaRAG、KG-RAG 的改进方向",
        task_type="multi_doc",
    )
    assert items[:5] == ["Self-RAG", "CRAG", "A-RAG", "TeaRAG", "KG-RAG"]


def test_c3_final_budget_allows_four_calls_for_large_multi_doc() -> None:
    items = ["Self-RAG", "CRAG", "A-RAG"]
    assert c3_final_rag_budget(task_type="multi_doc", required_items=items) == 4
    assert c3_final_rag_budget(task_type="simple_qa", required_items=items) == 1


def test_c3_final_preset_loosens_evidence_grader_without_touching_lite() -> None:
    lite = run_profile_for_preset("c3_lite_v2")
    final = run_profile_for_preset("c3_final")
    no_evidence = run_profile_for_preset("c3_final_no_evidence_grader")
    no_rrf = run_profile_for_preset("c3_final_no_rrf")
    assert lite.evidence_grader_min_partial_relevance == 0.55
    assert final.evidence_grader_min_partial_relevance == 0.35
    assert final.evidence_grader_min_keep == 3
    assert final.max_retrieval_queries == 4
    assert no_evidence.use_evidence_grader is False
    assert no_rrf.multi_query_fusion == "score"


def test_final_evidence_grader_policy_can_keep_lower_partial_evidence() -> None:
    hits = [
        EvidenceChunk("c1", "d1", "direct evidence", 0.9),
        EvidenceChunk("c2", "d1", "partial evidence", 0.7),
        EvidenceChunk("c3", "d1", "fallback context", 0.4),
    ]
    grades = [
        EvidenceGrade("c1", 0.9, "direct", [], True),
        EvidenceGrade("c2", 0.4, "partial", [], True),
        EvidenceGrade("c3", 0.1, "irrelevant", [], False),
    ]
    lite_kept = filter_hits_by_grades(
        hits,
        grades,
        task_type="multi_doc",
        min_partial_relevance=0.55,
        min_keep=2,
    )
    final_kept = filter_hits_by_grades(
        hits,
        grades,
        task_type="multi_doc",
        min_partial_relevance=0.35,
        min_keep=3,
    )
    assert [h.chunk_id for h in lite_kept] == ["c1", "c2"]
    assert [h.chunk_id for h in final_kept] == ["c1", "c2", "c3"]


def test_c3_final_subagent_tool_is_only_exposed_when_enabled() -> None:
    normal_tools = build_topic4_rag_tools(
        enable_c4_tools=False,
        use_rag_subagent_tools=True,
    )
    final_tools = build_topic4_rag_tools(
        enable_c4_tools=False,
        use_rag_subagent_tools=True,
        enable_c3_final_tools=True,
    )
    assert "rag_subagent_c3_final" not in {getattr(t, "name", "") for t in normal_tools}
    assert "rag_subagent_c3_final" in {getattr(t, "name", "") for t in final_tools}


def test_c4_disabled_tool_aliases_filter_registered_tools() -> None:
    tools = build_topic4_rag_tools(
        enable_c4_tools=True,
        disabled_tools=["file_reader", "calculator", "code_runner"],
    )
    names = {getattr(t, "name", "") for t in tools}
    assert "topic4_file_read" not in names
    assert "topic4_calculator" not in names
    assert "topic4_code_runner" not in names
    assert "sandbox_exec_python" not in names
    assert "topic4_table_analyzer" in names


def test_layer2_prompt_contains_c3_final_required_item_contract() -> None:
    plan = SessionPlan(
        document_path=None,
        task_summary="compare methods",
        needs_retrieval_tools=True,
        suggested_pipelines=["c2_stage2_rerank"],
        plan_for_layer2="compare all methods",
        reasoning_brief="needs evidence",
        raw={},
    )
    msg = compose_layer2_user_message(
        user_original="比较 Self-RAG、CRAG、A-RAG",
        plan=plan,
        enable_c4_tools=False,
        enable_c3_final_optimization=True,
        c3_task_type="multi_doc",
        c3_required_items=["Self-RAG", "CRAG", "A-RAG"],
    )
    assert "C3-final required-item coverage repair" in msg
    assert "rag_subagent_c3_final" in msg
    assert "required_items=Self-RAG, CRAG, A-RAG" in msg
    assert "Do not omit it" in msg or "do not omit it" in msg


def test_layer2_prompt_contains_c4_ablation_contracts() -> None:
    plan = SessionPlan(
        document_path=None,
        task_summary="read csv and calculate",
        needs_retrieval_tools=False,
        suggested_pipelines=[],
        plan_for_layer2="use tools",
        reasoning_brief="tool task",
        raw={},
    )
    msg = compose_layer2_user_message(
        user_original="读取 CSV 并计算均值",
        plan=plan,
        enable_c4_tools=True,
        c4_ablate_tool_citation=True,
        c4_ablate_tool_priority_prompt=True,
    )
    assert "C4 tool-priority ablation" in msg
    assert "C4 tool-citation ablation" in msg
    assert "Do not include [tool:...] citation ids" in msg

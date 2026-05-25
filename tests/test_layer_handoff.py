"""document_path 与 L2 消息衔接。"""

from agentic_rag.deep_planning.session_planner import (
    compose_layer2_user_message,
    looks_like_document_path,
)
from agentic_rag.deep_planning.session_planner import SessionPlan
from agentic_rag.orchestration.planning_extensions import kb_execution_notes_for_layer2


def test_rejects_retrieval_scope_ui_text_as_path():
    scope = (
        "检索范围：**系统全库 Chroma + 本会话附加临时索引**（单次 RAG 融合检索）\n"
        "- 附加文件数：1"
    )
    assert looks_like_document_path(scope) is False


def test_accepts_windows_path():
    assert looks_like_document_path(r"E:\Agentic-RAG-Evaluation-1\data\raw\a.md") is True


def test_kb_notes_skip_fake_path(tmp_path):
    scope = "检索范围：**系统全库 Chroma + 本会话附加临时索引**"
    notes = kb_execution_notes_for_layer2(
        project_root=tmp_path,
        doc_resolved=None,
        plan_document_path_str=scope,
        kb_mutation_intent="none",
    )
    assert "未能解析为存在的本地文件" not in notes
    assert "Chroma 全库" in notes


def test_continue_execute_message_keeps_layer1_block():
    plan = SessionPlan(
        document_path=None,
        task_summary="推荐 GUIAgent 评测方法",
        needs_retrieval_tools=True,
        suggested_pipelines=["c2_stage3_context"],
        plan_for_layer2="检索知识库",
        reasoning_brief="test",
        raw={},
    )
    scope = "检索范围：**系统全库 Chroma + 本会话附加临时索引**"
    msg = compose_layer2_user_message(
        user_original="给我推荐 GUIAgent 评测方法",
        plan=plan,
        orchestration_addon="请补充 AgentBench 检索",
        retrieval_scope_note=scope,
        use_knowledge_base=True,
        enable_c4_tools=True,
    )
    assert "【第二层接入 · 第一层规划结果】" in msg
    assert "请补充 AgentBench 检索" in msg
    assert "任务摘要：推荐 GUIAgent 评测方法" in msg
    assert "系统侧·检索范围" in msg
    assert "未能解析" not in msg

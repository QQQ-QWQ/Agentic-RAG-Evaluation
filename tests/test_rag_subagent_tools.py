"""RAG 子 Agent 工具注册与配额。"""

from __future__ import annotations

import json

from agentic_rag.deep_planning.rag_subagent_tools import (
    RAG_SUBAGENT_SPECS,
    SUBAGENT_TOOL_NAMES,
    build_rag_subagent_tools,
)
from agentic_rag.deep_planning.tool_quota import (
    RAG_TOOL_NAMES,
    RagToolQuota,
    reset_rag_tool_quota,
    wrap_tools_with_rag_quota,
)


def test_subagent_specs_cover_c0_c1_c2():
    names = {s[0] for s in RAG_SUBAGENT_SPECS}
    assert names == {"rag_subagent_c0", "rag_subagent_c1", "rag_subagent_c2"}
    assert SUBAGENT_TOOL_NAMES == names


def test_build_subagent_tools_count():
    tools = build_rag_subagent_tools(use_knowledge_base=True)
    assert len(tools) == 3
    tool_names = {getattr(t, "name", "") for t in tools}
    assert tool_names == SUBAGENT_TOOL_NAMES


def test_rag_quota_blocks_after_limit():
    q = reset_rag_tool_quota(max_calls=2)
    assert q.try_consume("rag_subagent_c0") is None
    assert q.try_consume("rag_subagent_c1") is None
    blocked = q.try_consume("topic4_rag_query")
    assert blocked is not None
    data = json.loads(blocked)
    assert data["error"] == "rag_tool_quota_exceeded"


def test_rag_tool_names_include_subagents():
    assert "rag_subagent_c2" in RAG_TOOL_NAMES


def test_quota_block_returns_tool_message_for_langgraph():
    """配额超限时的 JSON 须包装为 ToolMessage，否则 LangGraph ToolNode 报 unexpected type: str。"""
    from langchain_core.messages import ToolMessage

    from agentic_rag.deep_planning.tool_invoke_compat import coerce_for_tool_node

    q = RagToolQuota(max_calls=1)
    q.count = 1
    block = q.try_consume("rag_subagent_c0")
    assert block is not None
    call = {
        "type": "tool_call",
        "name": "rag_subagent_c0",
        "id": "test_call_id",
        "args": {"question": "ping"},
    }
    out = coerce_for_tool_node(block, call, "rag_subagent_c0")
    assert isinstance(out, ToolMessage)
    assert "rag_tool_quota_exceeded" in str(out.content)


def test_wrapped_tools_invoke_keep_distinct_handlers():
    """审计/配额包装不得在循环中共享 original_invoke（否则全落到 topic4_rag_query）。"""
    from agentic_rag.deep_planning.tools_factory import build_topic4_rag_tools

    tools = build_topic4_rag_tools(
        use_knowledge_base=True,
        enable_c4_tools=False,
        use_rag_subagent_tools=True,
    )
    by_name = {t.name: t for t in tools}
    invoke_ids = {n: id(by_name[n].invoke) for n in SUBAGENT_TOOL_NAMES}
    assert len(set(invoke_ids.values())) == len(SUBAGENT_TOOL_NAMES)

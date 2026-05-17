"""工具治理测试。"""

from __future__ import annotations

from agentic_rag.runtime.state.app_state import PermissionState
from agentic_rag.runtime.tools.governance import (
    assemble_tool_pool,
    filter_tools_by_deny_rules,
    get_all_base_tool_specs,
)


class _FakeTool:
    def __init__(self, name: str):
        self.name = name


def test_c3_tool_specs_count():
    assert len(get_all_base_tool_specs(enable_c4=False)) == 2
    assert len(get_all_base_tool_specs(enable_c4=True)) >= 4


def test_filter_denies_c4_when_c3():
    tools = [_FakeTool("topic4_rag_query"), _FakeTool("topic4_kb_ingest")]
    out = filter_tools_by_deny_rules(
        tools,
        permissions=PermissionState(enable_c4_tools=False),
    )
    names = [t.name for t in out]
    assert "topic4_rag_query" in names
    assert "topic4_kb_ingest" not in names


def test_assemble_dedup_sort():
    tools = [_FakeTool("b"), _FakeTool("a"), _FakeTool("a")]
    out = assemble_tool_pool(
        tools,
        permissions=PermissionState(enable_c4_tools=True),
    )
    assert [t.name for t in out] == ["a", "b"]

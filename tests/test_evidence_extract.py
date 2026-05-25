"""证据摘录提取（编排第三层知识库对齐）。"""

import json

from langchain_core.messages import ToolMessage

from agentic_rag.orchestration.evidence_extract import extract_latest_evidence_excerpt


def test_extract_skips_json_array_tool_output():
    """非 dict 的 Tool JSON（如数组）不得触发 .get 异常。"""
    msgs = [
        ToolMessage(
            content=json.dumps([{"doc_id": "doc_001"}]),
            name="topic4_table_analyzer",
            tool_call_id="t1",
        ),
        ToolMessage(
            content=json.dumps(
                {"evidence_excerpt": "[1] chunk from rag", "answer": "ok"}
            ),
            name="topic4_rag_query",
            tool_call_id="t2",
        ),
    ]
    assert extract_latest_evidence_excerpt(msgs) == "[1] chunk from rag"


def test_extract_empty_when_only_non_dict_json():
    msgs = [
        ToolMessage(
            content=json.dumps(["a", "b"]),
            name="topic4_calculator",
            tool_call_id="t1",
        ),
    ]
    assert extract_latest_evidence_excerpt(msgs) == ""

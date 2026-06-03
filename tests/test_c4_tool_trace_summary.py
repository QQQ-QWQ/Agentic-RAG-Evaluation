"""C4 批量评测的结构化工具调用摘要。"""

from __future__ import annotations

from agentic_rag.experiment.c34_batch import (
    _expected_tool_names,
    _summarize_trace,
    _tool_output_citation_ids,
    _tool_selection_match,
)


def test_c4_tool_trace_summary_parses_tool_message_content() -> None:
    rows = [
        {
            "event": "tool_invoke_start",
            "payload": {
                "tool": "topic4_file_read",
                "args": {"file_path": "data/raw/demo.md"},
            },
        },
        {
            "event": "tool_invoke_end",
            "payload": {
                "tool": "topic4_file_read",
                "output_preview": (
                    "content='{\"tool\":\"topic4_file_read\","
                    "\"schema_version\":\"topic4.tool.v1\","
                    "\"ok\":true,\"data\":{\"text\":\"demo\"}}' "
                    "name='topic4_file_read'"
                ),
                "output_chars": 120,
            },
        },
    ]

    summary = _summarize_trace(rows)

    assert summary["actual_tool_names"] == ["topic4_file_read"]
    assert summary["tool_call_count"] == 1
    assert summary["tool_success_count"] == 1
    assert summary["tool_call_success_rate"] == 1.0
    assert summary["actual_tool_calls"][0]["id"] == "tool:topic4_file_read#1"
    assert summary["actual_tool_calls"][0]["output_ok"] is True


def test_c4_tool_trace_summary_records_tool_failure_without_program_error() -> None:
    rows = [
        {"event": "tool_invoke_start", "payload": {"tool": "topic4_table_analyzer"}},
        {
            "event": "tool_invoke_end",
            "payload": {
                "tool": "topic4_table_analyzer",
                "output_preview": (
                    '{"tool":"topic4_table_analyzer",'
                    '"schema_version":"topic4.tool.v1",'
                    '"ok":false,"error":"file missing"}'
                ),
            },
        },
    ]

    summary = _summarize_trace(rows)

    assert summary["tool_call_count"] == 1
    assert summary["tool_success_count"] == 0
    assert summary["tool_call_success_rate"] == 0.0
    assert summary["actual_tool_calls"][0]["output_error"] == "file missing"


def test_expected_tool_matching_does_not_treat_shell_as_code_runner() -> None:
    expected = _expected_tool_names("table_analyzer,calculator,code_runner")

    assert expected == ["table_analyzer", "calculator", "code_runner"]
    assert (
        _tool_selection_match(
            expected,
            ["topic4_table_analyzer", "topic4_calculator", "topic4_code_runner"],
        )
        is True
    )
    assert (
        _tool_selection_match(
            ["code_runner"],
            ["topic4_shell_exec"],
        )
        is False
    )


def test_tool_output_citation_ids_are_extracted_from_answer() -> None:
    answer = "结论来自表格统计 [tool:topic4_table_analyzer#1] 和计算 [tool:topic4_calculator#1]。"

    assert _tool_output_citation_ids(answer) == [
        "tool:topic4_table_analyzer#1",
        "tool:topic4_calculator#1",
    ]

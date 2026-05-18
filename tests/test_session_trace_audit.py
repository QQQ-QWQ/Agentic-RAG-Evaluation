"""会话 trace 与工具审计。"""

from __future__ import annotations

from unittest.mock import MagicMock

from agentic_rag.telemetry.audit_log import audit_record, get_audit_session_id, set_audit_session_id
from agentic_rag.telemetry.session_trace import load_session_trace, session_trace_path
from agentic_rag.telemetry.tool_audit import wrap_tool_with_audit


def test_audit_record_writes_trace_and_global(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("agentic_rag.config.PROJECT_ROOT", tmp_path)
    set_audit_session_id("sess01")
    paths = audit_record("test_event", payload={"k": 1})
    assert "trace" in paths
    trace = load_session_trace("sess01", project_root=tmp_path)
    assert len(trace) == 1
    assert trace[0]["event"] == "test_event"
    global_path = tmp_path / "runs/logs/audit/global_audit.jsonl"
    assert global_path.is_file()


def test_wrap_tool_invoke(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("agentic_rag.config.PROJECT_ROOT", tmp_path)
    set_audit_session_id("t2")
    class _FakeTool:
        name = "demo_tool"

        def invoke(self, input: object, config: object = None, **kwargs: object) -> str:
            return "ok-result"

    wrapped = wrap_tool_with_audit(_FakeTool())
    assert wrapped.invoke({"q": "hi"}) == "ok-result"
    rows = load_session_trace("t2", project_root=tmp_path)
    events = [r["event"] for r in rows]
    assert "tool_invoke_start" in events
    assert "tool_invoke_end" in events


def test_wrap_structured_tool_invoke(tmp_path, monkeypatch) -> None:
    """@tool 装饰的 StructuredTool 须能包装 invoke（Pydantic 不可直接赋值字段）。"""
    from langchain_core.tools import tool

    monkeypatch.setattr("agentic_rag.config.PROJECT_ROOT", tmp_path)
    set_audit_session_id("t3")

    @tool
    def demo_tool(q: str) -> str:
        """demo"""
        return f"echo:{q}"

    wrapped = wrap_tool_with_audit(demo_tool)
    assert wrapped.invoke({"q": "hi"}) == "echo:hi"
    rows = load_session_trace("t3", project_root=tmp_path)
    events = [r["event"] for r in rows]
    assert "tool_invoke_start" in events
    assert "tool_invoke_end" in events

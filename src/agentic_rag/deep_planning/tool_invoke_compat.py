"""LangGraph ToolNode 兼容：将裸 str 等输出包装为 ToolMessage。"""

from __future__ import annotations

from typing import Any


def coerce_for_tool_node(result: Any, tool_input: Any, tool_name: str) -> Any:
    """LangGraph ``ToolNode`` 只接受 ToolMessage/Command；裸 str 会触发 unexpected type。"""
    from langchain_core.messages import ToolMessage
    from langchain_core.tools.base import _format_output, _is_tool_call

    if isinstance(result, ToolMessage):
        return result
    try:
        from langgraph.types import Command

        if isinstance(result, Command):
            return result
    except ImportError:
        pass
    if _is_tool_call(tool_input):
        tool_call_id = tool_input.get("id")
        if tool_call_id:
            return _format_output(result, None, tool_call_id, tool_name, "success")
    return result

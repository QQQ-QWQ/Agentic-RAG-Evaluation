"""LangChain Tool 调用审计包装。"""

from __future__ import annotations

import json
from typing import Any

from agentic_rag.telemetry.audit_log import audit_record
from agentic_rag.telemetry.audit_payload import safe_json_obj, truncate_text


def _tool_input_payload(tool_input: Any) -> dict[str, Any]:
    if isinstance(tool_input, dict):
        return safe_json_obj(tool_input, max_len=4000)
    return {"input": truncate_text(str(tool_input), max_len=2000)}


def _tool_output_payload(tool_name: str, output: Any) -> dict[str, Any]:
    text = output if isinstance(output, str) else str(output)
    payload: dict[str, Any] = {
        "tool": tool_name,
        "output_preview": truncate_text(text, max_len=8000),
        "output_chars": len(text),
    }
    if tool_name == "topic4_rag_query":
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                payload["rag_compact"] = safe_json_obj(parsed, max_len=6000)
        except json.JSONDecodeError:
            pass
    return payload


def wrap_tool_with_audit(tool: Any, *, tool_name: str | None = None) -> Any:
    """包装 ``BaseTool`` 的 invoke/ainvoke，记录 start/end/error。"""
    name = tool_name or getattr(tool, "name", None) or getattr(tool, "__name__", "tool")

    if getattr(tool, "_topic4_audit_wrapped", False) is True:
        return tool

    original_invoke = tool.invoke
    original_ainvoke = getattr(tool, "ainvoke", None)

    def invoke(input: Any, config: Any = None, **kwargs: Any) -> Any:
        audit_record(
            "tool_invoke_start",
            payload={"tool": name, **_tool_input_payload(input)},
        )
        try:
            if config is not None:
                result = original_invoke(input, config=config, **kwargs)
            else:
                result = original_invoke(input, **kwargs)
        except Exception as exc:
            audit_record(
                "tool_invoke_error",
                payload={
                    "tool": name,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            raise
        audit_record("tool_invoke_end", payload=_tool_output_payload(name, result))
        return result

    async def ainvoke(input: Any, config: Any = None, **kwargs: Any) -> Any:
        if original_ainvoke is None:
            return invoke(input, config, **kwargs)
        audit_record(
            "tool_invoke_start",
            payload={"tool": name, **_tool_input_payload(input), "async": True},
        )
        try:
            if config is not None:
                result = await original_ainvoke(input, config=config, **kwargs)
            else:
                result = await original_ainvoke(input, **kwargs)
        except Exception as exc:
            audit_record(
                "tool_invoke_error",
                payload={
                    "tool": name,
                    "error": f"{type(exc).__name__}: {exc}",
                    "async": True,
                },
            )
            raise
        audit_record(
            "tool_invoke_end",
            payload={**_tool_output_payload(name, result), "async": True},
        )
        return result

    # StructuredTool 为 Pydantic 模型，不能直接 ``tool.invoke = …``（会抛 ValueError）。
    object.__setattr__(tool, "invoke", invoke)
    if original_ainvoke is not None:
        object.__setattr__(tool, "ainvoke", ainvoke)
    object.__setattr__(tool, "_topic4_audit_wrapped", True)
    return tool


def wrap_tools_with_audit(tools: list[Any]) -> list[Any]:
    return [wrap_tool_with_audit(t) for t in tools]

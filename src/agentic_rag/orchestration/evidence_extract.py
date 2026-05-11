"""从 LangGraph / Agent 消息中提取最近一次 RAG 工具返回的 evidence_excerpt。"""

from __future__ import annotations

import json
from typing import Any


def extract_latest_evidence_excerpt(messages: list[Any] | None) -> str:
    """解析 ``topic4_rag_query`` 返回的 JSON 字符串中的 ``evidence_excerpt``。"""
    if not messages:
        return ""

    try:
        from langchain_core.messages import ToolMessage
    except ImportError:
        ToolMessage = ()  # type: ignore[misc,assignment]

    for m in reversed(messages):
        if ToolMessage and isinstance(m, ToolMessage):
            content = m.content
            if not isinstance(content, str):
                continue
            try:
                data = json.loads(content)
                ex = data.get("evidence_excerpt")
                if isinstance(ex, str) and ex.strip():
                    return ex.strip()
            except (json.JSONDecodeError, TypeError):
                continue
    return ""


def extract_last_assistant_text(messages: list[Any] | None) -> str:
    """取最后一条 AI 文本（用于与证据对齐）。"""
    if not messages:
        return ""
    try:
        from langchain_core.messages import AIMessage
    except ImportError:
        return ""

    for m in reversed(messages):
        if isinstance(m, AIMessage):
            c = m.content
            if isinstance(c, str):
                return c.strip()
            if isinstance(c, list):
                parts = []
                for block in c:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                return "\n".join(parts).strip()
    return ""

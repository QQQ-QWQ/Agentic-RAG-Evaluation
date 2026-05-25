"""从 LangGraph / Agent 消息中提取最近一次 RAG 工具返回的 evidence_excerpt。"""

from __future__ import annotations

import json
import time
from typing import Any


def _tool_message_text(content: Any) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        joined = "\n".join(parts).strip()
        return joined if joined else None
    return None


def _agent_debug_log(*, hypothesis_id: str, message: str, data: dict) -> None:
    # #region agent log
    try:
        from agentic_rag import config

        path = config.PROJECT_ROOT / "debug-1b7e11.log"
        payload = {
            "sessionId": "1b7e11",
            "hypothesisId": hypothesis_id,
            "location": "evidence_extract.py",
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


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
            text = _tool_message_text(m.content)
            if not text:
                continue
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(data, dict):
                # #region agent log
                _agent_debug_log(
                    hypothesis_id="H1",
                    message="skip_non_dict_tool_json",
                    data={
                        "parsed_type": type(data).__name__,
                        "tool_name": getattr(m, "name", None),
                    },
                )
                # #endregion
                continue
            ex = data.get("evidence_excerpt")
            if isinstance(ex, str) and ex.strip():
                return ex.strip()
    return ""


def extract_last_assistant_text(messages: list[Any] | None) -> str:
    """取本轮 AI 答复全文（用于与证据对齐），与 format_agent_print 策略一致。"""
    if not messages:
        return ""
    from agentic_rag.deep_planning.agent_runner import collect_ai_reply_text

    return collect_ai_reply_text(messages, max_chars=24_000)

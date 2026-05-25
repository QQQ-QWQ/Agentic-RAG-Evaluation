"""多轮对话上下文格式化（Gradio / QueryEngine → 编排层）。"""

from __future__ import annotations

from typing import Any


def format_prior_conversation(
    messages_log: list[dict[str, Any]] | None,
    *,
    max_chars: int = 14_000,
    max_turns: int = 4,
) -> str:
    """将 ``QueryEngine`` 已落盘的 messages_log 转为 L1/L2 可读的此前会话块。"""
    if not messages_log:
        return ""
    tail = messages_log[-max_turns * 2 :] if max_turns > 0 else messages_log
    parts: list[str] = []
    for m in tail:
        role = str(m.get("role") or "user").strip()
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        label = "用户" if role == "user" else "助手"
        chunk = content
        if len(chunk) > 6000:
            chunk = chunk[:5800] + "\n…(该轮内容已截断)"
        parts.append(f"#### {label}\n{chunk}")
    if not parts:
        return ""
    out = "\n\n".join(parts)
    if len(out) > max_chars:
        return out[: max_chars - 20] + "\n…(此前会话已截断)"
    return out
